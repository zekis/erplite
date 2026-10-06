# -*- coding: utf-8 -*-
"""Tests for the project/activity query behind the scheduler.

Background. `erplite.scheduler.api.get_projects_and_activities` built raw SQL
against `tabProject` and `tabActivity` selecting six columns that are no longer
fields on either DocType:

    Project   project_manager, work_type
    Activity  subject, priority, estimated_hours, progress_percent

All six were real fields between "installs" (d837280, 12 Jul 2025) and
"initial commit" (8126278, 27 Oct 2025), which removed them. `bench migrate`
does not drop a column when its field goes, and this app ships no patch that
does, so they survive in the tables as orphans holding whatever was last
written to them. The query therefore did not raise `Unknown column`: it
returned stale or empty values, and ordered activities by a column nothing
maintains.

`get_projects_and_activities` is reached through `get_scheduler_data`, the
scheduler's only entry point, so every activity label in the scheduler came
from the orphaned `subject`.

The replacement uses `frappe.get_all` on the real fields. The stand-in has no
`db.sql`, so raw SQL here fails outright, and it validates field names where
Frappe 15 does not check them at all - either way these tests go red if the
orphaned columns come back. See fake_frappe.py for what Frappe really does
with a field name the DocType does not have.
"""

import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from fake_frappe import FakeFrappe, _dict  # noqa: E402

USER = "zeke@company.test"

# The columns that were removed from the DocTypes and must not be queried again.
ORPHANED = (
    "project_manager", "work_type",
    "subject", "priority", "estimated_hours", "progress_percent",
)


def load_scheduler_api(frappe):
    """Load erplite/scheduler/api.py with `frappe` replaced by the stand-in.

    Loaded from its path rather than imported as erplite.scheduler.api, because
    erplite/__init__.py pulls in parts of Frappe that have nothing to do with
    these queries.
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

    # The module imports frappe.utils at module scope and calls it only from
    # get_scheduler_data, which these tests do not exercise.
    utils = types.ModuleType("frappe.utils")
    utils.today = lambda: "2026-10-05"
    utils.add_days = lambda date, days: date
    frappe_pkg.utils = utils

    sys.modules["frappe"] = frappe_pkg
    sys.modules["frappe.utils"] = utils

    import importlib.util
    path = os.path.join(APP_ROOT, "erplite", "scheduler", "api.py")
    spec = importlib.util.spec_from_file_location("erplite_scheduler_api_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SchedulerQueryTestCase(unittest.TestCase):
    def setUp(self):
        self.frappe = FakeFrappe(session_user=USER, roles=["System Manager"])
        self.frappe.tables["Division"] = [
            _dict(name="div_eng", division_name="Engineering", color="#3b82f6"),
        ]
        self.frappe.tables["Project"] = [
            _dict(name="5gofgdoomv", project_name="Novalith", status="Open",
                  project_lead=USER, division="div_eng"),
            _dict(name="other01", project_name="Another project", status="Open",
                  project_lead=None, division=None),
            # "Archived", not "Cancelled": Project.status has no Cancelled option.
            # Activity does have one, which is why act_cancelled below is left as is.
            _dict(name="dead01", project_name="Shelved", status="Archived",
                  project_lead=USER, division="div_eng"),
        ]
        self.frappe.tables["Activity"] = [
            _dict(name="g68cfomvvu", project="5gofgdoomv", status="Open",
                  activity_name="PO-0392 - CCTP Systems Engineering support"),
            _dict(name="act_aardvark", project="5gofgdoomv", status="Open",
                  activity_name="Aardvark, to sort before the PO"),
            _dict(name="act_cancelled", project="5gofgdoomv", status="Cancelled",
                  activity_name="Called off"),
            _dict(name="act_other_proj", project="other01", status="Open",
                  activity_name="Activity on another project"),
        ]
        self.api = load_scheduler_api(self.frappe)

    def projects_by_name(self):
        return {p["name"]: p for p in self.api.get_projects_and_activities()}


class TestGetProjectsAndActivities(SchedulerQueryTestCase):
    def test_activities_carry_the_real_title_field(self):
        activities = self.projects_by_name()["5gofgdoomv"]["activities"]
        titles = {a["name"]: a["activity_name"] for a in activities}

        self.assertEqual(
            "PO-0392 - CCTP Systems Engineering support", titles["g68cfomvvu"]
        )
        for name, title in titles.items():
            self.assertIsNotNone(title, "%s has no title" % name)

    def test_keeps_a_subject_alias_for_the_built_front_end_bundle(self):
        # The bundle shipped in erplite/public/frontend/assets reads
        # activity.subject, and the scheduler_obs DropdownManager calls
        # .toLowerCase() on it with no guard, so null is not a safe value.
        # Drop the alias once the front end is rebuilt from frontend/src.
        for activity in self.projects_by_name()["5gofgdoomv"]["activities"]:
            self.assertEqual(activity["activity_name"], activity["subject"])

    def test_no_orphaned_column_is_queried(self):
        self.api.get_projects_and_activities()

        for query in self.frappe.queries:
            for field in query.fields:
                self.assertNotIn(
                    field, ORPHANED,
                    "%s is an orphaned column on %s, not a field"
                    % (field, query.doctype),
                )
            for field in query.filters:
                self.assertNotIn(field, ORPHANED)
            self.assertNotIn(query.order_by, ORPHANED)

    def test_activities_are_ordered_by_the_field_that_still_exists(self):
        # The old query ordered by t.subject, which nothing maintains, so the
        # order the scheduler showed was whatever was in the orphaned column.
        activities = self.projects_by_name()["5gofgdoomv"]["activities"]

        self.assertEqual(
            ["act_aardvark", "g68cfomvvu"], [a["name"] for a in activities]
        )

    def test_the_project_lead_is_returned_not_the_orphaned_project_manager(self):
        project = self.projects_by_name()["5gofgdoomv"]

        self.assertEqual(USER, project["project_lead"])
        self.assertNotIn("project_manager", project)

    def test_archived_projects_and_cancelled_activities_are_left_out(self):
        """Two different words on purpose: Project goes Archived, Activity Cancelled."""
        projects = self.projects_by_name()

        self.assertNotIn("dead01", projects)
        self.assertNotIn(
            "act_cancelled",
            [a["name"] for a in projects["5gofgdoomv"]["activities"]],
        )

    def test_activities_stay_with_their_own_project(self):
        projects = self.projects_by_name()

        self.assertEqual(
            ["act_other_proj"], [a["name"] for a in projects["other01"]["activities"]]
        )

    def test_division_name_and_colour_are_attached(self):
        projects = self.projects_by_name()

        self.assertEqual("Engineering", projects["5gofgdoomv"]["division_name"])
        self.assertEqual("#3b82f6", projects["5gofgdoomv"]["division_color"])
        self.assertNotIn("division_name", projects["other01"])


if __name__ == "__main__":
    unittest.main()
