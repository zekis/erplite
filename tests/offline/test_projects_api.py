# -*- coding: utf-8 -*-
"""Tests for the Activity queries in erplite.projects.api.

Background. `subject` and `assigned_to` are columns that still exist in
`tabActivity` but are no longer fields on the Activity DocType. Frappe 15's
get_all does not validate field names, so querying them failed silently:
`subject` came back as None and the `assigned_to` filter matched nothing. The
timesheet calendar therefore listed projects with no activities in them, and
the admin assignment dialog showed blank labels.

The Activity title field is `activity_name`, and assignment lives in Frappe's
standard mechanism: a ToDo row per assignee, with the `_assign` column on the
document kept in step by ToDo.update_in_reference().

These tests run without a bench. See fake_frappe.py for the stand-in, which
raises on an unknown field where real Frappe would quietly return None.
"""

import os
import re
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import fake_frappe  # noqa: E402
from fake_frappe import FakeFrappe, FakeAssignTo, UnknownField, _dict  # noqa: E402

USER = "zeke@tierneymorris.com.au"
OTHER = "someone.else@tierneymorris.com.au"


def load_api(frappe):
    """Load erplite/projects/api.py with `frappe` replaced by the stand-in.

    The module is loaded straight from its path rather than imported as
    erplite.projects.api, because erplite/__init__.py pulls in parts of Frappe
    that have nothing to do with these queries.
    """
    for name in list(sys.modules):
        if name == "frappe" or name.startswith("frappe."):
            del sys.modules[name]

    assign_to = FakeAssignTo(frappe)

    frappe_pkg = types.ModuleType("frappe")
    frappe_pkg.__path__ = []  # makes it a package, so submodules can be added
    for attr in dir(frappe):
        if not attr.startswith("__"):
            setattr(frappe_pkg, attr, getattr(frappe, attr))
    frappe_pkg._dict = _dict

    desk = types.ModuleType("frappe.desk")
    desk.__path__ = []
    form = types.ModuleType("frappe.desk.form")
    form.__path__ = []
    assign_mod = types.ModuleType("frappe.desk.form.assign_to")
    assign_mod.add = assign_to.add
    assign_mod.remove = assign_to.remove
    form.assign_to = assign_mod
    desk.form = form
    frappe_pkg.desk = desk

    sys.modules["frappe"] = frappe_pkg
    sys.modules["frappe.desk"] = desk
    sys.modules["frappe.desk.form"] = form
    sys.modules["frappe.desk.form.assign_to"] = assign_mod

    import importlib.util
    path = os.path.join(APP_ROOT, "erplite", "projects", "api.py")
    spec = importlib.util.spec_from_file_location("erplite_projects_api_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ActivityQueryTestCase(unittest.TestCase):
    def setUp(self):
        self.frappe = FakeFrappe(session_user=USER, roles=["System Manager"])
        self.frappe.tables["Project"] = [
            _dict(name="5gofgdoomv", project_name="Novalith", status="Open"),
            _dict(name="other01", project_name="Another project", status="Open"),
            # "Archived", not "Cancelled": Project.status has no Cancelled option.
            # This fixture said Cancelled for several sweeps and the test below passed
            # on it, demonstrating an exclusion that cannot happen on the real site.
            _dict(name="dead01", project_name="Shelved", status="Archived"),
        ]
        self.frappe.tables["Activity"] = [
            _dict(name="g68cfomvvu", activity_name="PO-0392 - CCTP Systems Engineering support",
                  description="Novalith PO-0392", project="5gofgdoomv", status="Open",
                  _assign='["%s"]' % USER),
            _dict(name="act_unassigned", activity_name="Nobody's activity",
                  description="", project="5gofgdoomv", status="Open", _assign=None),
            _dict(name="act_other_proj", activity_name="Activity on another project",
                  description="", project="other01", status="Open", _assign='["%s"]' % USER),
            _dict(name="act_other_user", activity_name="Someone else's activity",
                  description="", project="other01", status="Open", _assign='["%s"]' % OTHER),
        ]
        self.frappe.tables["ToDo"] = [
            _dict(name="todo1", reference_type="Activity", reference_name="g68cfomvvu",
                  allocated_to=USER, status="Open"),
            _dict(name="todo2", reference_type="Activity", reference_name="act_other_proj",
                  allocated_to=USER, status="Open"),
            _dict(name="todo3", reference_type="Activity", reference_name="act_other_user",
                  allocated_to=OTHER, status="Open"),
        ]
        self.api = load_api(self.frappe)


class TestGetProjectsAndActivities(ActivityQueryTestCase):
    def test_lists_only_the_activities_assigned_to_the_user(self):
        result = self.api.get_projects_and_activities()

        self.assertEqual(
            ["g68cfomvvu"],
            [a["name"] for a in result["5gofgdoomv"]["activities"]],
            "the unassigned activity in the same project should not be listed",
        )
        self.assertEqual(
            ["act_other_proj"],
            [a["name"] for a in result["other01"]["activities"]],
            "another user's activity should not be listed",
        )

    def test_returns_the_real_title_field(self):
        result = self.api.get_projects_and_activities()
        activity = result["5gofgdoomv"]["activities"][0]

        self.assertEqual("PO-0392 - CCTP Systems Engineering support", activity["activity_name"])
        self.assertIsNotNone(activity["activity_name"])

    def test_keeps_a_subject_alias_for_older_front_end_code(self):
        # SchedulerTable.vue, useSchedulerData.js and the scheduler_obs
        # DropdownManager still read activity.subject; DropdownManager calls
        # .toLowerCase() on it with no guard, so null is not a safe value.
        result = self.api.get_projects_and_activities()
        activity = result["5gofgdoomv"]["activities"][0]

        self.assertEqual(activity["activity_name"], activity["subject"])

    def test_cancelled_and_closed_assignments_are_ignored(self):
        # _assign is maintained from ToDos that are neither Cancelled nor
        # Closed, so this query has to use the same rule or the two disagree.
        for status in ("Cancelled", "Closed"):
            self.frappe.tables["ToDo"][0]["status"] = status
            result = self.api.get_projects_and_activities()
            self.assertEqual(
                [], result["5gofgdoomv"]["activities"],
                "a %s assignment should not appear" % status,
            )

    def test_projects_with_no_assigned_activities_are_still_listed_but_empty(self):
        self.frappe.tables["ToDo"] = []
        result = self.api.get_projects_and_activities()

        self.assertIn("5gofgdoomv", result)
        self.assertEqual([], result["5gofgdoomv"]["activities"])

    def test_archived_projects_are_excluded(self):
        """Archived is the only status Project has that means "do not show this".

        The filter used to read `["!=", "Cancelled"]`, which Project.status cannot be,
        so it excluded nothing and archived projects were listed.

        The positive half of this assertion is not decoration. An earlier version
        asserted only `assertNotIn("dead01", ...)`, and fault injection showed it
        passing with the filter reverted: `get_projects_and_activities` wraps its
        body in `except Exception` and returns `{"success": False, ...}`, in which
        "dead01" is also absent. **A test that asserts only an absence is satisfied
        by the endpoint failing outright.** Naming the projects that must be there
        is what makes the absence mean anything.
        """
        result = self.api.get_projects_and_activities()
        self.assertIn("5gofgdoomv", result)
        self.assertIn("other01", result)
        self.assertNotIn("dead01", result)

    def test_admin_can_view_another_users_activities(self):
        result = self.api.get_projects_and_activities(target_user=OTHER)
        self.assertEqual(
            ["act_other_user"],
            [a["name"] for a in result["other01"]["activities"]],
        )

    def test_a_non_admin_cannot_view_another_users_activities(self):
        self.frappe._roles = []
        self.api = load_api(self.frappe)
        result = self.api.get_projects_and_activities(target_user=OTHER)

        self.assertEqual(
            ["act_other_proj"],
            [a["name"] for a in result["other01"]["activities"]],
            "target_user should be ignored for a non-admin, who sees their own",
        )

    def test_it_queries_todo_rather_than_an_assigned_to_column(self):
        self.api.get_projects_and_activities()
        queried = {q.doctype for q in self.frappe.queries}

        self.assertIn("ToDo", queried)
        for query in self.frappe.queries:
            self.assertNotIn("assigned_to", query.filters)

    def test_no_error_was_swallowed(self):
        # get_projects_and_activities wraps everything in `except Exception`
        # and returns {}, so a silent failure looks like an empty calendar.
        result = self.api.get_projects_and_activities()
        self.assertEqual([], self.frappe.errors, "an exception was caught and logged")
        self.assertNotEqual({}, result)


class TestGetAllProjectsAndActivities(ActivityQueryTestCase):
    def test_returns_activities_with_their_real_titles(self):
        response = self.api.get_all_projects_and_activities()
        self.assertTrue(response["success"])

        activities = response["data"]["5gofgdoomv"]["activities"]
        titles = {a["name"]: a["activity_name"] for a in activities}
        self.assertEqual(
            "PO-0392 - CCTP Systems Engineering support", titles["g68cfomvvu"]
        )
        self.assertNotIn(None, titles.values(), "the dialog showed blank labels before")

    def test_reports_who_each_activity_is_assigned_to(self):
        response = self.api.get_all_projects_and_activities()
        activities = {
            a["name"]: a
            for project in response["data"].values()
            for a in project["activities"]
        }

        self.assertEqual([USER], activities["g68cfomvvu"]["assigned_users"])
        self.assertEqual(USER, activities["g68cfomvvu"]["assigned_to"])
        self.assertEqual([], activities["act_unassigned"]["assigned_users"])
        self.assertIsNone(activities["act_unassigned"]["assigned_to"])
        self.assertEqual([OTHER], activities["act_other_user"]["assigned_users"])

    def test_reports_every_assignee_when_there_is_more_than_one(self):
        self.frappe.tables["ToDo"].append(_dict(
            name="todo4", reference_type="Activity", reference_name="g68cfomvvu",
            allocated_to=OTHER, status="Open",
        ))
        response = self.api.get_all_projects_and_activities()
        activity = next(
            a for a in response["data"]["5gofgdoomv"]["activities"]
            if a["name"] == "g68cfomvvu"
        )

        self.assertEqual({USER, OTHER}, set(activity["assigned_users"]))
        self.assertIn(activity["assigned_to"], (USER, OTHER))

    def test_access_is_denied_to_a_non_admin(self):
        self.frappe._roles = []
        self.api = load_api(self.frappe)
        response = self.api.get_all_projects_and_activities()

        self.assertFalse(response["success"])
        self.assertEqual("Access denied", response["message"])

    def test_no_error_was_swallowed(self):
        self.api.get_all_projects_and_activities()
        self.assertEqual([], self.frappe.errors)


class TestAssignActivitiesToUser(ActivityQueryTestCase):
    def test_assigning_goes_through_frappes_standard_mechanism(self):
        response = self.api.assign_activities_to_user(
            OTHER, [{"activity_id": "act_unassigned", "assign": True}]
        )

        self.assertTrue(response["success"])
        self.assertEqual(
            [{"doctype": "Activity", "name": "act_unassigned", "assign_to": [OTHER]}],
            self.frappe.assignments_added,
        )

    def test_it_no_longer_writes_to_the_orphaned_column(self):
        # The old code did `activity_doc.assigned_to = user; activity_doc.save()`,
        # which reported success and persisted nothing, because assigned_to is
        # not a field on the DocType any more.
        self.api.assign_activities_to_user(
            OTHER, [{"activity_id": "act_unassigned", "assign": True}]
        )

        for doctype, name, fieldname, value in self.frappe.values_set:
            self.assertNotEqual("assigned_to", fieldname)

    def test_the_assignment_is_actually_persisted(self):
        self.api.assign_activities_to_user(
            OTHER, [{"activity_id": "act_unassigned", "assign": True}]
        )
        todos = [
            t for t in self.frappe.tables["ToDo"]
            if t["reference_name"] == "act_unassigned" and t["status"] == "Open"
        ]

        self.assertEqual(1, len(todos))
        self.assertEqual(OTHER, todos[0]["allocated_to"])

    def test_unassigning_cancels_the_todo(self):
        response = self.api.assign_activities_to_user(
            USER, [{"activity_id": "g68cfomvvu", "assign": False}]
        )

        self.assertTrue(response["success"])
        self.assertEqual([("Activity", "g68cfomvvu", USER)], self.frappe.assignments_removed)
        self.assertEqual("Cancelled", self.frappe.tables["ToDo"][0]["status"])

    def test_assigning_twice_does_not_raise(self):
        # add() reports a duplicate rather than raising, so the admin dialog
        # can be saved twice without an error.
        for _unused in range(2):
            response = self.api.assign_activities_to_user(
                USER, [{"activity_id": "g68cfomvvu", "assign": True}]
            )
            self.assertTrue(response["success"])

    def test_accepts_a_json_string_as_the_front_end_sends_it(self):
        response = self.api.assign_activities_to_user(
            OTHER, '[{"activity_id": "act_unassigned", "assign": true}]'
        )

        self.assertTrue(response["success"])
        self.assertEqual(1, len(self.frappe.assignments_added))

    def test_an_unknown_activity_is_skipped_rather_than_raising(self):
        response = self.api.assign_activities_to_user(
            OTHER, [
                {"activity_id": "no_such_activity", "assign": True},
                {"activity_id": "act_unassigned", "assign": True},
            ]
        )

        self.assertTrue(response["success"])
        self.assertEqual(1, len(self.frappe.assignments_added))
        self.assertIn("1", response["message"])

    def test_a_blank_activity_id_is_skipped(self):
        response = self.api.assign_activities_to_user(
            OTHER, [{"activity_id": None, "assign": True}]
        )

        self.assertTrue(response["success"])
        self.assertEqual([], self.frappe.assignments_added)

    def test_access_is_denied_to_a_non_admin(self):
        self.frappe._roles = []
        self.api = load_api(self.frappe)
        response = self.api.assign_activities_to_user(
            OTHER, [{"activity_id": "act_unassigned", "assign": True}]
        )

        self.assertFalse(response["success"])
        self.assertEqual([], self.frappe.assignments_added)


class TestTheOrphanedColumnsAreReallyGone(unittest.TestCase):
    """Guards the premise of the fix, so it cannot rot silently."""

    def test_the_activity_doctype_has_no_subject_or_assigned_to_field(self):
        fields = fake_frappe.doctype_fields("projects", "activity")

        self.assertIn("activity_name", fields)
        self.assertNotIn("subject", fields)
        self.assertNotIn("assigned_to", fields)

    def test_activity_name_is_the_title_field(self):
        import json
        path = os.path.join(
            APP_ROOT, "erplite", "projects", "doctype", "activity", "activity.json"
        )
        with open(path, "rb") as handle:
            definition = json.loads(handle.read().decode("utf-8"))

        self.assertEqual("activity_name", definition.get("title_field"))

    def test_the_scheduler_no_longer_reads_subject_through_get_value(self):
        # Two call sites in erplite/scheduler/api.py did
        #   entry['activity_name'] = frappe.db.get_value(
        #       "Activity", entry.activity, "subject")
        # which assigned None into a key already named activity_name.
        path = os.path.join(APP_ROOT, "erplite", "scheduler", "api.py")
        with open(path, "rb") as handle:
            source = handle.read().decode("utf-8")

        offenders = re.findall(
            r'get_value\(\s*["\']Activity["\'].*?["\']subject["\']', source, re.DOTALL
        )
        self.assertEqual([], offenders, "a get_value on Activity.subject is back")

    def test_the_fake_would_have_caught_the_old_query(self):
        # Proves these tests can actually fail: the pre-fix query raises here,
        # where real Frappe would have returned a row with subject = None.
        frappe = FakeFrappe()
        frappe.tables["Activity"] = [_dict(name="a1", activity_name="x", project="p1")]

        with self.assertRaises(UnknownField):
            frappe.get_all("Activity", fields=["name", "subject", "description"],
                           filters={"project": "p1"})

        with self.assertRaises(UnknownField):
            frappe.get_all("Activity", fields=["name"],
                           filters={"assigned_to": USER})


if __name__ == "__main__":
    unittest.main(verbosity=2)
