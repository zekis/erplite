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

TARGETS = {
    "xero_gate": XERO_GATE,
    "timesheet_ownership": TIMESHEET_OWNERSHIP,
    "timesheet_target_user": TIMESHEET_TARGET_USER,
    "scheduler_read_gate": SCHEDULER_READ_GATE,
}
