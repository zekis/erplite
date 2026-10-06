# -*- coding: utf-8 -*-
"""Tests for the timesheet dashboard widget's queries.

Background. `erplite.projects.dashboard_widgets.get_timesheet_widget_data`
runs three `frappe.get_all` queries against Timesheet Entry and Project, and
between them they named four fields that no longer exist:

    Timesheet Entry   task, date
    Project           project_manager

`task` was a real field on Timesheet Entry at "stable with working task
kanban" (98e9b04) and was renamed to `activity` by "Fixed drag" (6b8b473) --
the same Task -> Activity rename the whole app went through, which also took
the Task DocType out entirely. `date` was removed by "initial commit"
(8126278) with no successor; `check_in_time` is the field that now carries
when the entry happened. `project_manager` was removed from Project by the
same commit, which added `timesheet_approver` and `project_lead`.

This matters more than the scheduler bug did, for two reasons. The function is
`@frappe.whitelist()`, and it is reached from a second whitelisted entry point
as well (`erplite.projects.api.get_timesheet_app_data`), so it is called
straight from the browser. And it is the timesheet widget, on the path the
business actually uses.

Note what this bug does *not* do: it does not reliably raise. Frappe 15 never
checks a field name against the DocType (see fake_frappe.py for where that was
verified in frappe/frappe), so the outcome depends on the site's migration
history -- stale values out of an orphaned column, or a hard "Unknown column"
from MariaDB if the column was never created here. The fix is the same either
way, which is why it needed no check against the live site.

`project_manager`'s replacement is `timesheet_approver`, chosen by the owner
in review tray rev_e73092bfb5. Project carries both it and `project_lead`, so
which one gates timesheet approval was a business decision rather than a
rename -- and it is also the field Afterz already reads to decide who is shown
an Approve button, so erplite and Afterz now agree. The pending-approvals
block is restored on it, and
`test_the_project_query_filters_on_the_timesheet_approver` keeps it off the
orphaned column.
"""

import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from fake_frappe import FakeFrappe, UnknownField, _dict  # noqa: E402

USER = "zeke@company.test"
OTHER = "someone.else@company.test"

# Removed from Timesheet Entry by the Task -> Activity rename and by 8126278.
ORPHANED_ON_TIMESHEET_ENTRY = ("task", "date")


def load_dashboard_widgets(frappe):
    """Load erplite/projects/dashboard_widgets.py against the stand-in.

    Loaded by path rather than imported, for the same reason as the scheduler
    tests: erplite/__init__.py pulls in parts of Frappe these queries never
    touch.
    """
    for name in list(sys.modules):
        if name == "frappe" or name.startswith("frappe."):
            del sys.modules[name]

    frappe_pkg = types.ModuleType("frappe")
    frappe_pkg.__path__ = []
    for attr in dir(frappe):
        if not attr.startswith("__"):
            setattr(frappe_pkg, attr, getattr(frappe, attr))
    frappe_pkg._dict = _dict
    sys.modules["frappe"] = frappe_pkg

    import importlib.util
    path = os.path.join(APP_ROOT, "erplite", "projects", "dashboard_widgets.py")
    spec = importlib.util.spec_from_file_location(
        "erplite_dashboard_widgets_under_test", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WidgetTestCase(unittest.TestCase):
    def setUp(self):
        self.frappe = FakeFrappe(session_user=USER, roles=["System Manager"])
        self.frappe.tables["Project"] = [
            _dict(name="5gofgdoomv", project_name="Novalith", status="Open",
                  project_lead=USER, timesheet_approver=USER),
        ]
        self.frappe.tables["Timesheet Entry"] = [
            _dict(name="ts_open", employee=USER, is_active=1, status="Draft",
                  project="5gofgdoomv", activity="g68cfomvvu",
                  location="Site", check_in_time="2026-10-05 09:00:00",
                  duration_hours=0, modified="2026-10-05 09:00:00"),
            _dict(name="ts_done", employee=USER, is_active=0, status="Submitted",
                  project="5gofgdoomv", activity="g68cfomvvu",
                  location="Site", check_in_time="2026-10-02 08:30:00",
                  duration_hours=7.5, modified="2026-10-02 17:00:00"),
            _dict(name="ts_someone_else", employee=OTHER, is_active=1,
                  status="Submitted", project="5gofgdoomv",
                  activity="g68cfomvvu", location="Site",
                  check_in_time="2026-10-03 08:00:00", duration_hours=8,
                  modified="2026-10-03 17:00:00"),
        ]
        self.widgets = load_dashboard_widgets(self.frappe)


class TestGetTimesheetWidgetData(WidgetTestCase):
    def test_it_returns_data_at_all(self):
        """Before the fix this query named a field the DocType does not have."""
        data = self.widgets.get_timesheet_widget_data()
        self.assertEqual(
            sorted(data), ["active_timesheet", "pending_approvals", "recent_timesheets"]
        )

    def test_the_active_timesheet_is_the_users_own_open_one(self):
        active = self.widgets.get_timesheet_widget_data()["active_timesheet"]
        self.assertIsNotNone(active)
        self.assertEqual(active["name"], "ts_open")

    def test_the_activity_is_returned_not_the_renamed_task(self):
        active = self.widgets.get_timesheet_widget_data()["active_timesheet"]
        self.assertEqual(active["activity"], "g68cfomvvu")
        self.assertNotIn("task", active)

    def test_recent_timesheets_are_only_the_users_own(self):
        recent = self.widgets.get_timesheet_widget_data()["recent_timesheets"]
        self.assertEqual([r["name"] for r in recent], ["ts_open", "ts_done"])

    def test_the_date_key_is_kept_and_filled_from_check_in_time(self):
        """`date` has no successor field, so it is aliased rather than dropped.

        The response shape of a whitelisted endpoint is a contract with
        whatever front end calls it, so the key stays. It now carries a
        Datetime where the removed field was a Date.
        """
        recent = self.widgets.get_timesheet_widget_data()["recent_timesheets"]
        by_name = {r["name"]: r for r in recent}
        self.assertEqual(by_name["ts_done"]["date"], "2026-10-02 08:30:00")

    def test_no_orphaned_field_is_queried_on_timesheet_entry(self):
        self.widgets.get_timesheet_widget_data()
        queried = [q for q in self.frappe.queries if q["doctype"] == "Timesheet Entry"]
        self.assertTrue(queried, "expected Timesheet Entry to be queried")
        for query in queried:
            named = list(query.get("fields") or []) + list(query.get("filters") or {})
            for orphan in ORPHANED_ON_TIMESHEET_ENTRY:
                self.assertNotIn(
                    orphan, named,
                    "%r is not a field on Timesheet Entry" % (orphan,),
                )

    def test_pending_approvals_are_the_submitted_entries_this_user_approves(self):
        """The restored feature. USER is the approver on 5gofgdoomv.

        Both Submitted entries on that project are waiting, including the one
        somebody else filled in -- which is the point of an approval queue.
        Newest first, and the Draft entry is not in it.
        """
        pending = self.widgets.get_timesheet_widget_data()["pending_approvals"]
        self.assertEqual(
            [p["name"] for p in pending], ["ts_someone_else", "ts_done"]
        )

    def test_a_user_who_approves_nothing_sees_no_queue(self):
        """The gate is the field, not the mere existence of a Project.

        OTHER has an entry on 5gofgdoomv but is not its approver, so the queue
        is empty rather than showing the project's submitted work.
        """
        self.frappe.session.user = OTHER
        data = self.widgets.get_timesheet_widget_data()
        self.assertEqual(data["pending_approvals"], [])

    def test_the_project_query_filters_on_the_timesheet_approver(self):
        """And never on the orphaned column.

        A stale `project_manager` value can outlive the field -- `bench
        migrate` drops no columns -- so filtering on it would hand someone
        approval visibility off a value nothing maintains.
        """
        self.widgets.get_timesheet_widget_data()
        project_queries = [
            q for q in self.frappe.queries if q["doctype"] == "Project"
        ]
        self.assertEqual(len(project_queries), 1)
        self.assertEqual(
            project_queries[0]["filters"], {"timesheet_approver": USER}
        )

    def test_a_user_with_no_entries_gets_nothing_rather_than_an_error(self):
        self.frappe.session.user = "nobody@company.test"
        data = self.widgets.get_timesheet_widget_data()
        self.assertIsNone(data["active_timesheet"])
        self.assertEqual(data["recent_timesheets"], [])
        self.assertEqual(data["pending_approvals"], [])


class TestTheStandInWouldCatchARegression(WidgetTestCase):
    """The tests above only bite if the stand-in rejects a removed field.

    Asserting that directly, so a green run means something.
    """

    def test_querying_task_on_timesheet_entry_is_rejected(self):
        with self.assertRaises(UnknownField):
            self.frappe.get_all(
                "Timesheet Entry",
                filters={"employee": USER},
                fields=["name", "task"],
            )

    def test_filtering_project_on_project_manager_is_rejected(self):
        """So the pending-approvals test above means something.

        If the restored block went back to the removed field, this is the
        failure it would produce.
        """
        with self.assertRaises(UnknownField):
            self.frappe.get_all(
                "Project", filters={"project_manager": USER}, fields=["name"]
            )

    def test_querying_date_on_timesheet_entry_is_rejected(self):
        with self.assertRaises(UnknownField):
            self.frappe.get_all(
                "Timesheet Entry",
                filters={"employee": USER},
                fields=["name", "date"],
            )

    def test_the_fields_it_does_accept_are_the_real_ones(self):
        rows = self.frappe.get_all(
            "Timesheet Entry",
            filters={"employee": USER},
            fields=["name", "activity", "check_in_time"],
        )
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
