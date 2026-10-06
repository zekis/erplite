# -*- coding: utf-8 -*-
"""Whole-app guards against reading a field the DocType does not have.

A *query* naming a removed field is usually silent: `bench migrate` never drops the column, so
`frappe.get_all` reads a stale orphan column and nothing is thrown. That is the failure class the
other tests in this folder cover.

Attribute access is a different failure, and the severe one:

  * a document LOADED from the database gets its attributes from `SELECT *` (every real column,
    orphans included) plus `init_valid_columns()`, which fills in any declared field the row did
    not carry.  Reading a removed-but-still-present column gives a stale value.
  * a document built in memory -- `frappe.new_doc(...)`, or a controller running `validate()` on a
    save of a new record -- has only what it was handed plus `meta.get_valid_columns()`, which
    comes from the DocType's CURRENT field list, not from the table's columns.  There is no
    `__getattr__` anywhere in the MRO, so reading a field the DocType no longer declares raises
    AttributeError and the save dies.

That is what broke `scheduler.api.create_schedule_entry` (see test_schedule_entry.py): the
scheduler could not create an entry at all, while a query against the same removed field would
have failed silently. Testing the loaded case tells you nothing about the new case.

WRITING an undeclared attribute is the silent half of the same mistake, and it is why the first
two tests here were not enough. `doc.<x> = v` never raises -- it is an ordinary setattr on a
Python object -- and then `get_valid_dict()` builds the INSERT from `meta.get_valid_columns()`,
the DocType's declared fields, so the value is dropped without an error, a log line or a failed
save. The caller is told the write succeeded.

That is what `scheduler.doctype.schedule_row.create_schedule_row` did: a whitelisted endpoint
taking a `task` argument, assigning `doc.task` on a DocType that has only `activity`, and
discarding it on insert. The row was created with no work attached and the caller got its name
back. The first two tests here missed it for a year of sweeps because both filter on `ast.Load`:
the symptom being hunted was AttributeError, and a write has no symptom at all.

And `doc.<x> = v` is not the only way to write one. `db_set`, `set`, `update({...})` and
`setattr` name the field in a string argument instead, which is how the app really writes in a
controller -- five of the six `db_set` sites in this tree are `self.db_set("x", v)`. `db_set` is
the worst of them to miss: it builds its UPDATE from the name it was handed rather than from
`get_valid_dict()`, so an undeclared name is a failed statement rather than a quietly dropped
value. All four shapes are read here, on `self` and on a local holding a document.

These three sweeps cover the whole app so the class cannot come back in a module nobody is looking
at. All are deliberately conservative -- a name has to be declared nowhere to be reported -- so a
failure here is a real finding rather than something to add an exception for.

The fourth class, `TestWhatTheseSweepsCannotSee`, is the other half of that conservatism: it pins
what the sweeps deliberately do not report, because a limit that is only a comment cannot be told
apart from coverage. It also tests the two rules nothing else can observe -- the hot/cold split
(both buckets assert empty, so collapsing one into the other would fail nothing) and the
per-binding scope rule, where treating "out of scope" as "unknown" once dropped whole variables.
"""

import ast
import json
import os
import sys
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODULE_ROOT = os.path.join(APP_ROOT, "erplite")
sys.path.insert(0, HERE)

# Hooks Frappe runs on a document that exists only in memory. Anything reachable from one of these
# runs before the record has ever been in the database.
NEW_DOC_HOOKS = {
    "autoname", "before_naming", "before_validate", "validate", "before_insert",
    "after_insert", "before_save", "on_update", "before_submit", "on_submit",
    "on_change", "db_insert",
}

# frappe.model.document.Document / BaseDocument internals, plus Frappe's standard columns.
FRAPPE_ATTRS = {
    "name", "doctype", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "parent", "parentfield", "parenttype", "_assign", "_comments", "_user_tags", "_liked_by",
    "flags", "meta", "_meta", "_doc_before_save", "_action", "_original_modified", "_table_fields",
    "_valid_columns", "_no_feed", "_document_follows",
    "get", "set", "append", "extend", "remove", "update", "insert", "save", "submit", "cancel",
    "delete", "reload", "load_from_db", "db_set", "db_update", "run_method", "get_doc_before_save",
    "has_value_changed", "is_new", "get_valid_dict", "as_dict", "get_title", "check_permission",
    "throw", "get_url", "add_comment", "notify_update", "set_status", "queue_action",
    "get_all_children", "get_password", "precision", "get_formatted", "get_latest", "lock",
    "unlock", "add_tag", "get_tags", "append_to", "dont_update_if_missing", "get_permitted_fields",
    "validate_value", "validate_table_has_rows", "round_floats_in", "get_onload", "set_onload",
    "set_new_name", "cast", "get_value", "update_modified", "get_signature", "run_notifications",
    "get_doc", "_validate", "get_dict", "set_parent_in_children", "validate_update_after_submit",
}


def _app_doctypes():
    """Every DocType this app defines: its declared fields, where it lives, and what would not read.

    Returns (fields, dirpaths, unreadable): {DocType: set of declared fieldnames},
    {DocType: the folder it is declared in}, and a list of DocType JSONs that could not be parsed.

    That third value is why this is a tuple rather than one dict. A JSON this function cannot read
    used to be skipped with a bare `continue`, which dropped the DocType from the map -- and the
    map is what "undeclared" is measured against, so the `doctype in doctypes` guard downstream
    then made every violation on that DocType unreportable. A missing declared-field list is
    indistinguishable from there being nothing to find, so the tests assert this is empty instead
    of carrying on without it.

    The three tests in this file are the only ones that assert it. test_query_fields.py and
    test_client_scripts.py call this helper and discard it on purpose: an unreadable JSON shrinks
    their coverage too, but it is one fact and it only needs to be loud once -- no DocType JSON can
    stop parsing without the sweeps below going red in the same run.

    Layout fieldtypes (Section/Column Break, HTML, ...) put no column on the table but are counted
    as declared: we are looking for names declared NOWHERE, so counting them avoids false alarms.
    """
    fields, dirpaths, unreadable = {}, {}, []
    for dirpath, _dirs, _files in os.walk(MODULE_ROOT):
        base = os.path.basename(dirpath)
        jpath = os.path.join(dirpath, base + ".json")
        if "/doctype/" not in dirpath.replace(os.sep, "/") + "/":
            continue
        if not os.path.exists(jpath):
            continue
        try:
            with open(jpath, encoding="utf-8") as fh:
                data = json.load(fh)
        except (ValueError, OSError) as exc:
            unreadable.append("{}: {}".format(os.path.relpath(jpath, APP_ROOT), exc))
            continue
        if data.get("doctype") != "DocType":
            continue
        fields[data.get("name")] = {
            f["fieldname"] for f in data.get("fields", []) if f.get("fieldname")
        }
        dirpaths[data.get("name")] = dirpath
    return fields, dirpaths, unreadable


def _excused(attr, declared):
    """Names that are not a missing field: declared on the DocType, a Document internal, a dunder."""
    return attr in declared or attr in FRAPPE_ATTRS or attr.startswith("__")


def _call_written_fields(call, holder):
    """[(fieldname, how it is written)] for the call shapes that write a field on `holder`.

    A write does not have to look like `doc.x = v`. These four name the column in a string
    argument and end up in the same INSERT or UPDATE, so an undeclared name is dropped there
    exactly as it is for an attribute assignment -- except for `db_set`, which is worse: it
    builds the UPDATE from the name it was given rather than from get_valid_dict(), so an
    undeclared one is a failed statement rather than a quietly discarded value. Five of the six
    db_set sites in this tree are the `self.db_set("x", v)` form.

    Only literal fieldnames. A name assembled at runtime cannot be compared against a declared
    field list at all; that is pinned as a scope limit rather than guessed at.
    """
    out = []
    f = call.func
    if isinstance(f, ast.Name) and f.id == "setattr" and len(call.args) >= 2:
        target, attr = call.args[0], call.args[1]
        if isinstance(target, ast.Name) and target.id == holder:
            if isinstance(attr, ast.Constant) and isinstance(attr.value, str):
                out.append((attr.value, 'setattr({}, "{}", ...)'.format(holder, attr.value)))
        return out
    if not (
        isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == holder
    ):
        return out
    if f.attr in ("db_set", "set") and call.args:
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            out.append(
                (first.value, '{}.{}("{}", ...)'.format(holder, f.attr, first.value))
            )
    # `doc.update({...})`, and the dict form of db_set, which frappe forwards to update().
    if f.attr in ("update", "db_set") and call.args and isinstance(call.args[0], ast.Dict):
        for key in call.args[0].keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                out.append(
                    (key.value, '{}.{}({{"{}": ...}})'.format(holder, f.attr, key.value))
                )
    return out


class _ClassScan(ast.NodeVisitor):
    """What a controller class does with `self`: reads, writes, column writes, methods, call edges.

    `assigned` and `writes` hold the same attribute names, deliberately twice over: the read sweep
    needs the set (a name a controller assigns itself is a name it may legitimately read back),
    and the write sweep needs the positions.
    """

    def __init__(self):
        self.methods = set()
        self.assigned = set()
        self.reads = []
        self.writes = []
        self.column_writes = []
        self.self_calls = {}
        self._fn = []

    def visit_FunctionDef(self, node):
        self.methods.add(node.name)
        self._fn.append(node.name)
        self.self_calls.setdefault(node.name, set())
        self.generic_visit(node)
        self._fn.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        f = node.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "self":
            if self._fn:
                self.self_calls.setdefault(self._fn[-1], set()).add(f.attr)
        for attr, shape in _call_written_fields(node, "self"):
            self.column_writes.append((attr, shape, node.lineno, self._where()))
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            if isinstance(node.ctx, ast.Store):
                self.assigned.add(node.attr)
                self.writes.append((node.attr, node.lineno, self._where()))
            elif isinstance(node.ctx, ast.Load):
                self.reads.append((node.attr, node.lineno, self._where()))
        self.generic_visit(node)

    def _where(self):
        return self._fn[-1] if self._fn else "<class body>"


def _reachable_from_new(scan):
    """Every method reachable from a new-document hook, so helpers called by validate() count."""
    seen, stack = set(), [m for m in scan.methods if m in NEW_DOC_HOOKS]
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        for callee in scan.self_calls.get(m, ()):
            if callee in scan.methods and callee not in seen:
                stack.append(callee)
    return seen


def _literal_doctype(call):
    """The DocType name if this call is new_doc("X") or get_doc({"doctype": "X", ...})."""
    f = call.func
    fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
    if fname == "new_doc" and call.args:
        a = call.args[0]
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            return a.value
    if fname == "get_doc" and call.args:
        a = call.args[0]
        if isinstance(a, ast.Dict):
            for k, v in zip(a.keys, a.values):
                if (
                    isinstance(k, ast.Constant)
                    and k.value == "doctype"
                    and isinstance(v, ast.Constant)
                    and isinstance(v.value, str)
                ):
                    return v.value
    return None

def _loaded_doctype(call):
    """The DocType name if this call LOADS an existing record: get_doc("X", name)."""
    f = call.func
    fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
    if fname in ("get_doc", "get_cached_doc", "get_last_doc") and call.args:
        a = call.args[0]
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            return a.value
    return None


def _rebound_names(target):
    """The names an assignment target REBINDS.

    `doc.field = v` and `d[key] = v` rebind nothing -- they mutate the object the name
    already refers to. Walking a target for every ast.Name inside it gets this wrong and
    treats each field write as a reassignment, which silently empties the sweep.
    """
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        out = []
        for element in target.elts:
            out.extend(_rebound_names(element))
        return out
    if isinstance(target, ast.Starred):
        return _rebound_names(target.value)
    return []


_UNRESOLVED = object()


def _doc_vars(fn, doctypes, include_loaded):
    """Locals in `fn` that hold one known app DocType on every path through it.

    The rule is that EVERY binding of the name resolves to the same DocType. The rule
    before it -- bound exactly once -- threw away the unambiguous case of a name assigned
    twice from the SAME DocType, which is how a dropped write to `Timesheet Entry.date`
    sat under this guard for several sweeps: the update branch and the insert branch of
    one function each assigned `timesheet_doc`, agreeing on the DocType, and the count
    rule skipped the variable entirely.

    Anything unresolvable -- a `for`, `with`, comprehension or `except` binding, an
    import, an augmented assignment, a call this module cannot read a literal out of --
    marks the name unresolved and drops it. So a disagreement is still never reported.

    `include_loaded` is the one difference between the read and the write sweep, and it
    is not symmetric:

      * READ: False. A document loaded by get_doc("X", name) is populated from SELECT *,
        so it really does carry an orphan column, and reading one returns a stale value
        rather than raising. There is nothing to report.
      * WRITE: True. get_valid_dict() builds the INSERT or UPDATE from
        meta.get_valid_columns() no matter how the document arrived, so a write to an
        undeclared field is dropped on a loaded document exactly as on a new one.

    It is applied to each BINDING, not to the variable. "Out of scope" and "we do not know
    what this is" are different facts and conflating them lost findings: a loaded binding used
    to resolve to nothing, which marked the name unresolved and dropped it entirely -- so one
    function binding `timesheet_doc` from get_doc("Timesheet Entry", id) in its update branch
    and from new_doc in its insert branch was read-checked in neither, although the new-doc
    branch still raises. A loaded binding now agrees about the DocType and only declines to be
    reportable, so a name is dropped for being purely loaded (the scope limit above, intact)
    but kept when some other binding of it builds the document in memory.
    """
    seen = {}

    def note(name, value):
        seen.setdefault(name, set()).add(value)

    def resolve(call):
        """(DocType, whether a violation on it is reportable) for a binding call, else None."""
        dt = _literal_doctype(call)
        if dt is not None:
            return (dt, True)
        dt = _loaded_doctype(call)
        if dt is not None:
            return (dt, include_loaded)
        return None

    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            bound = resolve(node.value) if isinstance(node.value, ast.Call) else None
            for target in node.targets:
                resolved = bound if (bound and isinstance(target, ast.Name)) else _UNRESOLVED
                for name in _rebound_names(target):
                    note(name, resolved)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            for name in _rebound_names(node.target):
                note(name, _UNRESOLVED)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            for name in _rebound_names(node.target):
                note(name, _UNRESOLVED)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    for name in _rebound_names(item.optional_vars):
                        note(name, _UNRESOLVED)
        elif isinstance(node, ast.comprehension):
            for name in _rebound_names(node.target):
                note(name, _UNRESOLVED)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            note(node.name, _UNRESOLVED)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                note((alias.asname or alias.name).split(".")[0], _UNRESOLVED)

    out = {}
    for name, values in seen.items():
        if _UNRESOLVED in values:
            continue
        named = {doctype for doctype, _reportable in values}
        if len(named) != 1:
            continue
        if not any(reportable for _doctype, reportable in values):
            continue
        doctype = next(iter(named))
        if doctype in doctypes:
            out[name] = doctype
    return out


def _undeclared_doc_attrs(doctypes, ctx, include_loaded):
    """Sweep the app for a write or read of `<doc>.<attr>` where attr is not a field of <doc>.

    Returns (findings, parsed, unparseable). The third is not decoration. A file this sweep
    cannot parse contributes no findings and, with a bare `except: continue`, said nothing at
    all -- so coverage could shrink file by file with every assertion still green. A sweep that
    reads nothing passes exactly like a sweep that finds nothing, and the `parsed` count only
    catches the walk collapsing altogether, never one file going quiet.

    In the write sweep (`ctx` is ast.Store) the call shapes in _call_written_fields count too:
    `doc.x = v` is the commonest way to write a field, not the only one.
    """
    findings, unparseable, parsed = [], [], 0
    for dirpath, _dirs, names in os.walk(MODULE_ROOT):
        for n in sorted(names):
            if not n.endswith(".py"):
                continue
            path = os.path.join(dirpath, n)
            rel = os.path.relpath(path, APP_ROOT)
            try:
                with open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=path)
            except (SyntaxError, OSError) as exc:
                unparseable.append("{}: {}".format(rel, exc))
                continue
            parsed += 1
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for var, doctype in _doc_vars(fn, doctypes, include_loaded).items():
                    declared = doctypes[doctype]
                    for node in ast.walk(fn):
                        if (
                            isinstance(node, ast.Attribute)
                            and isinstance(node.value, ast.Name)
                            and node.value.id == var
                            and isinstance(node.ctx, ctx)
                        ):
                            if _excused(node.attr, declared):
                                continue
                            findings.append(
                                "{}:{}  {} is {!r}, then {}.{}  (in {}())".format(
                                    rel, node.lineno, var, doctype, var, node.attr, fn.name
                                )
                            )
                        elif ctx is ast.Store and isinstance(node, ast.Call):
                            for attr, shape in _call_written_fields(node, var):
                                if _excused(attr, declared):
                                    continue
                                findings.append(
                                    "{}:{}  {} is {!r}, then {}  (in {}())".format(
                                        rel, node.lineno, var, doctype, shape, fn.name
                                    )
                                )
    return sorted(set(findings)), parsed, unparseable



class TestControllersDoNotReadUndeclaredFields(unittest.TestCase):
    """`self.<x>` in a DocType's own controller, where <x> is not a field of that DocType.

    This is the shape that stopped the scheduler creating entries. Reaching it from validate() or
    any other new-document hook means creation raises AttributeError; elsewhere it means a stale
    read on a loaded document, which is still wrong but quieter.
    """

    def test_no_controller_reads_a_field_its_doctype_does_not_have(self):
        fields, dirpaths, unreadable = _app_doctypes()
        hot, cold, dropped, columns, unparseable, checked = [], [], [], [], [], 0

        for dt, dirpath in sorted(dirpaths.items()):
            base = os.path.basename(dirpath)
            ppath = os.path.join(dirpath, base + ".py")
            if not os.path.exists(ppath):
                continue
            rel = os.path.relpath(ppath, APP_ROOT)
            try:
                with open(ppath, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=ppath)
            except (SyntaxError, OSError) as exc:
                unparseable.append("{}: {}".format(rel, exc))
                continue
            checked += 1
            declared = fields[dt]
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                scan = _ClassScan()
                for child in node.body:
                    scan.visit(child)
                on_new = _reachable_from_new(scan)
                known = declared | scan.methods | scan.assigned | FRAPPE_ATTRS
                for attr, lineno, fn in scan.reads:
                    if attr in known or attr.startswith("__"):
                        continue
                    where = "{}:{}  {}.self.{}  (in {}())".format(rel, lineno, dt, attr, fn)
                    (hot if fn in on_new else cold).append(where)

                # The silent half, and it needs a different rule from the reads above. This
                # file's stated position is that a controller may invent attributes of its
                # own, which is exactly why `scan.assigned` is in the read sweep's known set
                # -- so "it is assigned here" cannot also be what excuses the write. What
                # separates a working transient from a lost field is that a transient is READ
                # BACK somewhere in the class. An undeclared attribute that is only ever
                # written is computed, dropped by get_valid_dict() on save, and never used by
                # anything: the save still succeeds and the value is simply gone.
                read_back = {attr for attr, _lineno, _fn in scan.reads}
                for attr, lineno, fn in scan.writes:
                    if _excused(attr, declared | scan.methods) or attr in read_back:
                        continue
                    dropped.append(
                        "{}:{}  {}.self.{} = ...  (in {}())".format(rel, lineno, dt, attr, fn)
                    )

                # db_set / set / update / setattr name the column in a string instead of going
                # through an attribute, and db_set puts that name straight into the UPDATE. The
                # read-back exemption does not apply to these: none of them can be a transient.
                for attr, shape, lineno, fn in scan.column_writes:
                    if _excused(attr, declared | scan.methods):
                        continue
                    columns.append("{}:{}  {}.{}  (in {}())".format(rel, lineno, dt, shape, fn))

        self.assertEqual(
            [],
            unparseable,
            "This sweep could not parse these controllers, so it reported nothing about them "
            "and the silence is not evidence:\n  " + "\n  ".join(unparseable),
        )
        self.assertEqual(
            [],
            unreadable,
            "These DocType JSONs could not be read, so their declared-field list -- the thing "
            "'undeclared' is measured against -- is missing:\n  " + "\n  ".join(unreadable),
        )
        self.assertGreater(checked, 20, "sweep found almost no controllers; the walk is wrong")
        self.assertEqual(
            [],
            hot,
            "These run on a document built in memory, so they raise AttributeError and the save "
            "fails -- the field is not on the DocType:\n  " + "\n  ".join(hot),
        )
        self.assertEqual(
            [],
            cold,
            "These read a field the DocType does not declare. On a loaded document it is a stale "
            "orphan column; on a new one it raises:\n  " + "\n  ".join(cold),
        )
        self.assertEqual(
            [],
            dropped,
            "These write an attribute the DocType does not declare and never read it back, so "
            "the value is computed and then dropped on save:\n  " + "\n  ".join(dropped),
        )
        self.assertEqual(
            [],
            columns,
            "These name an undeclared column in a write call. db_set builds its UPDATE from that "
            "name, so the statement fails rather than being discarded:\n  " + "\n  ".join(columns),
        )


class TestInMemoryDocumentsAreNotReadByUndeclaredField(unittest.TestCase):
    """`doc = frappe.new_doc("X")` ... `doc.<y>`, anywhere in the app, where <y> is not on X.

    Same failure as the controller sweep above but outside a controller, which is where the
    whitelisted endpoints live. Documents LOADED from the database are deliberately out of
    scope here: they are populated from SELECT *, so an orphan column is present and reading
    it returns a stale value instead of raising. Only documents built in memory raise.
    """

    def test_no_new_document_is_read_by_a_field_it_does_not_have(self):
        fields, _dirpaths, unreadable = _app_doctypes()
        findings, parsed, unparseable = _undeclared_doc_attrs(
            fields, ast.Load, include_loaded=False
        )

        self.assertEqual(
            [],
            unparseable,
            "This sweep could not parse these files, so it reported nothing about them and the "
            "silence is not evidence:\n  " + "\n  ".join(unparseable),
        )
        self.assertEqual(
            [],
            unreadable,
            "These DocType JSONs could not be read, so every violation on them is unreportable:"
            "\n  " + "\n  ".join(unreadable),
        )
        self.assertGreater(parsed, 50, "sweep parsed almost nothing; the walk is wrong")
        self.assertEqual(
            [],
            findings,
            "These read a field off a document built in memory that the DocType does not have, so "
            "they raise AttributeError:\n  " + "\n  ".join(findings),
        )


class TestDocumentsAreNotWrittenByUndeclaredField(unittest.TestCase):
    """`doc.<y> = v` where <y> is not a field of the DocType, however the doc was obtained.

    The silent twin of the test above, and the wider of the two. Nothing raises: the attribute
    is set on the object and then dropped by `get_valid_dict()`, which reads
    `meta.get_valid_columns()` -- the DocType's declared fields, not the table's columns. The
    write is accepted, discarded, and reported to the caller as a success.

    Unlike the read sweep this one includes documents loaded by `get_doc("X", name)`, because
    the UPDATE is built from the same declared-field list as the INSERT. Scoping the write
    sweep to in-memory documents, which is what it did at first, left every
    load-then-modify endpoint in the app unguarded -- the commonest shape there is.
    """

    def test_no_document_is_written_by_a_field_it_does_not_have(self):
        fields, _dirpaths, unreadable = _app_doctypes()
        findings, parsed, unparseable = _undeclared_doc_attrs(
            fields, ast.Store, include_loaded=True
        )

        self.assertEqual(
            [],
            unparseable,
            "This sweep could not parse these files, so it reported nothing about them and the "
            "silence is not evidence:\n  " + "\n  ".join(unparseable),
        )
        self.assertEqual(
            [],
            unreadable,
            "These DocType JSONs could not be read, so every violation on them is unreportable:"
            "\n  " + "\n  ".join(unreadable),
        )
        self.assertGreater(parsed, 50, "sweep parsed almost nothing; the walk is wrong")
        self.assertEqual(
            [],
            findings,
            "These write a field the DocType does not have. Nothing raises; get_valid_dict() "
            "drops the value on save and the caller is told it succeeded:\n  "
            + "\n  ".join(findings),
        )


def _snippet_fn(src, name="f"):
    """The FunctionDef called `name` in a snippet, for testing the helpers directly."""
    for node in ast.walk(ast.parse(textwrap.dedent(src))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError("no function {}() in the snippet".format(name))


class TestWhatTheseSweepsCannotSee(unittest.TestCase):
    """The three sweeps above are conservative. This is where the limits are written down.

    Each test here is a real way to write an undeclared field that the sweeps would not name,
    or a rule of theirs that nothing else can measure. It is here because the three
    `assertEqual([], findings)` calls above cannot say how much of the app they cover: a limit
    that is only a comment is indistinguishable from coverage, and the hot/cold split in
    particular is unobservable from outside -- both buckets assert empty, so a change that
    collapsed one into the other would not fail anything.
    """

    DT = {"Timesheet Entry": {"employee"}, "Schedule Row": {"project"}, "Schedule Entry": set()}

    def test_a_purely_loaded_document_is_write_checked_but_not_read_checked(self):
        """The one asymmetry between the two sweeps, in both directions."""
        fn = _snippet_fn("""
            def f(name):
                doc = frappe.get_doc("Timesheet Entry", name)
                return doc.booked_for
        """)
        self.assertEqual({}, _doc_vars(fn, self.DT, include_loaded=False))
        self.assertEqual({"doc": "Timesheet Entry"}, _doc_vars(fn, self.DT, include_loaded=True))

    def test_a_name_bound_both_loaded_and_new_is_read_checked(self):
        """Not a limit: the fix for one. The new-doc branch raises, so the name is in scope."""
        fn = _snippet_fn("""
            def f(existing):
                if existing:
                    doc = frappe.get_doc("Timesheet Entry", existing)
                else:
                    doc = frappe.new_doc("Timesheet Entry")
                return doc.booked_for
        """)
        self.assertEqual({"doc": "Timesheet Entry"}, _doc_vars(fn, self.DT, include_loaded=False))

    def test_a_name_bound_from_two_different_doctypes_is_dropped(self):
        """LIMIT: a disagreement is never reported, so a violation behind one is missed."""
        fn = _snippet_fn("""
            def f(other):
                doc = frappe.new_doc("Schedule Row")
                if other:
                    doc = frappe.new_doc("Schedule Entry")
                doc.task = other
        """)
        self.assertEqual({}, _doc_vars(fn, self.DT, include_loaded=True))

    def test_a_document_arriving_as_a_parameter_is_not_checked(self):
        """LIMIT: a module-level helper taking a doc. Nothing binds the name, so nothing resolves."""
        fn = _snippet_fn("""
            def f(doc):
                doc.task = 1
                return doc.also_not_a_field
        """)
        self.assertEqual({}, _doc_vars(fn, self.DT, include_loaded=True))

    def test_a_fieldname_built_at_runtime_is_not_checked(self):
        """LIMIT: there is nothing to compare against a declared-field list."""
        fn = _snippet_fn("""
            def f(fieldname, suffix, value):
                doc = frappe.new_doc("Schedule Row")
                doc.db_set(fieldname, value)
                setattr(doc, "task_" + suffix, value)
                doc.update(payload)
        """)
        self.assertEqual([], self._written(fn, "doc"))

    def test_a_child_row_appended_by_name_is_not_checked(self):
        """LIMIT: the keys belong to the child DocType, which these sweeps never resolve."""
        fn = _snippet_fn("""
            def f():
                doc = frappe.new_doc("Schedule Row")
                doc.append("daily_entries", {"not_a_field": 1})
        """)
        self.assertEqual([], self._written(fn, "doc"))
        self.assertIn("append", FRAPPE_ATTRS)

    def test_the_call_shaped_writes_are_recognised(self):
        """The positive half of the same walker: all four shapes, and only on the right holder."""
        fn = _snippet_fn("""
            def f():
                doc = frappe.new_doc("Schedule Row")
                other = frappe.new_doc("Schedule Row")
                doc.db_set("a", 1)
                doc.set("b", 1)
                doc.update({"c": 1})
                setattr(doc, "d", 1)
                doc.db_set({"e": 1})
                other.db_set("not_on_doc", 1)
        """)
        self.assertEqual(["a", "b", "c", "d", "e"], self._written(fn, "doc"))

    def test_the_hot_set_follows_self_call_edges(self):
        """The hot/cold split, which run.py cannot measure: both buckets assert empty."""
        scan = _ClassScan()
        tree = ast.parse(textwrap.dedent("""
            class Row:
                def validate(self):
                    self.check_times()

                def check_times(self):
                    self.recompute()

                def recompute(self):
                    pass

                def on_trash(self):
                    self.cleanup()

                def cleanup(self):
                    pass
        """))
        for child in tree.body[0].body:
            scan.visit(child)

        hot = _reachable_from_new(scan)
        self.assertEqual({"validate", "check_times", "recompute"}, hot)
        self.assertNotIn("on_trash", hot, "on_trash runs on a loaded document; it is not hot")
        self.assertNotIn("cleanup", hot)

    def _written(self, fn, holder):
        return sorted(
            attr
            for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            for attr, _shape in _call_written_fields(node, holder)
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
