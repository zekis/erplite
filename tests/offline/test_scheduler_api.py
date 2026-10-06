# -*- coding: utf-8 -*-
"""Tests for the project/activity query behind the scheduler.

Background. `erplite.scheduler.api.get_projects_and_activities` built raw SQL
against `tabProject` and `tabActivity` selecting six columns that are no longer
fields on either DocType:

    Project   project_manager, work_type
    Activity  subject, priority, estimated_hours, progress_percent

Which DocType each column belonged to matters, and this file used to ignore
it: `work_type` went from Project and stayed on Activity, so a flat list of
all six reported a correct Activity query as an orphaned column. See ORPHANED.

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

from fake_frappe import FakeFrappe, _dict, doctype_fields  # noqa: E402

USER = "pat@company.test"

# The columns removed from each DocType, which must not be queried again.
#
# Keyed by DocType on purpose. This was a flat tuple checked against every
# query, and `work_type` was removed from Project but is a live field on
# Activity (activity.json, in_standard_filter, since 8126278) -- so asking
# Activity for its own `work_type` was reported as "an orphaned column, not a
# field". A guard that fails on correct code gets deleted rather than fixed,
# which is worse than the miss it was protecting against. The fault-injection
# control that found it is in tests/faultinject/faults.py.
#
# Narrowing this loses no cover: a query naming a column that is not a field
# on the DocType it asks -- Activity for project_manager, say -- is refused by
# the stand-in itself (FakeFrappe._check_fields), which is the backstop for
# every field name, not just these six. This list adds what the stand-in
# cannot know: that these particular names were once real and are the specific
# regression being guarded. TestTheOrphanedListItself below checks the claim
# against the JSONs rather than trusting it.
ORPHANED = {
    "Project": ("project_manager", "work_type"),
    "Activity": ("subject", "priority", "estimated_hours", "progress_percent"),
}

# Flattened, for the one claim that is about all six regardless of DocType.
ALL_ORPHANED = tuple(sorted(set(sum((list(v) for v in ORPHANED.values()), []))))


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
            # The id deliberately sorts AFTER g68cfomvvu while its title sorts
            # before it, so sorting by `name` and sorting by `activity_name`
            # give different answers. With an "act_" id they agreed, and
            # test_activities_are_ordered_by_the_field_that_still_exists passed
            # just as well with order_by="name" -- it was pinning that the
            # query is ordered at all, not which field it is ordered by.
            _dict(name="z_aardvark", project="5gofgdoomv", status="Open",
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
        """No query asks a DocType for a column that DocType no longer has.

        Per DocType, not across all of them: see ORPHANED above.

        The stand-in's own field check is switched off for this one call, and
        that is the only reason this test can fail. FakeFrappe.get_all records
        the query and then validates its field names, raising UnknownField
        before the call returns -- so with the check in place, execution never
        reached the loop below and the red came entirely from the stand-in.
        Measured rather than reasoned, 7 Oct 2026: with everything below the
        loop deleted, all 28 faults in the `scheduler_api` fault-injection
        target still behaved exactly as expected. This test had never been
        able to fail, in the file whose subject it is.

        What that buys, and what it does not. It does NOT add cover: the
        stand-in's check is still on in every other test in this class, so an
        orphan goes red there whatever this test does. Measured after the fix
        as well as before -- neutering this test again still gave 28 of 28.
        No fault in the target is caught uniquely here, and nothing in this
        file should claim otherwise.

        What it buys is that the assertion stating the claim is the thing that
        judges it. The failure now reads "subject is an orphaned column on
        Activity, not a field" rather than "Activity has no field 'subject'",
        which is the difference between being told a regression came back and
        being told a field name is wrong. And the claim stays testable if the
        stand-in's validation is ever relaxed, which is the only way the
        backstop could quietly stop covering it.
        """
        self.frappe._check_fields = lambda *args, **kwargs: None
        self.api.get_projects_and_activities()

        for query in self.frappe.queries:
            orphaned = ORPHANED.get(query.doctype, ())
            for field in query.fields:
                self.assertNotIn(
                    field, orphaned,
                    "%s is an orphaned column on %s, not a field"
                    % (field, query.doctype),
                )
            for field in query.filters:
                self.assertNotIn(field, orphaned)
            self.assertNotIn(query.order_by, orphaned)

    def test_activities_are_ordered_by_the_field_that_still_exists(self):
        # The old query ordered by t.subject, which nothing maintains, so the
        # order the scheduler showed was whatever was in the orphaned column.
        #
        # The two ids sort the opposite way to their titles (see setUp), so this
        # is an assertion about activity_name and not merely about there being
        # an order_by at all.
        activities = self.projects_by_name()["5gofgdoomv"]["activities"]

        self.assertEqual(
            ["z_aardvark", "g68cfomvvu"], [a["name"] for a in activities]
        )
        self.assertNotEqual(
            sorted(a["name"] for a in activities),
            [a["name"] for a in activities],
            "the fixture no longer distinguishes name order from title order, "
            "so this test has stopped testing which field is ordered on",
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


class TestTheOrphanedListItself(unittest.TestCase):
    """ORPHANED is a claim about the DocType JSONs. Check it, do not trust it.

    The defect this guards is not "a column crept back into a query" -- it is
    "the list of columns is wrong", which makes every test above either blind
    or wrong about correct code, and says nothing when it happens. The flat
    version of this list spent its whole life calling a live Activity field an
    orphan, and passed throughout.
    """

    DOCTYPE_JSON = {"Project": ("projects", "project"),
                    "Activity": ("projects", "activity")}

    def test_every_orphaned_column_is_absent_from_its_own_doctype(self):
        for doctype, columns in ORPHANED.items():
            fields = doctype_fields(*self.DOCTYPE_JSON[doctype])
            for column in columns:
                self.assertNotIn(
                    column, fields,
                    "%s is listed as removed from %s but is a field on it today, "
                    "so every query for it is being called a regression"
                    % (column, doctype),
                )

    def test_each_orphaned_column_is_listed_against_one_doctype_only(self):
        """Two entries for one name is how the flat list went wrong."""
        seen = {}
        for doctype, columns in ORPHANED.items():
            for column in columns:
                self.assertNotIn(
                    column, seen,
                    "%s is listed against both %s and %s"
                    % (column, seen.get(column), doctype),
                )
                seen[column] = doctype
        self.assertEqual(len(ALL_ORPHANED), 6)

    def test_work_type_is_still_a_live_field_on_activity(self):
        """The specific false positive, named, so it cannot come back quietly.

        work_type was removed from Project by 8126278 and kept on Activity. If
        it is ever removed from Activity as well, this fails and it belongs in
        ORPHANED["Activity"] -- which is the point: that is a decision somebody
        makes, not a tuple that drifts.
        """
        self.assertIn("work_type", doctype_fields("projects", "activity"))
        self.assertNotIn("work_type", doctype_fields("projects", "project"))


if __name__ == "__main__":
    unittest.main()
