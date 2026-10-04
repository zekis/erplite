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

These two tests sweep the whole app for that class so it cannot come back in a module nobody is
looking at. Both are deliberately conservative -- a name has to be declared nowhere to be reported
-- so a failure here is a real finding rather than something to add an exception for.
"""

import ast
import json
import os
import sys
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
    """{DocType name: set of declared fieldnames} for every DocType this app defines.

    Layout fieldtypes (Section/Column Break, HTML, ...) put no column on the table but are counted
    as declared: we are looking for names declared NOWHERE, so counting them avoids false alarms.
    """
    out = {}
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
        except (ValueError, OSError):
            continue
        if data.get("doctype") != "DocType":
            continue
        fields = {f["fieldname"] for f in data.get("fields", []) if f.get("fieldname")}
        out[data.get("name")] = fields
        out.setdefault("__paths__", {})[data.get("name")] = dirpath
    return out


class _ClassScan(ast.NodeVisitor):
    """Attributes read on `self`, attributes assigned on `self`, methods, and self-call edges."""

    def __init__(self):
        self.methods = set()
        self.assigned = set()
        self.reads = []
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
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            if isinstance(node.ctx, ast.Store):
                self.assigned.add(node.attr)
            elif isinstance(node.ctx, ast.Load):
                self.reads.append(
                    (node.attr, node.lineno, self._fn[-1] if self._fn else "<class body>")
                )
        self.generic_visit(node)


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


class TestControllersDoNotReadUndeclaredFields(unittest.TestCase):
    """`self.<x>` in a DocType's own controller, where <x> is not a field of that DocType.

    This is the shape that stopped the scheduler creating entries. Reaching it from validate() or
    any other new-document hook means creation raises AttributeError; elsewhere it means a stale
    read on a loaded document, which is still wrong but quieter.
    """

    def test_no_controller_reads_a_field_its_doctype_does_not_have(self):
        doctypes = _app_doctypes()
        paths = doctypes.get("__paths__", {})
        hot, cold, checked = [], [], 0

        for dt, dirpath in sorted(paths.items()):
            base = os.path.basename(dirpath)
            ppath = os.path.join(dirpath, base + ".py")
            if not os.path.exists(ppath):
                continue
            checked += 1
            with open(ppath, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=ppath)
            rel = os.path.relpath(ppath, APP_ROOT)
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                scan = _ClassScan()
                for child in node.body:
                    scan.visit(child)
                on_new = _reachable_from_new(scan)
                known = doctypes[dt] | scan.methods | scan.assigned | FRAPPE_ATTRS
                for attr, lineno, fn in scan.reads:
                    if attr in known or attr.startswith("__"):
                        continue
                    where = "{}:{}  {}.self.{}  (in {}())".format(rel, lineno, dt, attr, fn)
                    (hot if fn in on_new else cold).append(where)

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


class TestInMemoryDocumentsAreNotReadByUndeclaredField(unittest.TestCase):
    """`doc = frappe.new_doc("X")` ... `doc.<y>`, anywhere in the app, where <y> is not on X.

    Same failure as above but outside a controller, which is where the whitelisted endpoints live.
    Scoped tightly on purpose: only locals assigned exactly once from a literal new_doc/get_doc,
    and only DocTypes this app defines, since a core DocType's field list is not in this repo and
    guessing it would produce noise.
    """

    def test_no_new_document_is_read_by_a_field_it_does_not_have(self):
        doctypes = _app_doctypes()
        doctypes.pop("__paths__", None)
        findings, parsed = [], 0

        for dirpath, _dirs, names in os.walk(MODULE_ROOT):
            for n in sorted(names):
                if not n.endswith(".py"):
                    continue
                p = os.path.join(dirpath, n)
                try:
                    with open(p, encoding="utf-8") as fh:
                        tree = ast.parse(fh.read(), filename=p)
                except (SyntaxError, OSError):
                    continue
                parsed += 1
                rel = os.path.relpath(p, APP_ROOT)
                for fn in ast.walk(tree):
                    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    origin, count = {}, {}
                    for node in ast.walk(fn):
                        targets = []
                        if isinstance(node, ast.Assign):
                            targets = node.targets
                        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                            targets = [node.target]
                        for t in targets:
                            if not isinstance(t, ast.Name):
                                continue
                            count[t.id] = count.get(t.id, 0) + 1
                            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                                dt = _literal_doctype(node.value)
                                if dt:
                                    origin[t.id] = dt
                    for var, dt in origin.items():
                        if count.get(var) != 1 or dt not in doctypes:
                            continue
                        for node in ast.walk(fn):
                            if not (
                                isinstance(node, ast.Attribute)
                                and isinstance(node.value, ast.Name)
                                and node.value.id == var
                                and isinstance(node.ctx, ast.Load)
                            ):
                                continue
                            if (
                                node.attr in doctypes[dt]
                                or node.attr in FRAPPE_ATTRS
                                or node.attr.startswith("__")
                            ):
                                continue
                            findings.append(
                                "{}:{}  {} = new {!r}, then {}.{}  (in {}())".format(
                                    rel, node.lineno, var, dt, var, node.attr, fn.name
                                )
                            )

        self.assertGreater(parsed, 50, "sweep parsed almost nothing; the walk is wrong")
        self.assertEqual(
            [],
            sorted(set(findings)),
            "These read a field off a document built in memory that the DocType does not have, so "
            "they raise AttributeError:\n  " + "\n  ".join(sorted(set(findings))),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
