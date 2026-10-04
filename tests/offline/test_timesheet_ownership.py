# -*- coding: utf-8 -*-
"""Who a Timesheet Entry belongs to, and who may change it.

Two different fields answer "whose timesheet is this", and nothing keeps them
in agreement:

  * Frappe decides permission from `owner`, the standard column it sets to
    `frappe.session.user` on insert (base_document.py, `if not self.creation:`
    -> `self.owner = self.modified_by = frappe.session.user`). The Projects
    User row on Timesheet Entry carries `if_owner: 1`, so for that role read
    and write are granted only on rows that user created
    (permissions.py `get_role_permissions`, the `if_owner` branch).
  * The app decides whose time it is from `employee`, a required Link to User.
    `get_week_timesheets`, `export_timesheet_data` and the dashboard widgets
    all filter on `employee`, through `frappe.get_all`, which frappe's own
    docstring says "will **not** check for permissions".

So a row can count as one person's hours while being editable only by
another, in both directions. Which rule was wanted is a product decision and
is with the owner as rev_84dce415b5; NOTHING here asserts that today's
behaviour is correct. These tests pin the premises the decision rests on, so
that if any of them changes the decision goes stale loudly rather than
quietly, and they lock in the parts that are already right so that whichever
way it is decided does not break them.

These tests run without a bench. See fake_frappe.py for the stand-in.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

DOCTYPE_DIR = os.path.join(
    APP_ROOT, "erplite", "projects", "doctype", "timesheet_entry"
)
DOCTYPE_JSON = os.path.join(DOCTYPE_DIR, "timesheet_entry.json")
CONTROLLER = os.path.join(DOCTYPE_DIR, "timesheet_entry.py")
API = os.path.join(APP_ROOT, "erplite", "projects", "api.py")

RIGHTS = ("read", "write", "create", "delete", "submit", "cancel")


def load_json():
    with open(DOCTYPE_JSON, encoding="utf-8") as fh:
        return json.load(fh)


def perm_rows():
    return load_json().get("permissions") or []


def field(fieldname):
    for f in load_json().get("fields") or []:
        if f.get("fieldname") == fieldname:
            return f
    return None


def role_permissions(roles, is_owner, permissions=None):
    """frappe.permissions.get_role_permissions for permlevel 0.

    Ported from frappe-version-15/frappe/permissions.py so that the
    consequence of `if_owner` is derived here rather than asserted from
    memory. Exercised against hand-built permission rows by
    TestThePortedPermissionRuleIsFaithful below.
    """
    rows = permissions if permissions is not None else perm_rows()
    applicable = [
        p for p in rows
        if p.get("role") in roles and int(p.get("permlevel", 0) or 0) == 0
    ]
    has_if_owner = any(p.get("if_owner", 0) for p in applicable)

    def without_if_owner(ptype):
        return any(
            p.get(ptype, 0) and not p.get("if_owner", 0) for p in applicable
        )

    perms, if_owner = {}, {}
    for ptype in RIGHTS:
        pvalue = any(p.get(ptype, 0) for p in applicable)
        perms[ptype] = int(bool(pvalue))
        if (
            pvalue
            and has_if_owner
            and not without_if_owner(ptype)
            and ptype != "create"
        ):
            # "if_owner does not come with create rights" -- frappe
            if_owner[ptype] = int(bool(pvalue and is_owner))
            perms[ptype] = 1 if ptype in ("select", "read") else 0
    if has_if_owner:
        perms.update(if_owner)
    return perms


def may(roles, ptype, is_owner, permissions=None):
    return bool(
        role_permissions(roles, is_owner, permissions).get(ptype, 0)
    )


class TestThePortedPermissionRuleIsFaithful(unittest.TestCase):
    """Self-tests for role_permissions above.

    The rule decides the whole finding, so it is tested against rows whose
    answer is obvious before it is pointed at the real DocType.
    """

    PLAIN = [{"role": "R", "read": 1, "write": 1, "create": 1, "delete": 1}]
    OWNED = [{"role": "R", "read": 1, "write": 1, "create": 1, "if_owner": 1}]
    BOTH = [
        {"role": "Mgr", "read": 1, "write": 1},
        {"role": "Usr", "read": 1, "write": 1, "if_owner": 1},
    ]

    def test_a_plain_row_grants_regardless_of_owner(self):
        for is_owner in (True, False):
            self.assertTrue(may(["R"], "write", is_owner, self.PLAIN))

    def test_an_if_owner_row_grants_write_only_to_the_owner(self):
        self.assertTrue(may(["R"], "write", True, self.OWNED))
        self.assertFalse(may(["R"], "write", False, self.OWNED))

    def test_a_non_owner_is_denied_read_on_a_particular_document(self):
        """The `if_owner` dict wins.

        Inside get_role_permissions, read and select are left open
        (`perms[ptype] = 1 if ptype in ("select", "read") else 0`) so that the
        list query can be built and then filtered by owner. has_permission
        then overwrites them: "Override with `if_owner` perms irrespective of
        user" -> `permissions.update(permissions.get("if_owner", {}))`. So for
        one named document a non-owner is refused read as well as write. My
        first version of this test asserted the intermediate value and the
        self-test caught it.
        """
        self.assertFalse(may(["R"], "read", False, self.OWNED))
        self.assertTrue(may(["R"], "read", True, self.OWNED))

    def test_create_is_never_restricted_by_if_owner(self):
        self.assertTrue(may(["R"], "create", False, self.OWNED))

    def test_a_plain_row_on_another_role_lifts_the_restriction(self):
        self.assertTrue(may(["Mgr", "Usr"], "write", False, self.BOTH))

    def test_a_role_you_do_not_hold_grants_nothing(self):
        self.assertFalse(may(["Someone Else"], "write", True, self.PLAIN))

    def test_a_higher_permlevel_row_is_not_applicable(self):
        rows = [{"role": "R", "write": 1, "permlevel": 1}]
        self.assertFalse(may(["R"], "write", True, rows))

    def test_an_absent_right_is_not_granted(self):
        self.assertFalse(may(["R"], "delete", True, self.OWNED))


class TestThePremisesOfTheDecision(unittest.TestCase):
    """The facts rev_84dce415b5 rests on. If one changes, say so loudly."""

    def test_projects_user_is_restricted_to_rows_it_created(self):
        rows = [p for p in perm_rows() if p.get("role") == "Projects User"]
        self.assertEqual(
            len(rows), 1, "expected exactly one Projects User permission row"
        )
        self.assertTrue(
            rows[0].get("if_owner"),
            "the decision assumes Projects User carries if_owner",
        )

    def test_projects_user_cannot_delete_at_all(self):
        self.assertFalse(
            may(["Projects User"], "delete", True),
            "a Projects User deleting even their own row is a change of rule",
        )

    def test_projects_manager_is_not_restricted_to_rows_it_created(self):
        self.assertTrue(may(["Projects Manager"], "write", False))

    def test_employee_is_a_required_editable_link_to_user(self):
        f = field("employee")
        self.assertIsNotNone(f, "Timesheet Entry has no employee field")
        self.assertEqual(f.get("fieldtype"), "Link")
        self.assertEqual(f.get("options"), "User")
        self.assertTrue(f.get("reqd"), "employee is expected to be required")
        self.assertFalse(
            f.get("read_only"),
            "employee being editable is why a row can name someone else",
        )
        self.assertFalse(
            f.get("permlevel"),
            "a permlevel on employee would restrict who may set it",
        )

    def test_the_controller_only_fills_a_blank_employee(self):
        with open(CONTROLLER, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("if not self.employee:", src)
        self.assertNotIn(
            "employee != frappe.session.user", src.split("def check_out")[0],
            "a check before check_out would mean validate() constrains it",
        )

    def test_the_week_view_filters_on_employee_not_owner(self):
        with open(API, encoding="utf-8") as fh:
            src = fh.read()
        week = src.split("def get_week_timesheets")[1].split("\ndef ")[0]
        self.assertIn('"employee": user_to_filter', week)
        self.assertNotIn("owner", week)

    def test_the_week_view_reads_through_get_all(self):
        # frappe.get_all: "will **not** check for permissions"
        with open(API, encoding="utf-8") as fh:
            src = fh.read()
        week = src.split("def get_week_timesheets")[1].split("\ndef ")[0]
        self.assertIn("frappe.get_all(", week)


class TestTheConsequencesInBothDirections(unittest.TestCase):
    """Derived from the premises above, not from today's source."""

    def test_a_row_created_for_you_by_an_admin_is_not_writable_by_you(self):
        # owner is the admin who inserted it, employee is you
        self.assertFalse(
            may(["Projects User"], "write", is_owner=False),
            "this is the half that leaves a person unable to fix their hours",
        )

    def test_a_row_you_created_naming_someone_else_stays_writable_by_you(self):
        self.assertTrue(may(["Projects User"], "write", is_owner=True))

    def test_nothing_stops_a_projects_user_creating_a_row_for_anyone(self):
        self.assertTrue(
            may(["Projects User"], "create", is_owner=False),
            "create carries no if_owner, and employee is editable",
        )


class TestWhatIsAlreadyRightAndMustStay(unittest.TestCase):
    """Whichever way the decision goes, these must not regress."""

    def test_check_out_refuses_someone_elses_entry(self):
        with open(CONTROLLER, encoding="utf-8") as fh:
            src = fh.read()
        body = src.split("def check_out")[1].split("\ndef ")[0]
        self.assertIn("if timesheet.employee != frappe.session.user:", body)

    def test_target_user_is_honoured_only_for_a_timesheet_admin(self):
        with open(API, encoding="utf-8") as fh:
            src = fh.read()
        for fn in (
            "save_timesheet_entries",
            "get_projects_and_activities",
            "get_week_timesheets",
        ):
            body = src.split("def %s" % fn)[1].split("\ndef ")[0]
            self.assertIn(
                "if target_user and is_timesheet_admin():", body,
                "%s must gate target_user on the admin check" % fn,
            )

    def test_is_timesheet_admin_is_a_role_check_on_the_caller(self):
        with open(API, encoding="utf-8") as fh:
            src = fh.read()
        body = src.split("def is_timesheet_admin")[1].split("\ndef ")[0]
        self.assertIn("frappe.get_roles(frappe.session.user)", body)

    def test_the_app_bypasses_frappes_permissions_in_exactly_one_place(self):
        """An audit-log insert. Anywhere else would need its own argument."""
        found = []
        for dirpath, _dirs, files in os.walk(os.path.join(APP_ROOT, "erplite")):
            if "public" in dirpath.split(os.sep) or ".git" in dirpath:
                continue
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                with open(path, encoding="utf-8", errors="replace") as fh:
                    for n, line in enumerate(fh, 1):
                        if "ignore_permissions" in line:
                            found.append(
                                (os.path.relpath(path, APP_ROOT), n,
                                 line.strip())
                            )
        self.assertEqual(
            [(f, l) for f, l, _ in found],
            [(os.path.join("erplite", "scheduler", "api.py"), 920)],
            "a new ignore_permissions needs its own justification: %r" % (found,),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
