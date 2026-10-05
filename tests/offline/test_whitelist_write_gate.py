# -*- coding: utf-8 -*-
"""A whitelisted endpoint that writes behind frappe's back must check permissions itself.

This is the whole-app generalisation of the owner's decision on review tray item
**rev_c3343b2cf3** (*"Enforce the DocType's own permissions."*, shipped as PR #20
and pinned by `test_xero_permission_gate.py`). That file pins six named
endpoints. This one pins the **rule**, so the next instance fails a test instead
of waiting to be found by a sweep.

## The rule, and why it is narrow

`@frappe.whitelist()` means the method is callable by name over HTTP by any
logged-in user. The Desk button is not the gate. So every whitelisted endpoint
needs a permission check somewhere between the request and the write.

Almost all of them get one for free, and that is why this guard reports so
little. `doc.save()`, `doc.insert()`, `doc.delete()` and `frappe.delete_doc()`
all check permissions inside frappe, on the document:

  * `insert` -> `check_permission("create")`
  * `save` -> `check_permission("write")`
  * `delete` / `frappe.delete_doc` -> `check_permission_and_not_submitted(doc)`
    in `frappe/model/delete_doc.py`, which calls `doc.has_permission("delete")`

and the document-level form honours `if_owner`, because
`frappe.permissions.get_doc_permissions` only restricts a permtype to the owner
when no applicable row grants it outright. So an endpoint that loads a document
and saves it is covered by the DocType's own rows without writing a line.

The writes that are **not** covered are the ones that go round the document
layer:

    frappe.db.set_value / set_single_value / delete / bulk_insert / truncate
    frappe.db.sql(...) with DELETE / UPDATE / INSERT / REPLACE / TRUNCATE / ...

None of those consults a permission row, a `validate()` or a hook. An endpoint
reaching one of them is checked only if it checks for itself.

`frappe.get_doc` is **not** a check either -- loading is free, only writing is
checked -- which is why the sweep looks for the write and not for the load.

## What this guard does not claim

It is about **writes**. An unchecked *read* is a different class and this file
says nothing about it: `frappe.db.sql("SELECT ...")` and `frappe.get_all` hand
out rows without consulting a permission row, and several endpoints here do
exactly that. `TestReadsAreNotCountedAsWrites` pins that boundary deliberately,
because counting `db.sql` as a write regardless of its verb is how a sweep
starts reporting ordinary reporting queries as security findings.

It follows calls **one level** into the app's own helpers, which is what the
Xero endpoints need (they write via `erplite/xero/accounts.py`). Two levels
deep and it would see nothing, so a deeper chain is a hole in this guard rather
than a guarantee.

A bare `helper()` is resolved to an explicit `from erplite.x import helper`
first, then to a definition in the **same module**, and otherwise not at all.
That matters more than it sounds: 21 function names in this app are defined in
more than one module (`validate` in 28 of them), so resolving by bare name
alone made one module's gate excuse another module's unchecked write. An
unresolved helper contributes neither writes nor gates -- a known blind spot,
and the safe direction for one, since inheriting a gate on a name match is how
a finding disappears.

Because a guard that reports nothing looks identical to a guard that sees
nothing, two test classes attack it rather than trust it:
`TestTheSweepCatchesANewInstance` runs the classifier over source built for the
purpose, and `TestAGateIsAShapeNotAName` pins the two name-match holes that
fault injection found in the first version of this file -- both of which left
it fully green with an unchecked `frappe.db.set_value` added to a live
whitelisted endpoint.
"""

import ast
import datetime
import io
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODULE_ROOT = os.path.join(APP_ROOT, "erplite")
SKIP_DIRS = {"node_modules", "__pycache__", ".git", "dist", "build"}

# frappe.db.* calls that write without consulting a permission row.
UNCHECKED_DB_WRITES = {
    "set_value", "set_single_value", "delete", "bulk_insert", "truncate",
}
# frappe.db.* calls carrying a raw statement, whose verb decides read vs write.
RAW_SQL_CALLS = {"sql", "multisql", "sql_ddl"}
WRITING_VERBS = {
    "DELETE", "UPDATE", "INSERT", "REPLACE", "TRUNCATE", "ALTER", "DROP", "CREATE",
}
READING_VERBS = {"SELECT", "SHOW", "DESC", "DESCRIBE", "EXPLAIN", "WITH"}

# Anything that consults who the caller is.
#
# This is split by **call shape**, and the split is load-bearing rather than
# tidiness. The first version of this guard matched these names either bare or
# as an attribute, and that silently blinded it: `erplite/scheduler/api.py`
# defines its own `get_roles(status="Active")`, which returns Scheduler Role
# rows and consults nobody, and `get_scheduler_data` calls it bare on line 28.
# So every whitelisted endpoint in that file calling `get_roles()` was scored
# "gated" on the strength of a name collision with `frappe.get_roles`. An
# unchecked `frappe.db.set_value` added to `get_scheduler_data` left this file
# wholly green -- the exact class of bug it exists to catch.
# `TestAGateIsAShapeNotAName` fault-injects that case.
#
# frappe's own checks are only ever reached as an attribute -- `frappe.x(...)`
# or `doc.x(...)` -- so requiring that form costs nothing and closes the
# collision.
FRAPPE_GATE_CALLS = {
    "has_permission", "only_for", "check_permission", "get_roles",
    "get_permitted_documents",
}

# App-defined helpers that are legitimately called bare, as
# `if not is_timesheet_admin(): return`.
#
# Membership here is a claim that the helper consults the caller, and
# `TestEveryListedAppGateReallyChecks` holds each one to it. That test is why
# `has_timesheet_permission` is **not** in this set: it is
# `@frappe.whitelist()`-ed, it is named exactly like a gate, and its whole body
# is `return True` (erplite/projects/api.py:8-12). The original set listed it.
# Nothing calls it today, so it masked nothing -- but the first
# `if not has_timesheet_permission(): return` would have scored an endpoint
# gated while leaving it open to every logged-in user.
APP_GATE_CALLS = {
    "is_timesheet_admin",
}

GATE_CALLS = FRAPPE_GATE_CALLS | APP_GATE_CALLS

# The endpoints that reach an unchecked write with no gate of their own.
#
# This is asserted as an exact set, so it fails in both directions:
#   * a new entry is a new instance of the rev_c3343b2cf3 class -- gate it;
#   * an entry disappearing means a gate landed -- tighten this set.
#
# It is **empty**, and that is the point rather than an oversight. The one
# entry it ever held was `clear_old_logs`, filed for the owner as review tray
# item rev_18a8f8826d and approved: it now calls
# `frappe.has_permission("Scheduler Log", "delete", throw=True)`, so the
# classifier scores it gated and this set has nothing left in it.
#
# An empty set makes the assertion strictly stronger, because every direction
# still fails: any new ungated endpoint is a new instance of the class, and a
# gate disappearing from `clear_old_logs` puts it straight back here.
# `TestClearOldLogsChecksDeletePermission` holds the gate itself -- including
# by deleting it from the real source and watching this classifier report the
# endpoint again, so a green sweep means the sweep still works.
KNOWN_UNGATED = set()


# --------------------------------------------------------------------------
# the classifier
# --------------------------------------------------------------------------

def _python_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                path = os.path.join(dirpath, fn)
                yield path, os.path.relpath(path, APP_ROOT).replace(os.sep, "/")


def _is_whitelisted(node):
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if dec.func.attr == "whitelist":
                return True
        if isinstance(dec, ast.Attribute) and dec.attr == "whitelist":
            return True
    return False


def _sql_verb(call):
    """The leading keyword of a raw statement, or None if it cannot be read."""
    arg = call.args[0] if call.args else None
    if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
        return None
    words = arg.value.strip().split()
    return words[0].upper() if words else None


def _unchecked_writes(node):
    """Every permission-bypassing write written directly inside `node`.

    Returns a list of (lineno, label). A raw statement whose text cannot be
    read as a literal is reported as "unreadable" and counted as a write: an
    unreadable write is something to look at, not something to assume is fine.
    """
    out = []
    for call in ast.walk(node):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
            continue
        attr = call.func.attr
        owner = call.func.value
        # frappe.db.<attr>(...)
        if not (isinstance(owner, ast.Attribute) and owner.attr == "db"):
            continue
        if attr in UNCHECKED_DB_WRITES:
            out.append((call.lineno, "db.%s" % attr))
        elif attr in RAW_SQL_CALLS:
            verb = _sql_verb(call)
            if verb is None:
                out.append((call.lineno, "db.%s (unreadable statement)" % attr))
            elif verb in WRITING_VERBS:
                out.append((call.lineno, "db.%s %s" % (attr, verb)))
    return out


def _gates(node):
    """Names of permission-ish calls inside `node`, by call shape.

    frappe's checks count only as an attribute (`frappe.get_roles(...)`,
    `doc.has_permission(...)`); app helpers count only bare. A bare call to a
    name frappe happens to share -- the app's own `get_roles()` -- is not a
    gate, which is the whole point of the split.
    """
    found = set()
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        if isinstance(call.func, ast.Attribute):
            if call.func.attr in FRAPPE_GATE_CALLS:
                found.add(call.func.attr)
        elif isinstance(call.func, ast.Name):
            if call.func.id in APP_GATE_CALLS:
                found.add(call.func.id)
    return found


def _called_bare_names(node):
    return {c.func.id for c in ast.walk(node)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}


def _index_functions(trees):
    """(relpath, name) -> [node] for every function defined in the app.

    Keyed by **module and name**, not by name alone. Keying by name alone is
    what the first version of this guard did, and in a Frappe app that is
    disastrous: 21 names here are defined in more than one module, including
    `validate` in 28 of them and `on_update` in 17, because every DocType
    controller defines them. `TestAGateIsAShapeNotAName` fault-injects the case
    that mattered.
    """
    index = {}
    for rel, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                index.setdefault((rel, node.name), []).append(node)
    return index


def _imported_from_app(scope):
    """local name -> (relpath, original name) for `from erplite.x import y`.

    Collected from anywhere inside `scope`, because this app imports its
    helpers both at module level (`customer.py:10`) and inside the function
    that uses them (`sales_invoice.py:68`).
    """
    out = {}
    for node in ast.walk(scope):
        if not isinstance(node, ast.ImportFrom):
            continue
        if not node.module or node.module.split(".")[0] != "erplite":
            continue
        rel = node.module.replace(".", "/") + ".py"
        for alias in node.names:
            out[alias.asname or alias.name] = (rel, alias.name)
    return out


def _resolve_helper(name, rel, node, module_imports, index):
    """Where a bare `name()` inside `node` actually goes, or None.

    An explicit import wins, then a definition in the same module. A name that
    resolves to neither is **unresolved**: it contributes no writes and, more
    importantly, no gates. Inheriting a gate across modules on a name match is
    how an unchecked write gets excused by an unrelated function that merely
    shares a name.
    """
    visible = dict(module_imports)
    visible.update(_imported_from_app(node))
    if name in visible:
        target_rel, target_name = visible[name]
        return index.get((target_rel, target_name)) or None
    return index.get((rel, name)) or None


def classify(trees):
    """(relpath, funcname) -> dict(writes=..., gates=..., via=...).

    Only whitelisted functions reaching an unchecked write are returned.
    """
    index = _index_functions(trees)
    found = {}
    for rel, tree in trees:
        module_imports = _imported_from_app(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _is_whitelisted(node):
                continue
            writes = [("%s:%d" % (rel, ln), label) for ln, label in _unchecked_writes(node)]
            gates = set(_gates(node))
            via = []
            unresolved = []
            for helper in sorted(_called_bare_names(node)):
                targets = _resolve_helper(helper, rel, node, module_imports, index)
                if targets is None:
                    unresolved.append(helper)
                    continue
                for node2 in targets:
                    if node2 is node:
                        continue
                    rel2 = _defining_module(node2, index)
                    for ln, label in _unchecked_writes(node2):
                        via.append(("%s() at %s:%d" % (helper, rel2, ln), label))
                    gates |= _gates(node2)
            if writes or via:
                found[(rel, node.name)] = {
                    "writes": writes, "gates": gates, "via": via,
                    "unresolved": sorted(unresolved),
                }
    return found


def _defining_module(node, index):
    for (rel, name), nodes in index.items():
        if node in nodes:
            return rel
    return "?"


def _app_trees():
    trees = []
    for path, rel in _python_files(MODULE_ROOT):
        with io.open(path, "r", encoding="utf-8", newline="") as fh:
            trees.append((rel, ast.parse(fh.read(), filename=rel)))
    return trees


# --------------------------------------------------------------------------
# the whole-app guard
# --------------------------------------------------------------------------

class TestEveryUncheckedWriteIsGated(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.found = classify(_app_trees())

    def test_the_ungated_set_is_exactly_the_known_one(self):
        ungated = {key for key, info in self.found.items() if not info["gates"]}

        new = sorted(ungated - KNOWN_UNGATED)
        gone = sorted(KNOWN_UNGATED - ungated)

        lines = []
        for rel, name in new:
            info = self.found[(rel, name)]
            where = info["writes"] + info["via"]
            lines.append(
                "  NEW, needs a gate: %s %s()\n%s" % (
                    rel, name,
                    "".join("      writes %s at %s\n" % (label, at) for at, label in where),
                )
            )
        for rel, name in gone:
            lines.append(
                "  NOW GATED: %s %s() -- remove it from KNOWN_UNGATED so this\n"
                "      guard keeps holding it closed.\n" % (rel, name)
            )

        self.assertEqual(
            ungated, KNOWN_UNGATED,
            "A whitelisted endpoint reaches a write that consults no permission "
            "row, and checks nothing itself. Whitelisted means any logged-in "
            "user can call it by name.\n" + "".join(lines)
        )

    def test_the_six_xero_endpoints_are_still_gated(self):
        """The ones rev_c3343b2cf3 was about, seen through this sweep's eyes."""
        xero = {key: info for key, info in self.found.items()
                if "send_to_xero" in key[1] or "import_from_xero" in key[1]}
        self.assertTrue(xero, "the sweep no longer sees the Xero endpoints at all")
        for key, info in sorted(xero.items()):
            self.assertIn(
                "has_permission", info["gates"],
                "%s %s() reaches an unchecked write with no has_permission: %r"
                % (key[0], key[1], info["writes"] + info["via"]))

    def test_the_sweep_sees_writes_made_through_a_helper(self):
        """One level of indirection must not hide a write.

        The invoice endpoints have no unchecked write of their own on the
        sales side -- it happens in `erplite/xero/accounts.py`. If this stops
        holding, the sweep has gone blind to the shape it was built for.
        """
        via_helper = [key for key, info in self.found.items() if info["via"]]
        self.assertTrue(
            via_helper,
            "no endpoint is seen writing through a helper any more; the "
            "one-level follow in classify() has probably stopped working")


class TestReadsAreNotCountedAsWrites(unittest.TestCase):
    """`db.sql` is only a write when its verb says so.

    Both sites below are reporting queries. Counting them as writes would put
    two ordinary SELECTs on a security list, which is how a guard like this
    loses the right to be believed.
    """

    def test_a_select_is_not_a_write(self):
        tree = ast.parse(
            "import frappe\n"
            "@frappe.whitelist()\n"
            "def totals():\n"
            "    return frappe.db.sql('SELECT COALESCE(SUM(duration), 0) FROM `tabX`')\n"
        )
        self.assertEqual(classify([("synthetic.py", tree)]), {})

    def test_the_scheduler_reporting_queries_are_not_flagged(self):
        found = classify(_app_trees())
        for rel, name in found:
            self.assertNotEqual(
                (rel, name),
                ("erplite/scheduler/api.py", "get_resources"),
                "get_resources reaches only SELECTs (via get_resource_utilization); "
                "it is an unchecked READ, which this file is not about")


class TestTheSweepCatchesANewInstance(unittest.TestCase):
    """A passing guard has to mean the sweep works, not that it sees nothing."""

    def _classify_one(self, src):
        return classify([("synthetic.py", ast.parse(src))])

    def test_a_bare_set_value_is_caught(self):
        found = self._classify_one(
            "import frappe\n"
            "@frappe.whitelist()\n"
            "def touch(name):\n"
            "    frappe.db.set_value('Sales Invoice', name, 'status', 'Paid')\n"
        )
        self.assertIn(("synthetic.py", "touch"), found)
        self.assertEqual(found[("synthetic.py", "touch")]["gates"], set())

    def test_a_raw_delete_is_caught(self):
        found = self._classify_one(
            "import frappe\n"
            "@frappe.whitelist()\n"
            "def wipe():\n"
            "    frappe.db.sql('DELETE FROM `tabScheduler Log`')\n"
        )
        self.assertIn(("synthetic.py", "wipe"), found)

    def test_a_write_hidden_one_level_down_is_caught(self):
        found = self._classify_one(
            "import frappe\n"
            "def _really_write(name):\n"
            "    frappe.db.set_value('Customer', name, 'x', 1)\n"
            "@frappe.whitelist()\n"
            "def looks_innocent(name):\n"
            "    return _really_write(name)\n"
        )
        self.assertIn(("synthetic.py", "looks_innocent"), found)
        self.assertTrue(found[("synthetic.py", "looks_innocent")]["via"])

    def test_an_unreadable_statement_is_reported_not_excused(self):
        found = self._classify_one(
            "import frappe\n"
            "@frappe.whitelist()\n"
            "def dynamic(stmt):\n"
            "    frappe.db.sql(stmt)\n"
        )
        self.assertIn(("synthetic.py", "dynamic"), found)
        labels = [label for _, label in found[("synthetic.py", "dynamic")]["writes"]]
        self.assertIn("db.sql (unreadable statement)", labels)

    def test_a_gated_endpoint_is_not_reported(self):
        found = self._classify_one(
            "import frappe\n"
            "@frappe.whitelist()\n"
            "def touch(name):\n"
            "    frappe.has_permission('Sales Invoice', 'write', doc=name, throw=True)\n"
            "    frappe.db.set_value('Sales Invoice', name, 'status', 'Paid')\n"
        )
        self.assertEqual(found[("synthetic.py", "touch")]["gates"], {"has_permission"})

    def test_a_save_is_not_reported_at_all(self):
        """The reason this guard is quiet: frappe checks the document path."""
        self.assertEqual(self._classify_one(
            "import frappe\n"
            "@frappe.whitelist()\n"
            "def rename(name, title):\n"
            "    doc = frappe.get_doc('Project', name)\n"
            "    doc.title = title\n"
            "    doc.save()\n"
        ), {})


class TestAGateIsAShapeNotAName(unittest.TestCase):
    """A gate has to be the function you think it is.

    Both holes this class pins were found by fault-injecting the shipped guard:
    an unchecked `frappe.db.set_value` added to `get_scheduler_data` left the
    whole file green. Two separate name matches excused it.
    """

    @classmethod
    def setUpClass(cls):
        cls.trees = _app_trees()
        cls.found = classify(cls.trees)
        cls.index = _index_functions(cls.trees)

    def _classify(self, modules):
        return classify([(rel, ast.parse(src)) for rel, src in modules])

    # -- hole 1: the app defines a function named like one of frappe's -----

    def test_the_apps_own_get_roles_is_still_there_to_be_confused(self):
        """The collision is real, so the guard against it is not theoretical."""
        self.assertIn(("erplite/scheduler/api.py", "get_roles"), self.index,
                      "scheduler/api.py no longer defines get_roles; this "
                      "class pins a collision that no longer exists, so "
                      "re-check what it is protecting.")
        source = [src for rel, src in
                  [(r, io.open(os.path.join(APP_ROOT, r), encoding="utf-8").read())
                   for r in ["erplite/scheduler/api.py"]]][0]
        self.assertIn("roles_data = get_roles()", source,
                      "get_scheduler_data no longer calls get_roles() bare.")
        # and it consults nobody: it returns Scheduler Role rows
        node = self.index[("erplite/scheduler/api.py", "get_roles")][0]
        self.assertEqual(_gates(node), set())

    def test_a_bare_call_to_a_frappe_gate_name_is_not_a_gate(self):
        found = self._classify([("erplite/scheduler/api.py",
            "import frappe\n"
            "def get_roles(status='Active'):\n"
            "    return frappe.get_all('Scheduler Role')\n"
            "@frappe.whitelist()\n"
            "def get_scheduler_data():\n"
            "    roles_data = get_roles()\n"
            "    frappe.db.set_value('Project', 'x', 'status', 'Open')\n"
            "    return roles_data\n")])
        key = ("erplite/scheduler/api.py", "get_scheduler_data")
        self.assertIn(key, found)
        self.assertEqual(found[key]["gates"], set(),
                         "a bare get_roles() was counted as frappe.get_roles")

    def test_frappes_own_get_roles_still_counts_as_a_gate(self):
        """Closing the hole must not stop the real check being recognised."""
        found = self._classify([("erplite/x.py",
            "import frappe\n"
            "@frappe.whitelist()\n"
            "def touch():\n"
            "    if 'System Manager' not in frappe.get_roles(frappe.session.user):\n"
            "        frappe.throw('no')\n"
            "    frappe.db.set_value('Project', 'x', 'status', 'Open')\n")])
        self.assertEqual(found[("erplite/x.py", "touch")]["gates"], {"get_roles"})

    # -- hole 2: two modules, one name ------------------------------------

    def test_a_gate_is_not_inherited_across_modules_on_a_name_match(self):
        """The deeper hole, and the one that actually excused the injection.

        `get_projects_and_activities` is defined in both `scheduler/api.py`
        (no gate) and `projects/api.py` (gated by `is_timesheet_admin`). The
        helper index was keyed by bare name, so the scheduler endpoint
        inherited the timesheet module's gate.
        """
        for rel in ("erplite/scheduler/api.py", "erplite/projects/api.py"):
            self.assertIn((rel, "get_projects_and_activities"), self.index,
                          "%s no longer defines get_projects_and_activities" % rel)
        gated = self.index[("erplite/projects/api.py",
                            "get_projects_and_activities")][0]
        ungated = self.index[("erplite/scheduler/api.py",
                              "get_projects_and_activities")][0]
        self.assertEqual(_gates(gated), {"is_timesheet_admin"})
        self.assertEqual(_gates(ungated), set())

        found = self._classify([
            ("erplite/projects/api.py",
             "import frappe\n"
             "def is_timesheet_admin():\n"
             "    return 'System Manager' in frappe.get_roles(frappe.session.user)\n"
             "def helper():\n"
             "    if not is_timesheet_admin():\n"
             "        return []\n"
             "    return frappe.get_all('Project')\n"),
            ("erplite/scheduler/api.py",
             "import frappe\n"
             "def helper():\n"
             "    return frappe.get_all('Project')\n"
             "@frappe.whitelist()\n"
             "def endpoint():\n"
             "    helper()\n"
             "    frappe.db.set_value('Project', 'x', 'status', 'Open')\n"),
        ])
        key = ("erplite/scheduler/api.py", "endpoint")
        self.assertIn(key, found)
        self.assertEqual(found[key]["gates"], set(),
                         "a gate was inherited from a same-named function in "
                         "another module")

    def test_a_write_is_not_invented_from_another_modules_namesake(self):
        """The same confusion the other way round: a false alarm."""
        found = self._classify([
            ("erplite/a.py",
             "import frappe\n"
             "def helper():\n"
             "    frappe.db.set_value('Project', 'x', 'y', 1)\n"),
            ("erplite/b.py",
             "import frappe\n"
             "def helper():\n"
             "    return frappe.get_all('Project')\n"
             "@frappe.whitelist()\n"
             "def endpoint():\n"
             "    return helper()\n"),
        ])
        self.assertNotIn(("erplite/b.py", "endpoint"), found,
                         "b.endpoint was blamed for a write in a.helper")

    def test_an_imported_helper_is_still_followed(self):
        """Module scoping must not lose the Xero endpoints' own helpers.

        They import across modules both at module level and inside the
        function, so both forms have to resolve.
        """
        for where in ("module", "function"):
            imp = "from erplite.xero.accounts import create_sales_invoice\n"
            src = ("import frappe\n"
                   + (imp if where == "module" else "")
                   + "@frappe.whitelist()\n"
                     "def send_to_xero(name):\n"
                   + ("    " + imp if where == "function" else "")
                   + "    return create_sales_invoice(name)\n")
            found = self._classify([
                ("erplite/xero/accounts.py",
                 "import frappe\n"
                 "def create_sales_invoice(name):\n"
                 "    frappe.db.set_value('Sales Invoice', name, 'x', 1)\n"),
                ("erplite/accounts/doctype/sales_invoice/sales_invoice.py", src),
            ])
            key = ("erplite/accounts/doctype/sales_invoice/sales_invoice.py",
                   "send_to_xero")
            self.assertIn(key, found, "a %s-level import was not followed" % where)
            self.assertTrue(found[key]["via"])

    def test_the_four_xero_senders_still_resolve_through_their_helper(self):
        """The same thing against the real app, not synthetic source."""
        for rel in ("erplite/accounts/doctype/sales_invoice/sales_invoice.py",
                    "erplite/accounts/doctype/purchase_invoice/purchase_invoice.py",
                    "erplite/crm/doctype/customer/customer.py",
                    "erplite/crm/doctype/supplier/supplier.py"):
            entry = self.found[(rel, "send_to_xero")]
            self.assertTrue(entry["via"],
                            "%s send_to_xero no longer resolves its helper, so "
                            "it is passing for the wrong reason" % rel)
            self.assertTrue(any("erplite/xero/accounts.py" in label
                                for label, _ in entry["via"]))

    # -- the meta-rule ----------------------------------------------------

    def test_every_listed_app_gate_really_checks(self):
        """Membership of APP_GATE_CALLS is a claim; this holds each one to it."""
        for name in sorted(APP_GATE_CALLS):
            matches = [nodes for (rel, n), nodes in self.index.items() if n == name]
            self.assertTrue(matches, "APP_GATE_CALLS names %s, which the app "
                                     "does not define" % name)
            for nodes in matches:
                body = "\n".join(ast.dump(n) for n in nodes)
                self.assertTrue("session" in body or "get_roles" in body,
                                "%s is listed as a gate but never consults the "
                                "caller" % name)

    def test_has_timesheet_permission_is_not_listed_as_a_gate(self):
        """It is named like a gate, whitelisted, and returns True to everyone.

        The first version of this guard listed it. Nothing calls it today, so
        it masked nothing -- but `if not has_timesheet_permission(): return`
        would have scored an endpoint gated while leaving it wide open.
        """
        self.assertNotIn("has_timesheet_permission", GATE_CALLS)
        node = self.index[("erplite/projects/api.py",
                           "has_timesheet_permission")][0]
        body = [n for n in node.body if not isinstance(n, ast.Expr)]
        self.assertEqual(len(body), 1)
        self.assertIsInstance(body[0], ast.Return)
        self.assertIs(body[0].value.value, True,
                      "has_timesheet_permission now does something; re-read it "
                      "before deciding whether it is a gate.")
        self.assertEqual(_gates(node), set())

    def test_the_other_clear_old_logs_is_not_a_second_instance(self):
        """Two modules define `clear_old_logs`; only one is the hazard.

        `XeroSyncLog.clear_old_logs` is a @staticmethod, not whitelisted, and
        deletes through `frappe.delete_doc`, which checks. Pinned because
        "this is the last instance in the app" was told to the owner, and a
        name-keyed index is exactly how that claim would rot unnoticed.
        """
        rel = "erplite/setup/doctype/xero_sync_log/xero_sync_log.py"
        node = self.index[(rel, "clear_old_logs")][0]
        self.assertFalse(_is_whitelisted(node))
        self.assertEqual(_unchecked_writes(node), [])
        self.assertNotIn((rel, "clear_old_logs"), self.found)


class TestSchedulerLogRowsAreWhatTheGateRestsOn(unittest.TestCase):
    """What Scheduler Log's own permission rows say -- which is now enforced.

    No policy is invented here or in the endpoint; both read the JSON the repo
    ships. `clear_old_logs` asks `has_permission` and frappe answers from these
    rows, so changing them changes who may clear the log. They are pinned so
    that the day they change, the decision in the owner's tray (rev_18a8f8826d)
    is re-read rather than quietly outdated.
    """

    @classmethod
    def setUpClass(cls):
        path = os.path.join(MODULE_ROOT, "scheduler", "doctype", "scheduler_log",
                            "scheduler_log.json")
        with io.open(path, "r", encoding="utf-8") as fh:
            cls.rows = json.load(fh).get("permissions", [])

    def test_only_system_manager_may_delete(self):
        may_delete = sorted(r["role"] for r in self.rows if r.get("delete"))
        self.assertEqual(
            may_delete, ["System Manager"],
            "clear_old_logs is gated on `delete` for this DocType, so this row "
            "is the whole policy: these are the roles that may clear the "
            "scheduler log. If the set has changed, re-read the filed decision "
            "(rev_18a8f8826d) rather than taking the new rows as intended.")

    def test_scheduler_user_has_no_write_of_any_kind(self):
        scheduler_user = [r for r in self.rows if r["role"] == "Scheduler User"]
        self.assertEqual(len(scheduler_user), 1)
        row = scheduler_user[0]
        for ptype in ("write", "create", "delete"):
            self.assertFalse(
                row.get(ptype),
                "Scheduler User is a read-only role on Scheduler Log (%s)" % ptype)

    def test_the_client_script_offers_the_button_to_system_manager_only(self):
        """The author's intent, in their own code, agreeing with the rows.

        The button check is not the gate -- a whitelisted method is callable by
        name whatever the Desk shows -- but it is the evidence that enforcing
        `delete` on Scheduler Log narrows this endpoint to who was meant to
        have it. If the script starts offering the button more widely, the
        rows, not this endpoint, are where that belongs.
        """
        path = os.path.join(MODULE_ROOT, "scheduler", "doctype", "scheduler_log",
                            "scheduler_log.js")
        with io.open(path, "r", encoding="utf-8") as fh:
            js = fh.read()
        self.assertIn("has_role('System Manager')", js)
        self.assertIn("clear_old_logs", js)


# --------------------------------------------------------------------------
# clear_old_logs: what it does once it is allowed to run
# --------------------------------------------------------------------------

class FakeLogTable(object):
    """An in-memory `tabScheduler Log` answering only this endpoint's queries.

    It raises on any statement it does not recognise. A stand-in that quietly
    answered an unfamiliar query would let these tests pass over a rewritten
    endpoint, which is the opposite of what they are for.

    The DELETE returns `()`, which is what frappe really returns: `db.sql`
    gives back `()` whenever the cursor has no description, and a DELETE has
    none. That single fact is why the endpoint used to report 0 deletions
    however many rows it removed.
    """

    def __init__(self, dates):
        self.rows = list(dates)          # ISO date strings, compared as text
        self.statements = []
        self.commits = 0

    def sql(self, query, values=(), **kwargs):
        flat = " ".join(query.split())
        self.statements.append(flat)
        cutoff = values[0] if values else None
        if flat.startswith("SELECT COUNT(*) FROM `tabScheduler Log` WHERE DATE(timestamp) < %s"):
            return ((len([d for d in self.rows if d < cutoff]),),)
        if flat.startswith("DELETE FROM `tabScheduler Log` WHERE DATE(timestamp) < %s"):
            self.rows = [d for d in self.rows if d >= cutoff]
            return ()
        raise AssertionError("FakeLogTable was sent a statement it does not know: %r" % flat)

    def commit(self):
        self.commits += 1


class FakeValidationError(Exception):
    pass


class FakePermissionError(Exception):
    """Stands in for `frappe.PermissionError`, which is **not** a ValidationError.

    In frappe 15.52.0 `PermissionError` subclasses `Exception` directly
    (`frappe/exceptions.py:34`, http_status_code 403) while `ValidationError`
    is its own branch (line 18). Keeping them unrelated here is what lets
    these tests tell "refused for permissions" apart from "refused for a bad
    argument", and it is why the gate must not sit inside the `try` that
    catches a bad `days`.
    """


class PermissionChecks(object):
    """Stands in for `frappe.has_permission`, and refuses to guess.

    It records what was asked and answers `allowed`. What it will not do is
    answer a question it was not set up for: anything other than `delete` on
    `Scheduler Log` is an `AssertionError` naming what was asked. A stand-in
    that cheerfully returned True for some other doctype would let every
    behaviour test below pass over an endpoint checking the wrong thing, which
    is the failure mode this whole file exists to catch.
    """

    def __init__(self, allowed=True):
        self.allowed = allowed
        self.calls = []

    def __call__(self, doctype=None, ptype="read", doc=None, user=None,
                 throw=False, **kwargs):
        self.calls.append({"doctype": doctype, "ptype": ptype, "doc": doc,
                           "user": user, "throw": throw})
        if (doctype, ptype) != ("Scheduler Log", "delete"):
            raise AssertionError(
                "PermissionChecks was asked about %r %r, which it has no answer "
                "for. clear_old_logs is meant to ask whether the caller may "
                "delete Scheduler Log; re-read the endpoint." % (doctype, ptype))
        if not self.allowed:
            if throw:
                raise FakePermissionError("No permission for Scheduler Log")
            return False
        return True


def load_scheduler_log(table, today="2026-10-05", allowed=True, source=None):
    """Load the real scheduler_log.py on top of a stand-in frappe.

    `allowed` is the answer the stand-in `has_permission` gives: the behaviour
    tests run as a caller who may delete, and the gate's own tests set it
    False. `source` replaces the file's text, which is how the gate is
    fault-injected -- loading the module with the check deleted must make
    tests fail, or they are not holding it.
    """
    frappe = types.ModuleType("frappe")
    frappe.db = table
    frappe._ = lambda message, *a, **k: message
    frappe.ValidationError = FakeValidationError
    frappe.PermissionError = FakePermissionError
    frappe.has_permission = PermissionChecks(allowed=allowed)

    def throw(message, exc=None, **kwargs):
        raise (exc or FakeValidationError)(message)

    frappe.throw = throw
    frappe.whitelist = lambda *a, **k: (lambda fn: fn)

    utils = types.ModuleType("frappe.utils")
    utils.today = lambda: today
    utils.now = lambda: today + " 12:00:00"

    def add_days(date_str, days):
        d = datetime.date.fromisoformat(str(date_str)[:10]) + datetime.timedelta(days=days)
        return d.isoformat()

    utils.add_days = add_days
    frappe.utils = utils

    model = types.ModuleType("frappe.model")
    model.__path__ = []
    document = types.ModuleType("frappe.model.document")

    class Document(object):
        pass

    document.Document = Document
    model.document = document
    frappe.model = model

    saved = {name: sys.modules.get(name) for name in
             ("frappe", "frappe.utils", "frappe.model", "frappe.model.document")}
    sys.modules.update({
        "frappe": frappe, "frappe.utils": utils,
        "frappe.model": model, "frappe.model.document": document,
    })
    try:
        path = os.path.join(MODULE_ROOT, "scheduler", "doctype", "scheduler_log",
                            "scheduler_log.py")
        module = types.ModuleType("scheduler_log_under_test")
        if source is None:
            with io.open(path, "r", encoding="utf-8") as fh:
                source = fh.read()
        exec(compile(source, path, "exec"), module.__dict__)
        module.frappe = frappe
        return module
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


class TestClearOldLogsReportsWhatItActuallyDeleted(unittest.TestCase):

    def test_the_count_is_the_number_of_rows_removed(self):
        table = FakeLogTable(["2026-01-01", "2026-02-01", "2026-10-04", "2026-10-05"])
        module = load_scheduler_log(table)

        result = module.clear_old_logs(days=30)

        # cutoff is 2026-09-05: the two January/February rows go.
        self.assertEqual(result["deleted_count"], 2)
        self.assertEqual(table.rows, ["2026-10-04", "2026-10-05"])

    def test_zero_deletions_report_zero(self):
        table = FakeLogTable(["2026-10-04", "2026-10-05"])
        module = load_scheduler_log(table)
        self.assertEqual(module.clear_old_logs(days=30)["deleted_count"], 0)

    def test_it_counts_before_it_deletes(self):
        """Order matters: counting after the DELETE would always report 0."""
        table = FakeLogTable(["2026-01-01"])
        module = load_scheduler_log(table)
        module.clear_old_logs(days=30)
        verbs = [s.split()[0] for s in table.statements]
        self.assertEqual(verbs, ["SELECT", "DELETE"])

    def test_the_work_is_committed(self):
        table = FakeLogTable(["2026-01-01"])
        module = load_scheduler_log(table)
        module.clear_old_logs(days=30)
        self.assertEqual(table.commits, 1)


class TestClearOldLogsRefusesADaysItCannotMean(unittest.TestCase):
    """`days` is caller-controlled, and the dangerous values are reachable.

    This function has no type annotations, so frappe's
    `transform_parameter_types` returns early and coerces nothing, and over a
    JSON request body `make_form_dict` runs `json.loads`, so the caller
    chooses the type. A negative int therefore arrives intact, and
    `add_days(today, -(-10000))` puts the cutoff thousands of days in the
    future, where `DATE(timestamp) < cutoff` matches every row in the table.
    """

    def test_a_negative_days_deletes_nothing(self):
        table = FakeLogTable(["2026-01-01", "2026-10-04", "2026-10-05"])
        module = load_scheduler_log(table)

        with self.assertRaises(FakeValidationError):
            module.clear_old_logs(days=-10000)

        self.assertEqual(table.statements, [], "it must refuse before touching the table")
        self.assertEqual(len(table.rows), 3)

    def test_minus_one_is_refused_too(self):
        table = FakeLogTable(["2026-10-05"])
        module = load_scheduler_log(table)
        with self.assertRaises(FakeValidationError):
            module.clear_old_logs(days=-1)

    def test_a_non_numeric_days_is_refused_rather_than_read_as_zero(self):
        """`cint('abc')` is 0, and 0 here means "delete everything before today"."""
        table = FakeLogTable(["2026-01-01", "2026-10-04"])
        module = load_scheduler_log(table)

        with self.assertRaises(FakeValidationError):
            module.clear_old_logs(days="abc")

        self.assertEqual(table.statements, [])
        self.assertEqual(len(table.rows), 2)

    def test_a_numeric_string_still_works(self):
        """The form-encoded path sends strings, and it worked before. Keep it."""
        table = FakeLogTable(["2026-01-01", "2026-10-04"])
        module = load_scheduler_log(table)
        self.assertEqual(module.clear_old_logs(days="30")["deleted_count"], 1)

    def test_zero_days_is_allowed_and_clears_everything_before_today(self):
        """0 is a meaning a caller can have: "clear the log". Not nonsense."""
        table = FakeLogTable(["2026-01-01", "2026-10-04", "2026-10-05"])
        module = load_scheduler_log(table)
        self.assertEqual(module.clear_old_logs(days=0)["deleted_count"], 2)
        self.assertEqual(table.rows, ["2026-10-05"])

    def test_the_default_is_still_thirty_days(self):
        table = FakeLogTable(["2026-08-01", "2026-10-04"])
        module = load_scheduler_log(table)
        self.assertEqual(module.clear_old_logs()["deleted_count"], 1)


# --------------------------------------------------------------------------
# clear_old_logs: who is allowed to run it at all (rev_18a8f8826d)
# --------------------------------------------------------------------------

SCHEDULER_LOG_REL = "erplite/scheduler/doctype/scheduler_log/scheduler_log.py"


def _scheduler_log_source():
    with io.open(os.path.join(APP_ROOT, SCHEDULER_LOG_REL), encoding="utf-8") as fh:
        return fh.read()


def _without_the_gate(source):
    """The real module with its permission check deleted, for fault injection.

    Every test below that claims to hold the gate is also run against this,
    because a test that passes with the gate removed was never holding it.
    """
    lines = source.splitlines(True)
    kept = [ln for ln in lines if "has_permission(" not in ln]
    if len(kept) != len(lines) - 1:
        raise AssertionError(
            "expected exactly one has_permission( line in %s, found %d -- the "
            "injection below would not be removing what it thinks it is"
            % (SCHEDULER_LOG_REL, len(lines) - len(kept)))
    return "".join(kept)


class TestClearOldLogsChecksDeletePermission(unittest.TestCase):
    """The owner's decision on rev_18a8f8826d: enforce Scheduler Log's own rows.

    `clear_old_logs` is `@frappe.whitelist()`, so any logged-in user can call
    it by name, and it deletes through `frappe.db.sql`, which consults no
    permission row. The DocType's rows give `delete` to System Manager alone
    (`TestSchedulerLogRowsAreWhatTheGateRestsOn`); until the gate landed,
    nothing enforced them.
    """

    def test_a_caller_who_may_not_delete_gets_nowhere(self):
        table = FakeLogTable(["2026-01-01", "2026-02-01", "2026-10-04"])
        module = load_scheduler_log(table, allowed=False)

        with self.assertRaises(FakePermissionError):
            module.clear_old_logs(days=30)

        self.assertEqual(table.statements, [],
                         "it must refuse before touching the table")
        self.assertEqual(len(table.rows), 3)
        self.assertEqual(table.commits, 0)

    def test_it_asks_whether_the_caller_may_delete_scheduler_log(self):
        table = FakeLogTable(["2026-01-01"])
        module = load_scheduler_log(table)

        module.clear_old_logs(days=30)

        calls = module.frappe.has_permission.calls
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["doctype"], "Scheduler Log")
        self.assertEqual(calls[0]["ptype"], "delete")
        self.assertTrue(calls[0]["throw"],
                        "without throw=True a False answer is just ignored")
        self.assertIsNone(
            calls[0]["doc"],
            "this deletes many rows at once, so the question is whether the "
            "caller may delete Scheduler Log at all; passing a doc would ask "
            "about one row and let `if_owner` answer for the whole table")

    def test_the_check_comes_before_days_is_read(self):
        """An unprivileged caller learns nothing about the argument.

        `days="abc"` is refused with a ValidationError once you are allowed in.
        Reaching that message without delete permission would turn this
        endpoint into a free argument oracle, and would also mean the delete
        path had already been entered on an unchecked caller's behalf.
        """
        table = FakeLogTable(["2026-01-01"])
        module = load_scheduler_log(table, allowed=False)

        with self.assertRaises(FakePermissionError):
            module.clear_old_logs(days="abc")
        self.assertEqual(table.statements, [])

    def test_the_refusal_is_not_a_validation_error(self):
        """So nothing catching a ValidationError can swallow it.

        In frappe 15.52.0 `PermissionError` subclasses `Exception` directly
        (`frappe/exceptions.py:34`) and carries 403, while `ValidationError`
        (line 18) carries 417. The stand-ins keep them unrelated for the same
        reason, and this holds the endpoint's refusal to the permission branch.
        """
        table = FakeLogTable(["2026-01-01"])
        module = load_scheduler_log(table, allowed=False)

        with self.assertRaises(module.frappe.PermissionError) as caught:
            module.clear_old_logs(days=30)
        self.assertNotIsInstance(caught.exception, FakeValidationError)
        self.assertFalse(issubclass(FakePermissionError, FakeValidationError))

    def test_the_gate_is_not_inside_a_try(self):
        """Read off the source, because `try` is how this would quietly rot.

        The function already catches `(TypeError, ValueError)` around
        `int(days)`. A check moved inside that block, or into any other
        handler, would still be a call to `has_permission` -- so the classifier
        and every test above would stay green -- while a handler catching
        broadly could drop the refusal on the floor.
        """
        tree = ast.parse(_scheduler_log_source())
        func = [n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "clear_old_logs"][0]

        in_a_try = set()
        for node in ast.walk(func):
            if isinstance(node, ast.Try):
                for inner in ast.walk(node):
                    in_a_try.add(id(inner))

        gates = [c for c in ast.walk(func)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                 and c.func.attr == "has_permission"]
        self.assertEqual(len(gates), 1)
        self.assertNotIn(id(gates[0]), in_a_try)

        # and it is a statement of the function body itself, not nested in a
        # branch that some argument could skip
        top_level = [n.value for n in func.body if isinstance(n, ast.Expr)]
        self.assertIn(gates[0], top_level)

    # -- fault injection: the gate removed from the real module ------------

    def test_without_the_gate_an_unprivileged_caller_wipes_the_log(self):
        """What these tests are worth, measured by breaking the thing.

        Same stand-in, same refusing answer, the real module with its one
        check deleted: the rows go. If this ever stops deleting them, the
        tests above have stopped depending on the gate.
        """
        table = FakeLogTable(["2026-01-01", "2026-02-01", "2026-10-04"])
        module = load_scheduler_log(
            table, allowed=False, source=_without_the_gate(_scheduler_log_source()))

        result = module.clear_old_logs(days=30)

        self.assertEqual(result["deleted_count"], 2)
        self.assertEqual(table.rows, ["2026-10-04"])
        self.assertEqual(module.frappe.has_permission.calls, [],
                         "nothing was asked, which is the whole finding")

    def test_the_whole_app_guard_reports_this_endpoint_without_the_gate(self):
        """The sweep's side of the same injection.

        `KNOWN_UNGATED` is empty, so `TestEveryUncheckedWriteIsGated` passing
        has to mean the classifier still sees this endpoint and still sees it
        gated -- not that it has gone blind to the file.
        """
        trees = []
        for rel, tree in _app_trees():
            if rel == SCHEDULER_LOG_REL:
                tree = ast.parse(_without_the_gate(_scheduler_log_source()))
            trees.append((rel, tree))

        key = (SCHEDULER_LOG_REL, "clear_old_logs")
        injected = classify(trees)
        self.assertIn(key, injected)
        self.assertEqual(injected[key]["gates"], set())
        self.assertTrue(any("DELETE" in label for _, label in injected[key]["writes"]))

    def test_as_shipped_the_sweep_sees_the_endpoint_and_scores_it_gated(self):
        real = classify(_app_trees())
        key = (SCHEDULER_LOG_REL, "clear_old_logs")
        self.assertIn(key, real,
                      "the sweep no longer sees clear_old_logs at all, so it is "
                      "not the reason KNOWN_UNGATED is empty")
        self.assertEqual(real[key]["gates"], {"has_permission"})


if __name__ == "__main__":
    unittest.main()
