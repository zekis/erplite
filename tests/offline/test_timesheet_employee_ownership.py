# -*- coding: utf-8 -*-
"""Who may book time against whose name, and who may correct it afterwards.

Owner's decision rev_84dce415b5. Two different fields answered "whose timesheet
is this" and nothing kept them in agreement:

  * **frappe decides who may read and write from `owner`**, the standard column
    it sets to the creating user (`set_user_and_timestamp`,
    frappe/model/document.py:555-566). The Projects User row on Timesheet Entry
    carries `if_owner`, so for that role both rights stop at the rows that user
    created (`get_role_permissions`, frappe/permissions.py:288-305);
  * **the app decides whose hours they are from `employee`**, a required
    editable Link to User, which `get_week_timesheets`, `export_timesheet_data`
    and the dashboard widgets all filter on through `frappe.get_all` -- which
    ignores permissions by design.

So it went wrong in both directions, and the fix is one rule on insert:
`employee` other than the session user needs write on the DocType, and when it
is allowed `owner` becomes that employee. After it, the two fields name the
same person.

## What is NOT asserted here

That the rule reaches a save. It must not. Acting on someone else's entry is
the whole of the approval workflow: Afterz's `submit_week_entries`,
`approve_all_entries`, `reject_entry_with_reason` and `unapprove_entry` each
`save()` an entry whose `employee` is someone else, and so do erplite's own
`approve_timesheet` and `reject_timesheet`. Those six paths are driven
end-to-end in test_afterz_timesheet_workflow.py; this file pins the structural
reason they are safe -- `TestTheRuleCannotReachASave` fails if the `is_new()`
guard is dropped or the rule is moved to a hook that runs on every save.

The two addresses below stand for "you" and "a second person". Neither is a
claim about who works here; `approver@company.test` is used the same way
in test_afterz_timesheet_workflow.py.

These tests run without a bench. See fake_frappe.py for the stand-in.
"""

import ast
import datetime
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from fake_frappe import (  # noqa: E402
    FakeFrappe,
    ValidationError,
    doctype_permissions,
    make_doc,
)
from test_afterz_timesheet_workflow import (  # noqa: E402
    DAY_IN,
    DAY_OUT,
    TickingClock,
    load_controller,
)

CONTROLLER = os.path.join(
    APP_ROOT, "erplite", "projects", "doctype", "timesheet_entry", "timesheet_entry.py")
API = os.path.join(APP_ROOT, "erplite", "projects", "api.py")

YOU = "pat@company.test"
COLLEAGUE = "approver@company.test"


def controller_source():
    with open(CONTROLLER, "rb") as handle:
        return handle.read().decode("utf-8")


def controller_function(name):
    """The AST of one method of TimesheetEntry, by name."""
    tree = ast.parse(controller_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(
        "TimesheetEntry has no %s(). The rule rev_84dce415b5 decided lives "
        "there; if it was renamed, this file needs to follow it rather than "
        "stop checking." % (name,))


class GateTestCase(unittest.TestCase):
    """Drives the real controller's validate() over the stand-in."""

    def frappe_for(self, user, roles):
        frappe = FakeFrappe(session_user=user, roles=roles)
        frappe.tables["Timesheet Entry"] = []
        return frappe

    def entry(self, frappe, employee, is_new=True):
        module, _pkg = load_controller(frappe, TickingClock())
        doc = make_doc(module.TimesheetEntry, "Timesheet Entry",
                       "projects", "timesheet_entry",
                       {"employee": employee,
                        "project": "5gofgdoomv",
                        "activity": "g68cfomvvu",
                        "check_in_time": DAY_IN,
                        "check_out_time": DAY_OUT,
                        "status": "Draft"},
                       is_new=is_new)
        # What frappe has already done by the time validate() runs: owner is the
        # session user, set in set_user_and_timestamp (document.py:555-566),
        # before check_permission("create") and before any hook.
        doc.owner = frappe.session.user
        return doc


class TestWhoMayBookTimeForWhom(GateTestCase):

    def test_booking_your_own_time_is_unchanged(self):
        frappe = self.frappe_for(YOU, ["Projects User"])
        doc = self.entry(frappe, YOU)
        doc.validate()
        self.assertEqual(doc.employee, YOU)
        self.assertEqual(doc.owner, YOU)

    def test_a_blank_employee_still_defaults_to_you(self):
        """set_employee_default runs first, so the gate never sees a blank."""
        frappe = self.frappe_for(YOU, ["Projects User"])
        doc = self.entry(frappe, None)
        doc.validate()
        self.assertEqual(doc.employee, YOU)
        self.assertEqual(doc.owner, YOU)

    def test_a_projects_user_cannot_book_against_a_colleague(self):
        """The direction that needed no admin at all.

        `create` is the one right `if_owner` never restricts
        (permissions.py:303-305), so before this any Projects User could insert
        an entry naming someone else, and the hours counted as theirs in every
        view -- all of which filter on `employee`.
        """
        frappe = self.frappe_for(YOU, ["Projects User"])
        doc = self.entry(frappe, COLLEAGUE)
        with self.assertRaises(ValidationError) as caught:
            doc.validate()
        self.assertIn("own name", str(caught.exception))

    def test_a_system_manager_may_book_for_a_colleague(self):
        frappe = self.frappe_for(YOU, ["System Manager"])
        doc = self.entry(frappe, COLLEAGUE)
        doc.validate()
        self.assertEqual(doc.employee, COLLEAGUE)

    def test_a_projects_manager_may_book_for_a_colleague(self):
        """Projects Manager holds write outright in the shipped rows.

        Worth stating because erplite's own `save_timesheet_entries` used to
        disagree: its `target_user` gate was `is_timesheet_admin()` -- System
        Manager or Timesheet Admin -- so a Projects Manager's `target_user`
        was silently discarded there and the hours were booked against
        themselves. That endpoint now defers to this rule instead of
        restating a narrower one; see test_timesheet_target_user.py.
        """
        frappe = self.frappe_for(YOU, ["Projects Manager"])
        doc = self.entry(frappe, COLLEAGUE)
        doc.validate()
        self.assertEqual(doc.employee, COLLEAGUE)

    def test_administrator_may_book_for_a_colleague(self):
        frappe = self.frappe_for("Administrator", [])
        doc = self.entry(frappe, COLLEAGUE)
        doc.validate()
        self.assertEqual(doc.employee, COLLEAGUE)

    def test_an_entry_booked_for_a_colleague_is_owned_by_that_colleague(self):
        frappe = self.frappe_for(YOU, ["System Manager"])
        doc = self.entry(frappe, COLLEAGUE)
        doc.validate()
        self.assertEqual(doc.owner, COLLEAGUE)

    def test_so_the_colleague_can_correct_their_own_hours(self):
        """The half that `if_owner` refused before: the point of the change."""
        frappe = self.frappe_for(YOU, ["System Manager"])
        doc = self.entry(frappe, COLLEAGUE)
        doc.validate()

        theirs = FakeFrappe(session_user=COLLEAGUE, roles=["Projects User"])
        self.assertTrue(
            theirs.has_permission("Timesheet Entry", "write", doc=doc),
            "a Projects User must be able to write the row that holds their own "
            "hours; that is what owner = employee buys")

    def test_and_could_not_before(self):
        """Counter-assert, so the test above is not vacuous.

        Same row, `owner` left as the person who entered it. frappe refuses.
        """
        frappe = self.frappe_for(YOU, ["System Manager"])
        doc = self.entry(frappe, COLLEAGUE)
        doc.validate()
        doc.owner = YOU                      # what frappe alone would have left

        theirs = FakeFrappe(session_user=COLLEAGUE, roles=["Projects User"])
        self.assertFalse(
            theirs.has_permission("Timesheet Entry", "write", doc=doc),
            "if this passes, `if_owner` is not being enforced and this whole "
            "item rests on nothing")


class TestTheRuleCannotReachASave(GateTestCase):
    """Insert-only, checked both by running it and by reading it."""

    def test_an_approver_saving_someone_elses_entry_is_not_gated(self):
        frappe = self.frappe_for(COLLEAGUE, ["Projects User"])
        doc = self.entry(frappe, YOU, is_new=False)
        doc.owner = YOU
        doc.validate()                       # must not throw
        self.assertEqual(doc.employee, YOU)
        self.assertEqual(doc.owner, YOU, "a save must not re-point owner")

    def test_the_rule_is_guarded_by_is_new(self):
        node = controller_function("validate_employee_ownership")
        guards = [
            stmt for stmt in node.body
            if isinstance(stmt, ast.If)
            and "is_new" in ast.dump(stmt.test)
        ]
        self.assertTrue(
            guards,
            "validate_employee_ownership() has no is_new() guard, so it now "
            "runs on every save. That refuses Afterz's submit, approve, reject "
            "and un-approve, and erplite's own approve_timesheet and "
            "reject_timesheet, all of which save an entry whose employee is "
            "someone else.")

    def test_validate_calls_it(self):
        called = {
            node.func.attr
            for node in ast.walk(controller_function("validate"))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertIn("validate_employee_ownership", called)
        self.assertLess(
            list(called).index("validate_employee_ownership")
            if "validate_employee_ownership" in list(called) else 0,
            len(called) + 1)

    def test_it_runs_after_set_employee_default(self):
        """Order matters: a blank employee must be filled before it is judged."""
        body = controller_function("validate").body
        order = [stmt.value.func.attr for stmt in body
                 if isinstance(stmt, ast.Expr)
                 and isinstance(stmt.value, ast.Call)
                 and isinstance(stmt.value.func, ast.Attribute)]
        self.assertIn("set_employee_default", order)
        self.assertIn("validate_employee_ownership", order)
        self.assertLess(order.index("set_employee_default"),
                        order.index("validate_employee_ownership"))

    def test_no_save_hook_assigns_owner(self):
        """`owner` is written in exactly one place, and that place is insert-only.

        A hook that re-pointed `owner` on every save would hand a row to
        whoever it was last booked for, which is not the same rule at all.
        """
        tree = ast.parse(controller_source())
        writers = set()
        for func in ast.walk(tree):
            if not isinstance(func, ast.FunctionDef):
                continue
            for node in ast.walk(func):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if (isinstance(target, ast.Attribute)
                            and target.attr == "owner"):
                        writers.add(func.name)
        self.assertEqual(
            writers, {"validate_employee_ownership"},
            "owner is assigned in %s; it may only be assigned by the "
            "insert-only rule." % (sorted(writers),))


class TestTheAuthorityTestIsTheDocTypesOwn(unittest.TestCase):
    """No role names in the rule: it enforces the rows the app ships.

    The general form of the owner's standing instruction -- enforce the
    permissions you already have, do not invent policy. It is also what makes
    the rule follow the JSON: grant a new role write on Timesheet Entry and that
    role may book for others, with no code change.
    """

    ROLE_NAMES = ("System Manager", "Projects Manager", "Projects User",
                  "Timesheet Admin", "Administrator")

    def test_the_rule_names_no_role(self):
        node = controller_function("validate_employee_ownership")
        # The docstring explains which roles hold write today, so it names them;
        # the rule itself must not. Scanning the whole function body including
        # its docstring is what the first version of this test did, and it
        # failed on the explanation rather than on the code.
        body = node.body[1:] if (node.body and isinstance(node.body[0], ast.Expr)
                                 and isinstance(node.body[0].value, ast.Constant)
                                 and isinstance(node.body[0].value.value, str)
                                 ) else node.body
        for literal in [n for stmt in body for n in ast.walk(stmt)]:
            if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                for role in self.ROLE_NAMES:
                    self.assertNotIn(
                        role, literal.value,
                        "the rule hard-codes the role %r. Ask frappe for the "
                        "DocType's write permission instead, so the shipped "
                        "rows stay the single answer." % (role,))

    def test_it_asks_frappe_for_write_on_this_doctype(self):
        node = controller_function("validate_employee_ownership")
        checks = [
            call for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "has_permission"
        ]
        self.assertEqual(len(checks), 1, "expected exactly one permission check")
        args = checks[0].args
        self.assertEqual(
            [a.attr if isinstance(a, ast.Attribute) else a.value for a in args],
            ["doctype", "write"])


class TestTheStandInsPermissionModel(unittest.TestCase):
    """Self-tests of the ported rule, on rows whose answer is obvious.

    This file would be worthless if the stand-in answered permission questions
    differently from frappe, and it did: before this change it let an `if_owner`
    row grant write at DocType level, so a Projects User passed
    `has_permission("Timesheet Entry", "write")` with no document -- which is
    the exact test the new rule turns on, and frappe refuses it
    (`get_role_permissions`, permissions.py:296-305: a right granted only by
    `if_owner` rows is set to 0, bar `select` and `read`, which stay 1 so the
    list view can load and be filtered by owner afterwards).
    """

    def row(self, owner):
        return {"doctype": "Timesheet Entry", "name": "TSE-2026-00001",
                "owner": owner, "get": lambda key: None}

    def doc(self, owner):
        class Row(dict):
            def get(self, key, default=None):
                return dict.get(self, key, default)
        return Row(owner=owner, name="TSE-2026-00001")

    def test_a_projects_user_has_no_write_at_doctype_level(self):
        frappe = FakeFrappe(session_user=YOU, roles=["Projects User"])
        self.assertFalse(frappe.has_permission("Timesheet Entry", "write"))

    def test_a_projects_user_may_write_their_own_row(self):
        frappe = FakeFrappe(session_user=YOU, roles=["Projects User"])
        self.assertTrue(
            frappe.has_permission("Timesheet Entry", "write", doc=self.doc(YOU)))

    def test_a_projects_user_may_not_write_another_persons_row(self):
        frappe = FakeFrappe(session_user=YOU, roles=["Projects User"])
        self.assertFalse(
            frappe.has_permission("Timesheet Entry", "write",
                                  doc=self.doc(COLLEAGUE)))

    def test_read_survives_at_doctype_level_so_the_list_can_load(self):
        frappe = FakeFrappe(session_user=YOU, roles=["Projects User"])
        self.assertTrue(frappe.has_permission("Timesheet Entry", "read"))

    def test_create_is_never_restricted_by_if_owner(self):
        frappe = FakeFrappe(session_user=YOU, roles=["Projects User"])
        self.assertTrue(frappe.has_permission("Timesheet Entry", "create"))

    def test_a_right_no_row_grants_is_refused(self):
        """Projects User has no delete row at all."""
        frappe = FakeFrappe(session_user=YOU, roles=["Projects User"])
        self.assertFalse(frappe.has_permission("Timesheet Entry", "delete"))
        self.assertFalse(
            frappe.has_permission("Timesheet Entry", "delete", doc=self.doc(YOU)))

    def test_a_manager_has_write_at_doctype_level_and_on_any_row(self):
        for role in ("System Manager", "Projects Manager"):
            frappe = FakeFrappe(session_user=YOU, roles=[role])
            self.assertTrue(frappe.has_permission("Timesheet Entry", "write"),
                            role)
            self.assertTrue(
                frappe.has_permission("Timesheet Entry", "write",
                                      doc=self.doc(COLLEAGUE)), role)

    def test_one_row_without_if_owner_decides_for_all_a_users_roles(self):
        """frappe's `has_permission_without_if_owner_enabled` is cross-role."""
        frappe = FakeFrappe(session_user=YOU,
                            roles=["Projects User", "Projects Manager"])
        self.assertTrue(frappe.has_permission("Timesheet Entry", "write"))
        self.assertTrue(
            frappe.has_permission("Timesheet Entry", "write",
                                  doc=self.doc(COLLEAGUE)))

    def test_administrator_is_allowed_before_any_row_is_read(self):
        frappe = FakeFrappe(session_user="Administrator", roles=[])
        self.assertTrue(frappe.has_permission("Timesheet Entry", "write"))
        self.assertTrue(
            frappe.has_permission("Timesheet Entry", "write",
                                  doc=self.doc(COLLEAGUE)))


class TestThePremises(unittest.TestCase):
    """What the rule rests on, read from the JSON so it goes stale loudly."""

    def setUp(self):
        self.rows = doctype_permissions("projects", "timesheet_entry")

    def test_projects_user_is_restricted_to_its_own_rows(self):
        self.assertTrue(self.rows["Projects User"]["if_owner"])

    def test_the_two_manager_roles_are_not(self):
        for role in ("System Manager", "Projects Manager"):
            self.assertFalse(self.rows[role]["if_owner"], role)
            self.assertIn("write", self.rows[role]["granted"], role)

    def test_employee_is_a_required_editable_link_to_user(self):
        import json
        path = os.path.join(APP_ROOT, "erplite", "projects", "doctype",
                            "timesheet_entry", "timesheet_entry.json")
        with open(path, "rb") as handle:
            definition = json.loads(handle.read().decode("utf-8"))
        field = [f for f in definition["fields"] if f["fieldname"] == "employee"][0]
        self.assertEqual(field["fieldtype"], "Link")
        self.assertEqual(field["options"], "User")
        self.assertTrue(field.get("reqd"))
        self.assertFalse(field.get("read_only"),
                         "a read-only employee would make the gate moot")
        self.assertFalse(field.get("permlevel"))

    def test_no_app_code_reads_owner_on_a_timesheet_entry(self):
        """`owner` now means the employee, so a reader of it would be wrong.

        Checked for the two modules that handle these rows. Afterz was checked
        the same way, read-only on the bench on 5 Oct 2026: it reads `owner`
        only for frappe's own Version and Comment rows (history_api.py) and for
        ToDo, never for a Timesheet Entry, and it declares no Timesheet Entry
        DocType of its own.
        """
        for path in (CONTROLLER, API):
            with open(path, "rb") as handle:
                source = handle.read().decode("utf-8")
            tree = ast.parse(source)
            reads = []
            for node in ast.walk(tree):
                if (isinstance(node, ast.Attribute) and node.attr == "owner"
                        and isinstance(node.ctx, ast.Load)):
                    reads.append(node.lineno)
            self.assertEqual(
                reads, [],
                "%s reads `owner` at %s. Since rev_84dce415b5 that field holds "
                "the employee on rows booked by someone else, not the person "
                "who entered them -- which is in modified_by."
                % (os.path.basename(path), reads))


if __name__ == "__main__":
    unittest.main()
