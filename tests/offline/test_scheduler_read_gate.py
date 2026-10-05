# -*- coding: utf-8 -*-
"""The scheduler's whitelisted reads apply the DocType's read rows.

Decision rev_d4b6b6ed62, option 1. Every `@frappe.whitelist()` function is
callable by name over HTTP by any logged-in user, so the Desk page is not the
gate. The scheduler's read endpoints used `frappe.get_all`, whose own docstring
in frappe 15.52.0 (`frappe/__init__.py:1993`) says it "will not check for
permissions", and the app called `frappe.get_list` -- the sibling that does
(`:1970`) -- nowhere at all. So no scheduler read consulted a permission row,
and `get_roles()` handed out every Scheduler Role including `hourly_rate` to
anyone with a login.

The change is `get_all` -> `get_list` at the whitelisted scheduler read call
sites. It invents no policy: it applies the rows the DocType JSONs already
ship.

WHAT THIS COSTS, pinned below rather than left to be discovered
---------------------------------------------------------------
The scheduler reads nine DocTypes, and they are not all gated on the same
roles:

    Division, Scheduler Role, Schedule Template  -> Scheduler Manager/User
    Project, Activity, Resource,
    Schedule Entry, Schedule Row                 -> Projects  Manager/User

`get_scheduler_data` reads from both groups. So a **Scheduler User**, whose
role exists for this module, is now refused `Project` -- and a **Projects
User** is now refused `Scheduler Role`. Neither can load the scheduler.
`System Manager` holds every row and is unaffected, as is `Administrator`,
which frappe allows before any row is read.

That is an inconsistency in the shipped permission rows, not in this change,
and widening the rows would be inventing policy rather than applying it. It is
pinned in `TestWhoTheRowsActuallyAdmit` so it is a recorded position with a
test on it rather than a surprise. If the rows are later made consistent, that
test goes red and says so.

WHAT IS DELIBERATELY NOT CONVERTED
----------------------------------
* **Internal integrity checks.** `Division.on_trash`, `Scheduler Role.on_trash`
  and `Schedule Entry`'s overlap check read rows to decide whether to
  `frappe.throw`. They do not return anything to the caller, and routing them
  through the caller's permissions would let a user without read rows delete a
  division that is still in use. They stay on `get_all`.
* **`get_role_resources`.** It queries `"Resource Role"`, a DocType that does
  not exist anywhere in this repo -- no JSON, no directory, and `Resource` has
  no child table at all. `get_role_statistics` counts the same missing DocType.
  The endpoint cannot run today whichever function it calls, so converting it
  would dress up a broken endpoint as a fixed one. Left exactly as it was and
  reported separately.

WHAT ELSE DIFFERS BETWEEN get_all AND get_list, CHECKED NOT ASSUMED
------------------------------------------------------------------
`get_all` is `get_list` with two keyword arguments added
(`frappe/__init__.py:2012-2015` in the installed 15.52.0):
`ignore_permissions=True` and `limit_page_length=0`. The second one looks like
a row cap this change would introduce, because `get_list`'s own docstring says
"limit_page_length: No of records in the page. Default 20". It is not:
`DatabaseQuery.execute` declares `limit_page_length=None`
(`frappe/model/db_query.py:88`), stores `cint(limit_page_length) if
limit_page_length else None` (`:145`), and only emits a LIMIT clause `if
self.limit_page_length` (`:1136`). 0 and None are both falsy, so neither
`get_all` nor `get_list` limits the rows, and the "Default 20" in the docstring
comes from a layer above this one. **Converting does not truncate a scheduler
read.** Read off the source on the live bench, not from memory.

What it does add, besides the DocType row, is row-level narrowing: `get_list`
applies User Permissions and `if_owner`. So a user restricted to one division
starts seeing one division. That is the half of option 1 worth saying out loud,
and the stand-in does not model it (see `fake_frappe.get_list`).

WHAT CHANGES FOR A REFUSED USER
-------------------------------
`get_list` does not return an empty list. `DatabaseQuery.execute` calls
`check_read_permission` (`frappe/model/db_query.py:115`), which calls
`has_permission(..., throw=True)`, so the refusal is `frappe.PermissionError`
and the request fails loudly. That is the behaviour `test_the_refusal_is_loud`
holds on to: a silent empty scheduler would be worse than an error.
"""

import ast
import os
import re
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from fake_frappe import (  # noqa: E402
    FakeFrappe, PermissionError as FakePermissionError, _dict,
)

USER = "zeke@tierneymorris.com.au"
SCHEDULER_API = os.path.join(APP_ROOT, "erplite", "scheduler", "api.py")


def load_scheduler_api(frappe):
    """Load erplite/scheduler/api.py with `frappe` replaced by the stand-in."""
    for name in list(sys.modules):
        if name == "frappe" or name.startswith("frappe."):
            del sys.modules[name]

    frappe_pkg = types.ModuleType("frappe")
    frappe_pkg.__path__ = []
    for attr in dir(frappe):
        if not attr.startswith("__"):
            setattr(frappe_pkg, attr, getattr(frappe, attr))
    frappe_pkg._dict = _dict
    frappe_pkg.PermissionError = FakePermissionError

    utils = types.ModuleType("frappe.utils")
    utils.today = lambda: "2026-10-05"
    utils.add_days = lambda date, days: "2026-11-04"
    frappe_pkg.utils = utils

    sys.modules["frappe"] = frappe_pkg
    sys.modules["frappe.utils"] = utils

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "erplite_scheduler_api_read_gate", SCHEDULER_API)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def populate(frappe):
    """The smallest set of rows that makes every scheduler read return something.

    A read that returns nothing cannot tell a refusal from an empty table, so
    every DocType asked about below has at least one row in it.
    """
    frappe.tables["Division"] = [
        _dict(name="div_eng", division_name="Engineering", division_code="ENG",
              color="#3b82f6", description="", is_active=1),
    ]
    frappe.tables["Project"] = [
        _dict(name="5gofgdoomv", project_name="Novalith", status="Open",
              project_lead=USER, division="div_eng"),
    ]
    frappe.tables["Activity"] = [
        _dict(name="g68cfomvvu", project="5gofgdoomv", status="Open",
              activity_name="PO-0392 - CCTP Systems Engineering support"),
    ]
    frappe.tables["Resource"] = [
        _dict(name="res_zeke", resource_name="Zeke", resource_type="Person",
              status="Active", capacity=8.0),
    ]
    frappe.tables["Scheduler Role"] = [
        _dict(name="role_se", role_name="Senior Systems Engineer",
              role_code="SSE", description="", is_active=1,
              color="#111111", hourly_rate=154.0),
    ]
    frappe.tables["Schedule Entry"] = [
        _dict(name="se_1", project="5gofgdoomv", activity="g68cfomvvu",
              resource="res_zeke", schedule_date="2026-10-06", duration=8.0,
              status="Planned", priority="Medium", start_time=None,
              end_time=None, description="", docstatus=0),
    ]
    return frappe


def api_for(roles):
    frappe = populate(FakeFrappe(session_user=USER, roles=roles))
    return frappe, load_scheduler_api(frappe)


class TestTheRowsAreApplied(unittest.TestCase):
    """A read now asks the DocType, and the answer changes with the caller."""

    def test_a_system_manager_still_sees_everything(self):
        """The control. Without it the refusals below could be a broken stand-in.

        Three endpoints, not `get_scheduler_data`: it reaches
        `get_resource_utilization`, which is raw `frappe.db.sql`, and the
        stand-in deliberately has no `db.sql` (see test_raw_sql.py). So the
        happy path through `get_scheduler_data` and `get_resources` cannot be
        run offline at all -- a gap that predates this change. The refusal
        tests still cover both, because the permission check fires before the
        SQL does.
        """
        frappe, api = api_for(["System Manager"])
        self.assertEqual(
            [p["name"] for p in api.get_projects_and_activities()], ["5gofgdoomv"])
        self.assertEqual([r["name"] for r in api.get_roles()], ["role_se"])
        self.assertEqual(
            [e["name"] for e in api.get_schedule_entries("2026-10-01", "2026-10-31")],
            ["se_1"])
        self.assertTrue(
            all(c.allowed for c in frappe.permission_checks),
            "a System Manager was refused something")

    def test_a_user_with_no_scheduler_roles_is_refused_the_charge_rates(self):
        """The finding, in one call: get_roles() returned hourly_rate to anyone."""
        frappe, api = api_for(["Blogger"])
        frappe.permissions["Blogger"] = {}
        with self.assertRaises(FakePermissionError):
            api.get_roles()

    def test_a_user_with_no_scheduler_roles_is_refused_the_whole_schedule(self):
        for call in ("get_scheduler_data", "get_projects_and_activities",
                     "get_resources", "get_roles"):
            with self.subTest(call=call):
                frappe, api = api_for(["Blogger"])
                with self.assertRaises(FakePermissionError):
                    getattr(api, call)()

    def test_the_date_ranged_reads_are_gated_too(self):
        for call in ("get_schedule_entries", "get_unassigned_entries"):
            with self.subTest(call=call):
                frappe, api = api_for(["Blogger"])
                with self.assertRaises(FakePermissionError):
                    getattr(api, call)("2026-10-01", "2026-10-31")
        frappe, api = api_for(["Blogger"])
        with self.assertRaises(FakePermissionError):
            api.get_schedule_rows()

    def test_the_refusal_is_loud(self):
        """Not an empty list. A silent empty scheduler would hide the refusal."""
        frappe, api = api_for(["Blogger"])
        try:
            api.get_projects_and_activities()
        except FakePermissionError:
            pass
        else:
            self.fail("get_projects_and_activities returned instead of raising")
        self.assertEqual(
            [(c.doctype, c.ptype, c.allowed) for c in frappe.permission_checks],
            [("Project", "read", False)],
            "the read was refused somewhere other than the Project read check")

    def test_administrator_is_allowed_before_any_row_is_read(self):
        """frappe/permissions.py:106-108, and it is why the owner is unaffected."""
        frappe = populate(FakeFrappe(session_user="Administrator", roles=[]))
        api = load_scheduler_api(frappe)
        self.assertEqual(len(api.get_roles()), 1)
        self.assertEqual(len(api.get_projects_and_activities()), 1)


class TestWhoTheRowsActuallyAdmit(unittest.TestCase):
    """The shipped rows split the scheduler's DocTypes across two role families.

    Recorded, not fixed: widening the rows would be inventing policy. If they
    are made consistent later, these two go red and this position is revisited.
    """

    def test_a_scheduler_user_is_refused_project(self):
        frappe, api = api_for(["Scheduler User"])
        self.assertEqual([r["role_name"] for r in api.get_roles()],
                         ["Senior Systems Engineer"],
                         "Scheduler Role grants read to Scheduler User")
        with self.assertRaises(FakePermissionError):
            api.get_projects_and_activities()
        with self.assertRaises(FakePermissionError):
            api.get_scheduler_data()

    def test_a_projects_user_is_refused_scheduler_role(self):
        frappe, api = api_for(["Projects User"])
        self.assertEqual([p["name"] for p in api.get_projects_and_activities()],
                         ["5gofgdoomv"],
                         "Project grants read to Projects User")
        with self.assertRaises(FakePermissionError):
            api.get_roles()

    def test_both_families_together_can_load_the_scheduler(self):
        frappe, api = api_for(["Projects User", "Scheduler User"])
        self.assertEqual(len(api.get_projects_and_activities()), 1)
        self.assertEqual(len(api.get_roles()), 1)
        self.assertEqual(len(api.get_schedule_entries("2026-10-01", "2026-10-31")), 1)


class TestNoSchedulerReadGoesBackToGetAll(unittest.TestCase):
    """Parsed, not called, so an endpoint no test exercises is still covered.

    `test_the_refusal_is_loud` and friends only reach the call sites they call.
    This reads the source, so a tenth whitelisted read added tomorrow with
    `frappe.get_all` fails here even if nobody writes a test for it.
    """

    # (module path, function) -> why it keeps frappe.get_all. Each reason is in
    # the module docstring above; this is the list, not the argument.
    ALLOWED_GET_ALL = {
        ("erplite/scheduler/doctype/division/division.py", "on_trash"):
            "integrity check before delete, returns nothing to the caller",
        ("erplite/scheduler/doctype/scheduler_role/scheduler_role.py", "on_trash"):
            "integrity check before delete, returns nothing to the caller",
        ("erplite/scheduler/doctype/schedule_entry/schedule_entry.py",
         "get_activity_progress"):
            "controller method, not reachable over HTTP; measures across every "
            "entry on the activity on purpose",
        ("erplite/scheduler/doctype/scheduler_role/scheduler_role.py",
         "get_role_resources"):
            'reads "Resource Role", a DocType this repo does not define',
    }

    def scheduler_sources(self):
        root = os.path.join(APP_ROOT, "erplite", "scheduler")
        for dirpath, _dirs, files in os.walk(root):
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, APP_ROOT).replace(os.sep, "/")
                with open(path, "rb") as handle:
                    source = handle.read().decode("utf-8")
                yield rel, source

    def calls_in(self, source):
        """(enclosing function, whitelisted?, frappe.<name>) for every query call."""
        tree = ast.parse(source)
        found = []

        def whitelisted(node):
            for dec in getattr(node, "decorator_list", []):
                target = dec.func if isinstance(dec, ast.Call) else dec
                if (isinstance(target, ast.Attribute)
                        and target.attr == "whitelist"
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "frappe"):
                    return True
            return False

        def walk(node, enclosing, is_whitelisted):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    walk(child, child.name, whitelisted(child))
                    continue
                if (isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Attribute)
                        and child.func.attr in ("get_all", "get_list")
                        and isinstance(child.func.value, ast.Name)
                        and child.func.value.id == "frappe"):
                    found.append((enclosing, is_whitelisted, child.func.attr))
                walk(child, enclosing, is_whitelisted)

        walk(tree, None, False)
        return found

    def test_every_whitelisted_scheduler_read_uses_get_list(self):
        checked = 0
        for rel, source in self.scheduler_sources():
            for function, is_whitelisted, which in self.calls_in(source):
                if not is_whitelisted:
                    continue
                checked += 1
                if which == "get_list":
                    continue
                with self.subTest(file=rel, function=function):
                    self.assertIn(
                        (rel, function), self.ALLOWED_GET_ALL,
                        "%s.%s is whitelisted -- callable by name by any logged-in "
                        "user -- and reads with frappe.get_all, which checks no "
                        "permission row. Use frappe.get_list, or add it to "
                        "ALLOWED_GET_ALL with the reason." % (rel, function))
        self.assertGreaterEqual(
            checked, 13,
            "found only %d whitelisted query calls in the scheduler; the sweep "
            "has stopped seeing the module" % checked)

    def test_the_internal_checks_still_bypass_permissions(self):
        """The other half: a delete guard must not run as the caller.

        Without this, "convert everything to get_list" looks like a tidy-up and
        lets a user with no read rows delete a division that is still in use.
        """
        bypassing = set()
        for rel, source in self.scheduler_sources():
            for function, is_whitelisted, which in self.calls_in(source):
                if not is_whitelisted and which == "get_all":
                    bypassing.add((rel, function))
        expected = {key for key in self.ALLOWED_GET_ALL
                    if key[1] in ("on_trash", "get_activity_progress")}
        self.assertEqual(
            bypassing, expected,
            "the scheduler's internal reads are no longer exactly the three that "
            "should bypass permissions. A new one means a read nobody has decided "
            "about; a missing one means a guard now runs as the caller, so a user "
            "without read rows could delete a division that is still in use.")

    def test_resource_role_really_is_undefined(self):
        """The reason get_role_resources is exempt, checked rather than asserted."""
        hits = []
        for dirpath, _dirs, files in os.walk(APP_ROOT):
            if ".git" in dirpath:
                continue
            for name in files:
                if name == "resource_role.json" or name == "resource_role.py":
                    hits.append(os.path.join(dirpath, name))
        self.assertEqual(hits, [],
                         "Resource Role is defined now, so get_role_resources can "
                         "be converted and its exemption removed")


class TestTheStandInActuallyChecks(unittest.TestCase):
    """Self-tests. An injection that does not inject proves nothing."""

    def test_get_all_asks_nothing(self):
        frappe = populate(FakeFrappe(session_user=USER, roles=["Blogger"]))
        rows = frappe.get_all("Project", fields=["name"])
        self.assertEqual([r["name"] for r in rows], ["5gofgdoomv"],
                         "get_all must keep returning rows to a user with no roles; "
                         "that is the behaviour the finding is about")
        self.assertEqual(frappe.permission_checks, [])

    def test_get_list_asks_and_refuses(self):
        frappe = populate(FakeFrappe(session_user=USER, roles=["Blogger"]))
        with self.assertRaises(FakePermissionError):
            frappe.get_list("Project", fields=["name"])
        self.assertEqual([(c.doctype, c.ptype, c.allowed, c.threw)
                          for c in frappe.permission_checks],
                         [("Project", "read", False, True)])

    def test_get_list_otherwise_behaves_exactly_as_get_all(self):
        frappe = populate(FakeFrappe(session_user=USER, roles=["System Manager"]))
        self.assertEqual(
            frappe.get_list("Project", fields=["name", "project_name"],
                            filters={"status": "Open"}, order_by="project_name"),
            frappe.get_all("Project", fields=["name", "project_name"],
                           filters={"status": "Open"}, order_by="project_name"))

    def test_get_list_still_validates_field_names(self):
        from fake_frappe import UnknownField
        frappe = populate(FakeFrappe(session_user=USER, roles=["System Manager"]))
        with self.assertRaises(UnknownField):
            frappe.get_list("Project", fields=["project_manager"])

    def test_every_doctype_the_scheduler_reads_has_its_rows_loaded(self):
        """Otherwise has_permission's AssertionError, not a refusal, is what fails."""
        frappe = FakeFrappe(session_user=USER)
        source = open(SCHEDULER_API, "rb").read().decode("utf-8")
        named = set(re.findall(r'frappe\.get_list\(\s*"([^"]+)"', source))
        self.assertTrue(named, "no get_list call sites found in scheduler/api.py")
        for doctype in sorted(named):
            with self.subTest(doctype=doctype):
                self.assertIn(doctype, frappe.permissions)


if __name__ == "__main__":
    unittest.main()
