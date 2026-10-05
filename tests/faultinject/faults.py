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


TARGETS = {"xero_gate": XERO_GATE}
