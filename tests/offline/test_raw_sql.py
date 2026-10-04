# -*- coding: utf-8 -*-
"""Whole-app guard: the query string handed to `frappe.db.sql` must be a literal.

The seventh surface guarded here, and the first one where the fault is a **security** bug rather
than a broken feature. The rule is deliberately blunt:

    the first argument to frappe.db.sql (and sql_list / sql_value / multisql) must be a plain
    string literal -- never an f-string, a .format() call, a % expression, a concatenation or a
    variable.

Everything that varies belongs in the second argument (`values`), which is the only thing Frappe
escapes. From `frappe/database/database.py`, `db.sql`'s own docstring: *":param values: Tuple /
List / Dict of values to be escaped and substituted in the query."* The query text itself is
passed to `self._cursor.execute(query, values)` (database.py:230) after nothing more than a
`.strip()` and an `ifnull` -> `coalesce` regex. When no values are given, `values = None` and the
driver executes the query string verbatim. **So anything spliced into the query string is SQL
syntax, not data.**

WHAT THIS FOUND WHEN IT WAS WRITTEN (6 Oct 2026), across every .py file in the app

One site, and it was reachable from the browser:
`erplite/projects/doctype/activity/activity.py:30`, in `get_activity_summary(project=None)` --
a `@frappe.whitelist()` module-level function, so callable as
`/api/method/erplite.projects.doctype.activity.activity.get_activity_summary?project=...`:

    status_counts = frappe.db.sql(\"\"\"
        SELECT status, COUNT(*) as count
        FROM `tabActivity`
        WHERE docstatus < 2 {project_filter}
        GROUP BY status
    \"\"\".format(
        project_filter=f"AND project = '{project}'" if project else ""
    ), as_dict=True)

The caller's `project` lands inside the quotes with no escaping and no `values`. Captured by
running the real function against a stub `frappe` that records the query (no database needed):

    project = "5gofgdoomv"                 -> WHERE docstatus < 2 AND project = '5gofgdoomv'
    project = "O'Brien Engineering"        -> WHERE docstatus < 2 AND project = 'O'Brien ...'
    project = "x' OR '1'='1"               -> WHERE docstatus < 2 AND project = 'x' OR '1'='1'
    project = "x' UNION SELECT name,1 ..." -> WHERE docstatus < 2 AND project = 'x' UNION ...

Note the third line before the dramatic ones: **an ordinary business name with an apostrophe
breaks the query.** This is a correctness bug with no attacker in the picture at all, which is
the cheaper half of the argument for fixing it.

Fixed by routing the query through `frappe.get_all`, which parameterises, and which is also what
commit 2eb630e did to this app's other raw queries. `fields=["status", "count(*) as count"]` with
`group_by="status"` is Frappe core's own idiom for this exact shape (`frappe/desk/listview.py:72`,
`frappe/workflow/doctype/workflow/workflow.py:132`, and five more), and `count` is in
`ALLOWED_SQL_FUNCTIONS`. The `filters` dict the original author had already started building --
and then left unused -- is what the fix fills in, so the fix honours the intent rather than
replacing it.

WHY A LITERAL-ONLY RULE RATHER THAN "DON'T INTERPOLATE CALLER INPUT"

Deciding whether a spliced value is caller-reachable needs dataflow, and a guard that tries it
will be wrong in both directions. Literal-or-not is exact, it is checkable from the AST alone,
and **the exception list is currently empty**: the other 11 `db.sql` sites in this app are all
plain literals already. If a future query genuinely needs a dynamic identifier (a table or column
name, which cannot be parameterised), the right move is an explicit documented exception here,
not a looser rule -- because at that point someone has to think about escaping, which is the
whole point.

KNOWN BLIND SPOTS, stated so they are places to look rather than places to stop:

  * Only calls whose receiver looks like a database handle are swept -- `<something>.db.sql(...)`
    or a bare `db.sql(...)`. A `.sql()` method reached through an alias this cannot see
    (`handle = frappe.db` then `handle.sql(...)`) is not swept. Those are listed by the pass as
    skipped rather than silently dropped, so the count is visible.
  * This says nothing about `order_by`, `group_by` or `having` passed to `get_all`, which Frappe
    sanitises but which have their own history. Checked by hand on 6 Oct 2026: no whitelisted
    endpoint in this app passes caller input to any of them.
  * A literal query is not necessarily a *correct* one. This guard is about where values come
    from, not about whether the columns exist -- that is `test_undeclared_attributes.py` and
    `test_doctype_metadata.py`.
"""

import ast
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODULE_ROOT = os.path.join(APP_ROOT, "erplite")

SKIP_DIRS = {"node_modules", "__pycache__", ".git", "dist", "build"}

SQL_METHODS = {"sql", "sql_list", "sql_value", "multisql"}


def _python_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                path = os.path.join(dirpath, fn)
                yield path, os.path.relpath(path, APP_ROOT).replace(os.sep, "/")


def _looks_like_db_handle(node):
    """True for `<anything>.db` or a bare name `db`.

    Deliberately narrow: it is better to list a call as skipped than to guess that some unrelated
    object's `.sql()` is a database call.
    """
    if isinstance(node, ast.Attribute):
        return node.attr == "db"
    if isinstance(node, ast.Name):
        return node.id == "db"
    return False


def classify_query_arg(arg):
    """Classify the query argument. Returns 'literal' for the only acceptable shape."""
    if arg is None:
        return "missing"
    if isinstance(arg, ast.Constant):
        return "literal" if isinstance(arg.value, str) else "non-string-constant"
    if isinstance(arg, ast.JoinedStr):
        return "f-string"
    if isinstance(arg, ast.Call):
        f = arg.func
        if isinstance(f, ast.Attribute) and f.attr == "format":
            return ".format() call"
        return "call to %s()" % getattr(f, "attr", getattr(f, "id", "?"))
    if isinstance(arg, ast.BinOp):
        return {"Mod": "%-formatting", "Add": "string concatenation"}.get(
            type(arg.op).__name__, "%s expression" % type(arg.op).__name__
        )
    if isinstance(arg, ast.Name):
        return "variable %r" % arg.id
    if isinstance(arg, ast.IfExp):
        return "conditional expression"
    return type(arg).__name__


class _SqlCallVisitor(ast.NodeVisitor):
    """Collects every db.sql-shaped call, with the enclosing function for the message."""

    def __init__(self, relpath):
        self.relpath = relpath
        self.calls = []     # dicts: file, line, method, kind, function
        self.skipped = []   # .sql() calls on a receiver we decline to guess about
        self._stack = []

    def visit_FunctionDef(self, node):
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in SQL_METHODS:
            where = dict(
                file=self.relpath,
                line=node.lineno,
                method=f.attr,
                function=self._stack[-1] if self._stack else "<module>",
            )
            if _looks_like_db_handle(f.value):
                arg = node.args[0] if node.args else None
                if arg is None:
                    for kw in node.keywords:
                        if kw.arg == "query":
                            arg = kw.value
                            break
                where["kind"] = classify_query_arg(arg)
                self.calls.append(where)
            else:
                self.skipped.append(where)
        self.generic_visit(node)


def _scan_source(src, relpath="<test>"):
    v = _SqlCallVisitor(relpath)
    v.visit(ast.parse(src))
    return v


class RawSqlQueriesAreLiterals(unittest.TestCase):
    """Pass A: the whole app, every db.sql query argument."""

    def test_every_db_sql_query_is_a_string_literal(self):
        findings, total, skipped = [], 0, []
        for path, rel in _python_files(MODULE_ROOT):
            with open(path, "rb") as fh:
                src = fh.read().decode("utf-8", "replace")
            try:
                v = _scan_source(src, rel)
            except SyntaxError as exc:  # pragma: no cover - would be a broken checkout
                self.fail("%s does not parse: %s" % (rel, exc))
            total += len(v.calls)
            skipped += v.skipped
            findings += [c for c in v.calls if c["kind"] != "literal"]

        self.assertGreater(total, 0, "swept no db.sql calls at all - has the layout moved?")

        if findings:
            lines = [
                "",
                "%d of %d db.sql call(s) build the query from something other than a literal." % (
                    len(findings), total),
                "",
                "Only the `values` argument is escaped (database.py:230 executes the query text",
                "verbatim), so anything spliced into the query string is SQL syntax, not data.",
                "",
            ]
            for f in sorted(findings, key=lambda f: (f["file"], f["line"])):
                lines.append("  %s:%d  in %s()  -- db.%s query built from: %s" % (
                    f["file"], f["line"], f["function"], f["method"], f["kind"]))
            lines += [
                "",
                "Remedy: keep the query a literal and move every value into `values`:",
                '    frappe.db.sql("... WHERE project = %(project)s", {"project": project})',
                "or, preferably, use frappe.get_all / frappe.db.get_all, which parameterises for",
                "you. A dynamic *identifier* (table or column name) cannot be parameterised at",
                "all - if that is genuinely needed, add a documented exception in this file.",
            ]
            self.fail("\n".join(lines))


class TheWalkerItself(unittest.TestCase):
    """Pass B: self-tests. A walker that decides what counts as a db call needs its boundaries
    tested, not just its happy path. Both of the previous two guards in this directory shipped
    with a scope bug that these cases would have caught."""

    def _kinds(self, src):
        return [c["kind"] for c in _scan_source(src).calls]

    # --- must NOT be findings -------------------------------------------------
    def test_a_plain_literal_is_accepted(self):
        self.assertEqual(self._kinds('frappe.db.sql("select 1")'), ["literal"])

    def test_a_literal_with_placeholders_and_values_is_accepted(self):
        self.assertEqual(
            self._kinds('frappe.db.sql("select a from b where c = %(c)s", {"c": c})'),
            ["literal"],
        )

    def test_a_triple_quoted_multiline_literal_is_accepted(self):
        self.assertEqual(self._kinds('frappe.db.sql("""\n  select 1\n""")'), ["literal"])

    def test_implicitly_concatenated_literals_are_one_literal(self):
        # "a" "b" is a single ast.Constant, not a BinOp, and is perfectly safe.
        self.assertEqual(self._kinds('frappe.db.sql("select a " "from b")'), ["literal"])

    def test_the_query_may_be_passed_by_keyword(self):
        self.assertEqual(self._kinds('frappe.db.sql(query="select 1")'), ["literal"])

    def test_a_sql_method_on_something_that_is_not_a_db_handle_is_skipped(self):
        v = _scan_source('report.sql(build_it())')
        self.assertEqual(v.calls, [])
        self.assertEqual(len(v.skipped), 1)

    def test_a_db_handle_reached_through_self_is_still_swept(self):
        self.assertEqual(self._kinds('self.db.sql("select 1")'), ["literal"])

    def test_a_bare_db_name_is_swept(self):
        self.assertEqual(self._kinds('db.sql("select 1")'), ["literal"])

    # --- must BE findings -----------------------------------------------------
    def test_an_f_string_is_a_finding(self):
        self.assertEqual(self._kinds('frappe.db.sql(f"select a from b where c = {c}")'),
                         ["f-string"])

    def test_a_format_call_is_a_finding(self):
        self.assertEqual(self._kinds('frappe.db.sql("where c = {c}".format(c=c))'),
                         [".format() call"])

    def test_percent_formatting_is_a_finding(self):
        self.assertEqual(self._kinds('frappe.db.sql("where c = \'%s\'" % c)'), ["%-formatting"])

    def test_concatenation_is_a_finding(self):
        self.assertEqual(self._kinds('frappe.db.sql("where c = " + c)'),
                         ["string concatenation"])

    def test_a_bare_variable_is_a_finding(self):
        self.assertEqual(self._kinds('frappe.db.sql(query_text)'), ["variable 'query_text'"])

    def test_a_conditional_expression_is_a_finding(self):
        self.assertEqual(self._kinds('frappe.db.sql(a if b else c)'), ["conditional expression"])

    def test_sql_list_and_sql_value_are_swept_too(self):
        self.assertEqual(self._kinds('frappe.db.sql_list(f"x {y}")'), ["f-string"])
        self.assertEqual(self._kinds('frappe.db.sql_value(f"x {y}")'), ["f-string"])

    # --- scope: the enclosing function must be attributed correctly -----------
    def test_the_enclosing_function_is_named_not_the_outer_one(self):
        calls = _scan_source(
            "def outer():\n"
            "    def inner():\n"
            "        frappe.db.sql(f'x {y}')\n"
            "    return inner\n"
        ).calls
        self.assertEqual([c["function"] for c in calls], ["inner"])

    def test_a_call_at_module_level_is_attributed_to_module(self):
        self.assertEqual([c["function"] for c in _scan_source("frappe.db.sql(f'x {y}')").calls],
                         ["<module>"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
