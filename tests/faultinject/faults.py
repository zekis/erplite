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
              True, [(TSE,
                      TSE_WRITE_CHECK
                      + "            frappe.throw(_(\n"
                        '                "You can only book time against your own name. "\n'
                        '                "Set Employee to yourself, or ask someone who may book time for "\n'
                        '                "others to enter it."\n'
                        "            ))\n",
                      "")]),
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


TARGETS = {
    "xero_gate": XERO_GATE,
    "timesheet_ownership": TIMESHEET_OWNERSHIP,
}
