# -*- coding: utf-8 -*-
"""`save_timesheet_entries(entries, target_user)`: whose hours get booked.

The endpoint took a `target_user` and gated it on its own role list:

    if target_user and is_timesheet_admin():   # System Manager or Timesheet Admin
        employee_user = target_user
    else:
        employee_user = frappe.session.user

`is_timesheet_admin()` is narrower than Timesheet Entry's own write
permission, which the shipped DocType rows also grant to Projects Manager.
So a Projects Manager who sent `target_user` had it **silently discarded**:
the hours were booked against themselves, and the endpoint returned
`{"success": True, "message": "Timesheet entries saved successfully"}` with
the saved entries listed. Nothing in the response carries `employee`, so a
caller could not tell whose timesheet it had just written.

The fix passes `target_user` through and lets the controller decide, which is
the one rule owner decision rev_84dce415b5 put there: on insert, an
`employee` other than the session user needs write on Timesheet Entry.
A caller who does not hold it now gets a refusal instead of a wrong booking.

## Severity, stated honestly

**Nothing on the live bench calls this endpoint.** Checked by grepping every
app on the site, including the live apps/afterz working tree, for
`save_timesheet_entries`: the only hit is its own `def`. Afterz's calendar
does not use it. So no hours are being misbooked today, and this is hardening
an endpoint that any logged-in user can still reach by name, because
`@frappe.whitelist()` is what makes a method callable -- not a button.

## Why the refusal lands in the controller and not before it

frappe's `insert()` (frappe 15.52.0, as installed on the bench) runs
`check_permission("create")` at document.py:288, **before**
`run_before_save_methods()` at :295 runs `validate`. `if_owner` never
restricts create -- permissions.py:236 sets `permissions["create"] = 0` only
for the User Permissions case and the comment says so outright ("if_owner
does not come with create rights") -- so a Projects User passes :288 and is
stopped by the controller's rule in `validate`, not by frappe. That is the
intended division: frappe answers "may you create one at all", the app
answers "may you put someone else's name on it".

These tests run without a bench. See fake_frappe.py for the stand-in.
"""

import ast
import datetime
import io
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from fake_frappe import (  # noqa: E402
    FakeFrappe,
    FakeUtils,
    ValidationError,
    make_doc,
)
from test_afterz_timesheet_workflow import (  # noqa: E402
    TickingClock,
    load_controller,
)
from test_projects_api import load_api  # noqa: E402

YOU = "zeke@tierneymorris.com.au"
COLLEAGUE = "someone.else@tierneymorris.com.au"

def attach_new_doc(frappe):
    """Give the stand-in a `new_doc` that returns the **real** controller.

    The point of this file is that the endpoint and the controller agree, so a
    stand-in `new_doc` handing back an inert bag of fields would prove nothing.
    This one returns a real TimesheetEntry, loaded by
    test_afterz_timesheet_workflow.load_controller and built by make_doc, with
    an `insert()` that mirrors frappe 15.52.0's order for the three steps that
    decide the outcome here (frappe/model/document.py:284-296):

        set_user_and_timestamp   -> owner = the session user          (:284)
        check_permission(create) -> frappe's own gate                 (:288)
        run_before_save_methods  -> the controller's validate         (:295)

    Nothing else about insert() is modelled and nothing else is asserted. The
    controller is loaded on first call, not here, because it does
    `import frappe` at module level and the stand-in is not in sys.modules
    until load_api or load_controller puts it there.

    `TheStandInIsTrustworthy` below fails if this insert stops calling the
    controller, so the refusal tests cannot pass vacuously.
    """
    state = {}

    def new_doc(doctype, **kwargs):
        if doctype != "Timesheet Entry":
            raise AssertionError("stand-in new_doc only knows Timesheet Entry")
        if "controller" not in state:
            module, _pkg = load_controller(frappe, TickingClock())
            state["controller"] = module.TimesheetEntry
        doc = make_doc(state["controller"], "Timesheet Entry", "projects",
                       "timesheet_entry", dict(kwargs))
        rows = frappe.tables.setdefault("Timesheet Entry", [])

        def insert(**_):
            # set_user_and_timestamp (document.py:284)
            doc.owner = frappe.session.user
            # check_permission("create") (document.py:288)
            if not frappe.has_permission("Timesheet Entry", "create", doc=doc):
                raise ValidationError("No permission to create Timesheet Entry")
            # run_before_save_methods -> validate (document.py:295)
            doc.validate()
            doc.name = "TS-TEST-%04d" % (len(rows) + 1)
            rows.append(doc)
            return doc

        doc.insert = insert
        return doc

    frappe.new_doc = new_doc
    return frappe


def api_for(user, roles):
    frappe = FakeFrappe(session_user=user, roles=roles)
    frappe.tables["Timesheet Entry"] = []
    # The endpoint reaches for frappe.utils.datetime.timedelta, which real
    # frappe has only because frappe/utils/__init__.py imports datetime.
    frappe.utils = FakeUtils()
    frappe.utils.datetime = datetime
    # Attached before load_api, which copies the stand-in's attributes onto
    # the module the endpoint will call.
    attach_new_doc(frappe)
    return frappe, load_api(frappe)


ONE_ENTRY = [{
    "project": "5gofgdoomv",
    "activity": "g68cfomvvu",
    "date": "2026-10-05",
    "start_time": "09:00",
    "duration": 2,
    "description": "CCTP systems engineering",
}]


def booked(frappe):
    """(employee, owner) for every Timesheet Entry the call wrote."""
    return [(d.employee, d.owner) for d in frappe.tables.get("Timesheet Entry", [])]


class TargetUserReachesTheEmployeeField(unittest.TestCase):
    def test_a_projects_manager_books_for_the_colleague_they_named(self):
        """The bug. Projects Manager holds write in the shipped rows."""
        frappe, api = api_for(YOU, ["Projects Manager"])
        result = api.save_timesheet_entries(ONE_ENTRY, target_user=COLLEAGUE)

        self.assertTrue(result["success"], result.get("message"))
        self.assertEqual([(COLLEAGUE, COLLEAGUE)], booked(frappe))

    def test_a_system_manager_still_books_for_the_colleague_they_named(self):
        frappe, api = api_for(YOU, ["System Manager"])
        result = api.save_timesheet_entries(ONE_ENTRY, target_user=COLLEAGUE)

        self.assertTrue(result["success"], result.get("message"))
        self.assertEqual([(COLLEAGUE, COLLEAGUE)], booked(frappe))

    def test_a_timesheet_admin_still_books_for_the_colleague_they_named(self):
        """Timesheet Admin was the other half of the old gate.

        It holds no row on Timesheet Entry of its own, so it reaches the
        controller's rule through System Manager or not at all. Here it is
        paired with Projects Manager, which is how a real timesheet admin on
        this site holds write; the assertion is that the old gate's own roles
        did not lose anything.
        """
        frappe, api = api_for(YOU, ["Timesheet Admin", "Projects Manager"])
        result = api.save_timesheet_entries(ONE_ENTRY, target_user=COLLEAGUE)

        self.assertTrue(result["success"], result.get("message"))
        self.assertEqual([(COLLEAGUE, COLLEAGUE)], booked(frappe))

    def test_no_target_user_books_for_the_caller(self):
        frappe, api = api_for(YOU, ["Projects User"])
        result = api.save_timesheet_entries(ONE_ENTRY)

        self.assertTrue(result["success"], result.get("message"))
        self.assertEqual([(YOU, YOU)], booked(frappe))

    def test_target_user_naming_the_caller_is_not_a_special_case(self):
        frappe, api = api_for(YOU, ["Projects User"])
        result = api.save_timesheet_entries(ONE_ENTRY, target_user=YOU)

        self.assertTrue(result["success"], result.get("message"))
        self.assertEqual([(YOU, YOU)], booked(frappe))


class AnUnauthorisedCallerIsRefusedNotMisbooked(unittest.TestCase):
    """The half that matters most: a refusal must not become a wrong booking."""

    def test_a_projects_user_cannot_book_against_a_colleague(self):
        frappe, api = api_for(YOU, ["Projects User"])
        result = api.save_timesheet_entries(ONE_ENTRY, target_user=COLLEAGUE)

        self.assertFalse(result["success"])
        self.assertEqual([], booked(frappe),
                         "a refused call must write no entry at all")

    def test_and_above_all_not_against_the_caller(self):
        """What the old code did: hours appear on the caller's own timesheet."""
        frappe, api = api_for(YOU, ["Projects User"])
        api.save_timesheet_entries(ONE_ENTRY, target_user=COLLEAGUE)

        self.assertNotIn(YOU, [employee for employee, _ in booked(frappe)])

    def test_the_refusal_says_whose_name_was_refused(self):
        frappe, api = api_for(YOU, ["Projects User"])
        result = api.save_timesheet_entries(ONE_ENTRY, target_user=COLLEAGUE)

        self.assertIn("own name", result["message"])

    def test_a_refused_batch_leaves_nothing_behind(self):
        """Every entry in a batch shares one employee, so the first one stops it.

        Worth pinning: the endpoint commits inside `try` and swallows the
        exception, so a failure part-way through a batch would otherwise be
        invisible. For this rule it cannot happen -- employee_user is decided
        once, before the loop.
        """
        frappe, api = api_for(YOU, ["Projects User"])
        batch = [dict(ONE_ENTRY[0]) for _ in range(3)]
        result = api.save_timesheet_entries(batch, target_user=COLLEAGUE)

        self.assertFalse(result["success"])
        self.assertEqual([], booked(frappe))


class TheEndpointDoesNotRestateTheRule(unittest.TestCase):
    def test_save_timesheet_entries_does_not_consult_a_role_list(self):
        """An AST assertion, because a comment cannot be relied on.

        `is_timesheet_admin()` is still the right gate for the two read
        endpoints in this module, which choose whose data to *show*. It is the
        wrong gate for deciding whose name goes on a row, and this test fails
        if it comes back.
        """
        path = os.path.join(APP_ROOT, "erplite", "projects", "api.py")
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        function = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "save_timesheet_entries")

        called = {
            node.func.id for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

        self.assertNotIn("is_timesheet_admin", called)
        self.assertNotIn("get_roles", called)

    def test_the_read_endpoints_still_do_consult_it(self):
        """The counterweight: this change is not a sweep of the whole module."""
        path = os.path.join(APP_ROOT, "erplite", "projects", "api.py")
        tree = ast.parse(io.open(path, encoding="utf-8").read())

        for name in ("get_projects_and_activities", "get_week_timesheets"):
            function = next(
                node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == name)
            called = {
                node.func.id for node in ast.walk(function)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
            self.assertIn("is_timesheet_admin", called, name)


class TheStandInIsTrustworthy(unittest.TestCase):
    """Self-tests. A refusal test is only worth what its stand-in is worth."""

    def test_the_stand_in_really_runs_validate(self):
        frappe, api = api_for(YOU, ["System Manager"])
        doc = frappe.new_doc("Timesheet Entry")
        doc.employee = COLLEAGUE
        doc.check_in_time = datetime.datetime(2026, 10, 5, 9, 0)
        doc.check_out_time = datetime.datetime(2026, 10, 5, 11, 0)

        seen = []
        real_validate = doc.validate
        doc.validate = lambda: (seen.append(True), real_validate())[1]
        doc.insert()

        self.assertEqual([True], seen, "insert() must call the controller")

    def test_the_stand_in_refuses_an_unauthorised_employee_directly(self):
        """Without going through the endpoint at all."""
        frappe, api = api_for(YOU, ["Projects User"])
        doc = frappe.new_doc("Timesheet Entry")
        doc.employee = COLLEAGUE
        doc.check_in_time = datetime.datetime(2026, 10, 5, 9, 0)
        doc.check_out_time = datetime.datetime(2026, 10, 5, 11, 0)

        with self.assertRaises(ValidationError):
            doc.insert()

    def test_the_stand_in_allows_your_own_name(self):
        frappe, api = api_for(YOU, ["Projects User"])
        doc = frappe.new_doc("Timesheet Entry")
        doc.employee = YOU
        doc.check_in_time = datetime.datetime(2026, 10, 5, 9, 0)
        doc.check_out_time = datetime.datetime(2026, 10, 5, 11, 0)
        doc.insert()

        self.assertEqual([(YOU, YOU)], booked(frappe))


if __name__ == "__main__":
    unittest.main()
