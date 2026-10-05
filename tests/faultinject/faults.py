# -*- coding: utf-8 -*-
"""The faults themselves: what to break, and which test file should notice.

Each target names one test file and the ways the code it guards could regress.
Patterns are literal source text, written with `\\n` -- `harness.nl` translates
them to the file's own line ending.

## Adding a target

Ask, for each thing the test file claims: *what edit to the real source would
make that claim false?* Then write it as a `Fault` and run it. Three habits
earn their keep:

* **Break the behaviour, not the spelling.** An edit that renames something the
  test matches by name proves only that the test reads that name.
* **Include at least one negative control** (`expect_red=False`): a real edit
  that changes no behaviour. If it goes red, the test is pinning the code's
  internals rather than its behaviour, and that is a finding about the test.
* **Cover every instance of the rule**, not a sample. A gate on four DocTypes
  needs four faults; a test that notices two of them is guarding two.
"""
from collections import namedtuple

Fault = namedtuple("Fault", "name expect_red edits")
Target = namedtuple("Target", "test faults")

# --- erplite/xero permission gate -----------------------------------------
# rev_c3343b2cf3, rev_6c9dc08cf7: six whitelisted endpoints that write to the
# owner's real Xero ledger, gated on each DocType's own permission rows.

SI = "erplite/accounts/doctype/sales_invoice/sales_invoice.py"
PI = "erplite/accounts/doctype/purchase_invoice/purchase_invoice.py"
CUST = "erplite/crm/doctype/customer/customer.py"
SUPP = "erplite/crm/doctype/supplier/supplier.py"
CUST_JSON = "erplite/crm/doctype/customer/customer.json"

SI_GATE = '    frappe.has_permission("Sales Invoice", "write", doc=docname, throw=True)\n'
PI_GATE = '    frappe.has_permission("Purchase Invoice", "write", doc=docname, throw=True)\n'
CUST_GATE = '    frappe.has_permission("Customer", "write", doc=docname, throw=True)\n'
SUPP_GATE = '    frappe.has_permission("Supplier", "write", doc=docname, throw=True)\n'
CUST_IMPORT_GATE = '    frappe.has_permission("Customer", "create", throw=True)\n'
SUPP_IMPORT_GATE = '    frappe.has_permission("Supplier", "create", throw=True)\n'


def _unprivileged_row(write):
    """A `Projects User` permission row, as the DocType JSONs spell one.

    `write` is the whole point: the gate on a send checks write, the gate on an
    import checks create, and the test claims both refuse this role. Granting
    it one without the other is how you find out whether both are really
    checked.
    """
    return (
        ' "permissions": [\n'
        '  {\n'
        '   "create": 1,\n'
        '   "delete": 0,\n'
        '   "email": 0,\n'
        '   "export": 0,\n'
        '   "print": 0,\n'
        '   "read": 1,\n'
        '   "report": 0,\n'
        '   "role": "Projects User",\n'
        '   "share": 0,\n'
        '   "write": %d\n'
        '  },\n' % write)


XERO_GATE = Target(
    test="tests/offline/test_xero_permission_gate.py",
    faults=[
        # The gate removed, on each of the six endpoints in turn. One fault per
        # endpoint on purpose: a single fault in Sales Invoice passing tells you
        # nothing about Supplier.
        Fault("gate deleted: Sales Invoice send", True, [(SI, SI_GATE, "")]),
        Fault("gate deleted: Purchase Invoice send", True, [(PI, PI_GATE, "")]),
        Fault("gate deleted: Customer send", True, [(CUST, CUST_GATE, "")]),
        Fault("gate deleted: Supplier send", True, [(SUPP, SUPP_GATE, "")]),
        Fault("gate deleted: Customer import (the `create` claim)", True,
              [(CUST, CUST_IMPORT_GATE, "")]),
        Fault("gate deleted: Supplier import (the `create` claim)", True,
              [(SUPP, SUPP_IMPORT_GATE, "")]),

        # The gate still there, but useless. Both of these would pass a test
        # that only looked for the call, which is why the test asserts its
        # position and its effect instead.
        Fault("gate moved inside the try, so `except Exception` relabels the "
              "refusal as a failed send", True, [
                  (SI,
                   SI_GATE + "\n    try:\n        # Get sales invoice\n",
                   "\n    try:\n    " + SI_GATE.rstrip("\n")
                   + "\n        # Get sales invoice\n"),
              ]),
        Fault("gate checks but does not throw", True, [
            (SI, 'doc=docname, throw=True)', 'doc=docname, throw=False)'),
        ]),

        # The rows, not the code. These are what prove the test enforces the
        # DocType's shipped permissions rather than a role list of its own: if
        # it were hardcoded, granting the role access would change nothing.
        Fault("rows grant the unprivileged role write (so the gate permits)",
              True, [(CUST_JSON, ' "permissions": [\n', _unprivileged_row(1))]),
        Fault("rows grant the unprivileged role create but not write (so "
              "write and create stop being the same set)",
              True, [(CUST_JSON, ' "permissions": [\n', _unprivileged_row(0))]),

        # rev_6c9dc08cf7: the duplicate-contact defect, as the three separate
        # things that have to hold.
        Fault("stale save re-added after the Xero post (the duplicate-contact "
              "bug, restored)", True, [
                  (CUST,
                   "            frappe.db.commit()\n            return True",
                   "            customer.xero_contact_id = xero_contact_id\n"
                   "            customer.save()\n"
                   "            frappe.db.commit()\n            return True"),
              ]),
        Fault("already-sent guard removed, so a retry sends a second contact",
              True, [
                  (CUST,
                   '        if customer.xero_contact_id:\n'
                   '            frappe.throw(_("This customer has already been '
                   'sent to Xero"))\n',
                   ''),
              ]),
        Fault("commit removed, so the recorded id rides on the request's own "
              "commit", True, [
                  (CUST, "            frappe.db.commit()\n", ""),
              ]),

        # Negative control. A local variable rename: real edit, no behaviour
        # change. If this goes red, the test is matching the app's internal
        # spelling and the test is what needs fixing.
        Fault("CONTROL: local variable renamed (must stay green)", False, [
            (CUST, "        xero_contact_id = create_customer(customer)",
             "        contact_id = create_customer(customer)"),
            (CUST, "        if xero_contact_id:", "        if contact_id:"),
        ]),
    ])

# --- erplite/timesheet employee ownership ----------------------------------
# rev_84dce415b5 (PR #27): on insert, booking time against someone else's name
# needs write on Timesheet Entry, and the row then belongs to that employee.
#
# This target is the reason the line-ending guard is per-file rather than a
# repo-wide claim: as committed, the controller below is CRLF and its DocType
# JSON is LF, in the same folder (a checkout with core.autocrlf=true will show
# you both as CRLF; the blobs are what the other copies of this repo see). `harness.read` detects each file's own ending, so a fault may
# name either -- but a pattern written for one and applied to the other matches
# nothing, which is the silent failure EXPECTED_MATCHES exists to catch.

TSE = "erplite/projects/doctype/timesheet_entry/timesheet_entry.py"
TSE_JSON = "erplite/projects/doctype/timesheet_entry/timesheet_entry.json"

# The rule itself, as the controller spells it (CRLF file).
TSE_IS_NEW_GUARD = "        if not self.is_new():\n            return\n"
TSE_SELF_GUARD = ("        if self.employee == frappe.session.user:\n"
                  "            return\n")
TSE_WRITE_CHECK = '        if not frappe.has_permission(self.doctype, "write"):\n'
TSE_REFUSAL = ("            frappe.throw(_(\n"
               '                "You can only book time against your own name. "\n'
               '                "Set Employee to yourself, or ask someone who may book time for "\n'
               '                "others to enter it."\n'
               "            ))\n")
TSE_OWNER_ASSIGN = "        self.owner = self.employee\n"
TSE_CALL = "        self.validate_employee_ownership()\n"
TSE_DEFAULT_CALL = "        self.set_employee_default()\n"

# The shipped rows and the field the rule judges (LF file).
TSE_IF_OWNER = '   "if_owner": 1,\n'
TSE_EMPLOYEE_FIELD = ('   "fieldname": "employee",\n'
                      '   "fieldtype": "Link",\n')


TIMESHEET_OWNERSHIP = Target(
    test="tests/offline/test_timesheet_employee_ownership.py",
    faults=[
        # --- the gate, removed or defeated -------------------------------
        Fault("gate deleted: any Projects User may book against a colleague",
              True, [(TSE, TSE_WRITE_CHECK + TSE_REFUSAL, "")]),
        Fault("gate warns instead of refusing, so the insert still happens",
              True, [(TSE, "            frappe.throw(_(\n",
                      "            frappe.msgprint(_(\n")]),
        Fault("gate asks about this row instead of the DocType, so if_owner "
              "answers for a row the booker owns", True, [
                  (TSE, 'frappe.has_permission(self.doctype, "write")',
                   'frappe.has_permission(self.doctype, "write", doc=self)'),
              ]),

        # --- the authority test: the rows, not a role list ----------------
        Fault("authority test replaced by a hardcoded role list (so the "
              "shipped rows stop deciding)", True, [
                  (TSE, 'if not frappe.has_permission(self.doctype, "write"):',
                   'if "System Manager" not in frappe.get_roles():'),
              ]),

        # --- the other half: owner follows employee -----------------------
        Fault("owner left as whoever entered it, so the employee cannot "
              "correct their own hours", True, [(TSE, TSE_OWNER_ASSIGN, "")]),

        # --- wiring: the rule has to run, and run late enough -------------
        Fault("validate() stops calling the rule", True,
              [(TSE, TSE_CALL, "")]),
        Fault("rule judged before a blank employee is defaulted",
              True, [(TSE, TSE_DEFAULT_CALL + TSE_CALL,
                      TSE_CALL + TSE_DEFAULT_CALL)]),

        # --- insert-only, which is what keeps the six approval paths alive -
        Fault("is_new() guard dropped, so the rule reaches every save and "
              "refuses Afterz's submit/approve/reject/un-approve",
              True, [(TSE, TSE_IS_NEW_GUARD, "")]),
        Fault("owner re-pointed on every save as well, handing the row to "
              "whoever it was last booked for", True, [
                  (TSE,
                   '        """Calculate duration in hours"""\n',
                   '        """Calculate duration in hours"""\n'
                   "        self.owner = self.employee\n"),
              ]),

        # --- the premises, read from the JSON (an LF file) ----------------
        Fault("rows grant Projects User write outright (if_owner dropped), so "
              "the gate permits what it was built to refuse",
              True, [(TSE_JSON, TSE_IF_OWNER, "")]),
        Fault("employee made read-only, which would make the gate moot",
              True, [(TSE_JSON, TSE_EMPLOYEE_FIELD,
                      TSE_EMPLOYEE_FIELD + '   "read_only": 1,\n')]),

        # --- negative control --------------------------------------------
        # The two early returns swapped. Both return with no side effect, so
        # this changes the source and changes no behaviour. If it goes red, the
        # test file is pinning the order the guards happen to be written in
        # rather than the rule's effect, and the test is what needs fixing.
        Fault("CONTROL: the two early returns swapped (must stay green)",
              False, [(TSE, TSE_IS_NEW_GUARD + TSE_SELF_GUARD,
                       TSE_SELF_GUARD + TSE_IS_NEW_GUARD)]),
    ])


# --- erplite/timesheet target_user ----------------------------------------
# PR #28: `save_timesheet_entries` took a `target_user` and gated it on its own
# role list -- `is_timesheet_admin()`, System Manager or Timesheet Admin. That
# is narrower than Timesheet Entry's write rows, which also grant Projects
# Manager. So a Projects Manager's `target_user` was silently discarded, the
# hours were booked against the caller, and the endpoint returned success. The
# endpoint now passes it through and the controller's rule -- the
# TIMESHEET_OWNERSHIP target above -- is the only rule.
#
# That is why the controller and JSON faults below are deliberately the same
# edits as that target's. This test file claims the endpoint has no rule of its
# own, and the only way to show that is that breaking the rule it defers to
# turns *this* file red too. If one of them did not, the endpoint would be
# deciding something for itself after all.

API = "erplite/projects/api.py"

API_DECISION = ("        if target_user:\n"
                "            employee_user = target_user\n"
                "        else:\n"
                "            employee_user = frappe.session.user\n")
# The gate as it stood before #28, verbatim from 78e2934^.
API_OLD_GATE = ("        if target_user and is_timesheet_admin():\n"
                "            employee_user = target_user\n"
                "        else:\n"
                "            employee_user = frappe.session.user\n")
API_WRITE_SITE = "                timesheet_doc.employee = employee_user\n"
API_FAILURE_RETURN = ('        return {"success": False, "message": '
                      'f"Error saving timesheet: {str(e)}"}\n')
# The first of the two read endpoints that keep the role list on purpose. Its
# comment is what makes the pattern name one of them rather than both.
API_READ_GATE = ("        if target_user and is_timesheet_admin():\n"
                 "            # Admin viewing another user's activities\n")

# The shipped row the defect depended on: Projects Manager holds write, which
# is precisely why the narrower role list threw their `target_user` away.
TSE_PM_WRITE = ('   "role": "Projects Manager",\n'
                '   "share": 1,\n'
                '   "write": 1\n')


TIMESHEET_TARGET_USER = Target(
    test="tests/offline/test_timesheet_target_user.py",
    faults=[
        # --- the defect itself, put back exactly as it was ----------------
        Fault("the bug restored: target_user gated on is_timesheet_admin, so a "
              "Projects Manager's is discarded and the hours go to the caller",
              True, [(API, API_DECISION, API_OLD_GATE)]),

        # --- target_user decided, used, or neither ------------------------
        # Two separate lines, so two faults: a test keyed on the decision alone
        # would not notice the row being written against someone else.
        Fault("target_user ignored outright: the hours always go to the caller",
              True, [(API, API_DECISION,
                      "        employee_user = frappe.session.user\n")]),
        Fault("target_user decided but not used: the row is written against the "
              "caller anyway", True,
              [(API, API_WRITE_SITE,
                "                timesheet_doc.employee = frappe.session.user\n")]),

        # --- a refusal has to arrive as one -------------------------------
        # The endpoint wraps its whole body in `except Exception` and reports
        # the failure in a return value, so these two are the difference
        # between "refused" and "quietly did something else".
        Fault("the refusal relabelled as success by the endpoint's own "
              "except Exception", True,
              [(API, API_FAILURE_RETURN,
                '        return {"success": True, "message": '
                'f"Error saving timesheet: {str(e)}"}\n')]),
        Fault("the refusal's reason dropped, so the caller is not told whose "
              "name was refused", True,
              [(API, 'f"Error saving timesheet: {str(e)}"}',
                '"Error saving timesheet"}')]),

        # --- the rule it defers to ----------------------------------------
        Fault("the controller's gate deleted, so there is nothing left to "
              "defer to", True, [(TSE, TSE_WRITE_CHECK + TSE_REFUSAL, "")]),
        Fault("the controller warns instead of refusing, so the endpoint "
              "reports success and the row is written anyway", True,
              [(TSE, "            frappe.throw(_(\n",
                "            frappe.msgprint(_(\n")]),
        Fault("owner left as whoever entered it, so the colleague cannot "
              "correct the hours booked for them", True,
              [(TSE, TSE_OWNER_ASSIGN, "")]),

        # --- the premises, in the shipped rows ----------------------------
        # Both are what prove this file's claims rest on the DocType's own
        # permissions. The first is the premise unique to this target: without
        # Projects Manager holding write there was never a bug to fix.
        Fault("Projects Manager loses write, so the one role the defect "
              "affected could not book for a colleague even now", True,
              [(TSE_JSON, TSE_PM_WRITE,
                '   "role": "Projects Manager",\n'
                '   "share": 1,\n'
                '   "write": 0\n')]),
        Fault("rows grant Projects User write outright (if_owner dropped), so "
              "the refusal never happens", True,
              [(TSE_JSON, TSE_IF_OWNER, "")]),

        # --- scope: the read endpoints keep their role list ---------------
        # The counterweight. #28 narrowed one endpoint, not the module, and
        # `is_timesheet_admin()` is still the right gate for choosing whose
        # data to show. Without this fault the AST test could be satisfied by
        # deleting the role list everywhere.
        Fault("the role list swept out of a read endpoint too, which this "
              "change deliberately did not do", True,
              [(API, API_READ_GATE,
                "        if target_user:\n"
                "            # Admin viewing another user's activities\n")]),

        # --- negative control ---------------------------------------------
        # The local variable renamed at all three of its occurrences: a real
        # edit to the source, no change in behaviour. If it goes red, the test
        # file is matching the endpoint's internal spelling.
        Fault("CONTROL: the local variable renamed (must stay green)", False, [
            (API, API_DECISION,
             "        if target_user:\n"
             "            whose_hours = target_user\n"
             "        else:\n"
             "            whose_hours = frappe.session.user\n"),
            (API, API_WRITE_SITE,
             "                timesheet_doc.employee = whose_hours\n"),
        ]),
    ])


# --- erplite/scheduler read permissions ------------------------------------
# rev_d4b6b6ed62, option 1 (PR #26): the scheduler's whitelisted reads used
# `frappe.get_all`, whose own docstring says it "will not check for
# permissions", so any logged-in user could read the whole schedule and every
# Scheduler Role's `hourly_rate`. The change is `get_all` -> `get_list` at the
# whitelisted read call sites -- and deliberately nowhere else: three internal
# integrity checks must keep bypassing permissions, or a user with no read rows
# could delete a division that is still in use.
#
# So this target has two halves pulling in opposite directions, and it needs a
# fault for each instance of both. Reverting one call site is one fault, twelve
# times over. The AST sweep notices all twelve, but only some are reached by a
# test that actually calls the endpoint, and breaking them one at a time is the
# only way to learn which -- a sample of two that both go red says nothing
# about the other ten.
#
# It spans two modules and both line endings: `scheduler/api.py` is CRLF and
# `projects/doctype/project/project.json` is LF, which is the per-file rule from
# the TIMESHEET_OWNERSHIP target showing up again across module boundaries.
# Three of the four controllers indent with TABS, not spaces.

SCH_API = "erplite/scheduler/api.py"
DIVISION = "erplite/scheduler/doctype/division/division.py"
SCHED_ROLE = "erplite/scheduler/doctype/scheduler_role/scheduler_role.py"
SCHED_TEMPLATE = "erplite/scheduler/doctype/schedule_template/schedule_template.py"
SCHED_ENTRY = "erplite/scheduler/doctype/schedule_entry/schedule_entry.py"
PROJECT_JSON = "erplite/projects/doctype/project/project.json"
SCHED_ROLE_JSON = "erplite/scheduler/doctype/scheduler_role/scheduler_role.json"


def _back_to_get_all(path, call_site):
    """One call site reverted to `frappe.get_all`: the regression, once.

    The replacement is derived from the pattern rather than written out, so the
    two cannot drift apart and a fault can only ever change the one thing it
    names.
    """
    assert "frappe.get_list(" in call_site, call_site
    return (path, call_site, call_site.replace("frappe.get_list(", "frappe.get_all("))


def _forward_to_get_list(path, call_site):
    """The opposite mistake: an internal integrity check made to run as the caller."""
    assert "frappe.get_all(" in call_site, call_site
    return (path, call_site, call_site.replace("frappe.get_all(", "frappe.get_list("))


# The twelve whitelisted read call sites, each with just enough context to be
# unique. `Schedule Entry` is read from three different endpoints, so those
# three carry their surrounding filters with them.
READS = [
    ("Project, in get_projects_and_activities", SCH_API,
     '    projects = frappe.get_list("Project",\n'),
    ("Activity, in get_projects_and_activities", SCH_API,
     '        activities = frappe.get_list("Activity",\n'),
    ("Resource, in get_resources", SCH_API,
     '    resources = frappe.get_list("Resource",\n'),
    ("Scheduler Role (the charge rates), in get_roles", SCH_API,
     '    roles = frappe.get_list("Scheduler Role",\n'),
    ("Schedule Entry, in get_schedule_entries", SCH_API,
     '    if resource:\n        filters["resource"] = resource\n'
     '    if project:\n        filters["project"] = project\n    \n'
     '    entries = frappe.get_list("Schedule Entry",\n'),
    ("Schedule Entry, in get_resource_capacity_report", SCH_API,
     '    # Get schedule entries for the period\n'
     '    entries = frappe.get_list("Schedule Entry",\n'),
    ("Schedule Entry, in get_unassigned_entries", SCH_API,
     '        "resource": ["is", "not set"],\n'
     '        "schedule_date": ["between", [start_date, end_date]],\n'
     '        "docstatus": ["!=", 2]\n    }\n    \n'
     '    if project:\n        filters["project"] = project\n    \n'
     '    entries = frappe.get_list("Schedule Entry",\n'),
    ("Schedule Row, in get_schedule_rows", SCH_API,
     '    schedule_rows = frappe.get_list("Schedule Row",\n'),
    ("Division, in division.get_active_divisions", DIVISION,
     '\tdivisions = frappe.get_list("Division",\n'),
    ("Project, in division.get_division_projects", DIVISION,
     '\tprojects = frappe.get_list("Project",\n'),
    ("Scheduler Role, in scheduler_role.get_active_roles", SCHED_ROLE,
     '\troles = frappe.get_list("Scheduler Role",\n'),
    ("Schedule Template, in schedule_template.get_active_templates", SCHED_TEMPLATE,
     '\ttemplates = frappe.get_list("Schedule Template",\n'),
]

# The internal reads that must keep bypassing permissions. Tabs, and
# `on_trash` in scheduler_role.py reads twice.
DIV_ON_TRASH = '\t\tprojects_using_division = frappe.get_all("Project", \n'
ROLE_ON_TRASH_RESOURCES = '\t\tresources_using_role = frappe.get_all("Resource Role", \n'
ROLE_ON_TRASH_ROWS = '\t\tschedule_rows_using_role = frappe.get_all("Schedule Row", \n'
ENTRY_PROGRESS = '        entries = frappe.get_all("Schedule Entry",\n'

# A permission row, as the DocType JSONs spell one. `read` is the whole point.
def _row(role, read):
    return (
        '  {\n'
        '   "create": 1,\n'
        '   "email": 1,\n'
        '   "export": 1,\n'
        '   "print": 1,\n'
        '   "read": %d,\n'
        '   "report": 1,\n'
        '   "role": "%s",\n'
        '   "share": 1,\n'
        '   "write": 1\n'
        '  },\n' % (read, role))


PROJECT_PERMS_OPEN = ' "permissions": [\n'
SCHED_ROLE_PERMS_OPEN = ' "permissions": [\n'
# The two rows the recorded inconsistency rests on.
PROJECT_USER_READ = ('   "read": 1,\n   "report": 1,\n'
                     '   "role": "Projects User",\n')
SCHEDULER_USER_READ = ('   "read": 1,\n   "report": 1,\n'
                       '   "role": "Scheduler User",\n')

# The local variable in get_roles, at all three of its occurrences.
ROLES_VAR = [
    ('    roles = frappe.get_list("Scheduler Role",\n',
     '    role_rows = frappe.get_list("Scheduler Role",\n'),
    ('    for role in roles:\n', '    for role in role_rows:\n'),
    ('    return roles\n', '    return role_rows\n'),
]


SCHEDULER_READ_GATE = Target(
    test="tests/offline/test_scheduler_read_gate.py",
    faults=[
        # --- the rule, reverted at each of its twelve instances -----------
        # One fault per call site, not a sample. Which tests each one turns red
        # is the interesting part: the AST sweep sees all twelve, while only the
        # endpoints a test actually calls are covered behaviourally too.
        Fault("read reverted to get_all: " + name, True,
              [_back_to_get_all(path, site)])
        for name, path, site in READS
    ] + [
        # --- the other half: internal checks must NOT run as the caller ----
        Fault("Division.on_trash made to read as the caller, so a user without "
              "read rows can delete a division that is still in use", True,
              [_forward_to_get_list(DIVISION, DIV_ON_TRASH)]),
        Fault("Scheduler Role.on_trash made to read as the caller, both of its "
              "reads", True,
              [_forward_to_get_list(SCHED_ROLE, ROLE_ON_TRASH_RESOURCES),
               _forward_to_get_list(SCHED_ROLE, ROLE_ON_TRASH_ROWS)]),
        Fault("Schedule Entry.get_activity_progress made to read as the "
              "caller, so progress is measured over the rows the caller may "
              "see instead of the activity", True,
              [_forward_to_get_list(SCHED_ENTRY, ENTRY_PROGRESS)]),

        # The same mistake in the other direction: a delete guard exposed over
        # HTTP. It keeps its `get_all`, so the AST sweep is satisfied -- this is
        # the fault that shows the two sweeps are not the same sweep.
        Fault("Division.on_trash whitelisted, so the delete guard becomes an "
              "HTTP endpoint that reads with permissions bypassed", True,
              [(DIVISION, '\tdef on_trash(self):\n',
                '\t@frappe.whitelist()\n\tdef on_trash(self):\n')]),

        # --- the premises, in the shipped rows ----------------------------
        # These are what prove the test enforces the DocType's own permissions
        # rather than a role list of its own: if it were hardcoded, changing the
        # rows would change nothing.
        Fault("rows grant an unrelated role (Blogger) read on Project, so the "
              "refusals the finding is about stop happening", True,
              [(PROJECT_JSON, PROJECT_PERMS_OPEN,
                PROJECT_PERMS_OPEN + _row("Blogger", 1))]),
        Fault("Projects User loses read on Project", True,
              [(PROJECT_JSON, PROJECT_USER_READ,
                PROJECT_USER_READ.replace('"read": 1', '"read": 0'))]),
        Fault("Scheduler User loses read on Scheduler Role", True,
              [(SCHED_ROLE_JSON, SCHEDULER_USER_READ,
                SCHEDULER_USER_READ.replace('"read": 1', '"read": 0'))]),
        # The recorded inconsistency, made consistent -- from each side, because
        # the split has two halves and a test that notices one may not notice
        # the other. TestWhoTheRowsActuallyAdmit pins a position, and these two
        # faults are how anyone finds out if the rows are later widened.
        #
        # The first of them is why `first_refusal` exists in that test file: it
        # came back GREEN the first time it was run. A Scheduler User granted
        # read on Project is still refused Activity half a line later, and
        # `assertRaises(PermissionError)` cannot tell those two refusals apart,
        # so the test went on passing against exactly the change it was written
        # to catch. The test now asserts which DocType refused.
        Fault("rows grant Scheduler User read on Project, resolving the split "
              "the test deliberately pins", True,
              [(PROJECT_JSON, PROJECT_PERMS_OPEN,
                PROJECT_PERMS_OPEN + _row("Scheduler User", 1))]),
        Fault("rows grant Projects User read on Scheduler Role, the other half "
              "of the same split", True,
              [(SCHED_ROLE_JSON, SCHED_ROLE_PERMS_OPEN,
                SCHED_ROLE_PERMS_OPEN + _row("Projects User", 1))]),

        # --- negative control ---------------------------------------------
        # The local variable in get_roles renamed at all three of its
        # occurrences: a real edit to the source, no change in behaviour. If it
        # goes red, the test file is matching the endpoint's internal spelling
        # and the test is what needs fixing.
        Fault("CONTROL: the local variable in get_roles renamed (must stay "
              "green)", False,
              [(SCH_API, old, new) for old, new in ROLES_VAR]),
    ])

# --- the whitelisted-write rule, whole-app ---------------------------------
# rev_18a8f8826d ("any logged-in user can wipe the scheduler's log") and the
# generalisation of rev_c3343b2cf3 it belongs to. The test file has two halves
# and both are injected here: `clear_old_logs` itself, and the sweep that is
# meant to notice the *next* instance of the rule rather than wait for someone
# to go looking. `KNOWN_UNGATED` is empty, so the sweep's green is a claim that
# no whitelisted endpoint in the app reaches an unchecked write ungated -- which
# is only worth anything if adding one turns it red.

SL = "erplite/scheduler/doctype/scheduler_log/scheduler_log.py"
SL_JSON = "erplite/scheduler/doctype/scheduler_log/scheduler_log.json"
SL_JS = "erplite/scheduler/doctype/scheduler_log/scheduler_log.js"

# This file is indented with TABS, where scheduler/api.py beside it uses four
# spaces. Same lesson as the line endings in #30/#31: indentation is a property
# of the file, and a pattern copied from its neighbour matches nothing.
SL_DEF = "def clear_old_logs(days=30):\n"
SL_GATE = '\tfrappe.has_permission("Scheduler Log", "delete", throw=True)\n'
SL_INT = '\t\tfrappe.throw(frappe._("days must be a whole number"))\n'
SL_NEGATIVE = ('\tif days < 0:\n'
               '\t\tfrappe.throw(frappe._("days must be zero or more"))\n')
SL_CUTOFF = "\tcutoff_date = frappe.utils.add_days(frappe.utils.today(), -days)\n"
SL_COUNT = ('\trows = frappe.db.sql("""\n'
            '\t\tSELECT COUNT(*) FROM `tabScheduler Log`\n'
            '\t\tWHERE DATE(timestamp) < %s\n'
            '\t""", (cutoff_date,))\n'
            '\tdeleted_count = rows[0][0] if rows else 0\n')
SL_DELETE = ('\tfrappe.db.sql("""\n'
             '\t\tDELETE FROM `tabScheduler Log`\n'
             '\t\tWHERE DATE(timestamp) < %s\n'
             '\t""", (cutoff_date,))\n')
SL_COMMIT = "\tfrappe.db.commit()\n"
SL_RETURN = '\t\t"deleted_count": deleted_count\n'

# The DELETE's own result, which is `()` in frappe because the cursor has no
# description -- the shape the endpoint shipped with before rev_18a8f8826d's
# PR, and which reported 0 however many rows it had removed.
SL_COUNT_OFF_THE_DELETE = ('\trows = frappe.db.sql("""\n'
                           '\t\tDELETE FROM `tabScheduler Log`\n'
                           '\t\tWHERE DATE(timestamp) < %s\n'
                           '\t""", (cutoff_date,))\n'
                           '\tdeleted_count = rows[0][0] if rows else 0\n')

# Hosts for the sweep's half. `get_scheduler_data` is whitelisted and gated by
# nothing -- 73 of the app's 88 whitelisted endpoints are, which is fine while
# they do not write. Giving one a write is the regression the sweep exists for.
SCH_DATA = '    """Get all data needed for the scheduler interface"""\n'
SCH_UTILISATION = '    """Get total scheduled hours for a resource on a specific date"""\n'
TSE_APPROVE = '    """Approve a timesheet entry"""\n'

WHITELIST_WRITE_GATE = Target(
    test="tests/offline/test_whitelist_write_gate.py",
    faults=[
        # --- the gate on clear_old_logs, broken eight ways ----------------
        Fault("gate deleted: any logged-in user wipes the scheduler log", True,
              [(SL, SL_GATE, "")]),
        Fault("gate asks about `read` instead of `delete`, which every "
              "Scheduler User holds", True,
              [(SL, SL_GATE,
                SL_GATE.replace('"delete"', '"read"'))]),
        Fault("gate asks about the wrong DocType (Scheduler Role)", True,
              [(SL, SL_GATE,
                SL_GATE.replace('"Scheduler Log"', '"Scheduler Role"'))]),
        Fault("gate checks but does not throw, so a False answer is ignored",
              True,
              [(SL, SL_GATE, SL_GATE.replace(", throw=True", ""))]),
        Fault("gate asks about one row instead of the DocType, letting "
              "`if_owner` answer for the whole table", True,
              [(SL, SL_GATE,
                SL_GATE.replace(", throw=True",
                                ', doc="SCHEDLOG-00001", throw=True'))]),
        Fault("gate moved inside the try, where a handler could drop the "
              "refusal", True,
              [(SL, SL_GATE + "\n\ttry:\n",
                "\ttry:\n\t" + SL_GATE)]),
        Fault("gate moved after `days` is read, turning the endpoint into an "
              "argument oracle for callers who may not delete", True,
              [(SL, SL_GATE, ""),
               (SL, SL_NEGATIVE, SL_NEGATIVE + "\n" + SL_GATE)]),
        Fault("gate nested in a branch, so days=0 skips it", True,
              [(SL, SL_GATE, "\tif days:\n\t" + SL_GATE)]),

        # --- `days`, which the caller chooses -----------------------------
        Fault("negative days accepted, putting the cutoff in the future so "
              "every row goes", True,
              [(SL, SL_NEGATIVE, "")]),
        Fault("days=0 refused as well, which is a meaning a caller can have",
              True,
              [(SL, "\tif days < 0:\n", "\tif days <= 0:\n")]),
        Fault("a non-numeric days read as 0 instead of refused, so a typo "
              "clears everything before today", True,
              [(SL, SL_INT, "\t\tdays = 0\n")]),
        Fault("the cutoff computed forwards, so `older than 30 days` deletes "
              "everything", True,
              [(SL, SL_CUTOFF, SL_CUTOFF.replace("-days", "days"))]),
        # Both sides of 30, because one side only shows the test rejects
        # *something*. These two were a single fault that came back GREEN; see
        # `test_the_default_is_still_thirty_days`, which was what needed fixing.
        Fault("the default retention lengthened from 30 days to 60", True,
              [(SL, SL_DEF, SL_DEF.replace("days=30", "days=60"))]),
        Fault("the default retention shortened from 30 days to 29", True,
              [(SL, SL_DEF, SL_DEF.replace("days=30", "days=29"))]),

        # --- what it reports, and whether the work lands ------------------
        Fault("the count read off the DELETE's own result, which is the bug "
              "the endpoint shipped with: always 0", True,
              [(SL, SL_COUNT + "\n" + SL_DELETE, SL_COUNT_OFF_THE_DELETE)]),
        Fault("counted after deleting, so it always reports 0", True,
              [(SL, SL_COUNT + "\n" + SL_DELETE, SL_DELETE + "\n" + SL_COUNT)]),
        Fault("commit removed, so the deletion rides on whatever the request "
              "does next", True,
              [(SL, SL_COMMIT, "")]),

        # --- the rows the gate rests on -----------------------------------
        # The endpoint invents no policy: it asks frappe, and frappe answers
        # from this JSON. So the rows are part of the behaviour being guarded.
        Fault("rows: System Manager loses delete, so nobody may clear the log",
              True,
              [(SL_JSON, '   "delete": 1,\n', "")]),
        Fault("rows: Scheduler User granted delete, which is who the gate is "
              "meant to keep out", True,
              [(SL_JSON, '   "role": "Scheduler User",\n',
                '   "delete": 1,\n   "role": "Scheduler User",\n')]),
        Fault("rows: Scheduler User granted write, so the read-only role is "
              "no longer read-only", True,
              [(SL_JSON, '   "role": "Scheduler User",\n   "share": 1\n',
                '   "role": "Scheduler User",\n   "share": 1,\n'
                '   "write": 1\n')]),

        # --- the author's own intent, in the client script -----------------
        Fault("the Desk button offered to Scheduler User, contradicting the "
              "rows the gate enforces", True,
              [(SL_JS, "has_role('System Manager')",
                "has_role('Scheduler User')")]),

        # --- the sweep: would it see the NEXT instance of the rule? --------
        # KNOWN_UNGATED is empty, so each of these has to turn the whole-app
        # guard red on its own. Note the host: `get_scheduler_data` is a read
        # endpoint with no gate, which is exactly where such a write appears.
        Fault("sweep: an unchecked db.set_value added to an ungated "
              "whitelisted endpoint", True,
              [(SCH_API, SCH_DATA, SCH_DATA +
                '    frappe.db.set_value("Scheduler Log", "SCHEDLOG-00001",\n'
                '                        "message", "scheduler opened")\n')]),
        Fault("sweep: a raw DELETE added to an ungated whitelisted endpoint",
              True,
              [(SCH_API, SCH_DATA, SCH_DATA +
                '    frappe.db.sql("""\n'
                '        DELETE FROM `tabScheduler Log`\n'
                '        WHERE DATE(timestamp) < %s\n'
                '    """, (start_date,))\n')]),
        Fault("sweep: an unchecked write one level down, in a helper an "
              "ungated endpoint calls", True,
              [(SCH_API, SCH_UTILISATION, SCH_UTILISATION +
                '    frappe.db.set_value("Resource", resource,\n'
                '                        "last_checked", date)\n')]),
        Fault("sweep: a statement built as a string, which cannot be read and "
              "so must be reported rather than excused", True,
              [(SCH_API, SCH_DATA, SCH_DATA +
                '    cleanup_sql = ("DELETE FROM `tabSchedule Entry` "\n'
                '                   "WHERE project = \'%s\'" % project)\n'
                '    frappe.db.sql(cleanup_sql)\n')]),
        Fault("sweep: one of the six Xero endpoints loses its gate, seen "
              "through the sweep instead of its own test", True,
              [(CUST, CUST_GATE, "")]),

        # --- two controls, of two different kinds -------------------------
        # 1. A real edit with no behaviour change at all. If it goes red, the
        #    test file is pinning the endpoint's internal spelling.
        Fault("CONTROL: the locals in clear_old_logs renamed (must stay "
              "green)", False,
              [(SL, '\trows = frappe.db.sql("""\n',
                '\tcounted = frappe.db.sql("""\n'),
               (SL, "\tdeleted_count = rows[0][0] if rows else 0\n",
                "\tremoved_rows = counted[0][0] if counted else 0\n"),
               (SL, SL_RETURN, '\t\t"deleted_count": removed_rows\n')]),
        # 2. The sweep's discrimination, which is a different claim: the same
        #    unchecked write that must be reported above is added to an
        #    endpoint that IS gated, and must NOT be reported. This one does
        #    change behaviour -- it is a control for the classifier, not a
        #    no-op edit -- and without it a sweep that simply reported every
        #    new write would pass all five faults above.
        Fault("CONTROL (sweep discrimination): the same unchecked write added "
              "to a GATED endpoint must not be reported (must stay green)",
              False,
              [(TSE, TSE_APPROVE, TSE_APPROVE +
                '    frappe.db.set_value("Timesheet Entry", timesheet_id,\n'
                '                        "approval_seen", 1)\n')]),
    ])

# --- erplite/xero invoice send --------------------------------------------
# rev_7b11901cfb, rev_5c3dfe6ff3: every invoice reaches Xero as a DRAFT, and a
# send whose reply is lost must not become a second invoice in the real ledger.
#
# Two kinds of fault live here, and they fail in opposite directions:
#   * the status one is about what we SEND -- getting it wrong authorises a bill
#     in the owner's accounts;
#   * the lookup ones are about what we send TWICE -- getting them wrong bills a
#     customer again. Each is written out once per DocType in the app, so each
#     is injected once per DocType: `send_to_xero` and the `create_*_invoice`
#     functions are near-copies, and a fix applied to one of them is a fix
#     applied to one of them.

ACCOUNTS = "erplite/xero/accounts.py"
XERO_INIT = "erplite/xero/__init__.py"
XERO_AUTH = "erplite/xero/auth.py"
XERO_CLIENT = "erplite/xero/client.py"

# The two call sites' invoice_data, each with its own InvoiceNumber expression.
SI_STATUS = ('        "Status": "DRAFT",\n'
             '        "InvoiceNumber": cstr(sales_invoice.name)')
PI_STATUS = ('        "Status": "DRAFT",\n'
             '        "InvoiceNumber": invoice_number\n')

# The comment goes with the call: it is the comment that says why the call is
# where it is, so a fault that moves or removes the call removes it too.
SI_LOOKUP = (
    "    # Don't post a second copy of an invoice Xero already has: see\n"
    "    # find_invoice_in_xero. Deliberately outside the try/except below, so that\n"
    "    # this stop reaches the user as a stop and not as a failed send.\n"
    '    existing = find_invoice_in_xero(\n'
    '        invoice_data["InvoiceNumber"], "ACCREC",\n'
    '        sales_invoice.customer_name, settings.tenant_id, token\n'
    '    )\n'
    '    if existing:\n'
    '        frappe.throw(_already_in_xero_message(invoice_data["InvoiceNumber"], existing))\n')

PI_LOOKUP = (
    "    # Don't post a second copy of an invoice Xero already has: see\n"
    "    # find_invoice_in_xero. Deliberately outside the try/except below, so that\n"
    "    # this stop reaches the user as a stop and not as a failed send.\n"
    '    existing = find_invoice_in_xero(\n'
    '        invoice_data["InvoiceNumber"], "ACCPAY",\n'
    '        purchase_invoice.supplier_name, settings.tenant_id, token\n'
    '    )\n'
    '    if existing:\n'
    '        frappe.throw(_already_in_xero_message(invoice_data["InvoiceNumber"], existing))\n')

# What follows the sales lookup, up to the POST. Needed verbatim so the lookup
# can be moved to the other side of `try:` in one edit.
SI_POST_PREAMBLE = (
    '\n'
    '    # Send to Xero\n'
    '    headers = {\n'
    '        "Authorization": f"Bearer {token}",\n'
    '        "Content-Type": "application/json",\n'
    '        "Accept": "application/json",\n'
    '        "Xero-Tenant-Id": settings.tenant_id\n'
    '    }\n'
    '    \n'
    '    try:\n'
    '        response = requests.post(\n')

SI_LOOKUP_INSIDE_TRY = (
    '\n'
    '    # Send to Xero\n'
    '    headers = {\n'
    '        "Authorization": f"Bearer {token}",\n'
    '        "Content-Type": "application/json",\n'
    '        "Accept": "application/json",\n'
    '        "Xero-Tenant-Id": settings.tenant_id\n'
    '    }\n'
    '    \n'
    '    try:\n'
    '        existing = find_invoice_in_xero(\n'
    '            invoice_data["InvoiceNumber"], "ACCREC",\n'
    '            sales_invoice.customer_name, settings.tenant_id, token\n'
    '        )\n'
    '        if existing:\n'
    '            frappe.throw(_already_in_xero_message(invoice_data["InvoiceNumber"], existing))\n'
    '        response = requests.post(\n')

# send_to_xero's handler for a stop: logged, then re-raised unchanged.
def _stop_handler(doctype):
    return ('        frappe.log_error("%s", f"Send to Xero stopped: {str(e)}")\n'
            '        raise\n' % doctype)


def _already_sent_guard(variable):
    return ('        # Check if already sent to Xero\n'
            '        if %s.xero_invoice_id:\n'
            '            frappe.throw(_("This invoice has already been sent to Xero"))\n'
            % variable)


# find_invoice_in_xero's four refusals and three match conditions.
FIND_UNREACHABLE = (
    '    except Exception as e:\n'
    '        frappe.throw(\n'
    '            f"Could not check whether Xero already has invoice {invoice_number}: "\n'
    '            f"{str(e)}. Nothing was sent. Please try again."\n'
    '        )\n')

FIND_NON_200 = (
    '    if response.status_code != 200:\n'
    '        frappe.throw(\n'
    '            f"Could not check whether Xero already has invoice {invoice_number}: "\n'
    '            f"Xero answered {response.status_code}, {response.text[:500]}. "\n'
    '            "Nothing was sent. Please try again."\n'
    '        )\n')

FIND_UNREADABLE = (
    '    try:\n'
    '        invoices = response.json().get("Invoices") or []\n'
    '    except Exception as e:\n'
    '        frappe.throw(\n'
    '            f"Could not read Xero\'s answer when checking invoice {invoice_number}: "\n'
    '            f"{str(e)}. Nothing was sent. Please try again."\n'
    '        )\n')

FIND_IGNORED_FILTER = (
    '    if others:\n'
    '        frappe.throw(\n'
    '            f"Could not check whether Xero already has invoice {invoice_number}: "\n'
    '            f"asked Xero for that number and it returned {len(invoices)} invoice(s), "\n'
    '            f"{len(others)} of them under other numbers, so the answer cannot be "\n'
    '            "trusted. Nothing was sent."\n'
    '        )\n')

FIND_TYPE = ('        if invoice.get("Type") != invoice_type:\n'
             '            continue\n')
FIND_VOIDED = ('        if cstr(invoice.get("Status")).strip().upper() in ("VOIDED", "DELETED"):\n'
               '            continue\n')
FIND_CONTACT = (
    '        if contact_name:\n'
    '            theirs = cstr((invoice.get("Contact") or {}).get("Name")).strip().lower()\n'
    '            if theirs != cstr(contact_name).strip().lower():\n'
    '                continue\n')

XERO_INVOICE_SEND = Target(
    test="tests/offline/test_xero_invoice_send.py",
    faults=[
        # 1. What status reaches Xero. The first two restore the removed branch
        #    verbatim; the second two make the same mistake without using the
        #    word, because `test_the_module_no_longer_mentions_authorised` reads
        #    the source and would catch the first two on their spelling alone.
        Fault("the AUTHORISED branch restored: Sales Invoice", True, [
            (ACCOUNTS, SI_STATUS,
             '        "Status": "AUTHORISED" if sales_invoice.status == "Submitted" else "DRAFT",\n'
             '        "InvoiceNumber": cstr(sales_invoice.name)')]),
        Fault("the AUTHORISED branch restored: Purchase Invoice", True, [
            (ACCOUNTS, PI_STATUS,
             '        "Status": "AUTHORISED" if purchase_invoice.status == "Submitted" else "DRAFT",\n'
             '        "InvoiceNumber": invoice_number\n')]),
        Fault("the status read off the local record, never spelling AUTHORISED: "
              "Sales Invoice", True, [
            (ACCOUNTS, SI_STATUS,
             '        "Status": cstr(sales_invoice.status).upper(),\n'
             '        "InvoiceNumber": cstr(sales_invoice.name)')]),
        Fault("the status read off the local record, never spelling AUTHORISED: "
              "Purchase Invoice", True, [
            (ACCOUNTS, PI_STATUS,
             '        "Status": cstr(purchase_invoice.status).upper(),\n'
             '        "InvoiceNumber": invoice_number\n')]),
        # What is recorded locally is what Xero said, not what we asked for --
        # the two differ precisely when Xero disagrees, which is the case worth
        # having a record of.
        Fault("the local record keeps our own status instead of Xero's answer", True, [
            (ACCOUNTS,
             '                frappe.db.set_value("Sales Invoice", sales_invoice.name, {\n'
             '                    "xero_invoice_id": invoice["InvoiceID"],\n'
             '                    "xero_invoice_number": invoice.get("InvoiceNumber"),\n'
             '                    "xero_status": invoice.get("Status"),\n',
             '                frappe.db.set_value("Sales Invoice", sales_invoice.name, {\n'
             '                    "xero_invoice_id": invoice["InvoiceID"],\n'
             '                    "xero_invoice_number": invoice.get("InvoiceNumber"),\n'
             '                    "xero_status": sales_invoice.status,\n')]),

        # 2. The lookup that makes a send repeatable, removed -- the exact state
        #    before the fix, once per DocType.
        Fault("the lookup deleted: Sales Invoice (a retry posts a second invoice)",
              True, [(ACCOUNTS, SI_LOOKUP, "")]),
        Fault("the lookup deleted: Purchase Invoice", True,
              [(ACCOUNTS, PI_LOOKUP, "")]),
        # Still called, but from inside the try, where `except Exception`
        # relabels the stop. The call's placement is the whole of what makes it
        # read as a stop, and it is one line of indentation away from being lost.
        Fault("the lookup moved inside create_sales_invoice's try, so the stop "
              "comes back as 'Error creating invoice in Xero'", True, [
            (ACCOUNTS, SI_LOOKUP + SI_POST_PREAMBLE, SI_LOOKUP_INSIDE_TRY)]),
        # And the re-wrap in send_to_xero itself, which is what hid the stops
        # before: "Failed to send invoice to Xero: Xero already has this one".
        Fault("send_to_xero re-wraps the stop as a failed send: Sales Invoice",
              True, [(SI, _stop_handler("Sales Invoice"),
                      '        frappe.log_error("Sales Invoice", f"Send to Xero stopped: {str(e)}")\n'
                      '        frappe.throw(_("Failed to send invoice to Xero: {0}").format(str(e)))\n')]),
        Fault("send_to_xero re-wraps the stop as a failed send: Purchase Invoice",
              True, [(PI, _stop_handler("Purchase Invoice"),
                      '        frappe.log_error("Purchase Invoice", f"Send to Xero stopped: {str(e)}")\n'
                      '        frappe.throw(_("Failed to send invoice to Xero: {0}").format(str(e)))\n')]),
        Fault("the already-sent guard deleted: Sales Invoice", True,
              [(SI, _already_sent_guard("sales_invoice"), "")]),
        Fault("the already-sent guard deleted: Purchase Invoice", True,
              [(PI, _already_sent_guard("purchase_invoice"), "")]),
        # A send whose outcome is unknown is traceable from one place only.
        Fault("the Error Log entry for a stop dropped: Sales Invoice", True,
              [(SI, _stop_handler("Sales Invoice"), "        raise\n")]),

        # 3. find_invoice_in_xero never answers "not there" on doubt. Each of
        #    the four ways it can be in doubt is made to answer None instead --
        #    the dangerous direction, since None means "go ahead and post".
        Fault("an unreachable Xero treated as 'not there'", True,
              [(ACCOUNTS, FIND_UNREACHABLE,
                '    except Exception:\n        return None\n')]),
        Fault("a non-200 on the lookup treated as 'not there'", True,
              [(ACCOUNTS, FIND_NON_200,
                '    if response.status_code != 200:\n        return None\n')]),
        Fault("an answer that cannot be read treated as 'not there'", True,
              [(ACCOUNTS, FIND_UNREADABLE,
                '    invoices = response.json().get("Invoices") or []\n')]),
        Fault("a filter Xero ignored treated as a trustworthy empty answer", True,
              [(ACCOUNTS, FIND_IGNORED_FILTER, "")]),

        # 4. What counts as a match. Dropping a condition blocks sends that
        #    should go through; widening one lets a duplicate past.
        Fault("VOIDED and DELETED invoices block the send", True,
              [(ACCOUNTS, FIND_VOIDED, "")]),
        Fault("only VOIDED frees the number again, not DELETED", True,
              [(ACCOUNTS, FIND_VOIDED,
                '        if cstr(invoice.get("Status")).strip().upper() in ("VOIDED",):\n'
                '            continue\n')]),
        Fault("Type dropped from the match, so our SINV- number on a bill blocks "
              "the invoice", True, [(ACCOUNTS, FIND_TYPE, "")]),
        Fault("the contact dropped from the match, so another supplier's INV-001 "
              "blocks our bill", True, [(ACCOUNTS, FIND_CONTACT, "")]),
        Fault("the lookup stops asking Xero for the one number", True, [
            (ACCOUNTS, '            params={"InvoiceNumbers": cstr(invoice_number)},\n',
             '            params={},\n')]),

        # 5. Every Xero call carries a timeout. One fault per module, because
        #    the claim is that no call site in the package is left out and the
        #    sweep walks every file in it -- a fault in accounts.py alone would
        #    prove only that it walks accounts.py.
        Fault("timeout dropped from the lookup GET (accounts.py)", True, [
            (ACCOUNTS,
             '            params={"InvoiceNumbers": cstr(invoice_number)},\n'
             '            timeout=XERO_HTTP_TIMEOUT\n',
             '            params={"InvoiceNumbers": cstr(invoice_number)},\n')]),
        Fault("timeout dropped from requests.delete in auth.py", True, [
            (XERO_AUTH,
             '                response = requests.delete(url, headers=headers, timeout=XERO_HTTP_TIMEOUT)\n',
             '                response = requests.delete(url, headers=headers)\n')]),
        Fault("timeout dropped from requests.put in client.py", True, [
            (XERO_CLIENT,
             '        response = requests.put(\n'
             '            url, \n'
             '            headers=self.get_headers(), \n'
             '            data=json.dumps(data),\n'
             '            timeout=XERO_HTTP_TIMEOUT,\n'
             '        )\n',
             '        response = requests.put(\n'
             '            url, \n'
             '            headers=self.get_headers(), \n'
             '            data=json.dumps(data),\n'
             '        )\n')]),
        # Used in nine places in auth.py and imported in one: a NameError at the
        # moment of the call, which nothing offline would otherwise reach.
        Fault("auth.py uses the timeout without importing it", True, [
            (XERO_AUTH, 'from erplite.xero import XERO_HTTP_TIMEOUT\n', '')]),
        Fault("the timeout is one number instead of a (connect, read) pair", True,
              [(XERO_INIT, 'XERO_HTTP_TIMEOUT = (10, 60)\n',
                'XERO_HTTP_TIMEOUT = 30\n')]),
        Fault("the read timeout is shorter than the connect timeout", True,
              [(XERO_INIT, 'XERO_HTTP_TIMEOUT = (10, 60)\n',
                'XERO_HTTP_TIMEOUT = (60, 10)\n')]),

        # 6. Controls: real edits, no behaviour change. One in the module under
        #    test and one in the caller, because the tests read both.
        Fault("CONTROL: a local renamed in find_invoice_in_xero (must stay green)",
              False, [
            (ACCOUNTS, '    wanted = cstr(invoice_number).strip().lower()\n',
             '    asked_for = cstr(invoice_number).strip().lower()\n'),
            (ACCOUNTS, '        if cstr(inv.get("InvoiceNumber")).strip().lower() != wanted\n',
             '        if cstr(inv.get("InvoiceNumber")).strip().lower() != asked_for\n')]),
        Fault("CONTROL: a local renamed in Sales Invoice's send_to_xero "
              "(must stay green)", False, [
            (SI, '        xero_invoice_id = create_sales_invoice(sales_invoice)\n',
             '        created_id = create_sales_invoice(sales_invoice)\n'),
            (SI, '        if xero_invoice_id:\n', '        if created_id:\n')]),
    ])


# --- the todo kanban page: who may assign, see and change a todo -----------
# The owner's rule: anyone may assign a todo to anyone, and whoever created or
# handed it on keeps track of it afterwards. That rule is frappe's own ToDo
# rule, and it is written out TWICE on this page -- once as `_can_manage_todo`
# for the writes, and once as the board's `or_filters` for the lists -- plus a
# third time in JavaScript as `canEditTodo`. Every copy gets its own faults:
# the same rule guarded unevenly across its copies is the recurring finding of
# this harness (2 of 4 DocTypes, 6 of 12 call sites, 7 red vs 1 red).

TODO_PAGE = "erplite/www/todo/index.py"
TODO_JS = "erplite/public/js/todo/data/TodoDataManager.js"

CAN_MANAGE = (
    "    return bool(\n"
    "        user_is_manager\n"
    "        or todo.allocated_to == user\n"
    "        or todo.assigned_by == user\n"
    "        or todo.owner == user\n"
    "    )\n")

IS_MANAGER_QUERY = (
    '    return bool(frappe.db.exists("Has Role", {\n'
    '        "parent": user,\n'
    '        "role": ["in", MANAGER_ROLES]\n'
    '    }))\n')

# The one permission line is written out twice, identically, so each call site
# is named by what follows it. That is the point rather than an inconvenience:
# a fault has to be able to hit one endpoint without the other.
_UPDATE_CHECK = (
    '        if not _can_manage_todo(todo, current_user, _is_manager(current_user)):\n'
    '            frappe.throw(_("You don\'t have permission to update this todo"))\n'
    '        \n')
STATUS_GATE = _UPDATE_CHECK + "        # Update status\n"
UPDATE_GATE = _UPDATE_CHECK + "        # Update fields if provided\n"
_ALLOCATED_TO_ONLY = (
    '        if not _is_manager(current_user) and todo.allocated_to != current_user:\n'
    '            frappe.throw(_("You don\'t have permission to update this todo"))\n'
    '        \n')

DELETE_CHECK = (
    '        if not _is_manager(current_user) and todo.allocated_to != current_user:\n')
DELETE_GATE = DELETE_CHECK + (
    '            frappe.throw(_("You don\'t have permission to delete this todo"))\n')

BOARD_OR_FILTERS = (
    '            or_filters={\n'
    '                "allocated_to": current_user,\n'
    '                "assigned_by": current_user,\n'
    '                "owner": current_user\n'
    '            },\n')
# Two status filters, one per branch of `if is_manager`. The manager's carries
# a trailing comment, which is what tells them apart.
NONMANAGER_STATUS_FILTER = '            filters={"status": ["!=", "Cancelled"]},\n'
MANAGER_STATUS_FILTER = (
    '            filters={"status": ["!=", "Cancelled"]},'
    '  # Don\'t show cancelled by default\n')

DIRECTORY = (
    '    users = frappe.get_all("User",\n'
    '        filters={"enabled": 1, "user_type": "System User"},\n'
    '        fields=["name", "full_name", "user_image"],\n'
    '        order_by="full_name"\n'
    '    )\n')

CREATE_DEFAULT_ASSIGNEE = (
    "        if not allocated_to:\n"
    "            allocated_to = current_user\n")

CAN_EDIT_JS = (
    "        return todo.allocated_to === this.currentUser\n"
    "            || todo.assigned_by === this.currentUser\n"
    "            || todo.owner === this.currentUser;\n")
CAN_DELETE_JS = "        return todo.allocated_to === this.currentUser;\n"


TODO_ASSIGNMENT = Target(
    test="tests/offline/test_todo_assignment.py",
    faults=[
        # 1. The server's copy of the rule. The pre-fix state first, then one
        #    fault per clause -- a three-way OR satisfied by any one clause is
        #    exactly the shape that a single fault flatters.
        Fault("the pre-fix rule restored: a todo is yours only while it is "
              "with you", True, [
            (TODO_PAGE, CAN_MANAGE,
             "    return bool(user_is_manager or todo.allocated_to == user)\n")]),
        Fault("assigned_by dropped from the server rule", True, [
            (TODO_PAGE, "        or todo.assigned_by == user\n", "")]),
        Fault("owner dropped from the server rule", True, [
            (TODO_PAGE, "        or todo.owner == user\n", "")]),
        Fault("allocated_to dropped from the server rule", True, [
            (TODO_PAGE, "        or todo.allocated_to == user\n", "")]),
        Fault("the manager shortcut dropped from the server rule", True, [
            (TODO_PAGE,
             "        user_is_manager\n        or todo.allocated_to == user\n",
             "        todo.allocated_to == user\n")]),
        Fault("the rule widened to everybody", True, [
            (TODO_PAGE, CAN_MANAGE, "    return True\n")]),

        # 2. Who counts as a manager. `Has Role` is a child table, so the user
        #    is in `parent`; asking for `name` is the mistake the stand-in's own
        #    docstring records having made, and it answers False for everybody.
        Fault("_is_manager asks Has Role for the row's name instead of the "
              "user's", True, [
            (TODO_PAGE, IS_MANAGER_QUERY,
             '    return bool(frappe.db.exists("Has Role", {\n'
             '        "name": user,\n'
             '        "role": ["in", MANAGER_ROLES]\n'
             '    }))\n')]),
        Fault("Administrator dropped from MANAGER_ROLES", True, [
            (TODO_PAGE, 'MANAGER_ROLES = ["System Manager", "Administrator"]\n',
             'MANAGER_ROLES = ["System Manager"]\n')]),
        Fault("any role at all makes you a manager", True, [
            (TODO_PAGE, IS_MANAGER_QUERY,
             '    return bool(frappe.db.exists("Has Role", {\n'
             '        "parent": user,\n'
             '    }))\n')]),

        # 3. create_todo: the assignee the user chose must survive.
        Fault("the pre-fix overwrite restored: a non-manager's chosen assignee "
              "replaced with themselves", True, [
            (TODO_PAGE, CREATE_DEFAULT_ASSIGNEE,
             "        if not allocated_to or not _is_manager(current_user):\n"
             "            allocated_to = current_user\n")]),
        Fault("the default assignee dropped, so a quick-add todo is allocated "
              "to nobody", True, [(TODO_PAGE, CREATE_DEFAULT_ASSIGNEE, "")]),
        Fault("assigned_by recorded as the assignee instead of the creator", True, [
            (TODO_PAGE, '            "assigned_by": current_user\n',
             '            "assigned_by": allocated_to\n')]),
        Fault("a new todo starts in Open rather than Backlog", True, [
            (TODO_PAGE,
             '            "status": "Backlog",  # New todos start in backlog\n',
             '            "status": "Open",\n')]),

        # 4. update_todo: handing a todo on, and the bookkeeping that keeps the
        #    person who did so able to follow it.
        Fault("the hand-over is not recorded, so whoever hands a todo on loses "
              "it", True, [
            (TODO_PAGE, "            todo.assigned_by = current_user\n", "")]),
        Fault("any update counts as a hand-over, overwriting assigned_by", True, [
            (TODO_PAGE,
             "        if allocated_to is not None and allocated_to != todo.allocated_to:\n",
             "        if allocated_to is not None:\n")]),
        Fault("allocated_to written even when the caller sent none", True, [
            (TODO_PAGE,
             "        if allocated_to is not None and allocated_to != todo.allocated_to:\n",
             "        if allocated_to != todo.allocated_to:\n")]),
        # Afterz's Planner Entry points at its parent todo by name, and
        # ignore_links_on_delete covers it, so frappe will not catch this.
        Fault("update_todo re-creates the todo instead of saving it, breaking "
              "Afterz's link to it", True, [
            (TODO_PAGE,
             "            todo.color = color\n        \n        todo.save()\n",
             "            todo.color = color\n        \n        todo.insert()\n")]),

        # 5. The two call sites of the rule, one endpoint at a time.
        Fault("the status endpoint keeps the old allocated_to-only check", True, [
            (TODO_PAGE, STATUS_GATE,
             _ALLOCATED_TO_ONLY + "        # Update status\n")]),
        Fault("the status endpoint's permission check deleted", True, [
            (TODO_PAGE, STATUS_GATE, "        # Update status\n")]),
        Fault("update_todo's permission check deleted", True, [
            (TODO_PAGE, UPDATE_GATE, "        # Update fields if provided\n")]),

        # 6. delete_todo is deliberately narrower than updating. That asymmetry
        #    is a decision on the record, so it is broken in both directions.
        Fault("delete widened to everyone who may update", True, [
            (TODO_PAGE, DELETE_CHECK,
             "        if not _can_manage_todo(todo, current_user, _is_manager(current_user)):\n")]),
        Fault("delete narrowed to managers only", True, [
            (TODO_PAGE, DELETE_CHECK, "        if not _is_manager(current_user):\n")]),
        Fault("delete's permission check deleted", True, [
            (TODO_PAGE, DELETE_GATE, "")]),

        # 7. The board's copy of the same three-way OR. `frappe.get_all` sets
        #    ignore_permissions=True, so these filters are the whole of what
        #    decides what a non-manager sees -- nothing behind them.
        Fault("the pre-fix board filter restored: allocated_to only", True, [
            (TODO_PAGE, NONMANAGER_STATUS_FILTER,
             '            filters={"status": ["!=", "Cancelled"],\n'
             '                     "allocated_to": current_user},\n'),
            (TODO_PAGE, BOARD_OR_FILTERS, "")]),
        Fault("assigned_by dropped from the board's filter", True, [
            (TODO_PAGE, '                "assigned_by": current_user,\n', "")]),
        Fault("owner dropped from the board's filter", True, [
            (TODO_PAGE, '                "owner": current_user\n',
             '                "assigned_by": current_user\n')]),
        Fault("allocated_to dropped from the board's filter", True, [
            (TODO_PAGE, '                "allocated_to": current_user,\n', "")]),
        Fault("cancelled todos come back onto a non-manager's board", True, [
            (TODO_PAGE, NONMANAGER_STATUS_FILTER, "")]),
        Fault("cancelled todos come back onto a manager's board", True, [
            (TODO_PAGE, MANAGER_STATUS_FILTER, "")]),
        Fault("every non-manager gets the manager's query", True, [
            (TODO_PAGE, "    if is_manager:\n", "    if True:\n")]),

        # 8. The three fields the page decides its own permissions from. None
        #    were sent before, so every card compared undefined with the current
        #    user -- always false, which hid every control from every
        #    non-manager. One fault per field, because one dropped field is the
        #    regression and the page shows nothing at all about it.
        Fault("allocated_to not sent to the page", True, [
            (TODO_PAGE, '            "allocated_to": todo.allocated_to,\n', "")]),
        Fault("assigned_by not sent to the page", True, [
            (TODO_PAGE, '            "assigned_by": todo.assigned_by,\n', "")]),
        Fault("owner not sent to the page", True, [
            (TODO_PAGE, '            "owner": todo.owner,\n', "")]),
        Fault("owner never asked for in the query, so the board cannot send it",
              True, [
            (TODO_PAGE, '        "assigned_by", "owner", "creation", "modified"\n',
             '        "assigned_by", "creation", "modified"\n')]),

        # 9. Anyone may assign to anyone, so anyone needs the whole directory.
        Fault("the assignable-user list narrowed to the caller again", True, [
            (TODO_PAGE, DIRECTORY,
             DIRECTORY
             + "    if not is_manager:\n"
               "        users = [u for u in users if u.name == current_user]\n")]),

        # 10. The client's copy. Both halves of a client/server pair are easy to
        #     leave behind one another, and the symptom -- a control hidden, or
        #     shown and then refused -- appears only in a browser.
        Fault("canEditTodo drops assigned_by, so the page and the server "
              "disagree", True, [
            (TODO_JS, "            || todo.assigned_by === this.currentUser\n", "")]),
        Fault("canEditTodo drops owner", True, [
            (TODO_JS, "            || todo.owner === this.currentUser;\n",
             "            ;\n")]),
        Fault("canDeleteTodo widened to canEditTodo's rule, so the delete "
              "button fails on the click", True, [
            (TODO_JS, CAN_DELETE_JS, CAN_EDIT_JS)]),

        # 11. Controls: real edits, no behaviour change. One per file the tests
        #     read, because two of these tests read source text rather than run
        #     it and would otherwise be satisfied by any edit at all.
        Fault("CONTROL: a local renamed in get_context (must stay green)",
              False, [
            (TODO_PAGE, "        processed_todo = {\n", "        card = {\n"),
            (TODO_PAGE, "        processed_todos.append(processed_todo)\n",
             "        processed_todos.append(card)\n")]),
        Fault("CONTROL: a local renamed in delete_todo (must stay green)",
              False, [
            (TODO_PAGE,
             "        current_user = frappe.session.user\n        \n"
             "        if not _is_manager(current_user) and todo.allocated_to != current_user:\n",
             "        me = frappe.session.user\n        \n"
             "        if not _is_manager(me) and todo.allocated_to != me:\n")]),
        Fault("CONTROL: a local renamed in TodoDataManager.makeRequest "
              "(must stay green)", False, [
            (TODO_JS, "        const options = {\n", "        const request = {\n"),
            (TODO_JS, "        const response = await fetch(url, options);\n",
             "        const response = await fetch(url, request);\n")]),
    ])

# --- trip status: a derived field a user is also allowed to set by hand ------
# rev_f9dce41f7f ("a Completed trip stays Completed") and the e585a5b
# regression before it: deriving `status` in before_save() overwrote whatever
# the "Start Trip" / "Complete Trip" buttons had just set, so both buttons
# silently did nothing. Guarded by tests/offline/test_trip_status.py, which
# pins three separate things -- the controller's behaviour, the premises it
# rests on (trip.js's buttons, trip.json's Select) and a whole-app rule -- so
# the faults below are grouped by which of the three should notice.

TRIP = "erplite/projects/doctype/trip/trip.py"
TRIP_JS = "erplite/projects/doctype/trip/trip.js"
TRIP_JSON = "erplite/projects/doctype/trip/trip.json"
SQ = "erplite/accounts/doctype/supplier_quote/supplier_quote.py"
SQ_JS = "erplite/accounts/doctype/supplier_quote/supplier_quote.js"

# The whole previous-document consultation, comments included. Deleting this is
# the pre-e585a5b-fix shape of the file.
TRIP_PREV_BLOCK = (
    '        previous = self.get_doc_before_save()\n'
    '        if previous:\n'
    "            # This save changed the status, so it was somebody's explicit\n"
    '            # choice -- a button or the Select -- and derivation must not\n'
    '            # overwrite it before the row is written.\n'
    '            if previous.status != self.status:\n'
    '                return\n'
    '            # And a trip that already reached a terminal status stays there,\n'
    '            # whatever the dates now say. Without this, clicking "Complete\n'
    '            # Trip" on a trip whose arrival is still in the future persisted\n'
    '            # Completed, and then the next unrelated save of that document\n'
    '            # derived it back to In Progress.\n'
    '            if previous.status in TERMINAL_STATUSES:\n'
    '                return\n'
    '\n')

TRIP_EXPLICIT_GUARD = ('            if previous.status != self.status:\n'
                       '                return\n')
TRIP_TERMINAL_GUARD = ('            if previous.status in TERMINAL_STATUSES:\n'
                       '                return\n')
TRIP_TERMINALS = 'TERMINAL_STATUSES = ("Completed", "Cancelled")\n'

# The three derivation arms. Each is a separate copy of the "Cancelled is
# honoured on insert" rule, so each gets its own fault: the file's own
# docstring claims all three carry it.
TRIP_ARM_FUTURE = ('            if now < departure:\n'
                   '                if self.status != "Cancelled":\n'
                   '                    self.status = "Planned"\n')
TRIP_ARM_RUNNING = ('            elif departure <= now <= arrival:\n'
                    '                if self.status != "Cancelled":\n'
                    '                    self.status = "In Progress"\n')
TRIP_ARM_PAST = ('            elif now > arrival:\n'
                 '                if self.status != "Cancelled":\n'
                 '                    self.status = "Completed"\n')


def _arm_unguarded(arm, value):
    """The same arm with its Cancelled exclusion removed."""
    return arm.replace('                if self.status != "Cancelled":\n'
                       '                    self.status = "%s"\n' % value,
                       '                self.status = "%s"\n' % value)


TRIP_STATUS = Target(
    test="tests/offline/test_trip_status.py",
    faults=[
        # 1. The explicit-change guard: a status this save set by hand, or by a
        #    button, must survive the save that sets it. This is the bug.
        Fault("the whole previous-document consultation deleted (the "
              "pre-e585a5b-fix shape of the file)", True,
              [(TRIP, TRIP_PREV_BLOCK, "")]),
        Fault("explicit-change guard deleted, terminal guard kept", True,
              [(TRIP, TRIP_EXPLICIT_GUARD, "")]),
        Fault("explicit-change guard inverted: == instead of !=, so derivation "
              "runs only when the status WAS changed", True,
              [(TRIP, '            if previous.status != self.status:\n',
                '            if previous.status == self.status:\n')]),
        Fault("guard rewritten with has_value_changed, the trap trip.py's own "
              "docstring names: True on insert, so a new trip is never derived",
              True,
              [(TRIP, TRIP_PREV_BLOCK,
                '        if self.has_value_changed("status"):\n'
                '            return\n\n')]),
        Fault("guard compares the wrong field, so a status change is not seen "
              "as explicit", True,
              [(TRIP, '            if previous.status != self.status:\n',
                '            if previous.trip_name != self.trip_name:\n')]),
        Fault("insert treated as its own previous document, so a new trip's "
              "given status is respected instead of derived", True,
              [(TRIP, '        previous = self.get_doc_before_save()\n',
                '        previous = self.get_doc_before_save() or self\n')]),

        # 2. The owner's rule, rev_f9dce41f7f: a stored terminal status is not
        #    derived away. One fault per half of TERMINAL_STATUSES, because the
        #    two halves are not guarded alike.
        Fault("terminal-status guard deleted (the owner's rule removed)", True,
              [(TRIP, TRIP_TERMINAL_GUARD, "")]),
        Fault("TERMINAL_STATUSES narrowed to Completed, dropping Cancelled",
              True, [(TRIP, TRIP_TERMINALS, 'TERMINAL_STATUSES = ("Completed",)\n')]),
        Fault("TERMINAL_STATUSES narrowed to Cancelled, dropping Completed",
              True, [(TRIP, TRIP_TERMINALS, 'TERMINAL_STATUSES = ("Cancelled",)\n')]),
        Fault("TERMINAL_STATUSES emptied", True,
              [(TRIP, TRIP_TERMINALS, 'TERMINAL_STATUSES = ()\n')]),
        # Written as a fault, on the belief -- which the test file's own
        # docstring stated -- that the explicit-change guard had to come first
        # or a hand correction to a Completed trip would be refused. It came
        # back green, and it is green because the two guards are equivalent in
        # order: both do nothing but `return`, so whichever fires, derivation
        # is skipped and whatever the save holds is written. Kept as a control,
        # because that equivalence is worth having stated somewhere, and the
        # test docstring is corrected.
        Fault("CONTROL: the two guards swapped -- equivalent, because each one "
              "only returns (must stay green)", False,
              [(TRIP, TRIP_PREV_BLOCK,
                '        previous = self.get_doc_before_save()\n'
                '        if previous:\n'
                '            if previous.status in TERMINAL_STATUSES:\n'
                '                return\n'
                '            if previous.status != self.status:\n'
                '                return\n'
                '\n')]),

        # 3. The per-arm Cancelled exclusions. trip.py's docstring says these
        #    three are what honours Cancelled on insert, where there is no
        #    previous document. One fault per arm, not one for the rule.
        Fault("Cancelled exclusion dropped from the future arm", True,
              [(TRIP, TRIP_ARM_FUTURE, _arm_unguarded(TRIP_ARM_FUTURE, "Planned"))]),
        Fault("Cancelled exclusion dropped from the running arm", True,
              [(TRIP, TRIP_ARM_RUNNING,
                _arm_unguarded(TRIP_ARM_RUNNING, "In Progress"))]),
        Fault("Cancelled exclusion dropped from the past arm", True,
              [(TRIP, TRIP_ARM_PAST, _arm_unguarded(TRIP_ARM_PAST, "Completed"))]),

        # 4. Derivation itself: the value each arm produces, and the two
        #    instants where the arms meet.
        Fault("future arm derives In Progress", True,
              [(TRIP, '                    self.status = "Planned"\n',
                '                    self.status = "In Progress"\n')]),
        Fault("running arm derives Planned", True,
              [(TRIP, '                    self.status = "In Progress"\n',
                '                    self.status = "Planned"\n')]),
        Fault("past arm derives In Progress", True,
              [(TRIP, '                    self.status = "Completed"\n',
                '                    self.status = "In Progress"\n')]),
        Fault("the departure instant moved into the future arm: a trip "
              "departing exactly now reads Planned, not In Progress", True,
              [(TRIP, '            if now < departure:\n',
                '            if now <= departure:\n')]),
        Fault("the arrival instant dropped from the running arm: a trip "
              "arriving exactly now is derived by no arm at all", True,
              [(TRIP, '            elif departure <= now <= arrival:\n',
                '            elif departure <= now < arrival:\n')]),
        Fault("derivation gated on the departure date alone, so a trip with no "
              "arrival date is derived", True,
              [(TRIP,
                '        if self.departure_datetime and self.arrival_datetime:\n'
                '            now = datetime.now()\n',
                '        if self.departure_datetime:\n'
                '            now = datetime.now()\n')]),

        # 5. validate(): duration, and the refusal of an impossible window.
        Fault("duration computed in hours, labelled days", True,
              [(TRIP, 'duration.total_seconds() / (24 * 3600)',
                'duration.total_seconds() / 3600')]),
        Fault("duration's sign reversed", True,
              [(TRIP, '            duration = arrival - departure\n',
                '            duration = departure - arrival\n')]),
        Fault("validate no longer calls validate_dates", True,
              [(TRIP, '        self.validate_dates()\n', "")]),
        Fault("validate no longer calls calculate_duration", True,
              [(TRIP, '        self.calculate_duration()\n', "")]),
        Fault("the refusal removed from validate_dates", True,
              [(TRIP,
                '                frappe.throw("Arrival date and time must be '
                'after departure date and time")\n',
                '                pass\n')]),
        Fault("arrival equal to departure allowed: <= becomes <", True,
              [(TRIP, '            if arrival <= departure:\n',
                '            if arrival < departure:\n')]),

        # 6. The whole-app rule. The app holds two instances of it and the test
        #    accepts either remedy, so there is a fault per instance and a
        #    fault that switches trip.py from one remedy to the other.
        Fault("supplier_quote's exclusion list removed, so Accept Quote and "
              "Reject Quote both silently do nothing", True,
              [(SQ,
                '\t\tif self.valid_until and self.valid_until < nowdate() and '
                'self.status not in ["Accepted", "Rejected"]:\n',
                '\t\tif self.valid_until and self.valid_until < nowdate():\n')]),
        Fault("supplier_quote protects only Accepted, so Reject Quote silently "
              "does nothing", True,
              [(SQ, 'self.status not in ["Accepted", "Rejected"]:\n',
                'self.status not in ["Accepted"]:\n')]),
        Fault("trip.py switched from consulting the previous document to "
              "excluding its buttons' values by name -- a remedy the whole-app "
              "rule accepts, and which disables most of the derivation", True,
              [(TRIP, TRIP_PREV_BLOCK, ""),
               (TRIP, '                if self.status != "Cancelled":\n'
                      '                    self.status = "Planned"\n',
                '                if self.status not in ("Cancelled", '
                '"In Progress", "Completed"):\n'
                '                    self.status = "Planned"\n'),
               (TRIP, '                if self.status != "Cancelled":\n'
                      '                    self.status = "In Progress"\n',
                '                if self.status not in ("Cancelled", '
                '"In Progress", "Completed"):\n'
                '                    self.status = "In Progress"\n'),
               (TRIP, '                if self.status != "Cancelled":\n'
                      '                    self.status = "Completed"\n',
                '                if self.status not in ("Cancelled", '
                '"In Progress", "Completed"):\n'
                '                    self.status = "Completed"\n')]),

        # 7. The premises. These tests read trip.js and trip.json as text, so
        #    they pin the facts the behavioural tests above assume.
        Fault("the Start Trip button sets Planned, so the tests' premise is "
              "stale", True,
              [(TRIP_JS, "                frm.set_value('status', 'In Progress');\n",
                "                frm.set_value('status', 'Planned');\n")]),
        Fault("the Start Trip button removed from trip.js", True,
              [(TRIP_JS,
                '        if (frm.doc.status === "Planned") {\n'
                "            frm.add_custom_button(__('Start Trip'), function() {\n"
                "                frm.set_value('status', 'In Progress');\n"
                '                frm.save();\n'
                '            });\n'
                '        }\n', "")]),
        Fault("Cancelled dropped from the status Select's options", True,
              [(TRIP_JSON,
                '   "options": "Planned\\nIn Progress\\nCompleted\\nCancelled",\n',
                '   "options": "Planned\\nIn Progress\\nCompleted",\n')]),
        Fault("the status Select's default removed, so inserts raise "
              "MandatoryError instead of deriving", True,
              [(TRIP_JSON, '   "default": "Planned",\n   "fieldname": "status",\n',
                '   "fieldname": "status",\n')]),
        Fault("status no longer required", True,
              [(TRIP_JSON,
                '   "options": "Planned\\nIn Progress\\nCompleted\\nCancelled",\n'
                '   "reqd": 1\n',
                '   "options": "Planned\\nIn Progress\\nCompleted\\nCancelled",\n'
                '   "reqd": 0\n')]),
        Fault("status changed from a Select to free text, so the whole-app "
              "rule stops looking at trip.py", True,
              [(TRIP_JSON, '   "fieldname": "status",\n   "fieldtype": "Select",\n',
                '   "fieldname": "status",\n   "fieldtype": "Data",\n')]),

        # 8. Controls: real edits with no behavioural difference. Three of
        #    these are equivalences worth having written down, not just inert
        #    renames -- each says something about why the code is shaped as it
        #    is, and a red would mean the test is pinning the shape instead.
        Fault("CONTROL: the local `previous` renamed (must stay green)", False,
              [(TRIP, '        previous = self.get_doc_before_save()\n'
                      '        if previous:\n',
                '        prior = self.get_doc_before_save()\n'
                '        if prior:\n'),
               (TRIP, '            if previous.status != self.status:\n',
                '            if prior.status != self.status:\n'),
               (TRIP, '            if previous.status in TERMINAL_STATUSES:\n',
                '            if prior.status in TERMINAL_STATUSES:\n')]),
        Fault("CONTROL: the locals in calculate_duration renamed (must stay "
              "green)", False,
              [(TRIP, '            departure = get_datetime(self.departure_datetime)\n'
                      '            arrival = get_datetime(self.arrival_datetime)\n'
                      '            duration = arrival - departure\n',
                '            dep = get_datetime(self.departure_datetime)\n'
                '            arr = get_datetime(self.arrival_datetime)\n'
                '            duration = arr - dep\n')]),
        Fault("CONTROL: the terminal guard reads self.status instead of "
              "previous.status -- equivalent, because the guard above it has "
              "already returned on any difference (must stay green)", False,
              [(TRIP, TRIP_TERMINAL_GUARD,
                '            if self.status in TERMINAL_STATUSES:\n'
                '                return\n')]),
        Fault("CONTROL: the past arm uses >= instead of > -- equivalent, "
              "because the running arm's inclusive upper bound already took "
              "the arrival instant (must stay green)", False,
              [(TRIP, '            elif now > arrival:\n',
                '            elif now >= arrival:\n')]),
        Fault("CONTROL: a set_value on the status Select added to a "
              "field-change handler, outside any button -- the whole-app rule "
              "is about buttons and must not flag it (must stay green)", False,
              [(SQ_JS,
                "\t\t\tfrm.set_value('valid_until', valid_until);\n",
                "\t\t\tfrm.set_value('valid_until', valid_until);\n"
                "\t\t\tfrm.set_value('status', 'Draft');\n")]),
    ])

# --- erplite post-save field writes (the whole-app detector) ---------------
# The first eight targets each asked of a *behavioural rule*: would this test
# notice if the rule were broken? This one asks it of a **detector** -- a
# whole-app sweep whose whole job is to find a bug class in real source. The
# question changes shape with it: not "is this rule pinned" but "what does this
# detector actually see, and what can real code do that it cannot see?"
#
# So every fault here plants (or removes) something in real app source and asks
# whether the sweep notices. Three of the six hook names in POST_SAVE_HOOKS
# (`on_change`, `on_update_after_submit`, `after_insert`) appear in no real
# controller at all, so a fault has to add the hook as well as the write --
# which is the measurement: those three are pinned only by synthetic source
# inside the test file.
#
# A third verdict is needed here that the first eight targets did not want.
# `CONTROL` means an edit that changes no behaviour and must stay green.
# **`KNOWN BLIND SPOT` means a real regression that this detector deliberately
# cannot see**, so it is also green -- but for the opposite reason, and reading
# it as a control would be reading "no bug here" off a line that means "bug,
# invisible, on purpose". Each one names why it is not worth closing.

PROJ = "erplite/projects/doctype/project/project.py"
PE = "erplite/accounts/doctype/payment_entry/payment_entry.py"
COMPANY = "erplite/setup/doctype/company/company.py"

# Project's three post-save hooks are all `pass`, which makes it the one
# controller where a planted write is the only thing in the hook.
PROJ_UPD = '    def on_update(self):\n        """Actions on update"""\n        pass\n'
PROJ_SUB = '    def on_submit(self):\n        """Actions on submit"""\n        pass\n'
PROJ_CAN = '    def on_cancel(self):\n        """Actions on cancel"""\n        pass\n'
PROJ_VALIDATE = ('    def validate(self):\n        """Validate project"""\n'
                 '        self.set_default_company()\n')


def _body(anchor, body):
    """One of Project's hooks with its `pass` replaced by `body`."""
    return (PROJ, anchor, anchor.replace("        pass\n", body))


def _added_hook(hook, body):
    """A post-save hook frappe runs but no real controller defines, added to
    Project after on_cancel (the last method in the file)."""
    return (PROJ, PROJ_CAN,
            PROJ_CAN + '    \n    def %s(self):\n%s' % (hook, body))


POST_SAVE_WRITES = Target(
    test="tests/offline/test_post_save_field_writes.py",
    faults=[
        # 1. The bug class itself, in each hook the real tree already defines.
        # One fault per hook, not a sample: the detector reads a frozenset of
        # names, and a frozenset is exactly the kind of thing that is right for
        # the names someone thought of.
        Fault("lost write planted in Project.on_update", True,
              [_body(PROJ_UPD, '        self.status = "Open"\n')]),
        Fault("lost write planted in Project.on_submit", True,
              [_body(PROJ_SUB, '        self.status = "Open"\n')]),
        Fault("lost write planted in Project.on_cancel", True,
              [_body(PROJ_CAN, '        self.status = "Cancelled"\n')]),

        # 2. The three hook names no real controller defines. These are the
        # measurement of what the real tree exercises: before this target they
        # were pinned only by synthetic source inside the test file.
        Fault("lost write in on_change, a hook no real controller defines",
              True, [_added_hook("on_change", '        self.status = "Open"\n')]),
        Fault("lost write in on_update_after_submit, a hook no real controller "
              "defines", True,
              [_added_hook("on_update_after_submit",
                           '        self.status = "Open"\n')]),
        Fault("lost write in after_insert, a hook no real controller defines",
              True, [_added_hook("after_insert", '        self.status = "Open"\n')]),

        # 3. The shapes a lost write can take. Plain assignment is one of
        # several ways to bind a field, and the sweep is a pattern match over
        # AST node types -- so each shape is a separate claim.
        Fault("lost write buried in if/for/try", True,
              [_body(PROJ_SUB,
                     '        if self.project_name:\n'
                     '            for _ in range(1):\n'
                     '                try:\n'
                     '                    self.status = "Open"\n'
                     '                except Exception:\n'
                     '                    pass\n')]),
        Fault("lost write as an augmented assignment", True,
              [_body(PROJ_UPD, '        self.status += "!"\n')]),
        Fault("lost write through self.set(), frappe's own field setter", True,
              [_body(PROJ_UPD, '        self.set("status", "Open")\n')]),
        Fault("lost write through setattr(self, ...)", True,
              [_body(PROJ_UPD, '        setattr(self, "status", "Open")\n')]),
        Fault("lost write as tuple unpacking onto two fields", True,
              [_body(PROJ_UPD,
                     '        self.status, self.project_name = "Open", "x"\n')]),
        Fault("lost write as an annotated assignment", True,
              [_body(PROJ_UPD, '        self.status: str = "Open"\n')]),
        Fault("lost write as a for-loop target", True,
              [_body(PROJ_UPD,
                     '        for self.status in ["Open"]:\n'
                     '            break\n')]),
        Fault("lost write as a with-statement target", True,
              [_body(PROJ_UPD,
                     '        with open(__file__) as self.project_name:\n'
                     '            pass\n')]),
        # frappe's BaseDocument.update() loops straight into set() for every
        # key (base_document.py:169-186), so a dict of fields is the same bug
        # class as a plain assignment -- and the only shape that loses several
        # fields at once. update_if_missing() is the same loop.
        Fault("lost write through self.update(), frappe's documented "
              "several-fields-at-once setter", True,
              [_body(PROJ_UPD,
                     '        self.update({"status": "Open", '
                     '"project_name": "x"})\n')]),
        Fault("lost write through self.update_if_missing()", True,
              [_body(PROJ_UPD,
                     '        self.update_if_missing({"status": "Open"})\n')]),

        # 4. The baseline. PENDING_DECISION keys a finding by
        # (file, class, hook, field) -- so these ask whether that key is tight
        # enough to let a NEW lost write through in a file that already has one.
        Fault("a second field lost in a baselined hook "
              "(SalesInvoice.on_submit also loses rounded_total)", True,
              [(SI, '        self.status = "Submitted"\n',
                '        self.status = "Submitted"\n'
                '        self.rounded_total = 0\n')]),
        Fault("a new hook in a baselined file (SalesInvoice.on_change loses "
              "status)", True,
              [(SI, '    def on_cancel(self):\n',
                '    def on_change(self):\n        self.status = "Open"\n'
                '    \n    def on_cancel(self):\n')]),
        Fault("a new hook in the other baselined file "
              "(PurchaseInvoice.on_update loses status)", True,
              [(PI, '    def on_cancel(self):\n',
                '    def on_update(self):\n        self.status = "Open"\n'
                '    \n    def on_cancel(self):\n')]),

        # 5. The baseline must not outlive what it documents. rev_7b11901cfb is
        # still open; when it is answered these lines change, and the test has
        # to say so rather than stay quietly green.
        Fault("a baselined lost write fixed by persisting it "
              "(SalesInvoice.on_submit calls db_update)", True,
              [(SI, '        if self.is_paid:\n            self.status = "Paid"\n',
                '        if self.is_paid:\n            self.status = "Paid"\n'
                '        self.db_update()\n')]),
        Fault("a baselined lost write removed outright "
              "(SalesInvoice.on_cancel no longer assigns status)", True,
              [(SI, '        """Actions on cancel"""\n        self.status = "Cancelled"\n',
                '        """Actions on cancel"""\n        pass\n')]),
        Fault("a baselined lost write removed outright "
              "(PurchaseInvoice.on_cancel no longer assigns status)", True,
              [(PI, '        """Actions on cancel"""\n        self.status = "Cancelled"\n',
                '        """Actions on cancel"""\n        pass\n')]),
        Fault("half a baselined entry removed: one of SalesInvoice.on_submit's "
              "TWO status lines goes, so the key survives and the line count "
              "does not", True,
              [(SI, '        if self.is_paid:\n            self.status = "Paid"\n',
                '        if self.is_paid:\n            pass\n')]),
        Fault("half a baselined entry removed, purchase side "
              "(PurchaseInvoice.on_submit keeps its key, loses a line)", True,
              [(PI, '        if self.is_paid:\n            self.status = "Paid"\n',
                '        if self.is_paid:\n            pass\n')]),

        # 6. The persisting-call escape, per hook. payment_entry is the one
        # controller that legitimately assigns in a post-save hook and then
        # writes the row, so it is where this half of the rule lives.
        Fault("db_update dropped from PaymentEntry.on_submit, so its status "
              "write is lost", True,
              [(PE, '        self.payment_status = "Submitted"\n        self.db_update()\n',
                '        self.payment_status = "Submitted"\n')]),
        Fault("db_update dropped from PaymentEntry.on_cancel, so its status "
              "write is lost", True,
              [(PE, '        self.payment_status = "Cancelled"\n        self.db_update()\n',
                '        self.payment_status = "Cancelled"\n')]),

        # 7. Every module the walk is meant to reach. The sweep selects
        # directories by `os.path.dirname(dirpath)` ending in "doctype", so a
        # module whose controllers sit anywhere else is invisible -- and which
        # modules it reaches is not visible from any single fault.
        Fault("lost write in the scheduler module (ScheduleEntry.on_update)",
              True,
              [(SCHED_ENTRY, '        # field to hold it.\n        pass\n',
                '        # field to hold it.\n        self.status = "Draft"\n')]),
        Fault("lost write in the setup module (Company.on_update)", True,
              [(COMPANY,
                '    def on_update(self):\n        """Actions after company update"""\n'
                '        pass\n',
                '    def on_update(self):\n        """Actions after company update"""\n'
                '        self.company_name = "x"\n')]),

        # 8. The two controllers this guard was written for, which must not
        # bring the mechanism back. Note what each fault breaks: the first two
        # restore an on_update, the last two remove the before_save that
        # carries the note explaining what belongs in it.
        Fault("Trip gets an on_update back, assigning status", True,
              [(TRIP, '    def before_save(self):\n',
                '    def on_update(self):\n        self.status = "Completed"\n'
                '    \n    def before_save(self):\n')]),
        Fault("Timesheet Entry gets an on_update back, assigning status", True,
              [(TSE, '    def before_save(self):\n',
                '    def on_update(self):\n        self.status = "Submitted"\n'
                '    \n    def before_save(self):\n')]),
        Fault("Trip's before_save renamed, so nothing derives its status",
              True, [(TRIP, '    def before_save(self):\n',
                      '    def _derive_status(self):\n')]),
        Fault("Timesheet Entry's before_save renamed, so the note warning "
              "against auto-submitting here goes with it", True,
              [(TSE, '    def before_save(self):\n',
                '    def _unused_hook(self):\n')]),

        # 9. A controller that does not parse. The sweep turns SyntaxError into
        # an AssertionError naming the file, rather than skipping it -- a
        # detector that silently stops reading a file it cannot parse would
        # report "no findings" for an app it never read.
        Fault("a controller stops parsing, so the sweep cannot read it", True,
              [_body(PROJ_UPD, '        self.status = "Open"\n    def (\n')]),

        # --- controls: real edits that genuinely change no behaviour ---------
        Fault("CONTROL: a non-field attribute set in a post-save hook "
              "(must stay green)", False,
              [_body(PROJ_UPD,
                     '        self.flags.ignore_x = True\n'
                     '        self._cached_total = 1\n'
                     '        self.not_a_field = 2\n')]),
        Fault("CONTROL: a field only read in a post-save hook "
              "(must stay green)", False,
              [_body(PROJ_UPD,
                     '        if self.status == "Open":\n'
                     '            frappe.logger().debug(self.status)\n')]),
        Fault("CONTROL: a field assigned in a PRE-save hook, where it persists "
              "(must stay green)", False,
              [(PROJ, PROJ_VALIDATE,
                PROJ_VALIDATE + '        self.status = "Open"\n')]),
        Fault("CONTROL: a nested class's on_update is not a hook "
              "(must stay green)", False,
              [_body(PROJ_UPD,
                     '        pass\n'
                     '    \n    class _Inner:\n'
                     '        def on_update(self):\n'
                     '            self.status = "Open"\n')]),
        Fault("CONTROL: a module-level on_update function is not a hook "
              "(must stay green)", False,
              [(PROJ, 'class Project(Document):\n',
                'def on_update(self):\n    self.status = "Open"\n\n'
                'class Project(Document):\n')]),
        Fault("CONTROL: a sibling top-level class that is not a Document has "
              "no frappe hooks, so its on_update must not be reported "
              "(must stay green)", False,
              [(PROJ, 'class Project(Document):\n',
                'class _ProjectTotals:\n    def on_update(self):\n'
                '        self.status = "Open"\n\n'
                'class Project(Document):\n')]),
        Fault("CONTROL: a local renamed in Project.validate_dates "
              "(must stay green)", False,
              [(PROJ,
                '        if self.start_date and self.end_date:\n'
                '            if self.start_date > self.end_date:\n',
                '        start, end = self.start_date, self.end_date\n'
                '        if start and end:\n'
                '            if start > end:\n')]),

        # --- known blind spots: real regressions, invisible on purpose -------
        # Each of these loses a field write and stays green. They are here to
        # be measured and named rather than closed: every one needs reasoning
        # about control flow or data flow, and this file's own rule is that a
        # missed case costs nothing while a confidently wrong finding sends
        # someone to rewrite working code.
        Fault("KNOWN BLIND SPOT: db_update() runs BEFORE the assignment, so "
              "the write is still lost (green: the persisting check is per "
              "hook, with no ordering)", False,
              [(PE, '        self.payment_status = "Submitted"\n        self.db_update()\n',
                '        self.db_update()\n        self.payment_status = "Submitted"\n')]),
        Fault("KNOWN BLIND SPOT: db_update() sits in a branch that cannot run "
              "(green: reachability is not read)", False,
              [(PE, '        self.payment_status = "Submitted"\n        self.db_update()\n',
                '        self.payment_status = "Submitted"\n'
                '        if False:\n            self.db_update()\n')]),
        Fault("KNOWN BLIND SPOT: the write moved into a closure the hook calls "
              "immediately (green: nested scopes are skipped, which the "
              "docstring justifies for callbacks -- this is not one)", False,
              [_body(PROJ_UPD,
                     '        def _go():\n'
                     '            self.status = "Open"\n'
                     '        _go()\n')]),
        Fault("KNOWN BLIND SPOT: self bound to a local first "
              "(green: no data flow)", False,
              [_body(PROJ_UPD,
                     '        doc = self\n'
                     '        doc.status = "Open"\n')]),
    ])

TARGETS = {
    "xero_gate": XERO_GATE,
    "timesheet_ownership": TIMESHEET_OWNERSHIP,
    "timesheet_target_user": TIMESHEET_TARGET_USER,
    "scheduler_read_gate": SCHEDULER_READ_GATE,
    "whitelist_write_gate": WHITELIST_WRITE_GATE,
    "xero_invoice_send": XERO_INVOICE_SEND,
    "todo_assignment": TODO_ASSIGNMENT,
    "trip_status": TRIP_STATUS,
    "post_save_writes": POST_SAVE_WRITES,
}
