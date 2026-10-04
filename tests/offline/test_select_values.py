# -*- coding: utf-8 -*-
"""Whole-app guard: a Select field is never given, or compared to, a value it cannot hold.

The other field sweeps in this folder ask whether a name exists -- does this DocType declare
this field, does this string name a real method. This one asks a narrower question about a
field that does exist: **is this one of the values the field is allowed to take?**

A `Select` field carries its whole permitted set in its own `options`, so this is decidable
offline from the DocType JSON. It is worth deciding, because the two ways of getting it wrong
have opposite and equally quiet symptoms:

  * **Writing** an unlisted value aborts the save. `Document._validate()` runs
    `_validate_selects()` (frappe-version-15/frappe/model/document.py:627, reached from
    `insert()` at :310 and from `_save()` at :417), and `_validate_selects`
    (base_document.py:892-920) ends in `frappe.throw` for any value not in `options`. Note the
    ordering: the controller's own `validate`/`before_save` hooks run *first*
    (`run_before_save_methods`, document.py:309 and :414), so a hook cannot see this coming and
    nothing a controller does can rescue it. If the caller wraps the save in `except Exception`
    -- which the whitelisted endpoints here do -- the abort is reported to the browser as a
    generic failure with HTTP 200, and `frappe.log_error(message)` records it without a stack.
    An endpoint that does this **cannot create a record for any input**.

  * **Filtering** on an unlisted value is valid SQL that quietly matches the wrong set.
    `frappe.get_all` does not compare filter values to `options` at all -- `Engine._apply_filter`
    only screens the filter *name* for special characters -- so the value goes into the WHERE
    clause and the database answers honestly about a value no row can hold. `== <impossible>`
    matches nothing; `!= <impossible>` matches everything, which is the dangerous direction,
    because the filter reads as if it excludes something and excludes nothing at all.

So the same mistake either kills a feature outright or widens a result set in silence, and
neither shows up as an error anywhere.

## Why the DocType is resolved from the call, not from the field name

A first version of this rule collected options by field *name* across every DocType and
flagged any literal that matched no DocType's options for that name. It reported two false
positives in `erplite/projects/api.py`: `{"reference_type": "Activity"}` on a ToDo query. That
is correct code -- `ToDo.reference_type` is a **Link to DocType** and will happily hold
"Activity" -- but `reference_type` is *also* a Select on Payment Entry, whose options are
payment kinds. Keying by name conflated two unrelated fields that happen to share one.

So this pass resolves the DocType from the call itself: the `"doctype"` key of a
`frappe.get_doc({...})` dict, or the first positional argument of a query. A call whose DocType
is not a literal is skipped rather than guessed at.

## Scope, and what this pass cannot see

Covered: `frappe.get_doc({...})` field literals, and `filters={...}` on `get_all`, `get_list`,
`db.count`, `db.get_value`, `db.get_all`, `db.get_list`, `db.exists` and `db.set_value`, for
`=`, `!=`, `in` and `not in`.

Not covered, and each is a real way past this guard:

  * `doc.status = "..."` attribute assignment. The DocType of a controller's `self` is knowable
    from its folder, but of an arbitrary local it is not, and guessing is what produced the
    false positives above. The write sites in this app all go through `get_doc`.
  * A value held in a variable, built by format string, or arriving from a request. The todo
    kanban's `update_todo_status(todo_name, new_status)` takes the status straight from the
    browser, so no static pass can see what it will be. Its caller
    (`erplite/public/js/todo/dragdrop/TodoDragDropManager.js:745-751`) maps the three kanban
    columns to "Backlog", "Planned" and "Open" -- two of which ToDo cannot hold -- and that
    mapping is in JavaScript, out of this pass's reach. KNOWN_CORE_SELECTS below is the record
    of it.
  * Frappe's own DocTypes, except the handful mirrored in KNOWN_CORE_SELECTS. These tests run
    without a bench, so there is no frappe source to read; an unmirrored core DocType is
    skipped silently. Extending the mirror is how coverage grows.
"""

import ast
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
APP = "erplite"
MODULE_ROOT = os.path.join(APP_ROOT, APP)

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "public"}

# Select options for the Frappe DocTypes this app writes to or filters on.
#
# Mirrored by hand because these tests run with no bench and no frappe checkout. Each entry
# below was read out of frappe version-15's own DocType JSON, not recalled; ToDo's status is
# also stated a second time in frappe's controller as
# `status: DF.Literal["Open", "Closed", "Cancelled"]`
# (frappe/desk/doctype/todo/todo.py:35), which is a useful cross-check on the mirror.
#
# A mirror can go stale against a frappe upgrade. It fails safe in the direction that matters:
# if frappe ADDS an option, this guard reports a violation that is no longer real, and someone
# reads this comment and widens it. It cannot invent a violation out of nothing.
KNOWN_CORE_SELECTS = {
    # frappe/desk/doctype/todo/todo.json
    "ToDo": {
        "status": {"Open", "Closed", "Cancelled"},
        "priority": {"High", "Medium", "Low"},
    },
}

QUERY_CALLS = {
    "frappe.get_all",
    "frappe.get_list",
    "frappe.db.count",
    "frappe.db.get_value",
    "frappe.db.get_all",
    "frappe.db.get_list",
    "frappe.db.exists",
    "frappe.db.set_value",
}

# Calls whose second positional argument is the filters, when `filters=` is not given by name.
POSITIONAL_FILTERS = {"frappe.db.get_value", "frappe.db.exists", "frappe.db.count"}


def _app_selects():
    """doctype -> fieldname -> set(options), from this app's own DocType JSONs."""
    found = {}
    for dirpath, dirnames, filenames in os.walk(MODULE_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            # A DocType's JSON is named after the folder it sits in.
            if not name.endswith(".json") or name[:-5] != os.path.basename(dirpath):
                continue
            with open(os.path.join(dirpath, name), encoding="utf-8") as handle:
                definition = json.load(handle)
            doctype = definition.get("name")
            if not doctype:
                continue
            for field in definition.get("fields", []):
                if field.get("fieldtype") != "Select":
                    continue
                fieldname, options = field.get("fieldname"), field.get("options")
                if not fieldname or not options:
                    continue
                allowed = {o.strip() for o in options.split("\n") if o.strip()}
                if allowed:
                    found.setdefault(doctype, {})[fieldname] = allowed
    return found


def _selects():
    found = _app_selects()
    for doctype, fields in KNOWN_CORE_SELECTS.items():
        found.setdefault(doctype, {}).update(fields)
    return found


def _python_files():
    for dirpath, dirnames, filenames in os.walk(MODULE_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                full = os.path.join(dirpath, name)
                yield full, os.path.relpath(full, APP_ROOT).replace(os.sep, "/")


def _const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _dict_value(node, key):
    """The literal string at `key` in a dict literal, or None."""
    for k, v in zip(node.keys, node.values):
        if _const_str(k) == key:
            return _const_str(v)
    return None


def violations():
    """[(rel_path, line, doctype, field, value, how, allowed)] over the whole app."""
    selects = _selects()
    found = []

    def check(rel, line, doctype, field, value, how):
        allowed = selects.get(doctype, {}).get(field)
        if allowed is None or value in allowed:
            return
        found.append((rel, line, doctype, field, value, how, allowed))

    def check_filters(rel, doctype, node):
        for key, value in zip(node.keys, node.values):
            field = _const_str(key)
            if not field:
                continue
            literal = _const_str(value)
            if literal is not None:
                check(rel, key.lineno, doctype, field, literal, "filter ==")
                continue
            # The [operator, operand] form.
            if not isinstance(value, (ast.List, ast.Tuple)) or len(value.elts) != 2:
                continue
            operator = (_const_str(value.elts[0]) or "").lower()
            operand = value.elts[1]
            if operator in ("in", "not in") and isinstance(operand, (ast.List, ast.Tuple)):
                for element in operand.elts:
                    literal = _const_str(element)
                    if literal is not None:
                        check(rel, key.lineno, doctype, field, literal,
                              "filter %s" % operator)
            elif operator in ("=", "==", "!="):
                literal = _const_str(operand)
                if literal is not None:
                    check(rel, key.lineno, doctype, field, literal,
                          "filter %s" % operator)

    for path, rel in _python_files():
        with open(path, encoding="utf-8", errors="replace") as handle:
            source = handle.read()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _dotted(node.func)
            keywords = {k.arg: k.value for k in node.keywords if k.arg}

            if name == "frappe.get_doc" and node.args and isinstance(node.args[0], ast.Dict):
                literal = node.args[0]
                doctype = _dict_value(literal, "doctype")
                if not doctype:
                    continue
                for key, value in zip(literal.keys, literal.values):
                    field, written = _const_str(key), _const_str(value)
                    if field and written is not None:
                        check(rel, key.lineno, doctype, field, written, "get_doc field")
                continue

            if name not in QUERY_CALLS:
                continue
            doctype = _const_str(node.args[0]) if node.args else None
            if not doctype:
                continue

            filters = keywords.get("filters")
            if filters is None and name in POSITIONAL_FILTERS and len(node.args) > 1:
                filters = node.args[1]
            if isinstance(filters, ast.Dict):
                check_filters(rel, doctype, filters)

            if name == "frappe.db.set_value" and len(node.args) >= 4:
                field, written = _const_str(node.args[2]), _const_str(node.args[3])
                if field and written is not None:
                    check(rel, node.lineno, doctype, field, written, "set_value")

    return found


class SelectOptionsAreRespected(unittest.TestCase):
    def test_no_select_field_is_given_a_value_it_cannot_hold(self):
        found = violations()
        if found:
            lines = [
                "%s:%d  [%s]  %s.%s = %r\n        allowed: %s"
                % (rel, line, how, doctype, field, value, ", ".join(sorted(allowed)))
                for rel, line, doctype, field, value, how, allowed in sorted(found)
            ]
            self.fail(
                "%d Select value(s) outside the field's own options.\n"
                "A write aborts the save; a filter matches the wrong set in silence.\n\n%s"
                % (len(found), "\n".join(lines))
            )

    def test_the_pass_can_see_this_apps_doctypes(self):
        """Guard the guard: if the JSON walk breaks, every check above passes vacuously."""
        selects = _app_selects()
        self.assertGreater(
            len(selects), 20,
            "only %d DocTypes with Select fields were found; the JSON walk is broken, which "
            "would make the whole-app check pass by seeing nothing" % len(selects))
        self.assertIn("Project", selects)
        self.assertIn("status", selects["Project"])

    def test_the_pass_can_see_a_violation_planted_in_this_apps_own_source(self):
        """Guard the guard, the other half: prove the AST walk reaches a real call site.

        A whole-app rule that reports nothing is indistinguishable from one that looks at
        nothing. This plants a call with a bad Select value in a temporary module inside the
        app tree and requires the pass to find it.
        """
        planted = os.path.join(MODULE_ROOT, "_select_guard_probe.py")
        source = (
            "import frappe\n"
            "\n"
            "def probe():\n"
            "    frappe.get_all('Project', filters={'status': ['!=', 'NotAStatus']})\n"
            "    return frappe.get_doc({'doctype': 'ToDo', 'status': 'NotAStatus'})\n"
        )
        with open(planted, "w", encoding="utf-8") as handle:
            handle.write(source)
        try:
            found = [v for v in violations() if v[0].endswith("_select_guard_probe.py")]
        finally:
            os.remove(planted)
        self.assertEqual(
            2, len(found),
            "the pass found %d of the 2 planted violations: %r" % (len(found), found))
        self.assertEqual({"Project", "ToDo"}, {v[2] for v in found})


class ToDoStatusMirrorIsStated(unittest.TestCase):
    """The mirror of a Frappe DocType is the one fact here that is not read from this repo.

    These assertions do not test the app. They state, in a place that runs, what the mirror
    claims, so that a frappe upgrade that changes ToDo's statuses turns into a failing test
    with this file's comment next to it rather than a silently wrong whole-app rule.
    """

    def test_todo_has_three_statuses_and_no_kanban_ones(self):
        self.assertEqual({"Open", "Closed", "Cancelled"},
                         KNOWN_CORE_SELECTS["ToDo"]["status"])

    def test_only_one_kanban_column_is_reachable(self):
        """The consequence worth naming: two of the board's three columns cannot fill.

        `erplite/www/todo/index.py:get_todo_column` and its browser twin
        `erplite/public/js/todo/utils/TodoUtils.js:128-137` map status to column as
        Backlog -> backlog, Planned -> todo, Open -> progress. Only one of those three
        statuses exists, so every ToDo that shows on the board shows in `progress`.
        """
        status_to_column = {"Backlog": "backlog", "Planned": "todo", "Open": "progress"}
        reachable = {
            column for status, column in status_to_column.items()
            if status in KNOWN_CORE_SELECTS["ToDo"]["status"]
        }
        self.assertEqual({"progress"}, reachable)


class StandInRejectsImpossibleSelectValues(unittest.TestCase):
    """The stand-in's half of this surface.

    The whole-app pass above reads source and cannot run anything. These tests
    cover the other direction: `fake_frappe` now refuses to serve a fixture row
    holding a Select value its DocType forbids, and refuses a filter comparing a
    Select field to such a value.

    That strictness is the thing that would have caught this surface years
    earlier. `test_projects_api` and `test_scheduler_api` each built a fixture
    Project with `status="Cancelled"` to show that `["!=", "Cancelled"]` left it
    out, and both passed -- because the stand-in checked field *names* and not
    field *values*, so an impossible row went in without complaint and the
    filter excluded it exactly as the test expected. On the real site
    Project.status has no Cancelled option, so no such row exists and that
    filter excludes nothing. The tests were green about a world that cannot
    happen.
    """

    def setUp(self):
        from fake_frappe import FakeFrappe, ImpossibleValue, _dict
        self.ImpossibleValue = ImpossibleValue
        self._dict = _dict
        self.frappe = FakeFrappe()

    def test_the_stand_in_knows_projects_real_statuses(self):
        self.assertEqual({"Opportunity", "Estimate", "Open", "Archived"},
                         self.frappe.select_options["Project"]["status"])

    def test_select_rows_refuses_an_impossible_fixture(self):
        self.frappe.tables["Project"] = [
            self._dict(name="p1", project_name="Fine", status="Open"),
            self._dict(name="p2", project_name="Shelved", status="Cancelled"),
        ]
        with self.assertRaises(self.ImpossibleValue) as caught:
            self.frappe.get_all("Project", fields=["name"])
        self.assertIn("Cancelled", str(caught.exception))
        self.assertIn("p2", str(caught.exception))

    def test_select_rows_allows_every_real_option_and_an_empty_value(self):
        self.frappe.tables["Project"] = [
            self._dict(name="p%d" % i, project_name="x", status=status)
            for i, status in enumerate(
                ["Opportunity", "Estimate", "Open", "Archived", None, ""])
        ]
        self.assertEqual(6, len(self.frappe.get_all("Project", fields=["name"])))

    def test_select_filters_refuses_an_impossible_filter(self):
        self.frappe.tables["Project"] = [
            self._dict(name="p1", project_name="Fine", status="Open")]
        for condition in (["!=", "Cancelled"], ["in", ["Open", "Active"]], "Cancelled"):
            with self.assertRaises(self.ImpossibleValue, msg=repr(condition)):
                self.frappe.get_all("Project", fields=["name"],
                                    filters={"status": condition})

    def test_select_filters_allow_the_real_statuses(self):
        self.frappe.tables["Project"] = [
            self._dict(name="p1", project_name="Fine", status="Open"),
            self._dict(name="p2", project_name="Gone", status="Archived"),
        ]
        kept = self.frappe.get_all("Project", fields=["name"],
                                   filters={"status": ["!=", "Archived"]})
        self.assertEqual(["p1"], [r["name"] for r in kept])

    def test_a_write_of_an_impossible_select_value_is_refused(self):
        """Real Frappe aborts the save; the stand-in raises rather than writing."""
        self.frappe.tables["ToDo"] = [self._dict(name="t1", status="Open")]
        with self.assertRaises(self.ImpossibleValue):
            self.frappe.db.set_value("ToDo", "t1", "status", "Backlog")
        self.assertEqual("Open", self.frappe.tables["ToDo"][0]["status"])

    def test_a_reverted_fixture_is_caught_by_the_stand_in(self):
        """The two suites that carried an impossible Project fixture now cannot.

        This reads their source rather than their fixtures, so it fails if
        either file reintroduces the value, whichever test happens to use it.
        """
        for name in ("test_projects_api.py", "test_scheduler_api.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                source = handle.read()
            self.assertNotIn(
                'project_name="Shelved", status="Cancelled"', source,
                "%s builds a Project with a status Project.status cannot hold" % name)


if __name__ == "__main__":
    unittest.main()
