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
than a guarantee; `TestTheSweepCatchesANewInstance` runs the classifier against
source built for the purpose so a passing run means the sweep still works, not
merely that it found nothing.
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

# Anything that consults who the caller is. Deliberately generous: a false
# "gated" is a quieter failure than this guard crying wolf over good code, and
# test_xero_permission_gate.py is what pins the *shape* of a real gate.
GATE_CALLS = {
    "has_permission", "only_for", "check_permission", "get_roles",
    "is_timesheet_admin", "has_timesheet_permission",
}

# The endpoints that reach an unchecked write with no gate of their own.
#
# This is asserted as an exact set, so it fails in both directions:
#   * a new entry is a new instance of the rev_c3343b2cf3 class -- gate it;
#   * an entry disappearing means a gate landed -- tighten this set.
#
# `clear_old_logs` is here as a known, filed gap, not an accepted one. It runs
# `DELETE FROM tabScheduler Log` with no check, while Scheduler Log's own rows
# give `delete` to System Manager alone and its client script only offers the
# button to System Manager (`scheduler_log.js`: `frappe.user.has_role`). So the
# author's intent and the DocType's rows agree, and nothing enforces either.
# Adding the gate changes who may call a live endpoint, so it is the owner's
# decision rather than a tidy-up, and is filed for him. What is pinned here
# meanwhile is the hazard and the rows a gate would rest on
# (`TestSchedulerLogRowsAreWhatAGateWouldRestOn`).
KNOWN_UNGATED = {
    ("erplite/scheduler/doctype/scheduler_log/scheduler_log.py", "clear_old_logs"),
}


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
    """Names of permission-ish calls inside `node`, attribute or bare."""
    found = set()
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        name = None
        if isinstance(call.func, ast.Attribute):
            name = call.func.attr
        elif isinstance(call.func, ast.Name):
            name = call.func.id
        if name in GATE_CALLS:
            found.add(name)
    return found


def _called_bare_names(node):
    return {c.func.id for c in ast.walk(node)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}


def _index_functions(trees):
    """name -> [(relpath, node)] for every function defined in the app."""
    index = {}
    for rel, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                index.setdefault(node.name, []).append((rel, node))
    return index


def classify(trees):
    """(relpath, funcname) -> dict(writes=..., gates=..., via=...).

    Only whitelisted functions reaching an unchecked write are returned.
    """
    index = _index_functions(trees)
    found = {}
    for rel, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _is_whitelisted(node):
                continue
            writes = [("%s:%d" % (rel, ln), label) for ln, label in _unchecked_writes(node)]
            gates = set(_gates(node))
            via = []
            for helper in sorted(_called_bare_names(node)):
                for rel2, node2 in index.get(helper, []):
                    if node2 is node:
                        continue
                    for ln, label in _unchecked_writes(node2):
                        via.append(("%s() at %s:%d" % (helper, rel2, ln), label))
                    gates |= _gates(node2)
            if writes or via:
                found[(rel, node.name)] = {"writes": writes, "gates": gates, "via": via}
    return found


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


class TestSchedulerLogRowsAreWhatAGateWouldRestOn(unittest.TestCase):
    """What Scheduler Log's own permission rows say, while the gate is pending.

    No policy is invented here; this reads the JSON the repo ships. It is
    pinned so that the day the rows change, the decision in the owner's tray
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
            "clear_old_logs deletes Scheduler Log rows with no permission check, "
            "so these rows are documentation rather than enforcement. If the set "
            "of roles allowed to delete has changed, re-read the filed decision.")

    def test_scheduler_user_has_no_write_of_any_kind(self):
        scheduler_user = [r for r in self.rows if r["role"] == "Scheduler User"]
        self.assertEqual(len(scheduler_user), 1)
        row = scheduler_user[0]
        for ptype in ("write", "create", "delete"):
            self.assertFalse(
                row.get(ptype),
                "Scheduler User is a read-only role on Scheduler Log (%s)" % ptype)

    def test_the_client_script_offers_the_button_to_system_manager_only(self):
        """The author's intent, in their own code, next to the unenforced rows."""
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


def load_scheduler_log(table, today="2026-10-05"):
    """Load the real scheduler_log.py on top of a stand-in frappe."""
    frappe = types.ModuleType("frappe")
    frappe.db = table
    frappe._ = lambda message, *a, **k: message
    frappe.ValidationError = FakeValidationError

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
        with io.open(path, "r", encoding="utf-8") as fh:
            exec(compile(fh.read(), path, "exec"), module.__dict__)
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


if __name__ == "__main__":
    unittest.main()
