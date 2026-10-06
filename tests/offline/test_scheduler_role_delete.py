# -*- coding: utf-8 -*-
"""Deleting a Scheduler Role succeeds.

`Scheduler Role.on_trash` opened with an integrity check against a DocType that
does not exist:

    resources_using_role = frappe.get_all("Resource Role",
        filters={"role": self.name}, fields=["parent"])

There is no `Resource Role` anywhere -- no JSON, no directory, and `Resource`
has no child table at all. The owner's answer (6 Oct 2026) is that there was
never meant to be one, so the check is dead code, not an unfinished feature.
It is removed here. The `Schedule Row` check below it, which guards a DocType
that does exist, stays exactly as it was.

WHY THIS BROKE DELETE OUTRIGHT, read off frappe 15.52.0 rather than assumed
--------------------------------------------------------------------------
`frappe.get_all` is `get_list(..., ignore_permissions=True)`, so it skips the
permission check and goes straight into `DatabaseQuery.execute`. That reaches

    self.columns = self.get_table_columns()          # db_query.py:186

before it runs any SQL, and `get_table_columns` is

    columns = self.get_db_table_columns("tab" + doctype)
    if not columns:
        raise self.TableMissingError("DocType", doctype)   # database.py:1326

`ignore_ddl` is False by default (`db_query.py:548-552`), so the exception is
raised rather than swallowed into `None`. So the dead read did not return an
empty list -- it raised `TableMissingError` on the way in, before the
`Schedule Row` check was ever reached, and `on_trash` runs inside the delete.
**Every attempt to delete a Scheduler Role failed, for every role, whether or
not anything used it.**

CHECKED ON THE LIVE SITE, not just in this repo (6 Oct 2026)
------------------------------------------------------------
    SHOW TABLES LIKE 'tab%Resource%'   -> tabResource          (only)
    SELECT name FROM tabDocType WHERE name LIKE '%Resource%'
                                       -> Resource             (only)
    tabScheduler Role                  -> 5 rows
    tabSchedule Row                    -> 5 rows

So the table really is absent on crew.tierneymorris.com.au, and the five roles
there were undeletable. Worth checking rather than inferring from the repo: a
DocType can be shipped by another installed app, and then the read would have
worked and this would be a different change.

WHAT IS DELIBERATELY NOT IN THIS CHANGE
---------------------------------------
`get_role_resources` and `get_role_statistics` read the same missing DocType
and are both broken in the same way. They are *reporting* endpoints -- they
return a number or a list to a caller, and fixing them means deciding what a
"resource for a role" is now that there is no join table, which is a design
question and not this change. They are left exactly as they are and pinned in
`TestWhatIsStillBroken` so the scope is recorded rather than forgotten.
`test_scheduler_read_gate.py` already holds `get_role_resources`' exemption
from the read gate for the same reason.

WHAT FAULT INJECTION ADDED (6 Oct 2026, nineteenth target)
----------------------------------------------------------
Sixteen injections against this file, fourteen of which it noticed. The two it
did not are now `TestARenamedRoleIsStillGuarded` and
`TestTheGuardDoesNotDependOnWhoIsDeleting`, and neither was a case nobody had
thought of -- both were cases every fixture here made unreachable:

  * every fixture gives the role the same string for `name` and `role_name`,
    so filtering the guard on the label instead of the link target passed
    every test in the file; and
  * every fixture is a System Manager, who holds both the delete on Scheduler
    Role and the read on Schedule Row, so moving the integrity read from
    `get_all` to `get_list` -- which breaks the delete outright for a
    Scheduler Manager, who holds the first and not the second -- passed every
    test in the file as well.

Auditing a fixture for the cases it cannot reach is cheaper than thinking of
new assertions, and it is where both of these were.
"""

import ast
import importlib.util
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from fake_frappe import (  # noqa: E402
    FakeDocumentBase,
    FakeFrappe,
    UnknownField,
    ValidationError,
    _dict,
    make_doc,
)

DOCTYPE_DIR = os.path.join(
    APP_ROOT, "erplite", "scheduler", "doctype", "scheduler_role")
CONTROLLER = os.path.join(DOCTYPE_DIR, "scheduler_role.py")

ROLE = "Senior Systems Engineer"


def load_scheduler_role(frappe):
    """Load the real scheduler_role.py with `frappe` replaced by the stand-in."""
    for name in list(sys.modules):
        if name == "frappe" or name.startswith("frappe."):
            del sys.modules[name]

    frappe_pkg = types.ModuleType("frappe")
    frappe_pkg.__path__ = []
    for attr in dir(frappe):
        if not attr.startswith("__"):
            setattr(frappe_pkg, attr, getattr(frappe, attr))
    frappe_pkg._dict = _dict

    model = types.ModuleType("frappe.model")
    model.__path__ = []
    document = types.ModuleType("frappe.model.document")
    document.Document = FakeDocumentBase
    model.document = document
    frappe_pkg.model = model

    sys.modules["frappe"] = frappe_pkg
    sys.modules["frappe.model"] = model
    sys.modules["frappe.model.document"] = document

    spec = importlib.util.spec_from_file_location(
        "erplite_scheduler_role_under_test", CONTROLLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SchedulerRoleDeleteTestCase(unittest.TestCase):
    def setUp(self):
        self.frappe = FakeFrappe(session_user="zeke@tierneymorris.com.au")
        self.module = load_scheduler_role(self.frappe)
        self.frappe.tables["Scheduler Role"] = [
            {"name": ROLE, "role_name": ROLE, "role_code": "SSE",
             "is_active": 1, "hourly_rate": 154.0},
        ]
        self.frappe.tables["Schedule Row"] = []

    def role(self):
        """The controller as frappe builds it for the row being deleted."""
        return make_doc(
            self.module.SchedulerRole, "Scheduler Role", "scheduler",
            "scheduler_role",
            {"role_name": ROLE, "role_code": "SSE", "is_active": 1,
             "hourly_rate": 154.0},
            is_new=False,
        )

    def schedule_row(self, role, name="SCH-ROW-2026-00001"):
        return {"name": name, "naming_series": "SCH-ROW-.YYYY.-",
                "project": "5gofgdoomv", "role": role,
                "total_hours": 8.0}


class TestDeletingARoleSucceeds(SchedulerRoleDeleteTestCase):
    """The behaviour the owner asked for: deleting a role works."""

    def test_on_trash_of_an_unused_role_does_not_raise(self):
        doc = self.role()
        doc.name = ROLE
        self.assertIsNone(doc.on_trash(),
                          "on_trash must complete for a role nothing uses")
        self.assertEqual(self.frappe.messages, [],
                         "on_trash must not msgprint on the happy path")

    def test_it_is_reached_through_a_real_delete(self):
        """delete_doc runs on_trash, which is where the failure lived.

        Calling `on_trash()` alone proves the method is clean; this proves the
        method a delete actually goes through is the one tested, by driving
        frappe's ordering -- on_trash first, then the row goes.
        """
        doc = self.role()
        doc.name = ROLE
        deleted = []

        def delete(doctype, name):
            doc.on_trash()                     # Document.delete() -> on_trash
            rows = self.frappe.tables[doctype]
            self.frappe.tables[doctype] = [r for r in rows if r["name"] != name]
            deleted.append((doctype, name))

        delete("Scheduler Role", ROLE)
        self.assertEqual(deleted, [("Scheduler Role", ROLE)])
        self.assertEqual(self.frappe.tables["Scheduler Role"], [],
                         "the role should be gone")

    def test_only_schedule_row_is_queried(self):
        """One read, naming a DocType that exists. No Resource Role read at all."""
        doc = self.role()
        doc.name = ROLE
        doc.on_trash()
        self.assertEqual([q.doctype for q in self.frappe.queries],
                         ["Schedule Row"])
        self.assertEqual(self.frappe.queries[0].filters, {"role": ROLE})


class TestTheRemainingGuardStillBites(SchedulerRoleDeleteTestCase):
    """Removing one check must not quietly remove the other.

    `Schedule Row` does exist (`tabSchedule Row`, 5 rows live), so this guard
    is a real integrity check and deleting a role out from under a schedule
    would orphan those rows.
    """

    def test_a_role_in_use_cannot_be_deleted(self):
        self.frappe.tables["Schedule Row"] = [self.schedule_row(ROLE)]
        doc = self.role()
        doc.name = ROLE
        with self.assertRaises(ValidationError) as caught:
            doc.on_trash()
        self.assertIn("1 schedule entries", str(caught.exception))

    def test_the_count_in_the_message_is_the_number_of_rows(self):
        """Pins `len(...)`, so the message cannot drift to a constant."""
        self.frappe.tables["Schedule Row"] = [
            self.schedule_row(ROLE, "SCH-ROW-2026-00001"),
            self.schedule_row(ROLE, "SCH-ROW-2026-00002"),
            self.schedule_row(ROLE, "SCH-ROW-2026-00003"),
        ]
        doc = self.role()
        doc.name = ROLE
        with self.assertRaises(ValidationError) as caught:
            doc.on_trash()
        self.assertIn("3 schedule entries", str(caught.exception))

    def test_a_row_using_a_different_role_does_not_block(self):
        """Without this, the test above would pass on `if any rows at all`."""
        self.frappe.tables["Schedule Row"] = [
            self.schedule_row("Project Manager", "SCH-ROW-2026-00009")]
        doc = self.role()
        doc.name = ROLE
        self.assertIsNone(doc.on_trash())


class TestTheTestWouldHaveCaughtIt(SchedulerRoleDeleteTestCase):
    """Controls. A green test that was never capable of being red proves nothing.

    The stand-in cannot raise frappe's `TableMissingError`, because it has no
    tables. What it does instead is refuse a DocType it was never told about
    (`fake_frappe._check_fields`: "fake frappe knows nothing about doctype"),
    which fails in the same place for the same reason -- the read is rejected
    before any row is considered. Both tests below assert that, so
    `test_on_trash_of_an_unused_role_does_not_raise` above is green because the
    dead read is gone and not because the stand-in tolerated it.
    """

    def test_the_stand_in_refuses_resource_role(self):
        with self.assertRaises(UnknownField):
            self.frappe.get_all("Resource Role",
                                filters={"role": ROLE}, fields=["parent"])

    def test_the_old_on_trash_body_still_fails_here(self):
        """The removed lines, run verbatim against the same stand-in."""
        doc = self.role()
        doc.name = ROLE
        frappe = self.module.frappe
        with self.assertRaises(UnknownField):
            resources_using_role = frappe.get_all(
                "Resource Role", filters={"role": doc.name}, fields=["parent"])
            self.fail("unreachable: %r" % (resources_using_role,))

    def test_the_stand_in_serves_schedule_row(self):
        """The other half: the DocType that is kept really is readable here."""
        self.frappe.tables["Schedule Row"] = [self.schedule_row(ROLE)]
        rows = self.frappe.get_all("Schedule Row",
                                   filters={"role": ROLE}, fields=["name"])
        self.assertEqual([r["name"] for r in rows], ["SCH-ROW-2026-00001"])


class TestARenamedRoleIsStillGuarded(SchedulerRoleDeleteTestCase):
    """The guard must filter on the link target, not on the label.

    `Schedule Row.role` is a Link to Scheduler Role, so it holds the role's
    **`name`**. The row also carries `role_name`, a read-only Data field with
    `fetch_from: "role.role_name"` -- the label, denormalised onto the row.
    For a role nobody has renamed the two are the same string, which is why
    the fixtures above cannot tell them apart: a guard filtering on
    `self.role_name` instead of `self.name` passes every other test in this
    file. Found by fault injection, which is the only reason it is here.

    They come apart on a rename, and that is a supported operation on this
    DocType rather than a hypothetical: `scheduler_role.json` declares
    `"allow_rename": 1` alongside `"autoname": "field:role_name"`, so the
    name is seeded from the label once, at insert, and can be changed
    afterwards without touching it. `frappe.rename_doc` updates the Link
    columns that point at the old name, so the schedule rows follow the
    document and hold the **new name** -- never the label. A guard reading the
    label then finds no rows, and the role is deleted out from under the
    schedule entries using it, which is precisely the orphan the guard exists
    to prevent.
    """

    LABEL = "Senior Systems Engineer"   # role_name, seeded the name at insert
    NAME = "SSE"                        # what a later rename left behind

    def setUp(self):
        super(TestARenamedRoleIsStillGuarded, self).setUp()
        self.frappe.tables["Scheduler Role"] = [
            {"name": self.NAME, "role_name": self.LABEL, "role_code": "SSE",
             "is_active": 1, "hourly_rate": 154.0},
        ]

    def renamed_role(self):
        doc = make_doc(
            self.module.SchedulerRole, "Scheduler Role", "scheduler",
            "scheduler_role",
            {"role_name": self.LABEL, "role_code": "SSE", "is_active": 1,
             "hourly_rate": 154.0},
            is_new=False,
        )
        doc.name = self.NAME
        return doc

    def row(self, name="SCH-ROW-2026-00001"):
        """A schedule row as a rename leaves it: link = name, label = role_name."""
        return {"name": name, "naming_series": "SCH-ROW-.YYYY.-",
                "project": "5gofgdoomv", "role": self.NAME,
                "role_name": self.LABEL, "total_hours": 8.0}

    def test_the_fixture_really_tells_the_two_apart(self):
        """Without this the two tests below could pass on either field."""
        doc = self.renamed_role()
        self.assertNotEqual(
            doc.name, doc.role_name,
            "this fixture exists to separate the link target from the label; "
            "if they are equal again it proves nothing")

    def test_a_renamed_role_in_use_cannot_be_deleted(self):
        self.frappe.tables["Schedule Row"] = [self.row()]
        doc = self.renamed_role()
        with self.assertRaises(ValidationError) as caught:
            doc.on_trash()
        self.assertIn("1 schedule entries", str(caught.exception))

    def test_the_guard_filters_on_the_name_the_rows_actually_hold(self):
        self.frappe.tables["Schedule Row"] = [self.row()]
        doc = self.renamed_role()
        with self.assertRaises(ValidationError):
            doc.on_trash()
        self.assertEqual(self.frappe.queries[0].filters, {"role": self.NAME},
                         "the Link column holds the name, so that is what the "
                         "guard must ask for")


class TestTheGuardDoesNotDependOnWhoIsDeleting(SchedulerRoleDeleteTestCase):
    """The integrity read must ignore permissions, or the delete breaks again.

    `frappe.get_all` is `frappe.get_list` with `ignore_permissions=True`
    (`frappe/__init__.py:1993-2012`), and `get_list` refuses a user with no
    read row -- `frappe.PermissionError`, not an empty list
    (`db_query.py:114-115`). So which of the pair this one read uses decides
    whether the guard's answer is a property of the data or of whoever is
    deleting.

    That is not a hypothetical here, and it needs no claim about frappe's
    row-level narrowing. Straight off the two DocType JSONs in this repo:

        Scheduler Role  delete: System Manager, Scheduler Manager
        Schedule Row    read:   System Manager, Projects Manager, Projects User

    **A `Scheduler Manager` may delete a Scheduler Role and has no read
    permission on Schedule Row at all.** Move this read to `get_list` and
    every delete by a Scheduler Manager raises PermissionError from inside
    `on_trash` -- the defect this file was written for, in a different colour,
    hitting the role most likely to be doing the deleting. Nothing else in
    the file noticed, because its own fixture is a System Manager, who holds
    both rights.
    """

    USER = "scheduler.manager@company.test"

    def a_scheduler_manager(self):
        """A stand-in whose session user may delete roles and read no rows."""
        frappe = FakeFrappe(session_user=self.USER, roles=["Scheduler Manager"])
        frappe.tables["Scheduler Role"] = [
            {"name": ROLE, "role_name": ROLE, "role_code": "SSE",
             "is_active": 1, "hourly_rate": 154.0},
        ]
        frappe.tables["Schedule Row"] = []
        return frappe, load_scheduler_role(frappe)

    def role_of(self, module):
        doc = make_doc(
            module.SchedulerRole, "Scheduler Role", "scheduler",
            "scheduler_role",
            {"role_name": ROLE, "role_code": "SSE", "is_active": 1,
             "hourly_rate": 154.0},
            is_new=False,
        )
        doc.name = ROLE
        return doc

    def test_that_user_may_delete_a_role_and_may_not_read_schedule_rows(self):
        """The two permission rows the tests below rest on, from the JSONs."""
        frappe, _module = self.a_scheduler_manager()
        self.assertTrue(
            frappe.has_permission("Scheduler Role", "delete"),
            "a Scheduler Manager is granted delete on Scheduler Role")
        self.assertFalse(
            frappe.has_permission("Schedule Row", "read"),
            "and is granted nothing at all on Schedule Row -- if that "
            "changes, this class is testing a user who no longer exists")

    def test_a_role_in_use_is_still_refused_for_that_user(self):
        frappe, module = self.a_scheduler_manager()
        frappe.tables["Schedule Row"] = [self.schedule_row(ROLE)]
        with self.assertRaises(ValidationError) as caught:
            self.role_of(module).on_trash()
        self.assertIn("1 schedule entries", str(caught.exception))

    def test_an_unused_role_still_deletes_for_that_user(self):
        frappe, module = self.a_scheduler_manager()
        self.assertIsNone(self.role_of(module).on_trash(),
                          "on_trash must not depend on the deleting user's "
                          "read rows: that is what get_all is for")
        self.assertEqual(frappe.messages, [])


class TestWhatIsStillBroken(unittest.TestCase):
    """Parsed, not called: the scope of this change, recorded.

    `on_trash` is clean. The two reporting endpoints are not, on purpose (see
    the module docstring). This holds that list exactly, so removing the dead
    read from `on_trash` cannot be mistaken later for having fixed the module,
    and so that fixing either endpoint goes red here and asks for the note
    above to be updated.
    """

    DEAD_DOCTYPE = "Resource Role"

    # function name -> why it still names the missing DocType
    STILL_READS_IT = {
        "get_role_resources":
            "reporting endpoint: what a resource-for-a-role means without a "
            "join table is a design question, not this change",
        "get_role_statistics":
            "same, and its resource_count has no defined replacement",
    }

    def setUp(self):
        with open(CONTROLLER, "rb") as handle:
            self.source = handle.read().decode("utf-8")
        self.tree = ast.parse(self.source)

    def test_the_source_really_parses(self):
        """A planted syntax error is a SyntaxError, so a clean parse means something."""
        with self.assertRaises(SyntaxError):
            ast.parse(self.source + "\n(((\n")

    def doctypes_read_by(self, func_name):
        """Every DocType literal in a frappe read call inside one function."""
        for node in ast.walk(self.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name != func_name:
                continue
            found = set()
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                if not isinstance(inner.func, ast.Attribute):
                    continue
                if inner.func.attr not in ("get_all", "get_list", "get_doc",
                                           "get_value", "count", "exists"):
                    continue
                if inner.args and isinstance(inner.args[0], ast.Constant) \
                        and isinstance(inner.args[0].value, str):
                    found.add(inner.args[0].value)
            return found
        self.fail("%s is not in %s any more" % (func_name, CONTROLLER))

    def test_on_trash_no_longer_reads_the_missing_doctype(self):
        self.assertEqual(
            self.doctypes_read_by("on_trash"), {"Schedule Row"},
            "on_trash must read exactly Schedule Row: adding the dead "
            "Resource Role read back makes every Scheduler Role undeletable "
            "again, and adding any other read is a decision nobody has made")

    def test_exactly_these_functions_still_read_it(self):
        offenders = {
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and self.DEAD_DOCTYPE in ast.get_source_segment(self.source, node)
        }
        self.assertEqual(
            offenders, set(self.STILL_READS_IT),
            "the functions still reading %r have changed. One fewer: good, "
            "update this list and the module docstring. One more: a dead read "
            "has come back." % (self.DEAD_DOCTYPE,))

    def test_no_resource_role_doctype_appeared(self):
        """If one is ever added, this change and that list need revisiting."""
        hits = []
        for dirpath, _dirs, files in os.walk(APP_ROOT):
            if ".git" in dirpath:
                continue
            for name in files:
                if name in ("resource_role.json", "resource_role.py"):
                    hits.append(os.path.join(dirpath, name))
        self.assertEqual(hits, [],
                         "Resource Role exists now, so on_trash's check was "
                         "not dead after all -- revisit this change")


if __name__ == "__main__":
    unittest.main()
