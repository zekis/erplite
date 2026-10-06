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

# The internal reads that must keep bypassing permissions. Tabs. `on_trash` in
# scheduler_role.py read twice until the dead `Resource Role` read was removed
# (tests/offline/test_scheduler_role_delete.py); it now has the one read below.
DIV_ON_TRASH = '\t\tprojects_using_division = frappe.get_all("Project", \n'
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
        Fault("Scheduler Role.on_trash made to read as the caller, so a user "
              "without read rows can delete a role a schedule still uses", True,
              [_forward_to_get_list(SCHED_ROLE, ROLE_ON_TRASH_ROWS)]),
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


# --- the app's string references, whole-app (the second detector target) ----
# `test_string_references.py` is the second *detector* in this tool, after
# post_save_writes, and it is a detector with no self-tests at all: five
# whole-app assertions and nothing synthetic. So the question is the one that
# target taught -- not "is this rule pinned" but "what can real code do that
# this cannot see?" -- and every fault here plants the real thing in real
# source.
#
# Two verdicts beyond RED, as in post_save_writes. `CONTROL` is an edit that
# changes no behaviour and must stay green. `KNOWN BLIND SPOT` is a real
# regression this sweep deliberately cannot see: also green, for the opposite
# reason, each one saying why it is not worth closing.

HOOKS = "erplite/hooks.py"
PATCHES = "erplite/patches.txt"
TODO_HTML = "erplite/www/todo/index.html"
TODO_JS = "erplite/www/todo/index.js"
APP_VUE = "frontend/src/App.vue"
CUSTOMER = "erplite/crm/doctype/customer/customer.py"
CUSTOMER_JS = "erplite/crm/doctype/customer/customer.js"
SQ = "erplite/accounts/doctype/supplier_quote/supplier_quote.py"
SQ_JS = "erplite/accounts/doctype/supplier_quote/supplier_quote.js"
ROLE_JS = "erplite/scheduler/doctype/scheduler_role/scheduler_role.js"
SCHED_API = "erplite/scheduler/api.py"
SCHED_API_JS = "frontend/src/components/scheduler/composables/useSchedulerAPI.js"
APP_INIT = "erplite/__init__.py"

# hooks.py's one live dotted path and its one live asset path sit in the same
# dict, which makes it the single file where both of pass A and pass B can be
# reached without touching a feature.
HOOKS_LOGO = '\t\t"logo": "/assets/erplite/images/toolbox.png",\n'
HOOKS_PERM = '\t\t"has_permission": "erplite.check_app_permission"\n'

# The one real patch in the app. frappe resolves `<first token>.execute`
# (frappe/modules/patch_handler.py:168) and aborts `bench migrate` if that
# raises -- the loudest failure of any surface this file sweeps.
PATCH_LINE = "erplite.patches.declare_todo_status_options\n"

# customer.js indents with spaces; scheduler_role.js with tabs. Both are
# written out here exactly as the file has them, because `nl` translates the
# line ending and nothing translates the indent.
C = " " * 20
CUSTOMER_CALL = (
    C + "method: 'erplite.crm.doctype.customer.customer.send_to_xero',\n"
    + C + "args: {\n"
    + C + "    'docname': frm.doc.name\n"
    + C + "},\n")
CUSTOMER_CALL_ARGS_FIRST = (
    C + "args: {\n"
    + C + "    'doc_name': frm.doc.name\n"
    + C + "},\n"
    + C + "method: 'erplite.crm.doctype.customer.customer.send_to_xero',\n")
CUSTOMER_ARG = C + "    'docname': frm.doc.name\n"

# Both of scheduler_role.js's two calls pass the same args block, so a fault
# there has to be anchored on the method line to match once.
ROLE_STATS_CALL = (
    "\t\t\t\t\tmethod: 'erplite.scheduler.doctype.scheduler_role"
    ".scheduler_role.get_role_statistics',\n"
    "\t\t\t\t\targs: {\n"
    "\t\t\t\t\t\trole: frm.doc.name\n"
    "\t\t\t\t\t},\n")

STRING_REFS = Target(
    test="tests/offline/test_string_references.py",
    faults=[
        # `patch_module_paths` strips a `finally:` prefix, because deferring the
        # run is all the prefix means. v15.52.0 does not: `execute_patch`
        # resolves `patchmodule.split(maxsplit=1)[0] + ".execute"` at
        # patch_handler.py:166-167, before the prefix check at :182, and
        # `get_attr` throws AppNotInstalledError on app "finally:erplite". So
        # the entry stops `bench migrate` while the parser calls it resolvable.
        # Found writing the todo_status_patch target, where closing a blind spot
        # by deferring to this parser opened this one.
        Fault("patches.txt uses the finally: prefix v15 cannot resolve", True,
              [("erplite/patches.txt", "erplite.patches.declare_todo_status_options",
                "finally:erplite.patches.declare_todo_status_options")]),
        # -- Pass A: /assets/<app>/... names a file the app ships -------------
        # Symptom: a 404 on every page that loads it, twice (the tag and the
        # rel=preload header). No exception, nothing in the Error Log.
        Fault("asset path in hooks.py names a file that is not shipped", True,
              [(HOOKS, HOOKS_LOGO,
                '\t\t"logo": "/assets/erplite/images/toolbox-v2.png",\n')]),
        Fault("the todo page's stylesheet link names a file that is not "
              "shipped", True,
              [(TODO_HTML,
                '<link rel="stylesheet" href="/assets/erplite/css/app_navigation.css">',
                '<link rel="stylesheet" href="/assets/erplite/css/app-navigation.css">')]),
        Fault("one of the todo page's seven script paths is wrong (template "
              "literal)", True,
              [(TODO_JS, "`/assets/erplite/js/todo/data/TodoDataManager.js`",
                "`/assets/erplite/js/todo/data/TodoDatamanager.js`")]),
        # The gap: pass B and pass C sweep frontend/src explicitly, pass A
        # walks MODULE_ROOT only. The un-built Vue source is where the next
        # asset reference would be written.
        Fault("missing asset referenced from the un-built Vue source "
              "(frontend/src)", True,
              [(APP_VUE, "<template>\n  <div id=\"app\">\n",
                "<template>\n  <div id=\"app\">\n"
                "    <link rel=\"stylesheet\" href=\"/assets/erplite/css/ghost.css\">\n")]),
        # The gap: os.path.exists is true for a directory, and a directory is
        # not something the web server will serve.
        Fault("asset path names a directory rather than a file", True,
              [(HOOKS, HOOKS_LOGO, '\t\t"logo": "/assets/erplite/images",\n')]),
        Fault("CONTROL: asset path carries a cache-busting query string",
              False,
              [(TODO_HTML,
                'href="/assets/erplite/css/app_navigation.css"',
                'href="/assets/erplite/css/app_navigation.css?v=2"')]),
        Fault("CONTROL: a missing asset path inside a comment", False,
              [(HOOKS, HOOKS_LOGO, HOOKS_LOGO +
                '\t\t# "logo": "/assets/erplite/images/ghost.png",\n')]),
        Fault("CONTROL: a missing asset path belonging to another app", False,
              [(HOOKS, HOOKS_LOGO, HOOKS_LOGO +
                '\t\t"ghost": "/assets/frappe/images/ghost.png",\n')]),

        # -- Pass B: every erplite.* dotted path resolves ---------------------
        # Symptom: frappe.handler.execute_cmd throws "Failed to get method for
        # command ..." -- a modal error dialog.
        Fault("hooks.py names a has_permission function that does not exist",
              True,
              [(HOOKS, HOOKS_PERM,
                '\t\t"has_permission": "erplite.check_app_permissions"\n')]),
        Fault("a DocType .js calls a method path that does not resolve", True,
              [(CUSTOMER_JS,
                "method: 'erplite.crm.doctype.customer.customer.send_to_xero',",
                "method: 'erplite.crm.doctype.customer.customer.send_to_zero',")]),
        Fault("the un-built Vue source calls a method path that does not "
              "resolve", True,
              [(SCHED_API_JS, "call('erplite.scheduler.api.bulk_create_entries'",
                "call('erplite.scheduler.api.bulk_create_entry'")]),
        Fault("the function a live call names is deleted", True,
              [(APP_INIT, "def check_app_permission():",
                "def check_app_permission_disabled():")]),
        Fault("a called module-level function is demoted to a class method "
              "(exists, but get_attr cannot reach it)", True,
              [(CUSTOMER, "@frappe.whitelist()\ndef send_to_xero(docname):",
                "class _Unreachable:\n    @frappe.whitelist()\n"
                "    def send_to_xero(docname):")]),
        Fault("CONTROL: a dotted path that resolves to nothing, in a Python "
              "comment", False,
              [(HOOKS, HOOKS_PERM, HOOKS_PERM +
                '\t\t# "has_permission": "erplite.ghost.nothing"\n')]),
        Fault("CONTROL: a dotted path that resolves to nothing, in a JS "
              "comment", False,
              [(CUSTOMER_JS,
                "method: 'erplite.crm.doctype.customer.customer.send_to_xero',",
                "// method: 'erplite.ghost.nothing',\n"
                "                    method: 'erplite.crm.doctype.customer.customer.send_to_xero',")]),
        Fault("CONTROL: a dotted path that resolves to nothing, in a README",
              False,
              [("erplite/projects/README.md",
                "erplite.projects.doctype.timesheet_entry.timesheet_entry.check_in",
                "erplite.projects.doctype.timesheet_entry.timesheet_entry.check_inn")]),
        Fault("KNOWN BLIND SPOT: a method path assembled from a template "
              "literal (invisible to all passes: it is not a literal string)",
              False,
              [(SCHED_API_JS, "call('erplite.scheduler.api.bulk_create_entries'",
                "call(`erplite.scheduler.api.${'bulk_create_entry'}`"
                " || 'erplite.scheduler.api.bulk_create_entries'")]),

        # -- Pass B2: patches.txt (the surface that aborts `bench migrate`) ---
        # frappe resolves `<first whitespace-delimited token>.execute` and
        # re-raises, so a wrong entry here stops a deploy before anything runs.
        Fault("patches.txt names a patch module that does not exist", True,
              [(PATCHES, PATCH_LINE,
                "erplite.patches.declare_todo_status_optoins\n")]),
        Fault("patches.txt names a module that exists but has no execute()",
              True, [(PATCHES, PATCH_LINE, "erplite.projects.utils\n")]),
        Fault("the patch module's execute() is renamed", True,
              [("erplite/patches/declare_todo_status_options.py",
                "def execute():", "def run():")]),
        Fault("patches.txt entry is one path element short", True,
              [(PATCHES, PATCH_LINE, "erplite.declare_todo_status_options\n")]),
        Fault("a misspelt patch entry carrying a trailing date, as frappe's "
              "own patches.txt writes them", True,
              [(PATCHES, PATCH_LINE,
                "erplite.patches.declare_todo_status_optoins #2026-10-06\n")]),
        Fault("CONTROL: the patch entry carries a trailing date (frappe splits "
              "on whitespace and resolves the first token only)", False,
              [(PATCHES, PATCH_LINE,
                "erplite.patches.declare_todo_status_options #2026-10-06\n")]),
        Fault("CONTROL: an execute: line, which frappe exec()s as python "
              "rather than resolving as a path", False,
              [(PATCHES, PATCH_LINE, PATCH_LINE +
                'execute:frappe.ghost.nothing("x")\n')]),
        Fault("CONTROL: a commented-out patch entry", False,
              [(PATCHES, PATCH_LINE, PATCH_LINE +
                "# erplite.patches.ghost_nothing\n")]),
        # A real move: out of one section and into the other. Written as one
        # edit and it was not a control -- it left the entry in place and added
        # a second copy, which the baseline test caught. Right answer, and
        # exactly what that test is for.
        Fault("CONTROL: the patch moves to the pre_model_sync section (both "
              "sections are swept; the move changes when it runs, not whether "
              "it resolves)", False,
              [(PATCHES, PATCH_LINE, ""),
               (PATCHES,
                "# Read docs to understand patches: https://frappeframework.com/docs/v14/user/en/database-migrations\n",
                "# Read docs to understand patches: https://frappeframework.com/docs/v14/user/en/database-migrations\n"
                + PATCH_LINE)]),

        # -- Pass B3: whitelisting -------------------------------------------
        # Symptom: frappe.is_whitelisted raises PermissionError, titled
        # "Method Not Allowed".
        Fault("@frappe.whitelist() removed from a function the front end "
              "calls", True,
              [(CUSTOMER, "@frappe.whitelist()\ndef send_to_xero(docname):",
                "def send_to_xero(docname):")]),
        # The carve-out itself -- a hooks.py path needs no whitelist -- is
        # pinned by the green baseline: `erplite.check_app_permission` has no
        # @frappe.whitelist() and hooks.py is its only caller. This is the
        # other side of it: once the front end calls that same function, the
        # absence of the decorator has to be reported.
        Fault("the front end starts calling a function that hooks.py names "
              "and that has no @frappe.whitelist()", True,
              [(CUSTOMER_JS,
                "method: 'erplite.crm.doctype.customer.customer.send_to_xero',",
                "method: 'erplite.check_app_permission',")]),
        Fault("CONTROL: the whitelist decorator takes an argument", False,
              [(CUSTOMER, "@frappe.whitelist()\ndef send_to_xero(docname):",
                "@frappe.whitelist(allow_guest=False)\ndef send_to_xero(docname):")]),

        # -- Pass C: the arguments a readable call passes ---------------------
        Fault("a called argument is renamed in the signature (the sent value "
              "is dropped by get_newargs)", True,
              [(CUSTOMER, "def send_to_xero(docname):",
                "def send_to_xero(doc_name):")]),
        Fault("a new required parameter is added to a front-end-called "
              "function", True,
              [(SCHED_API, "def bulk_create_entries(entries_data):",
                "def bulk_create_entries(entries_data, project):")]),
        # The gap: ARGS_OBJECT required `method` then `args`, in that order.
        Fault("the same wrong argument, with args written before method in the "
              "same frappe.call", True,
              [(CUSTOMER_JS, CUSTOMER_CALL, CUSTOMER_CALL_ARGS_FIRST)]),
        # The gap: ARGS_OBJECT's body was [^{}]*, so any nested object made the
        # whole call unreadable -- and a nested `filters` object is the ordinary
        # shape of a frappe.call.
        Fault("a wrong argument in a call whose args object contains a nested "
              "object", True,
              [(ROLE_JS, ROLE_STATS_CALL,
                ROLE_STATS_CALL
                .replace("role: frm.doc.name",
                         "role_name: frm.doc.name,\n\t\t\t\t\t\t"
                         "filters: { enabled: 1 }"))]),
        # The gap: posonlyargs were not read at all, so the surface described a
        # permanently uncallable function as callable. Two faults, because the
        # before-state differed between them and the difference is the whole
        # point. Making the ONLY parameter positional-only emptied `args`, so
        # the name the caller sends looked unknown and the old test went red --
        # the right colour with the wrong reason ("it accepts (none)"). Leave a
        # second parameter behind and the same bug is invisible.
        Fault("the only parameter of a front-end-called function is made "
              "positional-only (frappe.call passes by keyword, so it can "
              "never be called again)", True,
              [(SCHED_API, "def bulk_create_entries(entries_data):",
                "def bulk_create_entries(entries_data, /):")]),
        Fault("a positional-only parameter is added alongside a keyword one "
              "(same bug, and the caller's own argument still looks fine)",
              True,
              [(SCHED_API, "def bulk_create_entries(entries_data):",
                "def bulk_create_entries(project, /, entries_data):")]),
        Fault("CONTROL: a required parameter is given a default (the caller "
              "already sends it)", False,
              [(SCHED_API, "def bulk_create_entries(entries_data):",
                "def bulk_create_entries(entries_data=None):")]),
        Fault("CONTROL: the function gains **kwargs, so no sent name can be "
              "wrong", False,
              [(CUSTOMER, "def send_to_xero(docname):",
                "def send_to_xero(docname=None, **kwargs):")]),
        Fault("KNOWN BLIND SPOT: a wrong argument in a call whose args object "
              "cannot be read exactly (a spread). Reading it would mean "
              "guessing what the spread holds, and every required parameter "
              "would be reported missing.", False,
              [(CUSTOMER_JS, CUSTOMER_ARG,
                C + "    ...{'doc_name': frm.doc.name}\n")]),
        Fault("KNOWN BLIND SPOT: ES2015 shorthand (`{ docname }`) is not read "
              "as a key, so a call written that way is skipped rather than "
              "guessed at.", False,
              [(CUSTOMER_JS, CUSTOMER_ARG, C + "    doc_name\n")]),
    ],
)

# -- select_values -----------------------------------------------------------
#
# `test_select_values.py` is the third *detector* in this tool, after
# post_save_writes and string_refs. Its question is narrower than theirs: not
# "does this name exist" but "is this one of the values the field is allowed to
# take" -- decidable offline, because a Select carries its whole permitted set
# in its own `options`.
#
# The two previous detector targets taught the question to ask, so every fault
# here plants the real thing in real source: **what can real code do that this
# cannot see?** The answer turned out to be most of frappe's filter API. The
# sweep reads `filters={...}` and nothing else, and frappe's own get_all
# docstring documents filters as a list of lists beside the dict form.
#
# Three verdicts beyond RED. `CONTROL` changes no behaviour and must stay
# green. `FALSE POSITIVE` is an edit real frappe accepts that the sweep
# reported -- green once the sweep is right, and it is the sweep that was
# wrong, not the test. `KNOWN BLIND SPOT` is a real regression the sweep
# deliberately cannot see, green for the opposite reason, each saying why
# closing it would cost more than it buys.

TODO_PAGE = "erplite/www/todo/index.py"
PINV = "erplite/accounts/doctype/purchase_invoice/purchase_invoice.py"
XERO_ACCOUNTS = "erplite/xero/accounts.py"
PROJ_API = "erplite/projects/api.py"
SCHED_API2 = "erplite/scheduler/api.py"
TS_ENTRY = "erplite/projects/doctype/timesheet_entry/timesheet_entry.py"
ROLE_PY = "erplite/scheduler/doctype/scheduler_role/scheduler_role.py"

# The kanban's two reads of ToDo. The manager arm takes `filters=` alone; the
# other arm is the app's one live `or_filters=`, which is the surface this
# sweep never opened.
TODO_MGR_FILTER = (
    '            filters={"status": ["!=", "Cancelled"]},  '
    '# Don\'t show cancelled by default\n')
TODO_OR = (
    '            or_filters={\n'
    '                "allocated_to": current_user,\n'
    '                "assigned_by": current_user,\n'
    '                "owner": current_user\n'
    '            },\n')

# A planted call goes in front of a whitelisted endpoint's decorator, so the
# indentation is nothing and the anchor is one line that occurs once.
SCHED_ANCHOR = "@frappe.whitelist()\ndef get_projects_and_activities():\n"
PROJ_ANCHOR = "@frappe.whitelist()\ndef get_timesheet_users():\n"
ROLE_ANCHOR = "@frappe.whitelist()\ndef get_roles(status=\"Active\"):\n"


def _planted(body, anchor=SCHED_ANCHOR):
    """`body` as a module-level function planted in front of `anchor`."""
    return "def _planted_probe():\n" + body + "\n\n" + anchor


SELECT_VALUES = Target(
    test="tests/offline/test_select_values.py",
    faults=[
        # -- What the sweep already bites: the dict filter and get_doc --------
        # Symptom of a filter: valid SQL, the wrong set, in silence. `!=` an
        # impossible value excludes nothing at all.
        Fault("the kanban's ToDo status filter names a status ToDo cannot "
              "hold", True,
              [(TODO_PAGE, TODO_MGR_FILTER,
                '            filters={"status": ["!=", "Done"]},  '
                '# Don\'t show cancelled by default\n')]),
        Fault("a Project status filter names a status Project cannot hold",
              True,
              [(SCHED_API2, '        filters={"status": ["!=", "Archived"]},\n',
                '        filters={"status": ["!=", "Retired"]},\n')]),
        Fault("one element of a `not in` list is not a ToDo status", True,
              [(PROJ_API,
                '                "status": ["not in", ["Cancelled", "Closed"]]\n',
                '                "status": ["not in", ["Cancelled", "Done"]]\n')]),
        Fault("a Resource status filter names a status Resource cannot hold",
              True,
              [(ROLE_PY,
                '\tfilters={"name": ["in", resource_names], '
                '"status": "Active"},\n',
                '\tfilters={"name": ["in", resource_names], '
                '"status": "Enabled"},\n')]),
        # Symptom of a write: `_validate_selects` throws inside `_validate()`,
        # after the controller's own hooks have run, so nothing can rescue it
        # and the endpoint cannot create a record for any input.
        Fault("a new ToDo is created with a status ToDo cannot hold", True,
              [(TODO_PAGE,
                '            "status": "Backlog",  # New todos start in backlog\n',
                '            "status": "New",  # New todos start in backlog\n')]),
        Fault("a new Timesheet Entry is created with an impossible status",
              True,
              [(TS_ENTRY, '            "status": "Draft"\n',
                '            "status": "New"\n')]),
        Fault("db.set_value writes an impossible status (field and value "
              "positional)", True,
              [(PINV,
                '            frappe.db.set_value("Purchase Invoice", docname, '
                '"status", "Submitted")\n',
                '            frappe.db.set_value("Purchase Invoice", docname, '
                '"status", "Sent")\n')]),

        # -- The gap: frappe's filter API is wider than `filters={...}` -------
        # Each of these is the SAME violation as the four above, written the
        # way frappe's own documentation writes it.
        Fault("the same filter written as a list of lists (frappe's get_all "
              "docstring documents this form)", True,
              [(TODO_PAGE, TODO_MGR_FILTER,
                '            filters=[["status", "!=", "Done"]],\n')]),
        Fault("the same filter as a four-element list (doctype, fieldname, "
              "operator, value)", True,
              [(TODO_PAGE, TODO_MGR_FILTER,
                '            filters=[["ToDo", "status", "!=", "Done"]],\n')]),
        Fault("a dict filter inside a list (build_filter_conditions wraps a "
              "bare dict in one)", True,
              [(TODO_PAGE, TODO_MGR_FILTER,
                '            filters=[{"status": ["!=", "Done"]}],\n')]),
        Fault("an impossible status in the app's one live `or_filters` -- a "
              "surface the sweep never opened", True,
              [(TODO_PAGE, TODO_OR,
                '            or_filters={\n'
                '                "allocated_to": current_user,\n'
                '                "status": "Done",\n'
                '                "owner": current_user\n'
                '            },\n')]),
        Fault("filters passed positionally to get_all (execute() takes "
              "fields, then filters)", True,
              [(TODO_PAGE,
                '        todos = frappe.get_all("ToDo",\n' + TODO_MGR_FILTER +
                '            fields=todo_fields,\n',
                '        todos = frappe.get_all("ToDo", todo_fields, '
                '{"status": "Done"},\n')]),
        Fault("db.set_value's dict-of-values form, which four live Xero "
              "writes already use", True,
              [(XERO_ACCOUNTS,
                '                frappe.db.set_value("Purchase Invoice", '
                'purchase_invoice.name, {\n'
                '                    "xero_invoice_id": invoice["InvoiceID"],\n',
                '                frappe.db.set_value("Purchase Invoice", '
                'purchase_invoice.name, {\n'
                '                    "status": "Sent",\n'
                '                    "xero_invoice_id": invoice["InvoiceID"],\n')]),
        Fault("db.set_value's field and value given by keyword", True,
              [(PINV,
                '            frappe.db.set_value("Purchase Invoice", docname, '
                '"status", "Submitted")\n',
                '            frappe.db.set_value("Purchase Invoice", docname, '
                'field="status", val="Sent")\n')]),
        Fault("db.set_value's second argument as filters (documented: a name "
              "or filters for many rows)", True,
              [(PINV,
                '            frappe.db.set_value("Purchase Invoice", docname, '
                '"status", "Submitted")\n',
                '            frappe.db.set_value("Purchase Invoice", '
                '{"status": "Sent"}, "status", "Submitted")\n')]),
        Fault("frappe.get_value, the documented alias for db.get_value, which "
              "the app already calls three times", True,
              [(SCHED_API2, SCHED_ANCHOR,
                _planted('    return frappe.get_value("Project", '
                         '{"status": "Retired"}, "name")'))]),
        Fault("frappe.db.get_values, beside the get_value the sweep does "
              "read", True,
              [(SCHED_API2, SCHED_ANCHOR,
                _planted('    return frappe.db.get_values("Project", '
                         '{"status": "Retired"}, "name")'))]),
        Fault("frappe.get_last_doc, which passes its filters straight to "
              "get_all", True,
              [(SCHED_API2, SCHED_ANCHOR,
                _planted('    return frappe.get_last_doc("Project", '
                         'filters={"status": "Retired"})'))]),
        Fault("a child row inside a get_doc dict, carrying its own doctype",
              True,
              [(PROJ_API, PROJ_ANCHOR,
                _planted('    return frappe.get_doc({"doctype": "Project", '
                         '"rows": [{"doctype": "ToDo", "status": "Done"}]})',
                         PROJ_ANCHOR))]),
        Fault("get_doc's documented kwargs form", True,
              [(PROJ_API, PROJ_ANCHOR,
                _planted('    return frappe.get_doc(doctype="ToDo", '
                         'status="Done")', PROJ_ANCHOR))]),
        Fault("new_doc then update(), with the doctype in the same "
              "expression", True,
              [(PROJ_API, PROJ_ANCHOR,
                _planted('    return frappe.new_doc("ToDo").update('
                         '{"status": "Done"})', PROJ_ANCHOR))]),

        # -- FALSE POSITIVE: real frappe accepts these; the sweep reported ---
        # `_validate_selects` (base_document.py:892-920) is the authority on a
        # write, and it exempts all three. A sweep that is wrong here teaches
        # people to "fix" correct code, which is the one failure this file's
        # own ToDo comment exists to prevent.
        Fault("FALSE POSITIVE: naming_series, which _validate_selects exempts "
              "by name (line 897)", False,
              [(TS_ENTRY, '            "status": "Draft"\n',
                '            "status": "Draft",\n'
                '            "naming_series": "TSE-.YYYY.-"\n')]),
        Fault("FALSE POSITIVE: an empty Select value, which frappe skips as "
              "falsy (line 897)", False,
              [(TS_ENTRY, '            "status": "Draft"\n',
                '            "status": ""\n')]),
        Fault("FALSE POSITIVE: a written value with trailing space, which "
              "frappe strips before comparing (line 907)", False,
              [(TS_ENTRY, '            "status": "Draft"\n',
                '            "status": "Draft "\n')]),

        # -- CONTROL: correct code, and it must stay correct after the fix ----
        Fault("CONTROL: a `like` filter with a wildcard is not an options "
              "comparison", False,
              [(TODO_PAGE, TODO_MGR_FILTER,
                '            filters={"status": ["like", "%pen%"]},\n')]),
        Fault("CONTROL: a real status written as a list of lists -- the new "
              "forms must not over-report", False,
              [(TODO_PAGE, TODO_MGR_FILTER,
                '            filters=[["status", "!=", "Cancelled"]],\n')]),
        Fault("CONTROL: a four-element filter naming another doctype and a "
              "value that doctype does hold", False,
              [(TODO_PAGE, TODO_MGR_FILTER,
                '            filters=[["Project", "status", "!=", '
                '"Archived"]],\n')]),
        Fault("CONTROL: reference_type 'Activity' on ToDo is a Link, not the "
              "Select of the same name on Payment Entry", False,
              [(PROJ_API, PROJ_ANCHOR,
                _planted('    return frappe.get_all("ToDo", filters='
                         '{"reference_type": "Activity"})', PROJ_ANCHOR))]),
        Fault("CONTROL: a real ToDo status written through the dict form of "
              "set_value", False,
              [(XERO_ACCOUNTS,
                '                frappe.db.set_value("Purchase Invoice", '
                'purchase_invoice.name, {\n'
                '                    "xero_invoice_id": invoice["InvoiceID"],\n',
                '                frappe.db.set_value("Purchase Invoice", '
                'purchase_invoice.name, {\n'
                '                    "status": "Submitted",\n'
                '                    "xero_invoice_id": invoice["InvoiceID"],\n')]),

        # -- KNOWN BLIND SPOT: real regressions, deliberately invisible ------
        # Each needs something a single-expression read cannot have: the type
        # of a local, or a value that does not exist until runtime. Guessing
        # is what produced this file's original false positives, and silent
        # over-reach is the one failure a sweep cannot report.
        Fault("KNOWN BLIND SPOT: attribute assignment on a local whose "
              "doctype is not in the expression", False,
              [(PROJ_API, PROJ_ANCHOR,
                _planted('    doc = frappe.new_doc("ToDo")\n'
                         '    doc.status = "Done"\n'
                         '    return doc', PROJ_ANCHOR))]),
        Fault("KNOWN BLIND SPOT: the value held in a variable first", False,
              [(PROJ_API, PROJ_ANCHOR,
                _planted('    bad = "Done"\n'
                         '    return frappe.get_doc({"doctype": "ToDo", '
                         '"status": bad})', PROJ_ANCHOR))]),
        Fault("KNOWN BLIND SPOT: the value built by an f-string", False,
              [(PROJ_API, PROJ_ANCHOR,
                _planted('    return frappe.get_doc({"doctype": "ToDo", '
                         '"status": f"Do{\'ne\'}"})', PROJ_ANCHOR))]),
        Fault("KNOWN BLIND SPOT: the filters dict built by a helper", False,
              [(PROJ_API, PROJ_ANCHOR,
                _planted('    where = {"status": "Done"}\n'
                         '    return frappe.get_all("ToDo", filters=where)',
                         PROJ_ANCHOR))]),
    ],
)

# --- the patch that declares the todo board's two extra ToDo statuses ------
# rev_a007dfc7a8: "Declare them in code. Backlog and Planned must stay
# supported." The twelfth target, and behavioural again after three detectors:
# one small module, one text file that wires it up, and a test file that stubs
# frappe by hand. Which makes the governing question a different one from the
# detector targets' *what syntax can it read?* -- here it is **what is the
# stand-in more permissive about than frappe is?**

TSP = "erplite/patches/declare_todo_status_options.py"
PTXT = "erplite/patches.txt"

TODO_STATUS_PATCH = Target(
    test="tests/offline/test_todo_status_property_setter.py",
    faults=[
        # -- options_with_extra_statuses: the pure half ---------------------
        # The function's contract is four things at once: both statuses end up
        # present, existing options are kept verbatim, their order is kept, and
        # running it twice is a no-op. One fault each, because a test that
        # notices the missing status tells you nothing about the order.
        Fault("the two statuses are appended instead of prepended", True,
              [(TSP, 'return "\\n".join(missing + lines)',
                'return "\\n".join(lines + missing)')]),
        Fault("EXTRA_STATUSES in the wrong order", True,
              [(TSP, 'EXTRA_STATUSES = ("Backlog", "Planned")',
                'EXTRA_STATUSES = ("Planned", "Backlog")')]),
        Fault("Planned is no longer declared", True,
              [(TSP, 'EXTRA_STATUSES = ("Backlog", "Planned")',
                'EXTRA_STATUSES = ("Backlog",)')]),
        Fault("Backlog is no longer declared", True,
              [(TSP, 'EXTRA_STATUSES = ("Backlog", "Planned")',
                'EXTRA_STATUSES = ("Planned",)')]),
        # A site with no options at all must not be left with a blank option:
        # in frappe a leading empty line is what lets a Select hold no value,
        # so an accidental one changes what the field accepts.
        Fault("an empty options string leaves a blank option behind", True,
              [(TSP, '    if lines == [""]:  # no options at all; do not leave a blank one behind\n'
                     '        lines = []\n\n', "")]),
        Fault("a leading blank option is dropped instead of kept", True,
              [(TSP, '    present = {line.strip() for line in lines}',
                '    lines = [line for line in lines if line]\n'
                '    present = {line.strip() for line in lines}')]),
        Fault("None options crash instead of yielding the two statuses", True,
              [(TSP, 'lines = (options or "").split("\\n")',
                'lines = options.split("\\n")')]),
        # The one a hard-coded list would do: narrow the field to the list this
        # app knows about, silently deleting an option the site added itself.
        Fault("the options are narrowed to the year-old snapshot", True,
              [(TSP, 'return "\\n".join(missing + lines)',
                'return MEASURED_OPTIONS')]),
        Fault("re-running prepends the two statuses again", True,
              [(TSP, '    missing = [status for status in EXTRA_STATUSES if status not in present]',
                '    missing = list(EXTRA_STATUSES)')]),
        # KNOWN BLIND SPOT, closed by test_an_option_that_differs_only_by_
        # surrounding_space_is_not_duplicated. `present` strips because the live
        # options arrived as a hand-edited `tabDocField` row, which is exactly
        # where a trailing space comes from -- and an unstripped comparison then
        # prepends a second "Backlog" and the board grows a duplicate column.
        Fault("option membership stops ignoring surrounding space", True,
              [(TSP, 'present = {line.strip() for line in lines}',
                'present = {line for line in lines}')]),

        # -- execute(): what it reads --------------------------------------
        # KNOWN BLIND SPOT, closed by test_it_asks_for_ToDos_meta_and_not_
        # another_DocTypes. The stub is `lambda doctype: _Meta(...)` -- it
        # ignores the argument, so it answers for every DocType alike and the
        # one thing execute() reads from the site cannot be got wrong.
        Fault("the meta of the wrong DocType is read", True,
              [(TSP, 'frappe.get_meta("ToDo")', 'frappe.get_meta("Task")')]),
        Fault("the meta of the wrong field is read", True,
              [(TSP, '.get_field("status")', '.get_field("priority")')]),

        # -- execute(): the default half of the recovery story -------------
        # KNOWN BLIND SPOT, closed by test_a_reset_site_gets_the_default_back.
        # The patch pins two properties and the file asserted the recovery of
        # one. On a site frappe has reset, `status.default` is "Open", so this
        # edit pins "Open" -- the 17 Planned ToDos come back onto the list and
        # the board's first column stops being where a new ToDo lands. Half of
        # what the patch exists to do, lost silently.
        Fault("the site's own default is preserved instead of forced", True,
              [(TSP, '_declare("default", DEFAULT_STATUS)',
                '_declare("default", status.default or DEFAULT_STATUS)')]),
        Fault("the default is one of frappe's three", True,
              [(TSP, 'DEFAULT_STATUS = "Backlog"', 'DEFAULT_STATUS = "Open"')]),
        Fault("the default is not one of the options at all", True,
              [(TSP, 'DEFAULT_STATUS = "Backlog"', 'DEFAULT_STATUS = "To Do"')]),
        Fault("the default row is never written", True,
              [(TSP, '    _declare("default", DEFAULT_STATUS)\n', "")]),
        Fault("the options row is never written", True,
              [(TSP, '    _declare("options", options_with_extra_statuses(status.options))\n', "")]),

        # -- _declare(): the six columns of the Property Setter ------------
        # Each is a column `apply_property_setters` reads (meta.py:379-387), and
        # getting any of them wrong writes a row that is applied to the wrong
        # thing, or not applied at all, with no error either way.
        Fault("the Property Setter names the wrong DocType", True,
              [(TSP, '    setter = make_property_setter(\n        "ToDo",',
                '    setter = make_property_setter(\n        "Task",')]),
        Fault("the Property Setter names the wrong field", True,
              [(TSP, '        "ToDo",\n        "status",', '        "ToDo",\n        "priority",')]),
        # `cast(ps.property_type, ps.value)` (meta.py:386) reads the value back
        # with this. DocField.options and DocField.default are both Small Text
        # (core/doctype/docfield/docfield.json at v15.52.0).
        Fault("the property_type is not the DocField column's own fieldtype", True,
              [(TSP, '        "Small Text",', '        "Data",')]),
        # A DocType-level row is applied by the `doctype_or_field == "DocType"`
        # arm (meta.py:380) and never reaches the field at all.
        Fault("the row is written against the DocType, not the DocField", True,
              [(TSP, '        validate_fields_for_doctype=False,',
                '        for_doctype=True,\n        validate_fields_for_doctype=False,')]),
        # PropertySetter.on_update runs validate_fields_for_doctype on the whole
        # core DocType unless this is off (property_setter.py:53-60), which can
        # abort a migrate over a problem the patch did not cause.
        Fault("the whole core DocType is validated during the migrate", True,
              [(TSP, '        validate_fields_for_doctype=False,',
                '        validate_fields_for_doctype=True,')]),
        # reset_customization (customize_form.py:675-685) deletes Property
        # Setters filtered on is_system_generated: False, exempting
        # property != "options" and field_name != "naming_series" -- neither of
        # which covers the `default` row. Unmarked, Customize Form's "Reset to
        # defaults" drops it, and this patch runs once.
        Fault("neither row is marked system-generated", True,
              [(TSP, '    setter.db_set("is_system_generated", 1, update_modified=False)\n', "")]),
        Fault("the rows are marked as the user's customisation", True,
              [(TSP, 'setter.db_set("is_system_generated", 1, update_modified=False)',
                'setter.db_set("is_system_generated", 0, update_modified=False)')]),
        # is_system_generated is not an argument to make_property_setter
        # (property_setter.py:63-71), so it has to be written after the insert.
        # A plain attribute set never reaches the row.
        Fault("the mark is set on the object instead of the row", True,
              [(TSP, '    setter.db_set("is_system_generated", 1, update_modified=False)',
                '    setter.is_system_generated = 1')]),
        Fault("writing the mark bumps modified, on a row nobody edited", True,
              [(TSP, 'setter.db_set("is_system_generated", 1, update_modified=False)',
                'setter.db_set("is_system_generated", 1)')]),

        # -- patches.txt: a patch nothing runs protects nothing -------------
        Fault("the entry is gone from patches.txt", True,
              [(PTXT, "erplite.patches.declare_todo_status_options\n", "")]),
        Fault("the entry is commented out", True,
              [(PTXT, "erplite.patches.declare_todo_status_options",
                "# erplite.patches.declare_todo_status_options")]),
        # It reads ToDo's meta, so it must run after the DocTypes are synced.
        # In pre_model_sync it would read -- and pin -- whatever the field held
        # before frappe's own import reset it.
        Fault("the entry runs before the DocTypes are migrated", True,
              [(PTXT, "[pre_model_sync]\n",
                "[pre_model_sync]\nerplite.patches.declare_todo_status_options\n"),
               (PTXT, "# Needs the DocType migrated first: it reads ToDo's meta and writes a Property Setter against it.\n"
                      "erplite.patches.declare_todo_status_options\n", "")]),
        Fault("the module in patches.txt is misspelt", True,
              [(PTXT, "erplite.patches.declare_todo_status_options",
                "erplite.patches.declare_todo_status_optoins")]),
        Fault("the path in patches.txt is one element short", True,
              [(PTXT, "erplite.patches.declare_todo_status_options",
                "erplite.declare_todo_status_options")]),
        # Caught -- but by TestExecute calling `patch.execute()`, not by the
        # patches.txt test, which asks only whether the module names a file.
        # That narrower question is left to test_string_references.py's
        # PatchPathsResolve, which resolves the entry to a module-level
        # `execute`. Two answers to one question is how one of them goes stale.
        Fault("the patch module has no execute() to resolve", True,
              [(TSP, "def execute():", "def execute_patch():")]),

        # -- FALSE POSITIVES: forms of patches.txt frappe accepts ----------
        # Both of these were correct code that the file reported, which is the
        # failure mode that teaches people to switch a guard off. frappe parses
        # patches.txt with configparser and resolves
        # `patchmodule.split(maxsplit=1)[0]` (patch_handler.py:166); this file
        # split the whole stripped line on "." and asked for a file.
        Fault("frappe's own trailing-date form on the entry", False,
              [(PTXT, "erplite.patches.declare_todo_status_options",
                "erplite.patches.declare_todo_status_options #2026-10-05")]),
        # execute_patch checks the `execute:` prefix first (patch_handler.py:161)
        # and exec()s the rest. There is no path in the line to resolve.
        Fault("an execute: entry, which frappe exec()s rather than imports", False,
              [(PTXT, "[post_model_sync]\n",
                '[post_model_sync]\nexecute:frappe.db.set_single_value("System Settings", "country", "Australia")\n')]),
        # NOT a false positive, though it reads like one and the probe called it
        # one: at v15.52.0 `execute_patch` resolves the path *before* it looks
        # for the prefix (patch_handler.py:166-167 against :182), and `get_attr`
        # throws AppNotInstalledError on app name "finally:erplite". frappe
        # rejects this entry, so it is a failed deploy and something must say so.
        # Green **here** on purpose: patches.txt is parsed by
        # test_string_references.py and the tripwire for this belongs with the
        # parser, not in a second copy. The same fault is measured against that
        # file in STRING_REFS below.
        Fault("a finally: prefix, which v15 resolves before it strips", False,
              [(PTXT, "erplite.patches.declare_todo_status_options",
                "finally:erplite.patches.declare_todo_status_options")]),

        # -- the recorded measurement, and the tag its claims were read at --
        # MEASURED_OPTIONS is documentation: the live DocField, written down so
        # a reviewer can see what the patch pins without reading the database.
        # The mirror it is compared against is a set, so order was invisible --
        # KNOWN BLIND SPOT, closed by comparing it to this file's own
        # LIVE_OPTIONS as a string.
        Fault("the recorded live options are in the wrong order", True,
              [(TSP, 'MEASURED_OPTIONS = "Backlog\\nPlanned\\nOpen\\nClosed\\nCancelled"',
                'MEASURED_OPTIONS = "Open\\nClosed\\nCancelled\\nBacklog\\nPlanned"')]),
        Fault("the recorded live options lose a status", True,
              [(TSP, 'MEASURED_OPTIONS = "Backlog\\nPlanned\\nOpen\\nClosed\\nCancelled"',
                'MEASURED_OPTIONS = "Backlog\\nPlanned\\nOpen\\nClosed"')]),
        # KNOWN BLIND SPOT, closed by naming the tag. The test asked only for
        # the *shape* v15.x.y, in a docstring whose own point is that the tag is
        # what to re-check the mechanisms against -- so the one edit that makes
        # it misleading was the one it could not see.
        Fault("the docstring names a tag the claims were not read at", True,
              [(TSP, "v15.52.0", "v15.0.0")]),

        # -- controls -------------------------------------------------------
        Fault("control: the local in execute() is renamed", False,
              [(TSP, '    status = frappe.get_meta("ToDo").get_field("status")\n\n'
                     '    _declare("options", options_with_extra_statuses(status.options))',
                '    field = frappe.get_meta("ToDo").get_field("status")\n\n'
                '    _declare("options", options_with_extra_statuses(field.options))')]),
        Fault("control: `options or \"\"` written as an if-expression", False,
              [(TSP, 'lines = (options or "").split("\\n")',
                'lines = (options if options else "").split("\\n")')]),
        Fault("control: the comment above EXTRA_STATUSES is reworded", False,
              [(TSP, "# What the board needs on top of whatever frappe ships.",
                "# The statuses this app adds to whatever frappe ships.")]),
        # THE DISCRIMINATION CONTROL, and the one that found something. The two
        # rows are independent upserts into separately-named documents
        # (`{doc_type}-{field_name}-{property}`, property_setter.py:34-37), each
        # deleting only its own property's row (delete_property_setter, :90-98),
        # both applied by one pass over the table (meta.py:379). Nothing reads
        # the meta again between them. So declaring them the other way round is
        # behaviour-neutral -- and the file went red, in two places, because it
        # unpacked `calls` by position. Pinning the keystrokes, not the contract.
        Fault("control: the two rows are declared in the other order", False,
              [(TSP, '    _declare("options", options_with_extra_statuses(status.options))\n'
                     '    _declare("default", DEFAULT_STATUS)',
                '    _declare("default", DEFAULT_STATUS)\n'
                '    _declare("options", options_with_extra_statuses(status.options))')]),
    ],
)


# --- afterz's timesheet workflow ------------------------------------------
# e585a5b moved the check-out auto-submit into `before_save`, which runs on
# EVERY save -- including all five of Afterz's timesheet paths, each of which
# hands it a Draft row with both times already set. So creation locked the
# entry, submit-week found nothing, and reject and un-approve landed back on
# "Submitted": a rejection that silently re-queues the entry it just rejected,
# with no exception and nothing in the Error Log.
#
# The claim the test file makes is not "before_save is empty" but the general
# one: `status` is a workflow state other apps own, so NO hook on the save path
# may assign it, and the caller that means it says so itself. That is why the
# faults below put the submit in seven different hooks rather than only the one
# it was in -- a test that notices `before_save` and not `validate` is guarding
# a line, not a rule.
#
# The approval gate in the same file is the other half (rev_e73092bfb5): 8126278
# removed `project_manager` from the Project DocType, so the gate that still
# read it refused the one person Afterz shows an Approve button to.

AFZ_SUBMIT_IF_DRAFT = (
    '        if self.check_in_time and self.check_out_time and self.status == "Draft":\n'
    '            self.status = "Submitted"\n')

# before_save's body, as it stands: the end of its docstring, the leftover
# comment, and the `pass` that the test file insists on keeping.
AFZ_BEFORE_SAVE_BODY = ('        # Date field has been removed - no longer needed\n'
                        '        pass\n')

AFZ_VALIDATE_CALLS = ('        self.calculate_duration()\n'
                      '        self.validate_times()\n'
                      '        self.check_overlapping_entries()\n')

AFZ_DURATION_CALL = "        self.calculate_duration()\n"
AFZ_DEFAULT_CALL = "        self.set_employee_default()\n"
AFZ_OVERLAP_CALL = "        self.check_overlapping_entries()\n"

AFZ_DURATION_BOTH = ('            self.duration_hours = time_diff_in_hours('
                     'self.check_out_time, self.check_in_time)\n'
                     '            self.is_active = 0\n')
AFZ_DURATION_OPEN = ('            self.is_active = 1\n'
                     '            self.duration_hours = 0\n'
                     '        else:\n')

AFZ_DEFAULT_RULE = ('        if not self.employee:\n'
                    '            self.employee = frappe.session.user\n')

AFZ_SELF_EXCLUDE = '                "name": ["!=", self.name or ""]\n'
AFZ_OVERLAP_BLOCK = (
    '        active_entries = frappe.get_all("Timesheet Entry", \n'
    '            filters={\n'
    '                "employee": self.employee,\n'
    '                "is_active": 1,\n'
    '                "name": ["!=", self.name or ""]\n'
    '            },\n'
    '            fields=["name", "check_in_time", "project", "activity"]\n'
    '        )\n'
    '        \n'
    '        if active_entries:\n'
    '            entry = active_entries[0]\n'
)

# check_out's submit, and the save it must come before.
AFZ_CHECKOUT_SUBMIT = ('        if timesheet.status == "Draft":\n'
                       '            timesheet.status = "Submitted"\n')
AFZ_CHECKOUT_OWNERSHIP = ('        if timesheet.employee != frappe.session.user:\n'
                          '            frappe.throw(_("You can only check out your own '
                          'timesheet entries"))\n')
AFZ_CHECKOUT_ACTIVE = ('        if not timesheet.is_active:\n'
                       '            frappe.throw(_("This timesheet entry is not active"))\n')

# The gate is written out TWICE, once in approve_timesheet and once in
# reject_timesheet, and the two lines are byte-identical. Only the refusal
# message below each one tells them apart -- which is why every pattern here
# carries it, and why each fault has to be written twice to cover the rule.
AFZ_APPROVE_GATE = (
    '        if project.timesheet_approver != frappe.session.user and not '
    'frappe.has_permission("Timesheet Entry", "write"):\n'
    '            frappe.throw(_("Only the timesheet approver can approve '
    'timesheets for this project"))\n')
AFZ_REJECT_GATE = (
    '        if project.timesheet_approver != frappe.session.user and not '
    'frappe.has_permission("Timesheet Entry", "write"):\n'
    '            frappe.throw(_("Only the timesheet approver can reject '
    'timesheets for this project"))\n')
AFZ_APPROVE_SUBMITTED = ('        if timesheet.status != "Submitted":\n'
                         '            frappe.throw(_("Only submitted timesheets '
                         'can be approved"))\n')
AFZ_REJECT_SUBMITTED = ('        if timesheet.status != "Submitted":\n'
                        '            frappe.throw(_("Only submitted timesheets '
                        'can be rejected"))\n')
AFZ_APPROVE_WRITES = ('        timesheet.status = "Approved"\n'
                      '        timesheet.approved_by = frappe.session.user\n'
                      '        timesheet.approval_date = now_datetime()\n'
                      '        if approval_notes:\n'
                      '            timesheet.approval_notes = approval_notes\n')
AFZ_REJECT_WRITES = ('        timesheet.status = "Rejected"\n'
                     '        timesheet.approved_by = frappe.session.user\n')
AFZ_APPROVE_SWALLOW = ('    except Exception as e:\n'
                       '        frappe.log_error("Timesheet Approval", str(e))\n')


AFTERZ_WORKFLOW = Target(
    test="tests/offline/test_afterz_timesheet_workflow.py",
    faults=[
        # --- the regression itself, restored verbatim ---------------------
        Fault("e585a5b restored: before_save auto-submits, so creation locks "
              "the entry and reject/un-approve land back on Submitted",
              True, [(TSE, AFZ_BEFORE_SAVE_BODY,
                      AFZ_SUBMIT_IF_DRAFT)]),

        # --- the SAME rule in every other save hook -----------------------
        # The claim is not "before_save is empty", it is "no save hook owns
        # status". A test that notices one hook and not the next six is
        # guarding a line. Both halves of the file are in play here: the
        # behavioural tests catch the hooks the driver runs, the AST test
        # catches the ones it does not.
        Fault("the submit moved into validate() instead", True, [
            (TSE, AFZ_VALIDATE_CALLS, AFZ_VALIDATE_CALLS + AFZ_SUBMIT_IF_DRAFT)]),
        Fault("the submit moved into before_validate()", True, [
            (TSE, "    def validate(self):\n",
             "    def before_validate(self):\n" + AFZ_SUBMIT_IF_DRAFT
             + "\n    def validate(self):\n")]),
        Fault("the submit moved into before_insert(), so only creation locks",
              True, [
                  (TSE, "    def calculate_duration(self):\n",
                   "    def before_insert(self):\n" + AFZ_SUBMIT_IF_DRAFT
                   + "\n    def calculate_duration(self):\n")]),
        Fault("the submit moved back into on_update(), where it is discarded "
              "(only the source test can see this one)", True, [
                  (TSE, "    def calculate_duration(self):\n",
                   "    def on_update(self):\n" + AFZ_SUBMIT_IF_DRAFT
                   + "\n    def calculate_duration(self):\n")]),
        Fault("the submit moved into on_change()", True, [
            (TSE, "    def calculate_duration(self):\n",
             "    def on_change(self):\n" + AFZ_SUBMIT_IF_DRAFT
             + "\n    def calculate_duration(self):\n")]),
        Fault("the submit moved into after_insert()", True, [
            (TSE, "    def calculate_duration(self):\n",
             "    def after_insert(self):\n" + AFZ_SUBMIT_IF_DRAFT
             + "\n    def calculate_duration(self):\n")]),
        Fault("the submit moved into on_update_after_submit()", True, [
            (TSE, "    def calculate_duration(self):\n",
             "    def on_update_after_submit(self):\n" + AFZ_SUBMIT_IF_DRAFT
             + "\n    def calculate_duration(self):\n")]),

        # --- the same rule, spelled so the AST test cannot see it ---------
        # `setattr` is an assignment the source test does not recognise, and an
        # augmented assignment is one it does. Two faults, because they are two
        # different claims about which half of the file is load-bearing.
        Fault("before_save submits via setattr, invisible to the source test",
              True, [(TSE, AFZ_BEFORE_SAVE_BODY,
                      '        if self.check_in_time and self.check_out_time '
                      'and self.status == "Draft":\n'
                      '            setattr(self, "status", "Submitted")\n')]),
        Fault("before_save appends to status (an augmented assignment)",
              True, [(TSE, AFZ_BEFORE_SAVE_BODY,
                      '        if self.status == "Draft":\n'
                      '            self.status += "ted"\n')]),

        # --- the rule weakened rather than moved --------------------------
        Fault("before_save submits unconditionally, ignoring the times",
              True, [(TSE, AFZ_BEFORE_SAVE_BODY,
                      '        self.status = "Submitted"\n')]),
        Fault("before_save submits only on creation: the entry is locked the "
              "moment Afterz drags it onto the calendar", True, [
                  (TSE, AFZ_BEFORE_SAVE_BODY,
                   '        if self.is_new() and self.status == "Draft":\n'
                   '            self.status = "Submitted"\n')]),
        Fault("before_save re-submits only on later saves: creation is fine, "
              "reject and un-approve are no-ops", True, [
                  (TSE, AFZ_BEFORE_SAVE_BODY,
                   '        if not self.is_new() and self.status == "Draft":\n'
                   '            self.status = "Submitted"\n')]),
        Fault("the hook deleted outright, so the next person finds no note",
              True, [(TSE, "    def before_save(self):\n",
                      "    def _why_before_save_is_empty(self):\n")]),

        # --- check_out: the half of e585a5b that was right ----------------
        Fault("check_out stops submitting, so approve_timesheet can never be "
              "entered", True, [(TSE, AFZ_CHECKOUT_SUBMIT, "")]),
        Fault("check_out submits AFTER save(), so the status is discarded "
              "exactly as it was before e585a5b", True, [
                  (TSE, AFZ_CHECKOUT_SUBMIT + "        \n" + "        timesheet.save()\n",
                   "        timesheet.save()\n" + AFZ_CHECKOUT_SUBMIT)]),
        Fault("check_out submits whatever the status was, so checking out "
              "un-approves an approved entry", True, [
                  (TSE, AFZ_CHECKOUT_SUBMIT,
                   '        timesheet.status = "Submitted"\n')]),
        Fault("check_out's ownership check removed: anyone may check out "
              "anyone's entry", True, [(TSE, AFZ_CHECKOUT_OWNERSHIP, "")]),
        Fault("check_out's is_active check removed, so a finished entry can be "
              "checked out again and its times rewritten", True, [
                  (TSE, AFZ_CHECKOUT_ACTIVE, "")]),

        # --- validate() must still do its real job ------------------------
        # The fix is "take the status rule out", and the way to get that wrong
        # is to take something else out with it.
        Fault("calculate_duration no longer called: Afterz's hours are never "
              "derived", True, [(TSE, AFZ_DURATION_CALL, "")]),
        Fault("duration computed backwards, so every entry is negative",
              True, [(TSE,
                      'time_diff_in_hours(self.check_out_time, self.check_in_time)',
                      'time_diff_in_hours(self.check_in_time, self.check_out_time)')]),
        Fault("a finished entry left is_active, so the next check-in is "
              "refused as an overlap", True, [
                  (TSE, AFZ_DURATION_BOTH,
                   AFZ_DURATION_BOTH.replace("self.is_active = 0",
                                             "self.is_active = 1"))]),
        Fault("a checked-in entry not marked active, so check_out refuses it",
              True, [(TSE, AFZ_DURATION_OPEN,
                      AFZ_DURATION_OPEN.replace("self.is_active = 1",
                                                "self.is_active = 0"))]),
        Fault("validate_times no longer called, so check-out before check-in "
              "is accepted", True, [(TSE, "        self.validate_times()\n", "")]),
        Fault("the overlap check loses its self-exclusion, so saving an entry "
              "clashes with itself", True, [(TSE, AFZ_SELF_EXCLUDE,
                                             '                "name": ["!=", ""]\n')]),
        Fault("the overlap check no longer called", True,
              [(TSE, AFZ_OVERLAP_CALL, "")]),
        Fault("employee defaulting dropped", True, [(TSE, AFZ_DEFAULT_RULE, "")]),
        Fault("employee overwritten with the session user on every save, so "
              "approving someone's timesheet moves their hours to you",
              True, [(TSE, AFZ_DEFAULT_RULE,
                      "        self.employee = frappe.session.user\n")]),

        # --- the approval gate: TWICE, because it is written twice ---------
        Fault("approve reads a field the DocType no longer declares",
              True, [(TSE, AFZ_APPROVE_GATE,
                      AFZ_APPROVE_GATE.replace("project.timesheet_approver",
                                               "project.project_manager"))]),
        Fault("reject reads a field the DocType no longer declares",
              True, [(TSE, AFZ_REJECT_GATE,
                      AFZ_REJECT_GATE.replace("project.timesheet_approver",
                                              "project.project_manager"))]),
        Fault("approve's gate deleted: anyone may approve", True,
              [(TSE, AFZ_APPROVE_GATE, "")]),
        Fault("reject's gate deleted: anyone may reject", True,
              [(TSE, AFZ_REJECT_GATE, "")]),
        Fault("approve's gate inverted: only people who are NOT the approver "
              "may approve", True, [
                  (TSE, AFZ_APPROVE_GATE,
                   AFZ_APPROVE_GATE.replace(
                       "project.timesheet_approver != frappe.session.user",
                       "project.timesheet_approver == frappe.session.user"))]),
        Fault("reject's gate inverted", True, [
            (TSE, AFZ_REJECT_GATE,
             AFZ_REJECT_GATE.replace(
                 "project.timesheet_approver != frappe.session.user",
                 "project.timesheet_approver == frappe.session.user"))]),
        Fault("approve's write-permission hatch removed, so a Projects "
              "Manager loses approval", True, [
                  (TSE, AFZ_APPROVE_GATE,
                   AFZ_APPROVE_GATE.replace(
                       ' and not frappe.has_permission("Timesheet Entry", "write")',
                       ''))]),
        Fault("reject's write-permission hatch removed", True, [
            (TSE, AFZ_REJECT_GATE,
             AFZ_REJECT_GATE.replace(
                 ' and not frappe.has_permission("Timesheet Entry", "write")',
                 ''))]),
        Fault("approve's gate warns instead of refusing, so the approval still "
              "happens", True, [
                  (TSE, AFZ_APPROVE_GATE,
                   AFZ_APPROVE_GATE.replace("frappe.throw(_(",
                                            "frappe.msgprint(_("))]),
        Fault("reject's gate warns instead of refusing", True, [
            (TSE, AFZ_REJECT_GATE,
             AFZ_REJECT_GATE.replace("frappe.throw(_(",
                                     "frappe.msgprint(_("))]),
        Fault("approve stops requiring Submitted, so a Draft can be approved "
              "straight past the employee", True,
              [(TSE, AFZ_APPROVE_SUBMITTED, "")]),
        Fault("reject stops requiring Submitted", True,
              [(TSE, AFZ_REJECT_SUBMITTED, "")]),

        # --- what approve and reject actually write ------------------------
        Fault("approve leaves the entry Submitted", True, [
            (TSE, '        timesheet.status = "Approved"\n',
             '        timesheet.status = "Submitted"\n')]),
        Fault("reject leaves the entry Submitted, so it stays in the queue",
              True, [(TSE, '        timesheet.status = "Rejected"\n',
                      '        timesheet.status = "Submitted"\n')]),
        Fault("approve does not record who approved", True, [
            (TSE, AFZ_APPROVE_WRITES,
             AFZ_APPROVE_WRITES.replace(
                 "        timesheet.approved_by = frappe.session.user\n", ""))]),
        Fault("reject does not record who rejected", True, [
            (TSE, AFZ_REJECT_WRITES,
             AFZ_REJECT_WRITES.replace(
                 "        timesheet.approved_by = frappe.session.user\n", ""))]),
        Fault("approve discards the notes it was given", True, [
            (TSE, AFZ_APPROVE_WRITES,
             AFZ_APPROVE_WRITES.replace(
                 "            timesheet.approval_notes = approval_notes\n",
                 "            pass\n"))]),
        Fault("a refused approval saves anyway before throwing", True, [
            (TSE, AFZ_APPROVE_SUBMITTED,
             '        timesheet.status = "Approved"\n'
             '        timesheet.save()\n' + AFZ_APPROVE_SUBMITTED)]),

        # --- negative controls ---------------------------------------------
        # Real edits that change no behaviour. A control going red is a finding
        # about the test file, not about the code: it means the file is pinning
        # the way the controller is written rather than what it does.
        Fault("CONTROL: the overlap query's local renamed (must stay green)",
              False, [(TSE, AFZ_OVERLAP_BLOCK,
                       AFZ_OVERLAP_BLOCK.replace("active_entries",
                                                 "clashing_entries"))]),
        Fault("CONTROL: check_out reads the session user through a local "
              "(must stay green)", False, [
                  (TSE, AFZ_CHECKOUT_OWNERSHIP,
                   "        session_user = frappe.session.user\n"
                   + AFZ_CHECKOUT_OWNERSHIP.replace(
                       "frappe.session.user", "session_user"))]),
        Fault("CONTROL: the two derived-field branches reordered into a "
              "positive test (must stay green)", False, [
                  (TSE, '        if self.check_in_time and self.check_out_time:\n'
                        '            self.duration_hours = time_diff_in_hours('
                        'self.check_out_time, self.check_in_time)\n'
                        '            self.is_active = 0\n'
                        '        elif self.check_in_time and not self.check_out_time:\n',
                   '        if self.check_in_time and self.check_out_time is not None:\n'
                   '            self.duration_hours = time_diff_in_hours('
                   'self.check_out_time, self.check_in_time)\n'
                   '            self.is_active = 0\n'
                   '        elif self.check_in_time and not self.check_out_time:\n')]),
    ],
)



# --- the whole-app query-field sweep ---------------------------------------
# tests/offline/test_query_fields.py sweeps every .py under erplite/ and reports
# any query naming a field its DocType does not declare. Its own self-tests
# (TestTheSweepBites) run the detector over synthetic snippets, which proves the
# detector understands a shape -- not that the sweep reaches the shape where it
# really occurs. These faults are the second claim: a real field name in a real
# query in a real file, one per shape and per area of the app, and the sweep has
# to report it.
#
# The two names used most here are the app's own two historical mistakes:
# `Activity.subject` and `Timesheet Entry.date`, both removed from the DocType
# with the column still in the table. A fault that puts one back is the
# regression the sweep exists to stop, not an invented string.

QF_TSE = "erplite/projects/doctype/timesheet_entry/timesheet_entry.py"
QF_PAPI = "erplite/projects/api.py"
QF_SAPI = "erplite/scheduler/api.py"
QF_ACC = "erplite/accounts/doctype/account/account.py"
QF_PINV = "erplite/accounts/doctype/purchase_invoice/purchase_invoice.py"
QF_CUR = "erplite/setup/doctype/currency/currency.py"
QF_XAPI = "erplite/xero/api.py"
QF_SROLE = "erplite/scheduler/doctype/scheduler_role/scheduler_role.py"
QF_SENT = "erplite/scheduler/doctype/schedule_entry/schedule_entry.py"

QUERY_FIELDS = Target(
    test="tests/offline/test_query_fields.py",
    faults=[
        # --- `fields`, the shape the sweep was written for -----------------
        Fault("Timesheet Entry.date is back in a fields list (the removed "
              "column the sweep was written after)", True, [
                  (QF_TSE,
                   '            fields=["name", "check_in_time", "project", "activity"]',
                   '            fields=["name", "date", "project", "activity"]')]),
        Fault("Activity.subject is back in a fields list, as a bare name "
              "beside the alias that is legitimately there", True, [
                  (QF_PAPI,
                   '                fields=["name", "activity_name", "activity_name as subject", "description", "project"],',
                   '                fields=["name", "subject", "activity_name as subject", "description", "project"],')]),
        Fault("a fields list in the scheduler names a Project field that "
              "does not exist", True, [
                  (QF_SAPI,
                   '        fields=["name", "project_name", "status", "project_lead", "division"],',
                   '        fields=["name", "project_name", "status", "project_manager", "division"],')]),
        Fault("a fields list in a DocType controller names a Schedule Entry "
              "field that does not exist", True, [
                  (QF_SENT,
                   'frappe.get_all("Schedule Entry",',
                   'frappe.get_all("Schedule Entry", fields=["booked_by"],')]),
        # Written first as a positional ADDED beside the keyword, which is a
        # TypeError at runtime and which the sweep rightly ignores -- `fields=`
        # wins. A positional-only call is the shape that actually occurs.
        Fault("fields given as get_all's second positional rather than by "
              "keyword", True, [
                  (QF_TSE,
                   'active_entry = frappe.get_all("Timesheet Entry", \n            filters={\n                "employee": frappe.session.user,\n                "is_active": 1\n            },\n            fields=["name", "project", "activity"]',
                   'active_entry = frappe.get_all("Timesheet Entry", ["name", "date"],\n            filters={\n                "employee": frappe.session.user,\n                "is_active": 1\n            }')]),

        # --- `filters`, every form the sweep claims ------------------------
        Fault("a filters dict key names an Activity field that does not "
              "exist", True, [
                  (QF_SAPI,
                   '            filters={"project": project.name, "status": ["!=", "Cancelled"]},',
                   '            filters={"project": project.name, "activity_status": ["!=", "Cancelled"]},')]),
        Fault("a filters dict passed as the second positional, with no "
              "keyword", True, [
                  (QF_CUR,
                   '        if not frappe.db.get_value("Currency", {"is_base_currency": 1}):',
                   '        if not frappe.db.get_value("Currency", {"is_default_currency": 1}):')]),
        Fault("a list-form filter naming the field first", True, [
                  (QF_PAPI,
                   '            filters={"status": ["!=", "Archived"]},\n            order_by="project_name"\n        )\n        \n        result = {}',
                   '            filters=[["project_manager", "=", frappe.session.user]],\n            order_by="project_name"\n        )\n        \n        result = {}')]),
        # Written first as `[[...]] + [...]`, which is a BinOp and not a list
        # literal, so the sweep skipped it -- correctly, by the same rule that
        # makes it skip a non-literal DocType. A literal is the judged shape.
        Fault("a list-form filter naming the DocType then the field", True, [
                  (QF_PAPI,
                   '                filters={\n                    "name": ["in", assigned_activity_names],\n                    "project": ["in", list(result)]\n                },',
                   '                filters=[["Activity", "subject", "like", "%x%"]],')]),
        Fault("an or_filters key names a Project field that does not exist",
              True, [
                  (QF_SAPI,
                   '        filters={"status": ["!=", "Archived"]},\n        order_by="project_name"',
                   '        filters={"status": ["!=", "Archived"]},\n        or_filters={"project_manager": frappe.session.user},\n        order_by="project_name"')]),

        # --- ordering ------------------------------------------------------
        Fault("order_by names a Timesheet Entry field that does not exist",
              True, [
                  (QF_PAPI,
                   '                "employee": user_to_filter\n            },\n            order_by="check_in_time"',
                   '                "employee": user_to_filter\n            },\n            order_by="date desc"')]),
        Fault("group_by names an Activity field that does not exist", True, [
                  (QF_SAPI,
                   '            order_by="activity_name"',
                   '            group_by="assigned_to",\n            order_by="activity_name"')]),

        # --- the fieldname positions ---------------------------------------
        Fault("db.get_value's third positional names an Account field that "
              "does not exist", True, [
                  (QF_ACC,
                   '            is_group = frappe.db.get_value("Account", self.parent_account, "is_group")',
                   '            is_group = frappe.db.get_value("Account", self.parent_account, "is_group_account")')]),
        Fault("db.get_value's third positional is a list, and one entry of "
              "it does not exist", True, [
                  (QF_ACC,
                   '            parent_company = frappe.db.get_value("Account", self.parent_account, "company")',
                   '            parent_company = frappe.db.get_value("Account", self.parent_account, ["company", "cost_centre"])')]),
        Fault("db.set_value's scalar form writes a Purchase Invoice field "
              "that does not exist", True, [
                  (QF_PINV,
                   '            frappe.db.set_value("Purchase Invoice", docname, "status", "Submitted")',
                   '            frappe.db.set_value("Purchase Invoice", docname, "state", "Submitted")')]),
        Fault("db.set_value's dict form writes a Sales Invoice field that "
              "does not exist", True, [
                  ("erplite/xero/accounts.py",
                   '                frappe.db.set_value("Sales Invoice", sales_invoice.name, {',
                   '                frappe.db.set_value("Sales Invoice", sales_invoice.name, {\n                    "xero_pushed_on": None,')]),
        Fault("the fieldname given by keyword rather than by position -- the "
              "form this app already uses in xero/api.py", True, [
                  (QF_XAPI,
                   '                                    fieldname="creation",',
                   '                                    fieldname="synced_at",')]),

        # --- exists / count / pluck ----------------------------------------
        Fault("db.exists filters on a Timesheet Entry field that does not "
              "exist, so the guard is permanently off", True, [
                  (QF_TSE,
                   '        if not self.check_in_time:\n            return',
                   '        if frappe.db.exists("Timesheet Entry", {"date": self.name}):\n            return')]),
        Fault("db.count filters on a Schedule Entry field that does not "
              "exist", True, [
                  (QF_SENT,
                   'frappe.get_all("Schedule Entry",',
                   'frappe.db.count("Schedule Entry", filters={"booked_by": 1}) and frappe.get_all("Schedule Entry",')]),
        Fault("pluck names an Activity field that does not exist", True, [
                  (QF_SAPI,
                   '            fields=["name", "activity_name", "status"],',
                   '            pluck="subject",')]),

        # --- the sweep has to reach every corner of the app ----------------
        Fault("the bad query is in a www/ page controller, not a DocType or "
              "an api module", True, [
                  ("erplite/www/todo/index.py",
                   '    users = frappe.get_all("User",',
                   '    frappe.get_all("Project", fields=["project_manager"])\n    users = frappe.get_all("User",')]),
        Fault("the bad query is in a patch, which runs once against real "
              "data and is the worst place for a silent orphan read", True, [
                  ("erplite/patches/declare_todo_status_options.py",
                   '    setter.db_set("is_system_generated", 1, update_modified=False)',
                   '    frappe.get_all("Project", filters={"project_manager": 1})\n    setter.db_set("is_system_generated", 1, update_modified=False)')]),
        Fault("the bad query is in a dashboard widget module", True, [
                  ("erplite/projects/dashboard_widgets.py",
                   'from frappe import _',
                   'from frappe import _\n\n\ndef _widget_totals():\n    return frappe.get_all("Activity", fields=["subject"])')]),

        # --- the doctype has to be recognised however it is passed ---------
        # Written first as the keyword form alone, which names no undeclared
        # field and so gives the sweep nothing to find -- a fault that changes
        # the shape but not the violation proves only that the shape parses.
        Fault("the DocType is passed as a keyword, so the call has no "
              "positional arguments at all", True, [
                  (QF_SROLE,
                   '\t\tschedule_rows_using_role = frappe.get_all("Schedule Row", \n\t\t\tfilters={"role": self.name},\n\t\t\tfields=["name"]',
                   '\t\tschedule_rows_using_role = frappe.get_all(doctype="Schedule Row",\n\t\t\tfilters={"role": self.name},\n\t\t\tfields=["booked_by"]')]),

        # --- a file the sweep cannot read is a hole in it ------------------
        Fault("a file carrying a bad query is left unparseable, so the sweep "
              "skips it instead of reporting that it cannot see it", True, [
                  (QF_SAPI,
                   '            fields=["name", "activity_name", "status"],',
                   '            fields=["name", "subject", "status"],\n            (')]),

        # --- negative controls ---------------------------------------------
        Fault("CONTROL: a local renamed in a swept file, same query, same "
              "fields", False, [
                  (QF_SROLE,
                   '\t\tschedule_rows_using_role = frappe.get_all("Schedule Row", \n',
                   '\t\trows_using_role = frappe.get_all("Schedule Row", \n'),
                  (QF_SROLE,
                   '\t\tif schedule_rows_using_role:\n\t\t\tfrappe.throw(f"Cannot delete role. It is used in {len(schedule_rows_using_role)} schedule entries")',
                   '\t\tif rows_using_role:\n\t\t\tfrappe.throw(f"Cannot delete role. It is used in {len(rows_using_role)} schedule entries")')]),
        Fault("CONTROL: a declared field added to a fields list", False, [
                  (QF_SAPI,
                   '        fields=["name", "project_name", "status", "project_lead", "division"],',
                   '        fields=["name", "project_name", "status", "project_lead", "division", "project_code"],')]),
        Fault("CONTROL: a standard column every table has, named explicitly",
              False, [
                  (QF_TSE,
                   '            fields=["name", "check_in_time", "project", "activity"]',
                   '            fields=["name", "check_in_time", "project", "activity", "modified_by"]')]),
        Fault("CONTROL: an alias and a SQL expression, which the sweep must "
              "not judge", False, [
                  (QF_SAPI,
                   '            fields=["name", "activity_name", "status"],',
                   '            fields=["name", "activity_name as subject", "count(name) as n", "status"],')]),
    ],
)



# --- the whole-app undeclared-attribute sweep ------------------------------
# tests/offline/test_undeclared_attributes.py holds three whole-app sweeps:
# `self.<x>` read in a controller (split into hot -- reachable from a hook that
# runs on a document built in memory, so it raises -- and cold), `<doc>.<y>`
# read off a document built in memory, and `<doc>.<y> = v` written on any
# document however it was obtained.
#
# Unlike test_query_fields.py this file has no self-tests at all, so nothing has
# ever asked whether these sweeps reach the shapes they claim. The two names
# used most below are the app's own historical mistakes -- `Timesheet Entry.date`
# and `Schedule Row.task`, both named in the file's docstring as what it exists
# to stop -- so a fault that puts one back is a regression, not an invention.

UA_TSE = "erplite/projects/doctype/timesheet_entry/timesheet_entry.py"
UA_SROW = "erplite/scheduler/doctype/schedule_row/schedule_row.py"
UA_SROW_JSON = "erplite/scheduler/doctype/schedule_row/schedule_row.json"
UA_PAPI = "erplite/projects/api.py"
UA_ACC = "erplite/accounts/doctype/account/account.py"
UA_CUR = "erplite/setup/doctype/currency/currency.py"

UNDECLARED_ATTRS = Target(
    test="tests/offline/test_undeclared_attributes.py",
    faults=[
        # --- test 1: `self.<x>` read in a DocType's own controller ---------
        Fault("a hook reads self.date, the removed Timesheet Entry field "
              "(hot: runs on a new document, so the save raises)", True, [
                  (UA_TSE,
                   '        if self.check_in_time and self.check_out_time:\n'
                   '            self.duration_hours = time_diff_in_hours(self.check_out_time, self.check_in_time)',
                   '        if self.date and self.check_out_time:\n'
                   '            self.duration_hours = time_diff_in_hours(self.check_out_time, self.date)')]),
        Fault("a helper two self-calls from validate() reads an undeclared "
              "field (so the hot set has to follow self-call edges)", True, [
                  (UA_TSE,
                   '        if self.check_in_time and self.check_out_time:\n'
                   '            if get_datetime(self.check_in_time) >= get_datetime(self.check_out_time):',
                   '        if self.entry_date and self.check_out_time:\n'
                   '            if get_datetime(self.entry_date) >= get_datetime(self.check_out_time):')]),
        Fault("a read naming a field that IS declared -- on another DocType "
              "(so the sweep has to resolve per DocType, not app-wide)", True, [
                  (UA_TSE,
                   '                "employee": self.employee,\n'
                   '                "is_active": 1,',
                   '                "employee": self.resource_name,\n'
                   '                "is_active": 1,')]),
        Fault("a cold read: on_trash() runs only on a loaded document, so it "
              "is a stale orphan column rather than a raise", True, [
                  (UA_ACC,
                   'frappe.throw(_("Cannot delete account {0} as it has child accounts").format(self.name))',
                   'frappe.throw(_("Cannot delete account {0} as it has child accounts").format(self.account_label))')]),
        # The file's stated position is that a controller may invent its own
        # attributes: `scan.assigned` is added to the known set, so reading one
        # back is legitimate. This control holds that position to it.
        Fault("CONTROL: a transient the controller assigns itself, then reads "
              "back -- no behaviour change, and declared nowhere", False, [
                  (UA_TSE,
                   '            self.is_active = 1\n'
                   '            self.duration_hours = 0',
                   '            self._open_entry = 1\n'
                   '            self.is_active = self._open_entry\n'
                   '            self.duration_hours = 0')]),

        # --- test 2: a read off a document built in memory -----------------
        Fault("get_doc({\"doctype\": ...}) then reads the removed `date` "
              "field, so check-in raises instead of returning", True, [
                  (UA_TSE,
                   '            "timesheet_id": timesheet.name\n',
                   '            "timesheet_id": timesheet.name,\n'
                   '            "date": timesheet.date\n')]),
        Fault("new_doc(\"Schedule Row\") then reads an undeclared field as a "
              "fallback, so creating a row raises", True, [
                  (UA_SROW,
                   '    doc.resource = resource\n',
                   '    doc.resource = resource or doc.default_resource\n')]),
        # include_loaded=False is deliberate and the docstring argues it: a
        # loaded document is populated from SELECT *, so an orphan column is
        # present and reading it returns a stale value instead of raising.
        # This is that documented scope limit, not a control.
        Fault("SCOPE LIMIT: a read off a document LOADED by get_doc(\"X\", "
              "name) -- stale, not a raise, deliberately out of scope", False, [
                  (UA_TSE,
                   '        if timesheet.employee != frappe.session.user:',
                   '        if timesheet.booked_for != frappe.session.user:')]),
        # One function, two bindings of one name: the update branch LOADS a
        # Timesheet Entry and the insert branch NEW_DOCs one. The read sweep
        # drops the whole variable because the loaded binding is unresolved
        # under include_loaded=False -- although the new-doc branch is still
        # there and still raises.
        Fault("a read in the new_doc branch of a function whose other branch "
              "loads the same DocType into the same name", True, [
                  (UA_PAPI,
                   '                timesheet_doc.status = "Draft"\n'
                   '                timesheet_doc.insert()\n'
                   '                saved_entries.append({\n'
                   '                    "temp_id": entry.get(\'temp_id\'),\n'
                   '                    "id": timesheet_doc.name,\n'
                   '                    "project": project,\n'
                   '                    "activity": activity,\n'
                   '                    "date": date,',
                   '                timesheet_doc.status = "Draft"\n'
                   '                timesheet_doc.insert()\n'
                   '                saved_entries.append({\n'
                   '                    "temp_id": entry.get(\'temp_id\'),\n'
                   '                    "id": timesheet_doc.name,\n'
                   '                    "project": project,\n'
                   '                    "activity": activity,\n'
                   '                    "date": timesheet_doc.date,')]),

        # --- test 3: a write dropped on save ------------------------------
        Fault("Schedule Row.task is written again -- the exact regression this "
              "file was written after: the row saves with no work attached", True, [
                  (UA_SROW,
                   '    activity = activity or task\n'
                   '    if activity:\n',
                   '    doc.task = task\n'
                   '    activity = activity or task\n'
                   '    if activity:\n')]),
        Fault("a write on a document LOADED by get_doc(\"X\", name) -- the "
              "load-then-modify shape, which is most of the app", True, [
                  (UA_TSE,
                   '        timesheet.check_out_time = now_datetime()\n',
                   '        timesheet.check_out_time = now_datetime()\n'
                   '        timesheet.closed_on = now_datetime()\n')]),
        Fault("a write naming a field declared on another DocType, on a new "
              "document (so the write sweep resolves per DocType too)", True, [
                  (UA_SROW,
                   '    doc.daily_entries = "{}"\n',
                   '    doc.schedule_date = "{}"\n')]),
        # --- the shapes a write can take that are not `doc.x = v` ----------
        # `self.db_set("x", v)` is the one the app actually writes: five of the
        # six db_set sites in the tree are this form, in DocType controllers.
        Fault("a write through self.db_set(\"x\", v) with a fieldname the "
              "DocType does not declare", True, [
                  (UA_CUR,
                   '            self.db_set("is_base_currency", 1)\n',
                   '            self.db_set("is_base_currency_flag", 1)\n')]),
        # Nothing in the app writes an undeclared attribute on `self` today --
        # measured, zero sites -- so this costs no noise to guard.
        Fault("a controller writes self.<undeclared> = v: the hours are "
              "computed, dropped on save, and the entry still saves", True, [
                  (UA_TSE,
                   '            self.duration_hours = time_diff_in_hours(self.check_out_time, self.check_in_time)\n',
                   '            self.total_hours = time_diff_in_hours(self.check_out_time, self.check_in_time)\n')]),
        Fault("a write through setattr(doc, \"task\", task) rather than an "
              "attribute assignment", True, [
                  (UA_SROW,
                   '    doc.daily_entries = "{}"\n',
                   '    setattr(doc, "task", task)\n'
                   '    doc.daily_entries = "{}"\n')]),
        Fault("a write through doc.update({...}) with an undeclared key", True, [
                  (UA_SROW,
                   '    doc.daily_entries = "{}"\n',
                   '    doc.update({"task": task})\n'
                   '    doc.daily_entries = "{}"\n')]),
        # frappe's Document.set(fieldname, value) is the fourth shape the walker reads. No
        # site in the app writes this way today, so these two cost nothing in noise -- but a
        # shape the walker claims to cover and nothing measures is the hole this target is
        # about, so both halves (on `self` and on a local) are planted.
        Fault("a write through self.set(\"x\", v) with a fieldname the DocType "
              "does not declare", True, [
                  (UA_CUR,
                   '            self.db_set("exchange_rate", 1)\n',
                   '            self.set("exchange_rate_value", 1)\n')]),
        Fault("a write through doc.set(\"x\", v) on a document built in memory", True, [
                  (UA_SROW,
                   '    doc.daily_entries = "{}"\n',
                   '    doc.set("task", task)\n'
                   '    doc.daily_entries = "{}"\n')]),

        # --- whether the sweep READ the file the violation is in -----------
        # Same class as the third finding in test_query_fields.py: a sweep that
        # reads nothing passes exactly like a sweep that finds nothing.
        Fault("a real violation in a DocType controller the sweep cannot "
              "parse: red, but from the SyntaxError, not from the finding", True, [
                  (UA_SROW,
                   '    activity = activity or task\n'
                   '    if activity:\n',
                   '    doc.task = task\n'
                   '    activity = activity or task\n'
                   '    if activity:\n'),
                  (UA_SROW,
                   'from typing import Dict, Any',
                   'from typing import Dict, Any\n(((')]),
        # The schema side of the same question, and the worse half: the
        # DocType's declared-field list is what "undeclared" is measured
        # against, and a JSON the sweep cannot read drops the DocType from the
        # map entirely -- so every violation on it becomes unreportable.
        Fault("a real violation on a DocType whose JSON cannot be parsed (the "
              "declared-field list silently becomes unknown)", True, [
                  (UA_SROW,
                   '    activity = activity or task\n'
                   '    if activity:\n',
                   '    doc.task = task\n'
                   '    activity = activity or task\n'
                   '    if activity:\n'),
                  (UA_SROW_JSON,
                   ' "field_order": [',
                   ' "field_order": [[')]),

        # The fault above went red, but from the FIRST sweep hitting a
        # SyntaxError rather than from the violation being found: that sweep
        # calls ast.parse with no handler, and schedule_row.py happens to be a
        # DocType controller. These two measure the same question in a file no
        # controller sweep opens.
        Fault("a write violation in projects/api.py, to pin the pair below", True, [
                  (UA_PAPI,
                   '                timesheet_doc.is_active = 0\n',
                   '                timesheet_doc.date = date\n'
                   '                timesheet_doc.is_active = 0\n')]),
        Fault("the same violation in the same file, which the sweep now cannot "
              "parse: no controller sweep opens it, so nothing is red", True, [
                  (UA_PAPI,
                   '                timesheet_doc.is_active = 0\n',
                   '                timesheet_doc.date = date\n'
                   '                timesheet_doc.is_active = 0\n'),
                  (UA_PAPI,
                   'import frappe\n',
                   'import frappe\n(((\n')]),
        # --- controls ------------------------------------------------------
        Fault("CONTROL: the local holding the new document is renamed "
              "throughout create_schedule_row", False, [
                  (UA_SROW,
                   '    doc = frappe.new_doc("Schedule Row")\n'
                   '    doc.project = project\n',
                   '    row = frappe.new_doc("Schedule Row")\n'
                   '    row.project = project\n'),
                  (UA_SROW,
                   '        doc.activity = activity\n'
                   '    doc.resource = resource\n'
                   '    doc.daily_entries = "{}"\n'
                   '    doc.insert()\n'
                   '    \n'
                   '    return doc.name',
                   '        row.activity = activity\n'
                   '    row.resource = resource\n'
                   '    row.daily_entries = "{}"\n'
                   '    row.insert()\n'
                   '    \n'
                   '    return row.name')]),
        # The conservative rule the file documents: a name that does not
        # resolve to one DocType on every path is dropped, so a disagreement is
        # never reported. A violation hidden behind a disagreement is the price.
        Fault("SCOPE LIMIT: the violation is on a name also bound from a "
              "different DocType in the same function, so it is dropped", False, [
                  (UA_SROW,
                   '    activity = activity or task\n'
                   '    if activity:\n',
                   '    doc.task = task\n'
                   '    if not project:\n'
                   '        doc = frappe.new_doc("Schedule Entry")\n'
                   '    activity = activity or task\n'
                   '    if activity:\n')]),
    ],
)



# --- mandatory fields at insert ------------------------------------------
# rev_f9dce41f7f: a `frappe.get_doc({...}).insert()` must supply the DocType's
# mandatory fields. The sweep reads the dict literals statically and compares
# their keys against every `reqd` field in the app's 47 DocType JSONs.
#
# The sixteenth target, and the second of the two files the README listed as
# doing fault injection of their own. What that proved was narrower than it
# looked: both of its self-injections remove a *key* from a dict it has already
# parsed, so the only shape it ever tested is the one its author planted.
# Every fault below that goes green is a shape frappe raises on and the sweep
# calls supplied.
#
# Each fault's expectation is traced through frappe-version-15, not recalled.
# The one line that decides all of it is base_document.py:761-762:
#
#     for df in self.meta.get("fields", {"reqd": ("=", 1)}):
#         if self.get(df.fieldname) in (None, []) or not has_content(df):
#
# Note the second clause. The test file's own docstring describes only the
# first ("counts any reqd field whose value is in (None, [])"), and that
# omission is why "the key is present" reads as sufficient: `has_content`
# cstr()s the value and strips HTML and whitespace off it, so "", "   " and
# "<p></p>" are all missing too. Presence of a key is not content.

MFI_ACC = "erplite/xero/accounts.py"
MFI_XAPI = "erplite/xero/api.py"
MFI_CUST_JSON = "erplite/crm/doctype/customer/customer.json"
MFI_XSL_JSON = "erplite/setup/doctype/xero_sync_log/xero_sync_log.json"

# The anchor for an edit to the customer_type field, stopping short of the
# "options" line on purpose: that line holds JSON-escaped \\n, which is a
# backslash and an n in the file and would be read as a newline in a pattern.
MFI_CT_ANCHOR = ('   "fieldname": "customer_type",\n'
                 '   "fieldtype": "Select",\n')
MFI_CN_ANCHOR = ('   "fieldname": "customer_name",\n'
                 '   "fieldtype": "Data",\n')
MFI_COMPANY_ANCHOR = ('   "fieldname": "company",\n'
                      '   "fieldtype": "Link",\n')

MFI_SYNC_LOG_CALL = ('        sync_log = frappe.get_doc({\n'
                     '            "doctype": "Xero Sync Log",\n')

MANDATORY_FIELDS = Target(
    test="tests/offline/test_mandatory_fields_on_insert.py",
    faults=[
        # --- the bug it was written for, at both call sites ---------------
        Fault("the original bug: Customer built without customer_type", True, [
            (MFI_ACC,
             '                    "customer_type": "Company",\n', '')]),
        Fault("the original bug: Supplier built without supplier_type", True, [
            (MFI_ACC,
             '                    "supplier_type": "Company",\n', '')]),
        # The rule is about every reqd field, not the two that were found.
        Fault("Customer built without customer_name, the other reqd field",
              True, [
                  (MFI_ACC,
                   '                    "customer_name": contact["Name"],\n',
                   '')]),
        Fault("Supplier built without supplier_name", True, [
            (MFI_ACC,
             '                    "supplier_name": contact["Name"],\n', '')]),

        # --- the key is there and cannot satisfy frappe -------------------
        # base_document.py:762, first clause: None is missing.
        Fault("customer_type supplied as None -- the key is present and "
              "insert() still raises MandatoryError", True, [
                  (MFI_ACC,
                   '"customer_type": "Company",',
                   '"customer_type": None,')]),
        # Second clause, and worse than it looks: update_if_missing only fills
        # a field whose value `is None` (base_document.py:197), so passing ""
        # also defeats any default the DocType might have had.
        Fault("customer_type supplied as the empty string", True, [
            (MFI_ACC,
             '"customer_type": "Company",',
             '"customer_type": "",')]),
        Fault("customer_name supplied as whitespace -- has_content strips it",
              True, [
                  (MFI_ACC,
                   '"customer_name": contact["Name"],',
                   '"customer_name": "   ",')]),
        # The realistic one: every optional field in this dict is already
        # written `.get(key, "")`. Writing a reqd field that way is a one-word
        # edit, reads as more careful than the original, and reintroduces the
        # exact production failure for any Xero contact with no Name.
        Fault("customer_name supplied as contact.get(\"Name\", \"\") -- the "
              "shape every optional field in the same dict already uses",
              True, [
                  (MFI_ACC,
                   '"customer_name": contact["Name"],',
                   '"customer_name": contact.get("Name", ""),')]),

        # --- the two DocType-side exemptions frappe does not honour -------
        # The sweep skips a reqd field with a default. frappe applies a static
        # default only `if df.get("default")` (model/create_new.py:101) -- a
        # truthiness test, where the sweep's is `is not None`. An empty-string
        # default is therefore skipped by the sweep and never applied by
        # frappe, so insert() raises with nothing to point at.
        Fault("reqd customer_type given an empty-string default, and the key "
              "removed: a falsy default is never applied", True, [
                  (MFI_CUST_JSON, MFI_CT_ANCHOR,
                   MFI_CT_ANCHOR + '   "default": "",\n'),
                  (MFI_ACC,
                   '                    "customer_type": "Company",\n', '')]),
        # The sweep skips a reqd field that is read_only, reasoning that it
        # "cannot be passed in anyway". _get_missing_mandatory_fields does not
        # exempt read_only, and a server-side dict can set it, so the premise
        # is wrong in both directions: the insert fails, and the caller is the
        # one who could have fixed it.
        Fault("reqd customer_type made read_only, and the key removed: "
              "read_only is not exempt from mandatory validation", True, [
                  (MFI_CUST_JSON, MFI_CT_ANCHOR,
                   MFI_CT_ANCHOR + '   "read_only": 1,\n'),
                  (MFI_ACC,
                   '                    "customer_type": "Company",\n', '')]),

        # Isolating the two exemptions. The pair above remove a key from a
        # dict that this file's own self-injection asserts is passed, so their
        # RED may be that assertion rather than the sweep. Xero Sync Log is in
        # no self-test, so here only the sweep can speak.
        Fault("ISOLATED: company made reqd on Xero Sync Log with an "
              "empty-string default -- skipped by the sweep, never applied by "
              "frappe", True, [
                  (MFI_XSL_JSON, MFI_COMPANY_ANCHOR,
                   MFI_COMPANY_ANCHOR + '   "reqd": 1,\n   "default": "",\n')]),
        Fault("ISOLATED: company made reqd and read_only on Xero Sync Log -- "
              "skipped by the sweep, not exempt from mandatory validation",
              True, [
                  (MFI_XSL_JSON, MFI_COMPANY_ANCHOR,
                   MFI_COMPANY_ANCHOR + '   "reqd": 1,\n   "read_only": 1,\n')]),
        # --- a reqd field appearing on a DocType an insert site misses ----
        # The rule's stated value is that it "goes red the day somebody adds a
        # reqd field to a DocType that an existing insert site does not pass".
        # This is that day, on a second DocType and a second file, and it is
        # the control for the three call-site shapes below it.
        Fault("company made reqd on Xero Sync Log, which xero/api.py's sync "
              "log does not supply", True, [
                  (MFI_XSL_JSON, MFI_COMPANY_ANCHOR,
                   MFI_COMPANY_ANCHOR + '   "reqd": 1,\n')]),

        # --- call-site shapes the AST walker cannot see --------------------
        # Same regression as the fault above, with the call rewritten three
        # ways that change nothing about what frappe does.
        Fault("the same regression, with the call written "
              "frappe.get_doc(dict(...)) -- args[0] is a Call, not a Dict",
              True, [
                  (MFI_XSL_JSON, MFI_COMPANY_ANCHOR,
                   MFI_COMPANY_ANCHOR + '   "reqd": 1,\n'),
                  (MFI_XAPI,
                   MFI_SYNC_LOG_CALL +
                   '            "start_time": now_datetime(),\n'
                   '            "status": "In Progress"\n'
                   '        })\n',
                   '        sync_log = frappe.get_doc(dict(\n'
                   '            doctype="Xero Sync Log",\n'
                   '            start_time=now_datetime(),\n'
                   '            status="In Progress",\n'
                   '        ))\n')]),
        Fault("the same regression, with get_doc reached through a local name "
              "-- node.func is an ast.Name, not an ast.Attribute", True, [
                  (MFI_XSL_JSON, MFI_COMPANY_ANCHOR,
                   MFI_COMPANY_ANCHOR + '   "reqd": 1,\n'),
                  (MFI_XAPI,
                   '        sync_log = frappe.get_doc({\n',
                   '        _new = frappe.get_doc\n'
                   '        sync_log = _new({\n')]),
        # This one also asks what the "found something to check" guard is
        # worth. It asserts >= 5 sites and there are 6, so exactly one site
        # can disappear without the guard noticing.
        Fault("the same regression, with the doctype read from a local "
              "variable -- the site is dropped, and the >= 5 sites guard has "
              "6 to spend", True, [
                  (MFI_XSL_JSON, MFI_COMPANY_ANCHOR,
                   MFI_COMPANY_ANCHOR + '   "reqd": 1,\n'),
                  (MFI_XAPI, MFI_SYNC_LOG_CALL,
                   '        _dt = "Xero Sync Log"\n'
                   '        sync_log = frappe.get_doc({\n'
                   '            "doctype": _dt,\n')]),

        # --- negative controls --------------------------------------------
        # Real edits that change no behaviour. If either goes red the sweep is
        # pinning source text rather than the rule.
        Fault("CONTROL: the sync log call broken across lines, same dict",
              False, [
                  (MFI_XAPI,
                   '        sync_log = frappe.get_doc({\n',
                   '        sync_log = frappe.get_doc(\n'
                   '            {\n')]),
        Fault("CONTROL: customer_name marked bold in the DocType JSON, which "
              "is presentation and nothing to do with the rule", False, [
                  (MFI_CUST_JSON, MFI_CN_ANCHOR,
                   MFI_CN_ANCHOR + '   "bold": 1,\n')]),
    ],
)


# --- erplite/projects Activity queries -------------------------------------
# The timesheet calendar, the admin assignment dialog and the assignment
# endpoint itself: three whitelisted endpoints that read Activity through
# Frappe's standard assignment mechanism (a ToDo row per assignee).

PA = "erplite/projects/api.py"

# The two "Get all projects" blocks are byte-identical. Each pattern therefore
# carries the line that follows the block, which is what tells them apart:
# get_projects_and_activities continues into the ToDo query, while
# get_all_projects_and_activities continues into `result = {}`.
PROJ_BLOCK = (
    '            filters={"status": ["!=", "Archived"]},\n'
    '            order_by="project_name"\n'
    '        )\n'
    '        \n'
)
GPA_TAIL = "        # Activities assigned to this user"
GAPA_TAIL = "        result = {}\n"

NO_FILTER = (
    '            filters={},\n'
    '            order_by="project_name"\n'
    '        )\n'
    '        \n'
)

PROJECTS_API = Target("tests/offline/test_projects_api.py", [

    # --- get_projects_and_activities: the timesheet calendar ---------------
    Fault("gpa: archived projects are listed again", True, [
        (PA, PROJ_BLOCK + GPA_TAIL, NO_FILTER + GPA_TAIL)]),

    Fault("gpa: cancelled and closed assignments count again", True, [
        (PA, '                "allocated_to": user_to_filter,\n'
             '                "status": ["not in", ["Cancelled", "Closed"]]\n',
             '                "allocated_to": user_to_filter\n')]),

    Fault("gpa: every user's activities are listed, not just this user's", True, [
        (PA, '                "allocated_to": user_to_filter,\n',
             '                "allocated_to": ["is", "set"],\n')]),

    Fault("gpa: any user may view another user's activities", True, [
        (PA, "        if target_user and is_timesheet_admin():\n"
             "            # Admin viewing another user's activities\n"
             "            user_to_filter = target_user\n"
             "        else:\n"
             "            # Regular user or admin viewing their own activities\n"
             "            user_to_filter = frappe.session.user\n"
             "        \n"
             "        # Get all projects\n",
             "        user_to_filter = frappe.session.user\n"
             "        \n"
             "        # Get all projects\n")]),

    Fault("gpa: the title field is not selected (blank labels return)", True, [
        (PA, '                fields=["name", "activity_name", "activity_name as subject", "description", "project"],\n',
             '                fields=["name", "activity_name as subject", "description", "project"],\n')]),

    Fault("gpa: the subject alias older front-end code reads is dropped", True, [
        (PA, '                fields=["name", "activity_name", "activity_name as subject", "description", "project"],\n',
             '                fields=["name", "activity_name", "description", "project"],\n')]),

    Fault("gpa: activities are not confined to the listed projects", True, [
        (PA, '                    "name": ["in", assigned_activity_names],\n'
             '                    "project": ["in", list(result)]\n',
             '                    "name": ["in", assigned_activity_names]\n')]),

    # --- get_all_projects_and_activities: the admin assignment dialog ------
    Fault("gapa: archived projects are listed again", True, [
        (PA, PROJ_BLOCK + GAPA_TAIL, NO_FILTER + GAPA_TAIL)]),

    Fault("gapa: cancelled and closed assignments are reported as current", True, [
        (PA, '                    "status": ["not in", ["Cancelled", "Closed"]],\n'
             '                    "allocated_to": ["is", "set"]\n',
             '                    "allocated_to": ["is", "set"]\n')]),

    Fault("gapa: unallocated todos are counted as assignees", True, [
        (PA, '                    "status": ["not in", ["Cancelled", "Closed"]],\n'
             '                    "allocated_to": ["is", "set"]\n',
             '                    "status": ["not in", ["Cancelled", "Closed"]]\n')]),

    Fault("gapa: the subject alias the dialog's older code reads is dropped", True, [
        (PA, '                fields=["name", "activity_name", "activity_name as subject", "description"],\n',
             '                fields=["name", "activity_name", "description"],\n')]),

    Fault("gapa: only the first assignee is reported", True, [
        (PA, '                activity["assigned_users"] = allocated\n',
             '                activity["assigned_users"] = allocated[:1]\n')]),

    Fault("gapa: assigned_to is never reported", True, [
        (PA, '                activity["assigned_to"] = allocated[0] if allocated else None\n',
             '                activity["assigned_to"] = None\n')]),

    Fault("gapa: any user may open the admin assignment dialog", True, [
        (PA, '        if not is_timesheet_admin():\n'
             '            return {"success": False, "message": "Access denied"}\n'
             '        \n'
             '        # Get all projects\n',
             '        # Get all projects\n')]),

    # --- assign_activities_to_user ----------------------------------------
    Fault("assign: any user may assign activities to anyone", True, [
        (PA, '        if not is_timesheet_admin():\n'
             '            return {"success": False, "message": "Access denied"}\n'
             '        \n'
             '        # Parse assignments if it\'s a JSON string\n',
             '        # Parse assignments if it\'s a JSON string\n')]),

    Fault("assign: assigning does nothing (reports success, persists nothing)", True, [
        (PA, '                add_assignment({\n'
             '                    "doctype": "Activity",\n'
             '                    "name": activity_id,\n'
             '                    "assign_to": [user]\n'
             '                })\n',
             '                pass\n')]),

    Fault("assign: unassigning does nothing", True, [
        (PA, '                remove_assignment("Activity", activity_id, user)\n',
             '                pass\n')]),

    Fault("assign: an unknown activity is no longer skipped", True, [
        (PA, '            if not frappe.db.exists("Activity", activity_id):\n'
             '                continue\n\n',
             '')]),

    Fault("assign: a JSON string from the front end is no longer parsed", True, [
        (PA, '        if isinstance(activity_assignments, str):\n'
             '            activity_assignments = json.loads(activity_assignments)\n',
             '        pass\n')]),

    Fault("assign: omitting 'assign' now assigns instead of leaving alone", True, [
        (PA, "            should_assign = assignment.get('assign', False)\n",
             "            should_assign = assignment.get('assign', True)\n")]),

    Fault("assign: unassignments are not counted in the reported total", True, [
        (PA, '            updated_count += 1\n',
             '            updated_count += 1 if should_assign else 0\n')]),

    # --- controls: real edits that change no behaviour ---------------------
    # This one was written as a fault and came back green, and the green was
    # right: `if not activity_id: continue` is genuinely redundant, so a test
    # going red on its removal would be pinning an internal.
    #
    # It was nearly reported as a gap on the reasoning that the stand-in was
    # kinder than frappe -- that `exists(dt, "")` has no WHERE clause and
    # returns the first row. That is wrong, and the code path says so
    # (frappe 15.52.0, read on the bench):
    #
    #   exists(dt, dn)          -> get_value(dt, dn, ignore=True)      :1259
    #   get_values: `if (filters is not None) and ...`                 :612
    #     dn is None -> else branch -> get_values_from_single, which reads
    #                   tabSingles. Activity is not a Single, so: empty.
    #     dn is ""   -> apply_filters: `{"name": str(filters)}`  query.py:122
    #                   -> a real WHERE name = '' -> no row.
    #
    # Verified read-only against the live site, which holds 23 Activity rows:
    #   exists("Activity", None) -> None      exists("Activity", "") -> None
    #   exists("Activity", "g68cfomvvu") -> 'g68cfomvvu'
    #
    # So the stand-in's False was faithful, not kind. Kept as a control so the
    # claim cannot be quietly reintroduced.
    Fault("CONTROL assign: the redundant blank-id guard removed", False, [
        (PA, '            if not activity_id:\n'
             '                continue\n\n',
             '')]),

    Fault("CONTROL gapa: columns selected in a different order", False, [
        (PA, '                fields=["name", "activity_name", "activity_name as subject", "description"],\n',
             '                fields=["description", "name", "activity_name as subject", "activity_name"],\n')]),

    Fault("CONTROL gapa: which of several assignees is 'the' one is unspecified", False, [
        (PA, '                activity["assigned_to"] = allocated[0] if allocated else None\n',
             '                activity["assigned_to"] = allocated[-1] if allocated else None\n')]),

    Fault("CONTROL gapa: setdefault written out as an explicit branch", False, [
        (PA, '                assignees.setdefault(todo.reference_name, []).append(todo.allocated_to)\n',
             '                if todo.reference_name not in assignees:\n'
             '                    assignees[todo.reference_name] = []\n'
             '                assignees[todo.reference_name].append(todo.allocated_to)\n')]),

    Fault("CONTROL gpa: the result dict built by a loop rather than a comprehension", False, [
        (PA, '        result = {\n'
             '            project.name: {\n'
             '                "project_name": project.project_name,\n'
             '                "activities": []\n'
             '            }\n'
             '            for project in projects\n'
             '        }\n',
             '        result = {}\n'
             '        for project in projects:\n'
             '            result[project.name] = {\n'
             '                "project_name": project.project_name,\n'
             '                "activities": []\n'
             '            }\n')]),
])

# --- the whole-app raw-SQL literal guard -----------------------------------
# tests/offline/test_raw_sql.py is the app's only *security* guard: the first
# argument to frappe.db.sql (and sql_list / sql_value / multisql) must be a
# plain string literal, because only the `values` argument is escaped. Anything
# spliced into the query string is SQL syntax, not data.
#
# The faults below are the six non-literal shapes `classify_query_arg` names,
# each written at a real db.sql site in this app and each splicing a value that
# a caller can reach -- so every one of them is the bug the guard was written
# for (`get_activity_summary`, fixed), put back somewhere else.
#
# Two of them ask the question the file's own "known blind spots" section
# raises and does not answer: a query handed to a `.sql()` on a receiver the
# walker declines to recognise. The docstring says those are "listed by the
# pass as skipped rather than silently dropped, so the count is visible". They
# are not: `skipped` is collected in the sweep and never read.

RS_SAPI = "erplite/scheduler/api.py"
RS_RES = "erplite/scheduler/doctype/resource/resource.py"
RS_SENT = "erplite/scheduler/doctype/schedule_entry/schedule_entry.py"
RS_FY = "erplite/setup/doctype/fiscal_year/fiscal_year.py"
RS_FB = "erplite/setup/doctype/finance_book/finance_book.py"
RS_CUR = "erplite/setup/doctype/currency/currency.py"
RS_SLOG = "erplite/scheduler/doctype/scheduler_log/scheduler_log.py"
RS_STMPL = "erplite/scheduler/doctype/schedule_template/schedule_template.py"

# The utilisation query, as it stands: parameterised, both values in `values`.
RS_UTIL_OLD = (
    '    result = frappe.db.sql("""\n'
    '        SELECT COALESCE(SUM(duration), 0) as total_hours\n'
    '        FROM `tabSchedule Entry`\n'
    '        WHERE resource = %s AND schedule_date = %s AND docstatus != 2\n'
    '    """, (resource, date))'
)
# ... and spliced, which is the shape of the bug this guard exists to stop.
RS_UTIL_FSTRING = (
    '        SELECT COALESCE(SUM(duration), 0) as total_hours\n'
    '        FROM `tabSchedule Entry`\n'
    "        WHERE resource = '{resource}' AND schedule_date = '{date}' "
    'AND docstatus != 2\n'
)

RS_CAPACITY_OLD = (
    '        scheduled_hours = frappe.db.sql("""\n'
    '            SELECT COALESCE(SUM(duration), 0) as total_hours\n'
    '            FROM `tabSchedule Entry`\n'
    '            WHERE resource = %s AND schedule_date = %s AND docstatus != 2\n'
    '        """, (self.name, date))[0][0]'
)

RS_OVERLAP_OLD = (
    '        overlapping = frappe.db.sql("""\n'
    '            SELECT name, start_time, end_time, project\n'
    '            FROM `tabSchedule Entry`\n'
    '            WHERE resource = %s \n'
    '            AND schedule_date = %s \n'
    '            AND name != %s\n'
    '            AND docstatus != 2\n'
    '            AND (\n'
    '                (start_time <= %s AND end_time > %s) OR\n'
    '                (start_time < %s AND end_time >= %s) OR\n'
    '                (start_time >= %s AND end_time <= %s)\n'
    '            )\n'
    '        """, (\n'
    '            self.resource, self.schedule_date, self.name or "",\n'
    '            self.start_time, self.start_time,\n'
    '            self.end_time, self.end_time,\n'
    '            self.start_time, self.end_time\n'
    '        ), as_dict=True)'
)

RS_FY_OLD = (
    '        existing_fiscal_years = frappe.db.sql("""\n'
    '            SELECT name FROM `tabFiscal Year`\n'
    '            WHERE (\n'
    '                (%(start_date)s BETWEEN start_date AND end_date)\n'
    '                OR (%(end_date)s BETWEEN start_date AND end_date)\n'
    '                OR (start_date BETWEEN %(start_date)s AND %(end_date)s)\n'
    '            ) AND name != %(name)s\n'
    '            """, {\n'
    '                "start_date": self.start_date,\n'
    '                "end_date": self.end_date,\n'
    '                "name": self.name or "No Name"\n'
    '            }, as_dict=True)'
)

RS_FB_OLD = (
    '            frappe.db.sql("""\n'
    '                UPDATE `tabFinance Book` SET is_default = 0\n'
    '                WHERE is_default = 1 AND name != %s\n'
    '            """, (self.name))'
)

RS_CUR_OLD = (
    '            frappe.db.sql("""\n'
    '                UPDATE `tabCurrency` SET is_base_currency = 0\n'
    '                WHERE is_base_currency = 1 AND name != %s\n'
    '            """, (self.name))'
)

RS_SLOG_OLD = (
    '\trows = frappe.db.sql("""\n'
    '\t\tSELECT COUNT(*) FROM `tabScheduler Log`\n'
    '\t\tWHERE DATE(timestamp) < %s\n'
    '\t""", (cutoff_date,))\n'
    '\tdeleted_count = rows[0][0] if rows else 0'
)

RS_STMPL_OLD = (
    '\t\t\tmax_sort_order = frappe.db.sql(\n'
    '\t\t\t\t"SELECT COALESCE(MAX(sort_order), 0) FROM `tabSchedule Template`"\n'
    '\t\t\t)[0][0]'
)

RAW_SQL = Target(
    test="tests/offline/test_raw_sql.py",
    faults=[
        # --- the six shapes classify_query_arg names, at real sites --------
        Fault("an f-string splices a whitelisted endpoint's two arguments "
              "into the utilisation query", True, [
                  (RS_SAPI, RS_UTIL_OLD,
                   '    result = frappe.db.sql(f"""\n'
                   + RS_UTIL_FSTRING +
                   '    """)')]),
        Fault(".format() splices self.resource into the overlap query, which "
              "decides whether a booking is allowed", True, [
                  (RS_SENT, RS_OVERLAP_OLD,
                   '        overlapping = frappe.db.sql("""\n'
                   '            SELECT name, start_time, end_time, project\n'
                   '            FROM `tabSchedule Entry`\n'
                   "            WHERE resource = '{res}' \n"
                   '            AND schedule_date = %s \n'
                   '            AND name != %s\n'
                   '            AND docstatus != 2\n'
                   '            AND (\n'
                   '                (start_time <= %s AND end_time > %s) OR\n'
                   '                (start_time < %s AND end_time >= %s) OR\n'
                   '                (start_time >= %s AND end_time <= %s)\n'
                   '            )\n'
                   '        """.format(res=self.resource), (\n'
                   '            self.schedule_date, self.name or "",\n'
                   '            self.start_time, self.start_time,\n'
                   '            self.end_time, self.end_time,\n'
                   '            self.start_time, self.end_time\n'
                   '        ), as_dict=True)')]),
        Fault("%-formatting splices the resource name and date into the "
              "capacity query", True, [
                  (RS_RES, RS_CAPACITY_OLD,
                   '        scheduled_hours = frappe.db.sql("""\n'
                   '            SELECT COALESCE(SUM(duration), 0) as total_hours\n'
                   '            FROM `tabSchedule Entry`\n'
                   "            WHERE resource = '%s' AND schedule_date = '%s' "
                   'AND docstatus != 2\n'
                   '        """ % (self.name, date))[0][0]')]),
        Fault("concatenation splices a document name into an UPDATE -- an "
              "apostrophe in a currency name is enough to break it", True, [
                  (RS_CUR, RS_CUR_OLD,
                   '            frappe.db.sql(\n'
                   '                "UPDATE `tabCurrency` SET is_base_currency = 0 "\n'
                   '                "WHERE is_base_currency = 1 AND name != \'" '
                   '+ self.name + "\'"\n'
                   '            )')]),
        Fault("the query is built with % into a local and the call is handed "
              "the variable, so the splice is a line away from the call", True, [
                  (RS_FY, RS_FY_OLD,
                   '        query = """\n'
                   '            SELECT name FROM `tabFiscal Year`\n'
                   '            WHERE (\n'
                   "                ('%s' BETWEEN start_date AND end_date)\n"
                   "                OR ('%s' BETWEEN start_date AND end_date)\n"
                   "                OR (start_date BETWEEN '%s' AND '%s')\n"
                   "            ) AND name != '%s'\n"
                   '            """ % (self.start_date, self.end_date,\n'
                   '                   self.start_date, self.end_date,\n'
                   '                   self.name or "No Name")\n'
                   '        existing_fiscal_years = frappe.db.sql(query, as_dict=True)')]),
        Fault("a conditional expression picks between a spliced query and a "
              "literal one, so one arm is safe and the other is not", True, [
                  (RS_FB, RS_FB_OLD,
                   '            frappe.db.sql(\n'
                   '                f"UPDATE `tabFinance Book` SET is_default = 0 "\n'
                   '                f"WHERE name != \'{self.name}\'"\n'
                   '                if self.name else\n'
                   '                "UPDATE `tabFinance Book` SET is_default = 0"\n'
                   '            )')]),
        # --- shapes that reach the classifier's other branches -------------
        Fault("a dict of queries, called by subscript -- reaches the "
              "classifier's fallback branch, which no self-test covers", True, [
                  (RS_RES,
                   '        # Get total scheduled hours for this resource on the given date\n'
                   + RS_CAPACITY_OLD,
                   '        # Get total scheduled hours for this resource on the given date\n'
                   '        queries = {\n'
                   '            "capacity": f"""\n'
                   '            SELECT COALESCE(SUM(duration), 0) as total_hours\n'
                   '            FROM `tabSchedule Entry`\n'
                   "            WHERE resource = '{self.name}' "
                   "AND schedule_date = '{date}' AND docstatus != 2\n"
                   '            """,\n'
                   '        }\n'
                   '        scheduled_hours = frappe.db.sql(queries["capacity"])[0][0]')]),
        Fault("an f-string wrapped in .strip(), so the query argument is a "
              "call and the splice is inside it", True, [
                  (RS_SAPI, RS_UTIL_OLD,
                   '    result = frappe.db.sql(f"""\n'
                   + RS_UTIL_FSTRING +
                   '    """.strip())')]),
        Fault("the query is passed by keyword and is an f-string -- the "
              "keyword path is self-tested only with a literal", True, [
                  (RS_STMPL, RS_STMPL_OLD,
                   '\t\t\ttable = "Schedule Template"\n'
                   '\t\t\tmax_sort_order = frappe.db.sql(\n'
                   '\t\t\t\tquery=f"SELECT COALESCE(MAX(sort_order), 0) '
                   'FROM `tab{table}`"\n'
                   '\t\t\t)[0][0]')]),
        # --- the other three methods in SQL_METHODS ------------------------
        Fault("sql_list with an f-string: the log-clearing endpoint's cutoff "
              "goes into the query text", True, [
                  (RS_SLOG, RS_SLOG_OLD,
                   '\trows = frappe.db.sql_list(f"""\n'
                   '\t\tSELECT COUNT(*) FROM `tabScheduler Log`\n'
                   "\t\tWHERE DATE(timestamp) < '{cutoff_date}'\n"
                   '\t""")\n'
                   '\tdeleted_count = rows[0] if rows else 0')]),
        Fault("sql_value with .format() building a table name -- the one case "
              "the file says cannot be parameterised at all", True, [
                  (RS_STMPL, RS_STMPL_OLD,
                   '\t\t\tmax_sort_order = frappe.db.sql_value(\n'
                   '\t\t\t\t"SELECT COALESCE(MAX(sort_order), 0) FROM `tab{doctype}`"'
                   '.format(doctype=self.doctype)\n'
                   '\t\t\t)')]),
        Fault("CONTROL: multisql called correctly -- a dict of two literals, "
              "which is the only shape multisql accepts", False, [
                  (RS_CUR, RS_CUR_OLD,
                   '            frappe.db.multisql({\n'
                   '                "mariadb": """\n'
                   '                    UPDATE `tabCurrency` SET is_base_currency = 0\n'
                   '                    WHERE is_base_currency = 1 AND name != %s\n'
                   '                """,\n'
                   '                "postgres": """\n'
                   '                    UPDATE "tabCurrency" SET is_base_currency = 0\n'
                   '                    WHERE is_base_currency = 1 AND name != %s\n'
                   '                """,\n'
                   '            }, (self.name))')]),
        Fault("an f-string in multisql's mariadb arm -- the real hazard, "
              "which until the fix was red for the same reason a correct "
              "multisql was", True, [
                  (RS_CUR, RS_CUR_OLD,
                   '            frappe.db.multisql({\n'
                   '                "mariadb": f"""\n'
                   '                    UPDATE `tabCurrency` SET is_base_currency = 0\n'
                   "                    WHERE is_base_currency = 1 AND name != '{self.name}'\n"
                   '                """,\n'
                   '                "postgres": """\n'
                   '                    UPDATE "tabCurrency" SET is_base_currency = 0\n'
                   '                    WHERE is_base_currency = 1 AND name != %s\n'
                   '                """,\n'
                   '            })')]),
        Fault("a dialect map built into a local and passed to multisql by "
              "name, so there is nothing in the call for the sweep to read",
              True, [
                  (RS_CUR, RS_CUR_OLD,
                   '            dialects = {\n'
                   '                "mariadb": f"""\n'
                   '                    UPDATE `tabCurrency` SET is_base_currency = 0\n'
                   "                    WHERE is_base_currency = 1 AND name != '{self.name}'\n"
                   '                """,\n'
                   '            }\n'
                   '            frappe.db.multisql(dialects)')]),
        # --- the walker's scope, exercised through app code ----------------
        # `_looks_like_db_handle` recognises `<anything>.db` and the bare name
        # `db`. Every other alias is dropped into `skipped`, which the sweep
        # collects and never reports.
        Fault("the handle is put in a local called `handle` first, so the "
              "spliced query is on a receiver the walker drops", True, [
                  (RS_SAPI, RS_UTIL_OLD,
                   '    handle = frappe.db\n'
                   '    result = handle.sql(f"""\n'
                   + RS_UTIL_FSTRING +
                   '    """)')]),
        Fault("the handle is cached on the document as self.handle, so the "
              "receiver is an attribute the walker drops", True, [
                  (RS_RES, RS_CAPACITY_OLD,
                   '        self.handle = frappe.db\n'
                   '        scheduled_hours = self.handle.sql(f"""\n'
                   '            SELECT COALESCE(SUM(duration), 0) as total_hours\n'
                   '            FROM `tabSchedule Entry`\n'
                   "            WHERE resource = '{self.name}' "
                   "AND schedule_date = '{date}' AND docstatus != 2\n"
                   '        """)[0][0]')]),
        Fault("`from frappe import db` then db.sql(f...) -- the one alias the "
              "walker does recognise, proved through app code", True, [
                  (RS_SAPI, RS_UTIL_OLD,
                   '    from frappe import db\n'
                   '    result = db.sql(f"""\n'
                   + RS_UTIL_FSTRING +
                   '    """)')]),
        # --- the blunt rule's own cost, stated rather than hidden ----------
        Fault("BY DESIGN: a hoisted local holding the identical literal is "
              "rejected too -- no behaviour change, and the file argues for "
              "exactly this rather than attempting dataflow", True, [
                  (RS_FB, RS_FB_OLD,
                   '            query = """\n'
                   '                UPDATE `tabFinance Book` SET is_default = 0\n'
                   '                WHERE is_default = 1 AND name != %s\n'
                   '            """\n'
                   '            frappe.db.sql(query, (self.name))')]),
        # --- controls ------------------------------------------------------
        Fault("CONTROL: one literal split into two adjacent literals, which "
              "the parser joins -- safe, and not concatenation", False, [
                  (RS_STMPL,
                   '\t\t\t\t"SELECT COALESCE(MAX(sort_order), 0) FROM `tabSchedule Template`"\n',
                   '\t\t\t\t"SELECT COALESCE(MAX(sort_order), 0) "\n'
                   '\t\t\t\t"FROM `tabSchedule Template`"\n')]),
        Fault("CONTROL: an f-string in the `values` argument, which is the "
              "one place a value belongs", False, [
                  (RS_RES,
                   '        """, (self.name, date))[0][0]',
                   '        """, (f"{self.name}", date))[0][0]')]),
        Fault("CONTROL: the query text reformatted inside the literal -- the "
              "guard judges the shape, not the SQL", False, [
                  (RS_SENT,
                   '            WHERE resource = %s \n'
                   '            AND schedule_date = %s \n',
                   '            WHERE resource = %s\n'
                   '            AND schedule_date = %s\n')]),
        Fault("CONTROL: the local holding the result renamed", False, [
                  (RS_FY,
                   '        existing_fiscal_years = frappe.db.sql("""\n',
                   '        clashes = frappe.db.sql("""\n'),
                  (RS_FY,
                   '        if existing_fiscal_years:\n'
                   '            fiscal_years = ", ".join([d.name for d in existing_fiscal_years])',
                   '        if clashes:\n'
                   '            fiscal_years = ", ".join([d.name for d in clashes])')]),
        Fault("CONTROL: the remedy the failure message recommends -- named "
              "placeholders and a values dict -- must not itself be a finding",
              False, [
                  (RS_FB, RS_FB_OLD,
                   '            frappe.db.sql("""\n'
                   '                UPDATE `tabFinance Book` SET is_default = 0\n'
                   '                WHERE is_default = 1 AND name != %(name)s\n'
                   '            """, {"name": self.name})')]),
    ],
)


# --- Scheduler Role delete ------------------------------------------------
# PR #44: `Scheduler Role.on_trash` opened with a `frappe.get_all("Resource
# Role", ...)` against a DocType that has no table, and `get_table_columns`
# raises `TableMissingError` before any SQL runs -- so `on_trash` threw on
# every delete, for every role, and the `Schedule Row` integrity check below
# it was never reached. The dead read is gone; the `Schedule Row` check stays.
#
# The file guards both halves, and a third thing: the two reporting endpoints
# that still read the missing DocType are pinned by name, so the scope of the
# change is recorded rather than remembered.
#
# `scheduler_role.py` is tab-indented and CRLF; patterns here are written with
# tabs and `\n`, and `harness.nl` translates the endings.

ROLE_CTL = "erplite/scheduler/doctype/scheduler_role/scheduler_role.py"

# The integrity read, verbatim -- note the trailing space after the DocType.
SRD_READ = (
    '\t\tschedule_rows_using_role = frappe.get_all("Schedule Row", \n'
    '\t\t\tfilters={"role": self.name},\n'
    '\t\t\tfields=["name"]\n'
    '\t\t)\n'
)

SRD_GUARD = (
    '\t\tif schedule_rows_using_role:\n'
    '\t\t\tfrappe.throw(f"Cannot delete role. It is used in '
    '{len(schedule_rows_using_role)} schedule entries")\n'
)

# The lines PR #44 removed, as they stood.
SRD_DEAD_READ = (
    '\t\tresources_using_role = frappe.get_all("Resource Role", \n'
    '\t\t\tfilters={"role": self.name},\n'
    '\t\t\tfields=["parent"]\n'
    '\t\t)\n'
    '\t\t\n'
)

SRD_FILTER = '\t\t\tfilters={"role": self.name},\n'

SRD_ACTIVE_ROLES = '\troles = frappe.get_list("Scheduler Role",\n'

SRD_RESOURCES_READ = (
    '\tresource_roles = frappe.get_all("Resource Role",\n'
    '\t\tfilters={"role": role},\n'
    '\t\tfields=["parent"]\n'
    '\t)\n'
)

SCHEDULER_ROLE_DELETE = Target("tests/offline/test_scheduler_role_delete.py", [
    # -- the regression the change was made to stop --
    Fault("the dead Resource Role read comes back", True,
          [(ROLE_CTL, SRD_READ, SRD_DEAD_READ + SRD_READ)]),

    Fault("the hook frappe calls on delete is renamed, so nothing runs", True,
          [(ROLE_CTL, '\tdef on_trash(self):\n', '\tdef on_delete(self):\n')]),

    # -- the guard that was kept must keep biting --
    Fault("the Schedule Row guard is gone", True,
          [(ROLE_CTL, SRD_GUARD, '')]),

    Fault("the guard is inverted", True,
          [(ROLE_CTL, '\t\tif schedule_rows_using_role:\n',
            '\t\tif not schedule_rows_using_role:\n')]),

    Fault("the refusal becomes a message, so the delete proceeds", True,
          [(ROLE_CTL, '\t\t\tfrappe.throw(f"Cannot delete role.',
            '\t\t\tfrappe.msgprint(f"Cannot delete role.')]),

    Fault("the count in the refusal is a constant", True,
          [(ROLE_CTL, '{len(schedule_rows_using_role)} schedule entries',
            '1 schedule entries')]),

    # -- the read the guard rests on --
    Fault("the guard counts every schedule row, whosever role it names", True,
          [(ROLE_CTL, SRD_FILTER, '\t\t\tfilters={},\n')]),

    Fault("the guard filters on the wrong column", True,
          [(ROLE_CTL, SRD_FILTER, '\t\t\tfilters={"project": self.name},\n')]),

    Fault("the guard filters on the label, not the link target", True,
          [(ROLE_CTL, SRD_FILTER,
            '\t\t\tfilters={"role": self.role_name},\n')]),

    Fault("the guard reads a DocType that exists but holds nothing", True,
          [(ROLE_CTL, 'frappe.get_all("Schedule Row", ',
            'frappe.get_all("Schedule Entry", ')]),

    Fault("the integrity read consults the deleting user's read rows", True,
          [(ROLE_CTL, 'schedule_rows_using_role = frappe.get_all(',
            'schedule_rows_using_role = frappe.get_list(')]),

    # -- the recorded scope: which functions still read the missing DocType --
    Fault("a third function starts reading the missing DocType", True,
          [(ROLE_CTL, SRD_ACTIVE_ROLES,
            '\tfrappe.get_all("Resource Role", filters={}, fields=["parent"])\n'
            + SRD_ACTIVE_ROLES)]),

    Fault("one of the two known-broken endpoints is quietly fixed", True,
          [(ROLE_CTL, SRD_RESOURCES_READ, '\tresource_roles = []\n')]),

    # -- controls: real edits to the source that change no behaviour --
    Fault("CONTROL the local variable is renamed", False,
          [(ROLE_CTL, '\t\tschedule_rows_using_role = frappe.get_all',
            '\t\trows_using_role = frappe.get_all'),
           (ROLE_CTL, SRD_GUARD,
            '\t\tif rows_using_role:\n'
            '\t\t\tfrappe.throw(f"Cannot delete role. It is used in '
            '{len(rows_using_role)} schedule entries")\n')]),

    Fault("CONTROL the read asks for one more column", False,
          [(ROLE_CTL, '\t\t\tfields=["name"]\n',
            '\t\t\tfields=["name", "role"]\n')]),

    Fault("CONTROL the keyword arguments swap places", False,
          [(ROLE_CTL,
            '\t\t\tfilters={"role": self.name},\n\t\t\tfields=["name"]\n',
            '\t\t\tfields=["name"],\n\t\t\tfilters={"role": self.name}\n')]),
])

# --- endpoint wiring: a button's method and a DocType literal ----------------
# rev_0ee5b675ce. Two whole-app rules over the app's own text -- every
# `frappe.call` method resolves, and every DocType literal names a DocType that
# exists -- plus the narrow guard on the field the owner decided against.
#
# A sweep over the whole app is easy to injure without noticing: it can stop
# reaching a site and pass by finding nothing. So half of these faults break a
# DocType name, and half move a call somewhere the sweep cannot read it, which
# is the failure that looks like success.
#
# `scheduler_role.py` (ROLE_CTL above) is tab-indented; `scheduler/api.py` and
# `xero/accounts.py` are space-indented; all three are CRLF, and `harness.nl`
# translates the endings.

SCHED_API = "erplite/scheduler/api.py"
XERO_ACC = "erplite/xero/accounts.py"
LOG_CTL = "erplite/scheduler/doctype/scheduler_log/scheduler_log.py"
LOG_JS = "erplite/scheduler/doctype/scheduler_log/scheduler_log.js"
ACTIVITY_JS = "erplite/projects/doctype/activity/activity.js"

SRD_READ_HEAD = '\t\tschedule_rows_using_role = frappe.get_all("Schedule Row", \n'

NEW_SCHEDULE_ENTRY = '        doc = frappe.new_doc("Schedule Entry")\n'

# The app's only read of frappe's own `File` DocType, verbatim.
FILE_READ = (
    '        attachments = frappe.get_all("File", \n'
    '                                   filters={\n'
    '                                       "attached_to_doctype": "Purchase Invoice",\n'
    '                                       "attached_to_name": purchase_invoice_name\n'
    '                                   },\n'
    '                                   fields=["name", "file_name", "file_url", "is_private"])\n'
)

ENDPOINT_WIRING = Target("tests/offline/test_endpoint_wiring.py", [
    # -- a DocType literal naming something that exists nowhere --
    Fault("a read's DocType is a plural that exists nowhere", True,
          [(ROLE_CTL, 'frappe.get_all("Schedule Row", \n',
            'frappe.get_all("Schedule Rows", \n')]),

    Fault("new_doc names a DocType nothing declares -- the Purchase Order "
          "shape, in another file", True,
          [(SCHED_API, NEW_SCHEDULE_ENTRY,
            '        doc = frappe.new_doc("Schedule Entries")\n')]),

    Fault("the wrong DocType arrives as a keyword argument, with no "
          "positional argument to read", True,
          [(ROLE_CTL, SRD_READ_HEAD,
            '\t\tschedule_rows_using_role = frappe.get_all(\n'
            '\t\t\tdoctype="Schedule Rows",\n')]),

    # -- the recorded reads of a DocType that really is missing --
    Fault("a third function starts reading the missing Resource Role", True,
          [(ROLE_CTL, SRD_ACTIVE_ROLES,
            '\tfrappe.get_all("Resource Role", filters={}, fields=["parent"])\n'
            + SRD_ACTIVE_ROLES)]),

    Fault("one of the two known-broken reads is quietly dropped", True,
          [(ROLE_CTL, SRD_RESOURCES_READ, '\tresource_roles = []\n')]),

    # -- the sweep losing sight of a call, which passes by finding nothing --
    Fault("the read moves behind a frappe.db alias, out of the sweep's sight",
          True,
          [(ROLE_CTL, SRD_READ_HEAD,
            '\t\tdb = frappe.db\n'
            '\t\tschedule_rows_using_role = db.get_all("Schedule Rows", \n')]),

    Fault("new_doc is called through `from frappe import new_doc`, where the "
          "walker cannot read the receiver", True,
          [(SCHED_API, 'from frappe import _\n',
            'from frappe import _, new_doc\n'),
           (SCHED_API, NEW_SCHEDULE_ENTRY,
            '        doc = new_doc("Schedule Entry")\n')]),

    Fault("the app's only read of frappe's File DocType goes, leaving the "
          "excuse for it behind", True,
          [(XERO_ACC, FILE_READ,
            '        attachments = frappe.get_doc(\n'
            '            "Purchase Invoice", purchase_invoice_name'
            ').get("attachments") or []\n')]),

    # -- a button pointing at a method that is not there --
    Fault("a whitelisted endpoint is renamed and the button is left pointing "
          "at the old name", True,
          [(LOG_CTL, 'def clear_old_logs(days=30):\n',
            'def clear_logs(days=30):\n')]),

    Fault("a button is pointed at a module the function was never moved to",
          True,
          [(LOG_JS,
            "erplite.scheduler.doctype.scheduler_log.scheduler_log.clear_old_logs",
            "erplite.scheduler.api.clear_old_logs")]),

    # -- the field the owner decided against --
    Fault("the progress_percent handler comes back", True,
          [(ACTIVITY_JS,
            "frappe.ui.form.on('Activity', {\n\trefresh: function(frm) {\n",
            "frappe.ui.form.on('Activity', {\n"
            "\tprogress_percent: function(frm) {\n"
            "\t\tif (frm.doc.progress_percent === 100) {\n"
            "\t\t\tfrm.set_value('status', 'Completed');\n"
            "\t\t}\n"
            "\t},\n"
            "\n"
            "\trefresh: function(frm) {\n")]),

    # -- controls: real edits to the source that change no behaviour --
    Fault("CONTROL a swept read asks for one more column", False,
          [(ROLE_CTL, '\t\t\tfields=["name"]\n',
            '\t\t\tfields=["name", "role"]\n')]),

    Fault("CONTROL a swept read's keyword arguments swap places", False,
          [(ROLE_CTL,
            '\t\t\tfilters={"role": self.name},\n\t\t\tfields=["name"]\n',
            '\t\t\tfields=["name"],\n\t\t\tfilters={"role": self.name}\n')]),

    Fault("CONTROL the variable holding a swept read's result is renamed",
          False,
          [(ROLE_CTL, '\t\tschedule_rows_using_role = frappe.get_all',
            '\t\trows_using_role = frappe.get_all'),
           (ROLE_CTL, SRD_GUARD,
            '\t\tif rows_using_role:\n'
            '\t\t\tfrappe.throw(f"Cannot delete role. It is used in '
            '{len(rows_using_role)} schedule entries")\n')]),
])

# --- the shape of a read, not the name --------------------------------------
# tests/offline/test_read_shapes.py. A Single has no table of its own, so
# `get_all` on one raises; a child row belongs to a parent, so an unparented
# read returns everybody's. The three sites edited below are every child read
# the app has plus one of its nineteen Single reads -- the other eighteen are
# the same shape at the same receiver, and a fault per copy would measure the
# same claim eighteen times.

AUTH_SINGLE = ('def get_access_token():\n'
               '    """Get access token using client credentials flow"""\n'
               '    settings = frappe.get_single("Xero Settings")\n')

SQ_CHILD_READ = (
    '\t\t\tquote_items = frappe.get_all("Supplier Quote Item",\n'
    '\t\t\t\tfilters={"parent": quote.name, "item_name": ["like", f"%{item_name}%"]},\n'
    '\t\t\t\tfields=["item_name", "rate", "amount"]\n'
    '\t\t\t)\n')

TODO_HAS_ROLE = ('    return bool(frappe.db.exists("Has Role", {\n'
                 '        "parent": user,\n'
                 '        "role": ["in", MANAGER_ROLES]\n'
                 '    }))\n')

READ_SHAPES = Target("tests/offline/test_read_shapes.py", [
    # -- a row query against a DocType that has no table --
    Fault("a Single is read with frappe.get_all -- the mistake this file was "
          "written after", True,
          [(XERO_AUTH, AUTH_SINGLE,
            'def get_access_token():\n'
            '    """Get access token using client credentials flow"""\n'
            '    settings = frappe.get_all("Xero Settings")[0]\n')]),

    Fault("the same read through frappe.db, which forwards to the same "
          "function", True,
          [(XERO_AUTH, AUTH_SINGLE,
            'def get_access_token():\n'
            '    """Get access token using client credentials flow"""\n'
            '    settings = frappe.db.get_list("Xero Settings")[0]\n')]),

    # -- a shape nobody has read frappe's source for --
    Fault("a Single is read with a shape that is neither verified safe nor "
          "known fatal", True,
          [(XERO_AUTH, AUTH_SINGLE,
            'def get_access_token():\n'
            '    """Get access token using client credentials flow"""\n'
            '    settings = frappe.db.count("Xero Settings")\n')]),

    # -- the floor, in both directions --
    Fault("a twentieth Single read arrives and nobody looks at its shape", True,
          [(XERO_AUTH, AUTH_SINGLE,
            'def get_access_token():\n'
            '    """Get access token using client credentials flow"""\n'
            '    settings = frappe.get_single("Xero Settings")\n'
            '    frappe.get_single("Xero Settings")\n')]),

    Fault("a Single read is dropped, so the rule quietly covers one less", True,
          [(XERO_AUTH, AUTH_SINGLE,
            'def get_access_token():\n'
            '    """Get access token using client credentials flow"""\n'
            '    settings = _settings_from_somewhere_else()\n')]),

    # -- a child read that stops naming a parent --
    Fault("the app's only child-table list read loses its parent filter, so it "
          "returns every quote's items", True,
          [(SQ, SQ_CHILD_READ,
            '\t\t\tquote_items = frappe.get_all("Supplier Quote Item",\n'
            '\t\t\t\tfilters={"item_name": ["like", f"%{item_name}%"]},\n'
            '\t\t\t\tfields=["item_name", "rate", "amount"]\n'
            '\t\t\t)\n')]),

    Fault("a child read's filters are built elsewhere, where the sweep cannot "
          "see whether a parent is named", True,
          [(SQ, SQ_CHILD_READ,
            '\t\t\titem_filters = {"item_name": ["like", f"%{item_name}%"]}\n'
            '\t\t\tquote_items = frappe.get_all("Supplier Quote Item",\n'
            '\t\t\t\tfilters=item_filters,\n'
            '\t\t\t\tfields=["item_name", "rate", "amount"]\n'
            '\t\t\t)\n')]),

    Fault("the Has Role read stops naming a parent, so holding the role under "
          "any user at all passes the manager check", True,
          [(TODO_PAGE, TODO_HAS_ROLE,
            '    return bool(frappe.db.exists("Has Role", {\n'
            '        "role": ["in", MANAGER_ROLES]\n'
            '    }))\n')]),

    # -- controls: real edits to the source that change no behaviour --
    Fault("CONTROL a Single read swaps get_single for the get_doc it is "
          "defined as", False,
          [(XERO_AUTH, AUTH_SINGLE,
            'def get_access_token():\n'
            '    """Get access token using client credentials flow"""\n'
            '    settings = frappe.get_doc("Xero Settings")\n')]),

    Fault("CONTROL a Single read's DocType arrives as a keyword argument",
          False,
          [(XERO_AUTH, AUTH_SINGLE,
            'def get_access_token():\n'
            '    """Get access token using client credentials flow"""\n'
            '    settings = frappe.get_single(doctype="Xero Settings")\n')]),

    Fault("CONTROL a child read's filter keys swap places", False,
          [(SQ, SQ_CHILD_READ,
            '\t\t\tquote_items = frappe.get_all("Supplier Quote Item",\n'
            '\t\t\t\tfilters={"item_name": ["like", f"%{item_name}%"], "parent": quote.name},\n'
            '\t\t\t\tfields=["item_name", "rate", "amount"]\n'
            '\t\t\t)\n')]),

    Fault("CONTROL the child read is written on one line instead of four",
          False,
          [(SQ, SQ_CHILD_READ,
            '\t\t\tquote_items = frappe.get_all("Supplier Quote Item", filters={"parent": quote.name, "item_name": ["like", f"%{item_name}%"]}, fields=["item_name", "rate", "amount"])\n')]),
])


# --- DocType names in the browser -------------------------------------------
# tests/offline/test_client_doctypes.py. Two of these shapes fail in silence:
# `frappe.ui.form.on` registers handlers into a bucket keyed on the name it is
# given, which `get_event_handler_list` creates on demand and `get_handlers`
# only reads under the open form's own doctype (script_manager.js:14-26, :154);
# `frappe.listview_settings[x]` is read as `|| {}` (base_list.js:43). So the
# faults below are not hypothetical typos -- each one leaves a form or a list
# view quietly not doing what its script says, with nothing in a build, a
# migrate or a test run to say so.

ACT_JS = "erplite/projects/doctype/activity/activity.js"
PROJ_LIST_JS = "erplite/projects/doctype/project/project_list.js"
TRIP_JS2 = "erplite/projects/doctype/trip/trip.js"
TS_JS = "erplite/projects/doctype/timesheet_entry/timesheet_entry.js"
SCHED_API_JS2 = "frontend/src/components/scheduler/composables/useSchedulerAPI.js"

ACT_FORM_ON = "frappe.ui.form.on('Activity', {\n"
ACT_LISTVIEW = "frappe.listview_settings['Activity'] = {\n"
PROJ_LISTVIEW = "frappe.listview_settings['Project'] = {\n"
TRIP_ROUTE = '            frappe.set_route("List", "Purchase Invoice");\n'
TS_READ = ("                frappe.db.get_value('Project', frm.doc.project, "
           "'timesheet_approver')\n")
TS_LINK_FIELD = ("                        {\n"
                 "                            label: __('Project'),\n"
                 "                            fieldname: 'project',\n"
                 "                            fieldtype: 'Link',\n"
                 "                            options: 'Project',\n"
                 "                            reqd: 1\n"
                 "                        },\n"
                 "                        {\n"
                 "                            label: __('Activity'),\n")
SCHED_PROJECT_RESOURCE = ("  const projectsResource = createListResource({\n"
                          "    doctype: 'Project',\n")

SQ_DESK_URL = ("\t\thtml += '<td><a href=\"/app/supplier-quote/' + quote.name + "
               "'\" target=\"_blank\">View</a></td>';\n")
SCHED_TABLE_VUE = "frontend/src/components/scheduler/SchedulerTable.vue"
VUE_DESK_URL = ("const handleEditProject = (projectId) => {\n"
                "  window.open(`/app/project/${projectId}`, '_blank')\n")

CLIENT_DOCTYPES = Target("tests/offline/test_client_doctypes.py", [
    # -- a name that exists nowhere, in each shape the app uses --
    Fault("a form script is registered under a misspelt DocType, so every "
          "handler in the file is dead and nothing says so", True,
          [(ACT_JS, ACT_FORM_ON, "frappe.ui.form.on('Acitivity', {\n")]),

    Fault("a list view's settings are registered under a misspelt DocType, so "
          "the indicators and buttons are silently absent", True,
          [(PROJ_LIST_JS, PROJ_LISTVIEW,
            "frappe.listview_settings['Porject'] = {\n")]),

    Fault("a button routes to a list of a DocType that does not exist", True,
          [(TRIP_JS2, TRIP_ROUTE,
            '            frappe.set_route("List", "Purchase Invoices");\n')]),

    Fault("a client read names a DocType that does not exist", True,
          [(TS_JS, TS_READ,
            "                frappe.db.get_value('Projects', frm.doc.project, "
            "'timesheet_approver')\n")]),

    Fault("the Vue app asks for a document type that does not exist", True,
          [(SCHED_API_JS2, SCHED_PROJECT_RESOURCE,
            "  const projectsResource = createListResource({\n"
            "    doctype: 'Project Plan',\n")]),

    Fault("a dialog's Link field offers a DocType that does not exist", True,
          [(TS_JS, TS_LINK_FIELD,
            "                        {\n"
            "                            label: __('Project'),\n"
            "                            fieldname: 'project',\n"
            "                            fieldtype: 'Link',\n"
            "                            options: 'Projekt',\n"
            "                            reqd: 1\n"
            "                        },\n"
            "                        {\n"
            "                            label: __('Activity'),\n")]),

    # -- a name that exists, on the wrong form: only location can judge these --
    Fault("a form script is registered under a DocType that exists but is not "
          "the one whose folder it sits in", True,
          [(ACT_JS, ACT_FORM_ON, "frappe.ui.form.on('Project', {\n")]),

    Fault("a list view's settings are registered under another real DocType", True,
          [(PROJ_LIST_JS, PROJ_LISTVIEW,
            "frappe.listview_settings['Activity'] = {\n")]),

    # -- the measured floors: a site leaving the sweep's reach --
    Fault("a read's DocType moves into a variable, so the literal leaves the "
          "sweep and the rule quietly covers one less site", True,
          [(TS_JS, TS_READ,
            "                const projectDoctype = 'Project';\n"
            "                frappe.db.get_value(projectDoctype, frm.doc.project, "
            "'timesheet_approver')\n")]),

    Fault("a doctype: key is built from a constant, so the Vue app's read "
          "leaves the sweep", True,
          [(SCHED_API_JS2, SCHED_PROJECT_RESOURCE,
            "  const PROJECT_DOCTYPE = 'Project'\n"
            "  const projectsResource = createListResource({\n"
            "    doctype: PROJECT_DOCTYPE,\n")]),

    Fault("a list view's settings are registered under a runtime value, so the "
          "name leaves the sweep and nothing judges what it points at", True,
          [(ACT_JS, ACT_LISTVIEW,
            "frappe.listview_settings[cur_list.doctype] = {\n")]),

    # -- controls: real edits that change no behaviour --
    # -- a desk URL, the shape that names a DocType without looking like one --
    Fault("a link opens a desk route whose slug names no DocType", True,
          [(SQ_JS, SQ_DESK_URL,
            "\t\thtml += '<td><a href=\"/app/supplier-quotes/' + quote.name + "
            "'\" target=\"_blank\">View</a></td>';\n")]),

    Fault("the Vue app opens a desk route for a DocType that does not exist -- "
          "in a .vue file, where none of the other rules here look", True,
          [(SCHED_TABLE_VUE, VUE_DESK_URL,
            "const handleEditProject = (projectId) => {\n"
            "  window.open(`/app/porject/${projectId}`, '_blank')\n")]),

    Fault("CONTROL a desk PAGE is linked to, which is not a DocType and must "
          "not be judged as one", False,
          [(SQ_JS, SQ_DESK_URL,
            "\t\thtml += '<td><a href=\"/app/user-profile\" "
            "target=\"_blank\">View</a></td>';\n")]),

    Fault("CONTROL a form script's DocType is quoted with double quotes", False,
          [(ACT_JS, ACT_FORM_ON, 'frappe.ui.form.on("Activity", {\n')]),

    Fault("CONTROL a form script's registration is wrapped onto two lines",
          False,
          [(ACT_JS, ACT_FORM_ON, "frappe.ui.form.on(\n\t'Activity', {\n")]),

    Fault("CONTROL scaffold naming a DocType that exists nowhere is left "
          "commented out, as nine DocType folders already do", False,
          [(ACT_JS, ACT_FORM_ON,
            "// frappe.ui.form.on('Nowhere At All', {\n"
            "// \trefresh(frm) {}\n"
            "// });\n"
            "frappe.ui.form.on('Activity', {\n")]),

    Fault("CONTROL a Select field is added whose options are values, not a "
          "DocType", False,
          [(TS_JS, TS_LINK_FIELD,
            "                        {\n"
            "                            label: __('Project'),\n"
            "                            fieldname: 'project',\n"
            "                            fieldtype: 'Link',\n"
            "                            options: 'Project',\n"
            "                            reqd: 1\n"
            "                        },\n"
            "                        {\n"
            "                            label: __('Mode'),\n"
            "                            fieldname: 'mode',\n"
            "                            fieldtype: 'Select',\n"
            "                            options: 'Start',\n"
            "                            reqd: 1\n"
            "                        },\n"
            "                        {\n"
            "                            label: __('Activity'),\n")]),
])


# --- a server method named in a URL -----------------------------------------
# tests/offline/test_api_url_methods.py. `/api/method/<path>` is resolved by
# `execute_cmd` with `get_attr`, which throws for a path it cannot reach and
# raises PermissionError for one that is not whitelisted (frappe/handler.py:
# 74-83). Loud at the HTTP layer; silent in the page wherever the caller reads
# the body rather than the status, which is what this app's Vue pages do. Five
# of the twelve method names are composed from a base URL and a literal, so
# several of the faults below break the composition rather than a name.

TD_JS = "erplite/public/js/todo/data/TodoDataManager.js"
TODO_IDX_PY = "erplite/www/todo/index.py"
MAIN_JS = "frontend/src/main.js"
USER_MENU_VUE = "frontend/src/components/scheduler/UserMenu.vue"
HOME_VUE = "frontend/src/pages/Home.vue"
WWW_ERPLITE_PY = "erplite/www/erplite.py"

TD_BASE = "        this.baseUrl = '/api/method/erplite.www.todo.index';\n"
TD_COMPOSE = "        const url = `${this.baseUrl}.${method}`;\n"
TD_CALL = "            const response = await this.makeRequest('get_todos');\n"
TODO_GET_TODOS = "@frappe.whitelist()\ndef get_todos():\n"
TODO_METRICS = "@frappe.whitelist()\ndef get_daily_metrics():\n"
MAIN_URL = "        url: '/api/method/erplite.www.erplite.get_context_for_dev',\n"
LOGOUT_URL = "    window.location.href = '/api/method/logout'\n"
HOME_URL = ("    const response = await fetch("
            "'/api/method/erplite.vue_test.api.test_connection')\n")

API_URL_METHODS = Target("tests/offline/test_api_url_methods.py", [
    # -- the name at one end or the other is wrong --
    Fault("a composed call asks the todo module for a method it does not "
          "define, so the board silently loads nothing", True,
          [(TD_JS, TD_CALL,
            "            const response = await this.makeRequest('get_todoz');\n")]),

    Fault("the method behind a composed call is renamed server-side, so every "
          "caller of it 417s", True,
          [(TODO_IDX_PY, TODO_GET_TODOS,
            "@frappe.whitelist()\ndef fetch_todos():\n")]),

    Fault("the base URL names a module that is not in the tree, so all five "
          "methods composed onto it are unreachable", True,
          [(TD_JS, TD_BASE,
            "        this.baseUrl = '/api/method/erplite.www.todo.api';\n")]),

    Fault("a URL is pointed at a real function that has no "
          "@frappe.whitelist(), so frappe answers Method Not Allowed", True,
          [(MAIN_JS, MAIN_URL,
            "        url: '/api/method/erplite.www.erplite.get_context',\n")]),

    Fault("the whitelist comes off the one method nothing but a URL calls, "
          "which is why this target has to be the one that notices", True,
          [(TODO_IDX_PY, TODO_METRICS, "def get_daily_metrics():\n")]),

    # -- the rule is fine; the sweep stopped reaching -----------------------
    Fault("the URL is composed with + instead of interpolated, so the sweep "
          "can no longer follow the base URL and says so", True,
          [(TD_JS, TD_COMPOSE,
            "        const url = this.baseUrl + '.' + method;\n")]),

    # -- the recorded defect goes stale, in both directions -----------------
    Fault("the dead Home.vue call is pointed at a method that exists, so the "
          "entry recorded for it in UNRESOLVED is stale", True,
          [(HOME_VUE, HOME_URL,
            "    const response = await fetch("
            "'/api/method/erplite.www.erplite.get_context_for_dev')\n")]),

    Fault("a sixth call to the deleted module appears, under a name that is "
          "not one of the four recorded", True,
          [(HOME_VUE, HOME_URL,
            "    const response = await fetch("
            "'/api/method/erplite.vue_test.api.delete_task')\n")]),

    # -- negative controls --------------------------------------------------
    Fault("CONTROL frappe's logout is written in the versioned form v1 also "
          "serves", False,
          [(USER_MENU_VUE, LOGOUT_URL,
            "    window.location.href = '/api/v1/method/logout'\n")]),

    Fault("CONTROL the base URL is written with double quotes", False,
          [(TD_JS, TD_BASE,
            '        this.baseUrl = "/api/method/erplite.www.todo.index";\n')]),

    Fault("CONTROL a whitelist spells out the default it already has", False,
          [(TODO_IDX_PY, TODO_METRICS,
            "@frappe.whitelist(allow_guest=False)\ndef get_daily_metrics():\n")]),

    Fault("CONTROL a composed call's method name is written in double quotes",
          False,
          [(TD_JS, TD_CALL,
            '            const response = await this.makeRequest("get_todos");\n')]),
])


# --- the DocType JSON itself, which deploying never validates --------------
# tests/offline/test_doctype_json_validation.py. Frappe has twenty-three checks
# for these files and runs none of them on deploy: `sync.py:111` imports each
# JSON with `data_import` false, `import_file.py:235` sets `ignore_validate`,
# and `document.py:1099` returns before `validate`. Fourteen more are gated on
# `not frappe.flags.in_migrate` (`doctype.py:1646`) and so are skipped twice
# over. Verified against frappe 15.52.0, the live version. So the faults below
# are not caught by a build, a migrate, or any test but this one -- and three
# of the four reach the user as a page that used to work and now does not.

TRIP_JSON = "erplite/projects/doctype/trip/trip.json"
KA_JSON = "erplite/erplite/doctype/knowledge_article/knowledge_article.json"
PINV_JSON = "erplite/accounts/doctype/purchase_invoice/purchase_invoice.json"
RESOURCE_JSON = "erplite/scheduler/doctype/resource/resource.json"
PROJECT_JSON = "erplite/projects/doctype/project/project.json"
ACTIVITY_JSON = "erplite/projects/doctype/activity/activity.json"

TRIP_NAME_FIELD = ('  {\n'
                   '   "fieldname": "trip_name",\n'
                   '   "fieldtype": "Data",\n')
KA_TITLE_FIELD = ' "title_field": "title"\n'
PINV_STATUS_DEFAULT = ('   "default": "Draft",\n'
                       '   "fieldname": "status",\n')
PROJECT_OPEN_STATE = ('  {\n'
                      '   "color": "Green",\n'
                      '   "title": "Open"\n'
                      '  },\n')
ACTIVITY_CANCELLED_STATE = ('  {\n'
                            '   "color": "Red",\n'
                            '   "title": "Cancelled"\n'
                            '  }\n')
RESOURCE_FIRST_PERM = ('  {\n'
                       '   "create": 1,\n'
                       '   "delete": 1,\n'
                       '   "email": 1,\n'
                       '   "export": 1,\n'
                       '   "print": 1,\n'
                       '   "read": 1,\n'
                       '   "report": 1,\n'
                       '   "role": "System Manager",\n')

DOCTYPE_JSON_VALIDATION = Target(
    "tests/offline/test_doctype_json_validation.py", [

    # -- a fieldname that shadows Document's own attribute --
    Fault("a fieldname is renamed to one of Document's reserved attributes, so "
          "every instance of the DocType overwrites it on load", True,
          [(TRIP_JSON, TRIP_NAME_FIELD,
            '  {\n'
            '   "fieldname": "flags",\n'
            '   "fieldtype": "Data",\n')]),

    # -- a DocType-level field reference that stops resolving --
    Fault("title_field names a field that no longer exists, so the name reaches "
          "the link-search query as a column", True,
          [(KA_JSON, KA_TITLE_FIELD, ' "title_field": "article_title"\n')]),

    # -- the silent one: a default a Select cannot hold --
    Fault("a Select field's default is not one of its options, so every new "
          "document starts holding a value the field cannot have", True,
          [(PINV_JSON, PINV_STATUS_DEFAULT,
            '   "default": "Drafted",\n'
            '   "fieldname": "status",\n')]),

    # -- a permission row frappe would have refused --
    Fault("a permission row grants cancel without submit, which frappe rejects "
          "on save and nothing checks on deploy", True,
          [(RESOURCE_JSON, RESOURCE_FIRST_PERM,
            '  {\n'
            '   "cancel": 1,\n'
            '   "create": 1,\n'
            '   "delete": 1,\n'
            '   "email": 1,\n'
            '   "export": 1,\n'
            '   "print": 1,\n'
            '   "read": 1,\n'
            '   "report": 1,\n'
            '   "role": "System Manager",\n')]),

    # -- a state that colours a status the field cannot hold --
    Fault("a states entry names a status that is not one of the field's options, so "
          "indicator.js:82 never finds it and the colour silently does nothing", True,
          [(PROJECT_JSON, PROJECT_OPEN_STATE,
            '  {\n'
            '   "color": "Green",\n'
            '   "title": "Opened"\n'
            '  },\n')]),

    # -- a state colour outside the ten DocType State offers --
    Fault("a states entry is given a colour DocType State's Select does not offer, which "
          "stops the Desk saving the DocType and renders a class with no CSS rule", True,
          [(ACTIVITY_JSON, ACTIVITY_CANCELLED_STATE,
            '  {\n'
            '   "color": "Black",\n'
            '   "title": "Cancelled"\n'
            '  }\n')]),

    # Negative control. A field's label is user-visible text that no rule in
    # this sweep reads: every check judges fieldnames, fieldtypes, options,
    # defaults and permission flags. If this goes red, the sweep has started
    # pinning the wording of the form rather than the validity of the DocType,
    # and the sweep is what needs fixing.
    Fault("CONTROL: a field's label reworded (must stay green)", False,
          [(TRIP_JSON, '   "label": "Trip Name",\n',
            '   "label": "Name of Trip",\n')]),
])


# --- status literals in client scripts ------------------------------------
# tests/offline/test_status_literals.py. The browser-side half of
# `test_select_values.py`: nothing in frappe compares a string in a `.js` file
# to a DocType's `options`, so a stale status name is valid JavaScript that
# decides the wrong thing forever. Three shapes, three different outcomes, and
# none of them raises: a map miss read through `set_indicator_formatter` prints
# `class="indicator undefined"`; the same miss inside `get_indicator` is
# skipped by frappe's truthiness guard unless it sits inside a returned array,
# in which case it reaches the pill's class attribute; and a `!=` against a
# value the field cannot hold is simply always true. The test file's docstring
# carries the frappe line numbers for each.
#
# The faults below are in two groups, because the test file makes two kinds of
# claim and either can fail on its own:
#   * the rule -- no client script names a value its Select field cannot hold;
#   * the floors -- the sweep still reaches 20 sites, both shapes are still
#     matched, and 19 of them are still judged against a declared `Select`.
# A rule that has stopped looking at anything passes, which is the failure this
# suite keeps meeting, so the floors are injected against as deliberately as
# the rule is.

TE_JS = "erplite/projects/doctype/timesheet_entry/timesheet_entry.js"
TEL_JS = "erplite/projects/doctype/timesheet_entry/timesheet_entry_list.js"
TRIP_JS = "erplite/projects/doctype/trip/trip.js"
ACT_JS = "erplite/projects/doctype/activity/activity.js"
ST_JS = "erplite/scheduler/doctype/schedule_template/schedule_template.js"
RES_JS = "erplite/scheduler/doctype/resource/resource.js"
XS_JS = "erplite/setup/doctype/xero_settings/xero_settings.js"
TRIP_JSON = "erplite/projects/doctype/trip/trip.json"
ACT_JSON = "erplite/projects/doctype/activity/activity.json"

TRIP_OPTIONS = '"options": "Planned\\nIn Progress\\nCompleted\\nCancelled"'
ACT_STATUS_FIELD = ('"fieldname": "status",\n'
                    '   "fieldtype": "Select",\n'
                    '   "hidden": 1,')

STATUS_LITERALS = Target(
    test="tests/offline/test_status_literals.py",
    faults=[
        # -- the rule, once per file that has a judged site, because a typo in
        # -- one client script tells you nothing about the next one --
        Fault("a status compared to a value the field cannot hold: the approval "
              "button never appears (Timesheet Entry)", True,
              [(TE_JS, "frm.doc.status === 'Submitted'",
                "frm.doc.status === 'Submitting'")]),
        Fault("one arm of an || is impossible: a rejected entry stays editable "
              "(Timesheet Entry)", True,
              [(TE_JS, "frm.doc.status === 'Rejected'",
                "frm.doc.status === 'Declined'")]),
        Fault("a status compared to a value the field cannot hold: Start Trip "
              "is never offered (Trip)", True,
              [(TRIP_JS, 'frm.doc.status === "Planned"',
                'frm.doc.status === "Plan"')]),
        Fault("a non-status Select compared to an impossible value: equipment "
              "capacity is never set (Resource)", True,
              [(RES_JS, "frm.doc.resource_type === 'Person'",
                "frm.doc.resource_type === 'Persons'")]),
        Fault("the Australian spelling of an American option: Disconnect from "
              "Xero never shows (Xero Settings)", True,
              [(XS_JS, "frm.doc.authorization_status === 'Authorized'",
                "frm.doc.authorization_status === 'Authorised'")]),
        # -- the map shapes: a hole in a colour map, which renders the word
        # -- `undefined` into a class attribute rather than throwing --
        Fault("a key in an indicator colour map no longer matches an option: "
              "the indicator loses its colour (Activity)", True,
              [(ACT_JS, "'Complete': 'blue',", "'Completed': 'blue',")]),
        Fault("a key in a named colour map no longer matches an option: the "
              "fallback colour is used for sick leave (Schedule Template)", True,
              [(ST_JS, "'sick': '#ec4899',", "'Sick': '#ec4899',")]),
        # -- the other direction: the literal stays, the options move under it.
        # -- Editing a Select's options is the commonest way a correct client
        # -- script becomes a wrong one, and nothing on deploy compares them.
        Fault("an option is dropped from the DocType JSON, leaving a correct "
              "client script naming a value that no longer exists (Trip)", True,
              [(TRIP_JSON, TRIP_OPTIONS,
                '"options": "Planned\\nCompleted\\nCancelled"')]),
        # -- the floors. Each of these leaves the rule above true and takes a
        # -- site out of its reach, which is the only way this file can go
        # -- quiet without anyone noticing.
        Fault("CONTROL-SHAPED REGRESSION: a behaviour-preserving refactor to "
              "`includes()` takes a comparison out of the sweep's reach "
              "(Timesheet Entry list)", True,
              [(TEL_JS, '} else if (doc.status === "Approved") {',
                '} else if (["Approved"].includes(doc.status)) {')]),
        Fault("a map is keyed through a call, so the `[doc.field]` shape stops "
              "matching and the map shape goes quiet (Schedule Template)", True,
              [(ST_JS, "status_colors[frm.doc.status]",
                "status_colors[String(frm.doc.status)]")]),
        Fault("a judged Select becomes a Data field, so every literal compared "
              "to it stops being judged (Activity)", True,
              [(ACT_JSON, ACT_STATUS_FIELD,
                '"fieldname": "status",\n'
                '   "fieldtype": "Data",\n'
                '   "hidden": 1,')]),

        # -- negative controls: real edits that change no behaviour. If one of
        # -- these goes red, the test is pinning the source's spelling rather
        # -- than what the code does.
        Fault("control: the quotes around a correct literal change from double "
              "to single", False,
              [(TRIP_JS, 'frm.doc.status === "Planned"',
                "frm.doc.status === 'Planned'")]),
        Fault("control: a correct comparison goes from === to ==", False,
              [(TE_JS, "frm.doc.status === 'Approved'",
                "frm.doc.status == 'Approved'")]),
        Fault("control: the colour map's variable is renamed", False,
              [(ST_JS, "const status_colors = {", "const status_palette = {"),
               (ST_JS, "status_colors[frm.doc.status]",
                "status_palette[frm.doc.status]")]),
        Fault("control: a Select's options are reordered, same set", False,
              [(TRIP_JSON, TRIP_OPTIONS,
                '"options": "Cancelled\\nCompleted\\nIn Progress\\nPlanned"')]),
    ])


# --- a function shadowing a module-level import -------------------------------
# tests/offline/test_shadowed_imports.py. Python's own scoping rule, not
# frappe's: a name assigned anywhere in a function body is local for the whole
# body, so a module-level import used above that binding raises
# UnboundLocalError. It compiles, it imports, and it resolves under a linter.
#
# The two real instances this guard was written for -- in
# erplite/everything_search/api.py -- were fixed and then the whole feature was
# removed (#9), so both passes now sweep 134 files and find nothing. That is the
# right answer and it is also why this target matters more than most: with no
# live instance left, the only thing keeping the walker honest against real
# source was that it was green, and green is what a walker that found nothing at
# all would also be.
#
# Nearly every fault below is the SAME use site under the SAME three `_()`
# guards, varying only the form of the binding. That is deliberate: the use, the
# file and the line distance are held constant so the one thing that differs is
# the thing being tested -- whether the walker recognises that form as a binding.

XAPI = "erplite/xero/api.py"

# handle_callback() calls _() at three guards before this point, so any binding
# of `_` introduced here is live: all three raise UnboundLocalError.
EXCHANGE = (
    '    # Exchange code for tokens\n'
    '    if auth.get_tokens(code):\n')
EXCHANGE_BODY = (
    EXCHANGE
    + '        frappe.msgprint(_("Successfully connected to Xero"))\n'
    '        return True\n')

# sync_all() first uses now_datetime() inside the frappe.get_doc({...}) below.
SYNC_LOG_OPEN = (
    '        # Create sync log\n'
    '        sync_log = frappe.get_doc({\n')
SYNC_LOG_SAVED = (
    '        sync_log.insert()\n'
    '        frappe.db.commit()\n')

# A local alias for a module-level import. Behaviourally identical -- same
# object, same call -- which is what makes the pair below an experiment rather
# than two edits: above the first use it is harmless and must stay green; below
# it, the same line is an UnboundLocalError and must go red.
ALIAS = '        now_datetime = frappe.utils.now_datetime\n'

SHADOWED_IMPORTS = Target(
    test="tests/offline/test_shadowed_imports.py",
    faults=[
        # --- pass A: a module-level import used before it is bound locally ----
        # The original bug, restored in its original shape: a returned pair with
        # the second element thrown away into `_`.
        Fault("`_` bound by a discarded tuple element (the shape the guard was "
              "written for)", True, [
                  (XAPI, EXCHANGE,
                   '    # Exchange code for tokens\n'
                   '    tokens, _ = auth.get_tokens(code)\n'
                   '    if tokens:\n'),
              ]),
        Fault("`_` bound by a for-loop target", True, [
            (XAPI, EXCHANGE_BODY,
             '    # Exchange code for tokens, retrying a transient failure\n'
             '    for _ in range(3):\n'
             '        if auth.get_tokens(code):\n'
             '            frappe.msgprint(_("Successfully connected to Xero"))\n'
             '            return True\n'),
        ]),
        Fault("`_` bound by a `with ... as`", True, [
            (XAPI, EXCHANGE,
             '    # Exchange code for tokens\n'
             '    with frappe.db.savepoint("xero_tokens") as _:\n'
             '        tokens = auth.get_tokens(code)\n'
             '    if tokens:\n'),
        ]),
        Fault("`_` bound by an `except ... as`", True, [
            (XAPI, EXCHANGE,
             '    # Exchange code for tokens\n'
             '    try:\n'
             '        tokens = auth.get_tokens(code)\n'
             '    except Exception as _:\n'
             '        tokens = None\n'
             '    if tokens:\n'),
        ]),
        Fault("`_` bound by a walrus", True, [
            (XAPI, EXCHANGE,
             '    # Exchange code for tokens\n'
             '    if (_ := auth.get_tokens(code)):\n'),
        ]),
        # The binding ast reports as an Import node rather than a Name in Store
        # context, so a walk over Name nodes alone cannot see it. A deferred
        # import is ordinary in a frappe app, which is what makes it reachable.
        Fault("`_` bound by the function's own `from frappe import _`", True, [
            (XAPI, EXCHANGE,
             '    # Exchange code for tokens\n'
             '    from frappe import _\n'
             '    if auth.get_tokens(code):\n'),
        ]),
        # Pass A must not be about `_`. Same edit as the control below it, moved
        # from above the first use of now_datetime() to below it.
        Fault("a module import other than `_` used before it is bound "
              "(now_datetime)", True, [
                  (XAPI, SYNC_LOG_SAVED,
                   '        sync_log.insert()\n' + ALIAS
                   + '        frappe.db.commit()\n'),
              ]),

        # --- pass B: stricter, and only about `_` -----------------------------
        # get_connection_status() never calls _(), so there is no use before the
        # binding and pass A is right to stay quiet. Pass B is the only thing
        # that fails here -- delete it and this fault goes green, which is what
        # "stricter" has to mean to be worth having. get_value with a list
        # fieldname returns a tuple, so the unpack is the real frappe idiom.
        Fault("`_` bound with nothing calling _() in that function yet "
              "(latent: pass B only)", True, [
                  (XAPI, '    last_sync = frappe.db.get_value("Xero Sync Log", ',
                   '    last_sync, _ = frappe.db.get_value("Xero Sync Log", '),
                  (XAPI, 'fieldname="creation",',
                   'fieldname=["creation", "status"],'),
              ]),

        # --- controls: real edits, no behaviour changed, must stay green ------
        # A comprehension's loop target is bound in the comprehension's own
        # scope, so this function never binds `_` at all and its three _() calls
        # are fine. `[... for _ in ...]` is ordinary Python; a guard that fails
        # on it gets deleted rather than fixed. This control is what found the
        # false positive -- it went red before _comprehension_scoped existed.
        Fault("a comprehension target named `_` (not a binding of the enclosing "
              "function)", False, [
                  (XAPI, EXCHANGE,
                   '    # Exchange code for tokens\n'
                   '    retry_slots = [None for _ in range(3)]\n'
                   '    if auth.get_tokens(code):\n'),
              ]),
        # Two claims in one: a parameter is bound on entry so it has no unbound
        # window, and a nested def is its own scope so its binding must not be
        # attributed to handle_callback -- which would report the outer _()
        # calls as the bug.
        Fault("a nested function whose parameter is named `_`", False, [
            (XAPI, EXCHANGE,
             '    # Exchange code for tokens\n'
             '    def _unchanged(_):\n'
             '        return _\n'
             '    if auth.get_tokens(code):\n'),
        ]),
        Fault("a local tuple unpack of names that are not module-level imports",
              False, [
                  (XAPI, EXCHANGE,
                   '    # Exchange code for tokens\n'
                   '    mime, token_kind = (None, None)\n'
                   '    if auth.get_tokens(code):\n'),
              ]),
        # The documented limit of pass A, held as a control so that widening it
        # to latent non-`_` names is a decision somebody makes rather than a
        # drift nobody notices. Identical text to the red fault above; only its
        # position relative to the first use differs.
        Fault("a module import other than `_` bound ABOVE its first use "
              "(latent: pass A's stated limit)", False, [
                  (XAPI, SYNC_LOG_OPEN,
                   '        # Create sync log\n' + ALIAS
                   + '        sync_log = frappe.get_doc({\n'),
              ]),
    ],
)

# --- the scheduler's project and activity query ---------------------------
# tests/offline/test_scheduler_api.py.
# `get_projects_and_activities` is reached only through `get_scheduler_data`,
# the scheduler's one entry point, so every project row and activity label the
# scheduler shows comes out of this single function. It used to be raw SQL over
# six columns whose fields were removed by 8126278; `bench migrate` does not
# drop a column when its field goes and this app ships no patch that does, so
# the columns survived as orphans and the query returned stale or empty values
# instead of raising `Unknown column`. The replacement uses `frappe.get_all` on
# the real fields.
#
# Which DocType each orphan belonged to is the whole difficulty: `work_type`
# went from Project and is still a live field on Activity, so a flat list of all
# six -- which is what the test file had -- calls a correct Activity query a
# regression. The first control below is what found that.

SAPI = "erplite/scheduler/api.py"

# The six anchors, each matching exactly once in a CRLF file.
SA_PROJ_FIELDS = '        fields=["name", "project_name", "status", "project_lead", "division"],\n'
SA_PROJ_FILTERS = '        filters={"status": ["!=", "Archived"]},\n'
SA_PROJ_ORDER = '        order_by="project_name"\n'
SA_ACT_FIELDS = '            fields=["name", "activity_name", "status"],\n'
SA_ACT_FILTERS = '            filters={"project": project.name, "status": ["!=", "Cancelled"]},\n'
SA_ACT_ORDER = '            order_by="activity_name"\n'

SA_ALIAS = "            activity['subject'] = activity.activity_name\n"
SA_DIV_NAME = "                project['division_name'] = division_data.division_name\n"
SA_DIV_COLOR = "                project['division_color'] = division_data.color\n"

# Whole blocks, for the two renaming controls. Note the trailing space after
# `project.division,` -- it is in the source and the pattern must carry it.
SA_DIV_BLOCK = (
    '        if project.division:\n'
    '            division_data = frappe.db.get_value("Division", project.division, \n'
    '                ["division_name", "color"], as_dict=True)\n'
    '            if division_data:\n'
    "                project['division_name'] = division_data.division_name\n"
    "                project['division_color'] = division_data.color\n"
)
SA_ALIAS_BLOCK = (
    '        for activity in activities:\n'
    '            # Compatibility alias: the built scheduler bundle under\n'
    '            # erplite/public/frontend/assets/ still reads `subject`. Remove this\n'
    '            # once the frontend has been rebuilt from frontend/src.\n'
    "            activity['subject'] = activity.activity_name\n"
)


SCHEDULER_API = Target(
    test="tests/offline/test_scheduler_api.py",
    faults=[
        # --- each orphaned column back, at the DocType it was removed from ---
        # One fault per column rather than one sample: the file's claim is about
        # six columns, and a test that notices two of them guards two. Each is
        # caught twice over -- by name, as the specific regression, and by the
        # stand-in refusing a field the DocType JSON does not have -- which is
        # deliberate: the named list is documentation that rots loudly, the
        # stand-in is the backstop that covers every other field name too.
        Fault("orphan back in the Project query: project_manager", True, [
            (SAPI, SA_PROJ_FIELDS,
             '        fields=["name", "project_name", "status", "project_manager", "division"],\n')]),
        Fault("orphan back in the Project query: work_type", True, [
            (SAPI, SA_PROJ_FIELDS,
             '        fields=["name", "project_name", "status", "project_lead", "division", "work_type"],\n')]),
        Fault("orphan back in the Activity query: subject", True, [
            (SAPI, SA_ACT_FIELDS,
             '            fields=["name", "activity_name", "status", "subject"],\n')]),
        Fault("orphan back in the Activity query: priority", True, [
            (SAPI, SA_ACT_FIELDS,
             '            fields=["name", "activity_name", "status", "priority"],\n')]),
        Fault("orphan back in the Activity query: estimated_hours", True, [
            (SAPI, SA_ACT_FIELDS,
             '            fields=["name", "activity_name", "status", "estimated_hours"],\n')]),
        Fault("orphan back in the Activity query: progress_percent", True, [
            (SAPI, SA_ACT_FIELDS,
             '            fields=["name", "activity_name", "status", "progress_percent"],\n')]),

        # The other two places the test looks. `fields` is the obvious one; a
        # filter or an order_by on a column nothing maintains is the quieter
        # regression, because it changes which rows come back rather than
        # adding a key nobody reads.
        Fault("orphan in a filter, not in fields (Project.project_manager)", True, [
            (SAPI, SA_PROJ_FILTERS,
             '        filters={"status": ["!=", "Archived"], "project_manager": "zeke@company.test"},\n')]),
        Fault("orphan in order_by: Activity ordered by subject again, which is "
              "the regression this file was written for", True, [
                  (SAPI, SA_ACT_ORDER, '            order_by="subject"\n')]),
        Fault("orphan in order_by: Project ordered by project_manager", True, [
            (SAPI, SA_PROJ_ORDER, '        order_by="project_manager"\n')]),

        # Across DocTypes. ORPHANED is keyed by DocType, so this one is NOT
        # caught by the named list -- it is caught by the stand-in refusing a
        # field Activity does not have. The fault exists to pin that narrowing
        # the list to its DocTypes left this covered rather than uncovered.
        Fault("an orphan asked of the wrong DocType (Activity.project_manager) "
              "-- the stand-in's catch, not the named list's", True, [
                  (SAPI, SA_ACT_FIELDS,
                   '            fields=["name", "activity_name", "status", "project_manager"],\n')]),

        # --- the title and its compatibility alias ---------------------------
        Fault("the subject alias deleted (the built bundle calls "
              ".toLowerCase() on it with no guard)", True, [
                  (SAPI, SA_ALIAS, "")]),
        Fault("the alias set from the wrong field", True, [
            (SAPI, SA_ALIAS, "            activity['subject'] = activity.status\n")]),
        # The plausible wrong fix: do the aliasing in the query instead of the
        # loop. It looks tidier and leaves activity_name absent from every row,
        # so the real title is gone and only the compatibility key survives.
        Fault("activity_name aliased in the query, so the real field is gone", True, [
            (SAPI, SA_ACT_FIELDS,
             '            fields=["name", "activity_name as subject", "status"],\n')]),

        # --- project_lead, which is what replaced project_manager -----------
        # Not the same fault as the orphan above: that one asks whether the
        # removed column is queried, this one asks whether the live field
        # reaches the caller under its own name.
        Fault("project_lead dropped from the Project query", True, [
            (SAPI, SA_PROJ_FIELDS,
             '        fields=["name", "project_name", "status", "division"],\n')]),

        # --- which rows come back -------------------------------------------
        Fault("Archived projects no longer filtered out", True, [
            (SAPI, SA_PROJ_FILTERS, '        filters={},\n')]),
        Fault("Cancelled activities no longer filtered out", True, [
            (SAPI, SA_ACT_FILTERS,
             '            filters={"project": project.name},\n')]),
        Fault("the project filter dropped, so every project gets every "
              "activity", True, [
                  (SAPI, SA_ACT_FILTERS,
                   '            filters={"status": ["!=", "Cancelled"]},\n')]),

        # --- the order -------------------------------------------------------
        # These two are the pair that pins the ordering claim. Ordering by
        # `name` used to be GREEN: the fixture's ids happened to sort the same
        # way as their titles, so the assertion could not tell "ordered by
        # activity_name" from "ordered at all". One fixture id was renamed so
        # the two orderings disagree; without that, this fault passes.
        Fault("ordered by name rather than activity_name (green until the "
              "fixture was made to discriminate)", True, [
                  (SAPI, SA_ACT_ORDER, '            order_by="name"\n')]),
        Fault("not ordered at all", True, [
            (SAPI, SA_ACT_ORDER, '            order_by=None\n')]),

        # --- the division lookup ---------------------------------------------
        Fault("division_name taken from the colour field", True, [
            (SAPI, SA_DIV_NAME,
             "                project['division_name'] = division_data.color\n")]),
        Fault("division_color taken from the name field", True, [
            (SAPI, SA_DIV_COLOR,
             "                project['division_color'] = division_data.division_name\n")]),
        Fault("the division lookup dropped entirely", True, [
            (SAPI, SA_DIV_NAME + SA_DIV_COLOR, "                pass\n")]),

        # --- controls: real edits, no behaviour changed, must stay green ------
        # THIS is the one that earned its keep. work_type is a live field on
        # Activity (activity.json, in_standard_filter, added by the same commit
        # that removed it from Project), so asking Activity for it is ordinary
        # correct code. The test reported it as "an orphaned column on Activity,
        # not a field", because its ORPHANED list was flat and checked against
        # every query regardless of DocType. A guard that fails on correct code
        # gets deleted rather than fixed, so this was worth more than a miss.
        Fault("the Activity query asks for work_type, which IS an Activity "
              "field", False, [
                  (SAPI, SA_ACT_FIELDS,
                   '            fields=["name", "activity_name", "status", "work_type"],\n')]),
        # Two more live fields, to pin that the control above is about DocType
        # scoping and not about work_type's spelling.
        Fault("the Activity query asks for description and estimate, both live "
              "fields", False, [
                  (SAPI, SA_ACT_FIELDS,
                   '            fields=["name", "activity_name", "status", "description", "estimate"],\n')]),
        Fault("the Project query asks for project_code, a live field", False, [
            (SAPI, SA_PROJ_FIELDS,
             '        fields=["name", "project_name", "status", "project_lead", "division", "project_code"],\n')]),

        # Renames: the source changes, nothing observable does. If either goes
        # red the test is pinning the function's internals rather than what it
        # returns, which is a finding about the test.
        Fault("a local variable renamed (division_data -> division_row)", False, [
            (SAPI, SA_DIV_BLOCK,
             '        if project.division:\n'
             '            division_row = frappe.db.get_value("Division", project.division, \n'
             '                ["division_name", "color"], as_dict=True)\n'
             '            if division_row:\n'
             "                project['division_name'] = division_row.division_name\n"
             "                project['division_color'] = division_row.color\n")]),
        Fault("the loop variable renamed (activity -> row)", False, [
            (SAPI, SA_ALIAS_BLOCK,
             '        for row in activities:\n'
             '            # Compatibility alias: the built scheduler bundle under\n'
             '            # erplite/public/frontend/assets/ still reads `subject`. Remove this\n'
             '            # once the frontend has been rebuilt from frontend/src.\n'
             "            row['subject'] = row.activity_name\n")]),
        # The `if project.division:` guard removed. Green, and the reason is
        # worth writing down rather than discovering twice: frappe's
        # db.get_value with `filters=None` does NOT fall through to "no WHERE
        # clause, take the first row" -- database.py:614 sends it to
        # get_values_from_single, which reads tabSingles, and Division is not a
        # Single DocType. So a project with no division still gets no division
        # attached; the edit costs a pointless query and changes no result. The
        # stand-in returns None by a different route and agrees on the outcome.
        Fault("the `if project.division:` guard made unconditional", False, [
            (SAPI, "        if project.division:\n", "        if True:\n")]),
    ],
)



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
    "string_refs": STRING_REFS,
    "select_values": SELECT_VALUES,
    "todo_status_patch": TODO_STATUS_PATCH,
    "afterz_workflow": AFTERZ_WORKFLOW,
    "query_fields": QUERY_FIELDS,
    "undeclared_attrs": UNDECLARED_ATTRS,
    "mandatory_fields": MANDATORY_FIELDS,
    "projects_api": PROJECTS_API,
    "raw_sql": RAW_SQL,
    "scheduler_role_delete": SCHEDULER_ROLE_DELETE,
    "endpoint_wiring": ENDPOINT_WIRING,
    "read_shapes": READ_SHAPES,
    "client_doctypes": CLIENT_DOCTYPES,
    "api_url_methods": API_URL_METHODS,
    "doctype_json_validation": DOCTYPE_JSON_VALIDATION,
    "status_literals": STATUS_LITERALS,
    "shadowed_imports": SHADOWED_IMPORTS,
    "scheduler_api": SCHEDULER_API,
}
