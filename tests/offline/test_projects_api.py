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
            # Assigned to USER, on the archived project. Without this row no
            # fixture activity sat on an excluded project, so the calendar's
            # `"project": ["in", list(result)]` filter could be deleted with
            # all 28 tests green -- and live that is a KeyError into the
            # endpoint's own `except Exception`, i.e. a silently empty
            # calendar. A fixture that cannot reach a guard cannot test it.
            _dict(name="act_on_archived", activity_name="Activity on a shelved project",
                  description="", project="dead01", status="Open",
                  _assign='["%s"]' % USER),
        ]
        # Three of these exist to reach the admin dialog's filters, which had
        # no fixture able to fail them: the dialog reads every activity on
        # every live project, so a ToDo that must be ignored has to be ignored
        # *there* as well as on the calendar.
        self.frappe.tables["ToDo"] = [
            _dict(name="todo1", reference_type="Activity", reference_name="g68cfomvvu",
                  allocated_to=USER, status="Open"),
            _dict(name="todo2", reference_type="Activity", reference_name="act_other_proj",
                  allocated_to=USER, status="Open"),
            _dict(name="todo3", reference_type="Activity", reference_name="act_other_user",
                  allocated_to=OTHER, status="Open"),
            _dict(name="todo_archived", reference_type="Activity", reference_name="act_on_archived",
                  allocated_to=USER, status="Open"),
            # Cancelled: _assign does not list it, so neither endpoint may.
            _dict(name="todo_cancelled", reference_type="Activity",
                  reference_name="act_unassigned", allocated_to=OTHER, status="Cancelled"),
            # A ToDo with no assignee at all. Counting it makes `None` an
            # assignee, which the dialog then renders as a user.
            _dict(name="todo_unallocated", reference_type="Activity",
                  reference_name="act_unassigned", allocated_to=None, status="Open"),
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

    def test_an_activity_on_an_archived_project_is_not_returned(self):
        """The calendar confines activities to the projects it listed.

        `act_on_archived` is assigned to USER and sits on the archived project,
        so the ToDo query finds it and only the
        `"project": ["in", list(result)]` filter keeps it out. Delete that
        filter and `result[activity.project]` is a KeyError on a project that
        was never put in the dict -- which the endpoint's own
        `except Exception` turns into an empty `{}`, i.e. a calendar with
        nothing in it and no error anywhere a user can see.

        The positive assertions are what make this bite: with the filter gone
        the endpoint returns `{}`, in which "dead01" is also absent.
        """
        result = self.api.get_projects_and_activities()

        self.assertIn("5gofgdoomv", result, "the endpoint did not complete")
        self.assertIn("other01", result)
        self.assertNotIn("dead01", result)
        self.assertEqual([], self.frappe.errors, "an exception was caught and logged")

        listed = {a["name"] for entry in result.values() for a in entry["activities"]}
        self.assertNotIn("act_on_archived", listed)
        self.assertIn("g68cfomvvu", listed, "the assigned activities are still listed")

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

    def test_archived_projects_are_excluded(self):
        """The same rule as the calendar's, on the endpoint that never asserted it.

        Both endpoints filter Project by `["!=", "Archived"]`. Only the
        calendar was ever asked about it, so the dialog's copy could be
        deleted with every test green. As above, the positive assertions
        matter: this endpoint returns {"success": False, ...} on an
        exception, and "dead01" is absent from that too.
        """
        response = self.api.get_all_projects_and_activities()

        self.assertTrue(response["success"], response.get("message"))
        self.assertIn("5gofgdoomv", response["data"])
        self.assertIn("other01", response["data"])
        self.assertNotIn("dead01", response["data"])

    def test_cancelled_and_closed_assignments_are_not_reported_as_current(self):
        # _assign is maintained from ToDos that are neither Cancelled nor
        # Closed. The dialog shows who is assigned, so it has to agree with
        # _assign or the admin is shown an assignee the document does not have.
        for status in ("Cancelled", "Closed"):
            self.frappe.tables["ToDo"][4]["status"] = status
            activities = self._activities_by_name()

            self.assertEqual(
                [], activities["act_unassigned"]["assigned_users"],
                "a %s ToDo was reported as a current assignee" % status,
            )
            self.assertIsNone(activities["act_unassigned"]["assigned_to"])

    def test_an_unallocated_todo_is_not_reported_as_an_assignee(self):
        # todo_unallocated is Open but has allocated_to unset. Counting it puts
        # None in assigned_users and makes assigned_to None-but-assigned, which
        # the dialog renders as a user who does not exist.
        activities = self._activities_by_name()

        self.assertEqual([], activities["act_unassigned"]["assigned_users"])
        self.assertNotIn(None, activities["act_unassigned"]["assigned_users"])

    def test_keeps_a_subject_alias_for_older_front_end_code(self):
        # Same reason as the calendar's alias test: the assignment dialog's
        # older code reads activity.subject. Asserted on the calendar only,
        # so the dialog's copy of the alias was free to be dropped.
        activities = self._activities_by_name()
        activity = activities["g68cfomvvu"]

        self.assertEqual(activity["activity_name"], activity["subject"])
        self.assertIsNotNone(activity["subject"])

    def _activities_by_name(self):
        response = self.api.get_all_projects_and_activities()
        self.assertTrue(response["success"], response.get("message"))
        return {
            a["name"]: a
            for project in response["data"].values()
            for a in project["activities"]
        }

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
        # Named by assignee, not just by activity. Counting every open ToDo on
        # the activity counted the unallocated fixture row too, which is not
        # what this test is about: the claim is that OTHER ends up with exactly
        # one open ToDo for it.
        todos = [
            t for t in self.frappe.tables["ToDo"]
            if t["reference_name"] == "act_unassigned"
            and t["status"] == "Open"
            and t["allocated_to"] == OTHER
        ]

        self.assertEqual(1, len(todos))

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
        """A blank id assigns nothing and does not raise, however it is blank.

        `assign_activities_to_user` rejects a blank id twice over: explicitly
        with `if not activity_id: continue`, and again because
        `frappe.db.exists` does not match one. Deleting the explicit guard
        leaves this test green, and that is correct rather than a gap -- see
        the CONTROL in tests/faultinject/faults.py. So this asserts the
        behaviour (nothing is assigned, nothing raises) and deliberately not
        which of the two rejections did it.

        Both blank forms are covered because they take different paths through
        frappe: `None` is read as a Single DocType and never reaches the
        Activity table at all, while `""` becomes a real `WHERE name = ''`.
        """
        for blank in (None, ""):
            with self.subTest(blank=blank):
                self.frappe.assignments_added = []
                response = self.api.assign_activities_to_user(
                    OTHER, [{"activity_id": blank, "assign": True}]
                )

                self.assertTrue(response["success"], response.get("message"))
                self.assertEqual([], self.frappe.assignments_added)
                self.assertEqual([], self.frappe.assignments_removed)

    def test_omitting_assign_leaves_the_activity_alone_rather_than_assigning(self):
        # `assignment.get('assign', False)` -- the default is the only thing
        # making an omitted key safe, and every other test supplies the key, so
        # the default could be flipped to True unnoticed. A default is only
        # tested by a caller that omits it.
        response = self.api.assign_activities_to_user(
            OTHER, [{"activity_id": "act_unassigned"}]
        )

        self.assertTrue(response["success"], response.get("message"))
        self.assertEqual(
            [], self.frappe.assignments_added,
            "an omitted 'assign' key assigned the activity",
        )
        self.assertEqual(
            [("Activity", "act_unassigned", OTHER)], self.frappe.assignments_removed
        )

    def test_unassignments_are_counted_in_the_reported_total(self):
        # The count is what the dialog shows the admin. Counting only
        # assignments reports "updated 0" for a save that really did unassign
        # two activities, which reads as a save that silently did nothing.
        response = self.api.assign_activities_to_user(
            USER, [
                {"activity_id": "g68cfomvvu", "assign": False},
                {"activity_id": "act_other_proj", "assign": False},
            ]
        )

        self.assertTrue(response["success"], response.get("message"))
        self.assertEqual(2, len(self.frappe.assignments_removed))
        self.assertIn("2", response["message"])

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
