# -*- coding: utf-8 -*-
"""Sending an invoice to Xero: what status it gets, and what a retry does.

This file pins the two decisions the owner made on 7 Oct 2026 (review tray
items rev_7b11901cfb and rev_5c3dfe6ff3). Both land in the same two functions,
`xero/accounts.py::create_sales_invoice` and `::create_purchase_invoice`.

## 1. Every invoice goes to Xero as a DRAFT, and now says so

The old line was

    "Status": "AUTHORISED" if <doc>.status == "Submitted" else "DRAFT",

which reads like a choice the document makes. It is not one:

  * **Sales Invoice** is not submittable (no `is_submittable` in its JSON, so
    `on_submit` never runs) and `status` is `read_only: 1`, so the field holds
    its default `"Draft"` for the life of the record. The AUTHORISED side of
    that branch was unreachable.
  * **Purchase Invoice** has the same unreachable `on_submit`, but its `status`
    Select is **not** read-only, so a user could set it to `Submitted` by hand
    and save. The same line then sent an **authorised** bill into the real Xero
    ledger. `send_to_xero` also writes `status = "Submitted"` after a successful
    send, so a second send of the same record would have been authorised too,
    had the already-sent guard not stopped it first.

Drafts are what the owner wants: invoices are reviewed and approved in Xero,
not in this app. So the status is now literally `"DRAFT"` at both call sites and
the branch is gone. For Sales Invoice that is dead code removed; for Purchase
Invoice it is a real behaviour change, and the tests below say so.

## 2. A send that fails without saying whether Xero got it

`xero_invoice_id` is written only after Xero answers 200, and the already-sent
guard in `send_to_xero` reads that same locally stored id. So a POST that
reaches Xero whose reply is lost leaves three things true at once: the invoice
is in Xero, the guard is still open, and the user is reading "Failed to send
invoice to Xero". The obvious retry creates a second invoice in the real
accounts -- measured, before the fix:

| step       | user saw             | invoices in Xero | `xero_invoice_id` |
|------------|----------------------|------------------|-------------------|
| click Send | "Failed ... timeout" | **1**            | `None`            |
| click again| *success*            | **2**            | `xero-2`          |

`find_invoice_in_xero` now asks Xero, by `InvoiceNumber`, before posting. Three
things about it are deliberate and are each pinned below:

  * it **never answers "not there" on doubt** -- an unreachable Xero, a non-200,
    an unreadable body, or a response that came back carrying other invoices'
    numbers (which means Xero ignored the filter, so the 100-row cap could be
    hiding ours) all stop the send instead of guessing;
  * a match must agree on `InvoiceNumber`, `Type` **and** the contact's name,
    because an ACCPAY number is the *supplier's* and two suppliers can both use
    "INV-001" -- matching on the number alone would block a legitimate bill;
  * `VOIDED` and `DELETED` invoices do not match, because Xero frees that number
    again and the send should go through.

And `send_to_xero` now re-raises `frappe.ValidationError` unchanged instead of
re-wrapping it as "Failed to send invoice to Xero: ...". A stop has to read as a
stop: re-labelling "Xero already has this invoice" as a failure is precisely
what invites the retry this work exists to prevent.

## What is NOT tested here, and cannot be

Whether Xero itself accepts or rejects a duplicate `InvoiceNumber`. That needs a
real write to the owner's accounts. Everything above holds either way: the point
is that the app no longer sends the second one.
"""
import datetime
import importlib.util
import io
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from fake_frappe import (  # noqa: E402
    FakeDocumentBase, FakeFrappe, ValidationError, _dict, doctype_fields,
    doctype_permissions,
)

APP_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
XERO_DIR = os.path.join(APP_ROOT, "erplite", "xero")

# Frappe's own File DocType, which the attachment upload queries. Not an erplite
# DocType, so there is no JSON in this repo to read it from.
FILE_FIELDS = {"name", "file_name", "file_url", "is_private", "attached_to_doctype",
               "attached_to_name", "owner", "creation", "modified", "modified_by",
               "docstatus", "idx"}


class Doc(object):
    """Document stand-in.

    Deliberately not a dict subclass: `_dict` inherits `dict.items`, which would
    shadow the `items` child table and make `for item in sales_invoice.items`
    iterate a bound method.
    """

    def __init__(self, **kw):
        self.__dict__.update(kw)
        self.comments = []

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __contains__(self, key):
        return key in self.__dict__

    def add_comment(self, kind, text):
        self.comments.append((kind, text))


class LostReply(Exception):
    """requests.exceptions.ReadTimeout: the POST reached Xero, the reply did not."""


class Unreachable(Exception):
    """requests.exceptions.ConnectionError on the lookup."""


class _Response(object):
    def __init__(self, status_code, payload, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeXero(object):
    """Xero, as far as this module can tell.

    `posted` is what Xero holds. An invoice is added to it *before* the reply is
    sent, because that is the order that makes the lost-reply case possible at
    all.
    """

    def __init__(self, lose_reply_on=(), holding=(), lookup_raises=None,
                 lookup_status=None, ignore_filter=False):
        self.posted = list(holding)
        self.lose_reply_on = set(lose_reply_on)
        self.lookup_raises = lookup_raises
        self.lookup_status = lookup_status
        self.ignore_filter = ignore_filter
        self.posts = 0
        self.lookups = []

    def post(self, url, headers=None, data=None, timeout=None, files=None, **kw):
        assert timeout is not None, "POST to %s has no timeout" % url
        self.posts += 1
        body = json.loads(data)
        created = []
        for invoice in body.get("Invoices", []):
            stored = dict(invoice)
            stored["InvoiceID"] = "xero-%d" % self.posts
            created.append(stored)
            self.posted.append(stored)
        if self.posts in self.lose_reply_on:
            raise LostReply("read timeout waiting for Xero")
        return _Response(200, {"Invoices": created})

    def get(self, url, headers=None, params=None, timeout=None, **kw):
        assert timeout is not None, "GET to %s has no timeout" % url
        self.lookups.append(dict(params or {}))
        if self.lookup_raises:
            raise self.lookup_raises("could not connect to api.xero.com")
        if self.lookup_status:
            return _Response(self.lookup_status, None, text="Forbidden")
        wanted = (params or {}).get("InvoiceNumbers")
        if self.ignore_filter or not wanted:
            found = list(self.posted)
        else:
            found = [i for i in self.posted
                     if str(i.get("InvoiceNumber", "")).lower() == str(wanted).lower()]
        return _Response(200, {"Invoices": found})


def xero_invoice(number, type_="ACCREC", contact="Novalith Technologies",
                 status="DRAFT", invoice_id="xero-pre"):
    """An invoice Xero already holds before the test starts."""
    return {"InvoiceID": invoice_id, "InvoiceNumber": number, "Type": type_,
            "Status": status, "Contact": {"Name": contact}}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_under_test(frappe, xero):
    """Install the stand-ins and load the real modules on top of them.

    `erplite/xero/__init__.py` is loaded from the file rather than faked, so
    `XERO_HTTP_TIMEOUT` is the value the app ships.
    """
    for name in list(sys.modules):
        if name == "frappe" or name.startswith("frappe.") or name.startswith("erplite"):
            del sys.modules[name]

    pkg = types.ModuleType("frappe")
    pkg.__path__ = []
    for attr in dir(frappe):
        if not attr.startswith("__"):
            setattr(pkg, attr, getattr(frappe, attr))
    pkg._dict = _dict
    pkg.ValidationError = ValidationError

    utils = types.ModuleType("frappe.utils")
    utils.now_datetime = lambda: datetime.datetime(2026, 10, 7, 9, 0, 0)
    utils.cstr = lambda v: "" if v is None else str(v)
    utils.get_files_path = lambda *a, **k: "/tmp"
    utils.get_datetime = lambda v: v
    pkg.utils = utils

    model = types.ModuleType("frappe.model")
    model.__path__ = []
    document = types.ModuleType("frappe.model.document")
    document.Document = FakeDocumentBase
    model.document = document
    pkg.model = model

    requests = types.ModuleType("requests")
    requests.post = xero.post
    requests.get = xero.get
    requests.put = lambda *a, **k: _Response(200, {})
    exceptions = types.ModuleType("requests.exceptions")
    exceptions.ReadTimeout = LostReply
    exceptions.ConnectionError = Unreachable
    requests.exceptions = exceptions

    auth = types.ModuleType("erplite.xero.auth")
    auth.get_valid_token = lambda: "a-valid-token"

    sys.modules.update({
        "frappe": pkg, "frappe.utils": utils, "frappe.model": model,
        "frappe.model.document": document, "requests": requests,
        "requests.exceptions": exceptions,
    })
    erplite = types.ModuleType("erplite")
    erplite.__path__ = []
    sys.modules["erplite"] = erplite
    sys.modules["erplite.xero"] = _load("erplite.xero", os.path.join(XERO_DIR, "__init__.py"))
    sys.modules["erplite.xero.auth"] = auth

    accounts = _load("erplite.xero.accounts", os.path.join(XERO_DIR, "accounts.py"))
    sys.modules["erplite.xero.accounts"] = accounts
    sales = _load("sales_invoice_under_test",
                  os.path.join(APP_ROOT, "erplite/accounts/doctype/sales_invoice/sales_invoice.py"))
    purchase = _load("purchase_invoice_under_test",
                     os.path.join(APP_ROOT, "erplite/accounts/doctype/purchase_invoice/purchase_invoice.py"))
    return accounts, sales, purchase


def world(doctype, module, doctype_dir, row):
    """A FakeFrappe holding one invoice, its settings and no attachments."""
    frappe = FakeFrappe(session_user="zeke@tierneymorris.com.au", roles=["System Manager"])
    frappe.fields[doctype] = doctype_fields(module, doctype_dir)
    # send_to_xero checks write permission before it posts (owner's decision
    # rev_c3343b2cf3), so the rows have to be here or the gate cannot answer.
    # System Manager holds write on all four, so nothing in this file is gated
    # out -- the refusal path is test_xero_permission_gate.py's subject.
    frappe.permissions[doctype] = doctype_permissions(module, doctype_dir)
    frappe.fields["File"] = FILE_FIELDS
    frappe.tables[doctype] = [row]
    frappe.tables["File"] = []
    settings = Doc(tenant_id="tenant-abc", access_token="tok", client_id="cid",
                   client_secret="secret", authorization_status="Authorized")
    frappe.get_single = lambda dt: settings

    def get_doc(dt, dn=None, **kw):
        for stored in frappe.tables.get(dt, []):
            if stored.get("name") == dn:
                return stored
        raise ValidationError("%s %s not found" % (dt, dn))

    frappe.get_doc = get_doc
    return frappe


def sales_row(status="Draft", name="SINV-00042", customer="Novalith Technologies"):
    return Doc(name=name, customer="CUST-0001", customer_name=customer,
               posting_date=datetime.date(2026, 10, 1),
               due_date=datetime.date(2026, 10, 31),
               status=status, xero_invoice_id=None, xero_invoice_number=None,
               xero_status=None, xero_sync_date=None,
               items=[Doc(description="CCTP Systems Engineering support",
                          item_name="Engineering", qty=100, rate=140.0, tax_rate=10)])


def purchase_row(status="Draft", name="PINV-00007", supplier="Novalith Technologies",
                 supplier_invoice_number="INV-001"):
    return Doc(name=name, supplier="SUPP-0001", supplier_name=supplier,
               supplier_invoice_number=supplier_invoice_number,
               posting_date=datetime.date(2026, 10, 1),
               due_date=datetime.date(2026, 10, 31),
               status=status, xero_invoice_id=None, xero_invoice_number=None,
               xero_status=None, xero_sync_date=None,
               items=[Doc(description="Rack mount kit", item_name="Hardware",
                          qty=2, rate=310.0, tax_rate=10)])


class InvoiceStatusTests(unittest.TestCase):
    """Decision 1: both kinds of invoice reach Xero as a DRAFT."""

    def send_sales(self, status, xero=None):
        xero = xero or FakeXero()
        frappe = world("Sales Invoice", "accounts", "sales_invoice", sales_row(status=status))
        accounts, sales, _purchase = load_under_test(frappe, xero)
        sales.send_to_xero("SINV-00042")
        return xero, frappe

    def send_purchase(self, status, xero=None):
        xero = xero or FakeXero()
        frappe = world("Purchase Invoice", "accounts", "purchase_invoice",
                       purchase_row(status=status))
        accounts, _sales, purchase = load_under_test(frappe, xero)
        purchase.send_to_xero("PINV-00007")
        return xero, frappe

    def test_sales_invoice_is_sent_as_a_draft(self):
        xero, _frappe = self.send_sales("Draft")
        self.assertEqual([i["Status"] for i in xero.posted], ["DRAFT"])
        self.assertEqual(xero.posted[0]["Type"], "ACCREC")

    def test_sales_invoice_is_a_draft_even_if_its_status_says_submitted(self):
        """`status` is read-only on Sales Invoice, so this cannot happen through
        the form. Pinned anyway: it is the input the removed branch keyed on."""
        xero, _frappe = self.send_sales("Submitted")
        self.assertEqual([i["Status"] for i in xero.posted], ["DRAFT"])

    def test_purchase_invoice_is_sent_as_a_draft(self):
        xero, _frappe = self.send_purchase("Draft")
        self.assertEqual([i["Status"] for i in xero.posted], ["DRAFT"])
        self.assertEqual(xero.posted[0]["Type"], "ACCPAY")

    def test_purchase_invoice_is_a_draft_even_when_set_to_submitted_by_hand(self):
        """The one real behaviour change: Purchase Invoice's `status` Select is
        editable, so before this change a hand-set "Submitted" sent an
        AUTHORISED bill to the live ledger."""
        xero, _frappe = self.send_purchase("Submitted")
        self.assertEqual([i["Status"] for i in xero.posted], ["DRAFT"])

    def test_the_module_no_longer_mentions_authorised(self):
        """Guard against the branch coming back by copy-paste."""
        with io.open(os.path.join(XERO_DIR, "accounts.py"), encoding="utf-8") as handle:
            source = handle.read()
        code = "\n".join(line.split("#")[0] for line in source.splitlines())
        self.assertNotIn("AUTHORISED", code)

    def test_the_local_record_keeps_what_xero_said(self):
        xero, frappe = self.send_sales("Draft")
        written = {field: value for _dt, _name, field, value in frappe.values_set}
        self.assertEqual(written["xero_invoice_id"], "xero-1")
        self.assertEqual(written["xero_status"], "DRAFT")
        self.assertEqual(written["xero_invoice_number"], "SINV-00042")


class RetryTests(unittest.TestCase):
    """Decision 2: a send whose reply is lost must not become two invoices."""

    def send_twice(self, xero, frappe, module, docname):
        outcomes = []
        for _attempt in (1, 2):
            try:
                module.send_to_xero(docname)
                outcomes.append(None)
            except Exception as error:          # noqa: BLE001 - that is the outcome
                outcomes.append(str(error))
        return outcomes

    def test_a_lost_reply_then_a_retry_leaves_one_invoice_in_xero(self):
        xero = FakeXero(lose_reply_on=(1,))
        frappe = world("Sales Invoice", "accounts", "sales_invoice", sales_row())
        _accounts, sales, _purchase = load_under_test(frappe, xero)

        first, second = self.send_twice(xero, frappe, sales, "SINV-00042")

        # The first attempt is a genuine failure and reads like one. It now
        # carries the inner message rather than "Failed to send invoice to Xero:
        # <the inner message>", because the re-wrap is what hid the stops.
        self.assertIn("read timeout waiting for Xero", first)
        # And it is in the Error Log, which is the only place a send whose
        # outcome is unknown can be traced from afterwards.
        self.assertTrue(frappe.errors, "a lost reply must leave an Error Log entry")

        self.assertEqual(len(xero.posted), 1, "the retry must not post a second invoice")
        self.assertEqual(xero.posts, 1)
        self.assertIsNotNone(second)
        self.assertIn("Xero already has invoice SINV-00042", second)
        self.assertIn("xero-1", second)

    def test_the_stop_is_not_dressed_up_as_a_failed_send(self):
        """A stop that reads as a failure is what makes someone click again."""
        xero = FakeXero(holding=[xero_invoice("SINV-00042")])
        frappe = world("Sales Invoice", "accounts", "sales_invoice", sales_row())
        _accounts, sales, _purchase = load_under_test(frappe, xero)

        with self.assertRaises(ValidationError) as caught:
            sales.send_to_xero("SINV-00042")

        self.assertNotIn("Failed to send invoice to Xero", str(caught.exception))
        self.assertIn("nothing was sent", str(caught.exception))
        self.assertEqual(xero.posts, 0)

    def test_the_already_sent_guard_is_also_reported_as_a_stop(self):
        xero = FakeXero()
        row = sales_row()
        row.xero_invoice_id = "xero-1"
        frappe = world("Sales Invoice", "accounts", "sales_invoice", row)
        _accounts, sales, _purchase = load_under_test(frappe, xero)

        with self.assertRaises(ValidationError) as caught:
            sales.send_to_xero("SINV-00042")

        self.assertEqual(str(caught.exception), "This invoice has already been sent to Xero")
        self.assertEqual(xero.posts, 0)
        self.assertEqual(xero.lookups, [], "no need to ask Xero; we already know")

    def test_an_unreachable_xero_stops_the_send_rather_than_guessing(self):
        xero = FakeXero(lookup_raises=Unreachable)
        frappe = world("Sales Invoice", "accounts", "sales_invoice", sales_row())
        _accounts, sales, _purchase = load_under_test(frappe, xero)

        with self.assertRaises(ValidationError) as caught:
            sales.send_to_xero("SINV-00042")

        self.assertIn("Could not check", str(caught.exception))
        self.assertIn("Nothing was sent", str(caught.exception))
        self.assertEqual(xero.posts, 0)

    def test_a_non_200_on_the_lookup_stops_the_send(self):
        xero = FakeXero(lookup_status=403)
        frappe = world("Sales Invoice", "accounts", "sales_invoice", sales_row())
        _accounts, sales, _purchase = load_under_test(frappe, xero)

        with self.assertRaises(ValidationError) as caught:
            sales.send_to_xero("SINV-00042")

        self.assertIn("Xero answered 403", str(caught.exception))
        self.assertEqual(xero.posts, 0)

    def test_an_ignored_filter_stops_the_send_because_absence_proves_nothing(self):
        """If Xero hands back other invoices' numbers it did not apply the
        filter, and its 100-row cap could be hiding ours on a later page."""
        xero = FakeXero(holding=[xero_invoice("SINV-00001", invoice_id="xero-a"),
                                 xero_invoice("SINV-00002", invoice_id="xero-b")],
                        ignore_filter=True)
        frappe = world("Sales Invoice", "accounts", "sales_invoice", sales_row())
        _accounts, sales, _purchase = load_under_test(frappe, xero)

        with self.assertRaises(ValidationError) as caught:
            sales.send_to_xero("SINV-00042")

        self.assertIn("under other numbers", str(caught.exception))
        self.assertEqual(xero.posts, 0)

    def test_a_voided_invoice_in_xero_does_not_block_the_send(self):
        """Xero frees the number again, so this send is the right thing to do."""
        xero = FakeXero(holding=[xero_invoice("SINV-00042", status="VOIDED")])
        frappe = world("Sales Invoice", "accounts", "sales_invoice", sales_row())
        _accounts, sales, _purchase = load_under_test(frappe, xero)

        sales.send_to_xero("SINV-00042")

        self.assertEqual(xero.posts, 1)

    def test_the_same_number_from_another_supplier_does_not_block_a_bill(self):
        """An ACCPAY `InvoiceNumber` is the supplier's own, so two suppliers can
        both send "INV-001". Matching on the number alone would refuse the
        second one for ever."""
        xero = FakeXero(holding=[xero_invoice("INV-001", type_="ACCPAY",
                                              contact="Someone Else Pty Ltd")])
        frappe = world("Purchase Invoice", "accounts", "purchase_invoice", purchase_row())
        _accounts, _sales, purchase = load_under_test(frappe, xero)

        purchase.send_to_xero("PINV-00007")

        self.assertEqual(xero.posts, 1)
        self.assertEqual(xero.posted[-1]["Contact"]["Name"], "Novalith Technologies")

    def test_the_same_number_from_the_same_supplier_does_block_a_bill(self):
        xero = FakeXero(holding=[xero_invoice("INV-001", type_="ACCPAY",
                                              contact="Novalith Technologies")])
        frappe = world("Purchase Invoice", "accounts", "purchase_invoice", purchase_row())
        _accounts, _sales, purchase = load_under_test(frappe, xero)

        with self.assertRaises(ValidationError) as caught:
            purchase.send_to_xero("PINV-00007")

        self.assertIn("Xero already has invoice INV-001", str(caught.exception))
        self.assertEqual(xero.posts, 0)

    def test_a_sales_invoice_matching_an_accpay_number_is_not_a_match(self):
        """Type is part of the match: our own SINV- number could in principle
        appear on a bill we received."""
        xero = FakeXero(holding=[xero_invoice("SINV-00042", type_="ACCPAY")])
        frappe = world("Sales Invoice", "accounts", "sales_invoice", sales_row())
        _accounts, sales, _purchase = load_under_test(frappe, xero)

        sales.send_to_xero("SINV-00042")

        self.assertEqual(xero.posts, 1)

    def test_the_lookup_asks_for_the_one_number(self):
        xero = FakeXero()
        frappe = world("Sales Invoice", "accounts", "sales_invoice", sales_row())
        _accounts, sales, _purchase = load_under_test(frappe, xero)

        sales.send_to_xero("SINV-00042")

        self.assertEqual(xero.lookups, [{"InvoiceNumbers": "SINV-00042"}])


class TimeoutTests(unittest.TestCase):
    """Every Xero HTTP call passes a timeout.

    `requests` has no default timeout, so a call without one can wait as long as
    the socket stays open. This is a source-level sweep rather than a behaviour
    test because the point is that *no* call site is left out -- the FakeXero
    above asserts the same thing for the two calls it serves.
    """

    def test_no_requests_call_in_the_xero_module_omits_a_timeout(self):
        import ast

        missing = []
        calls = 0
        for entry in sorted(os.listdir(XERO_DIR)):
            if not entry.endswith(".py"):
                continue
            path = os.path.join(XERO_DIR, entry)
            with io.open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "requests"):
                    calls += 1
                    if not any(kw.arg == "timeout" for kw in node.keywords):
                        missing.append("%s:%d requests.%s"
                                       % (entry, node.lineno, node.func.attr))

        self.assertGreater(calls, 0, "found no requests calls to check")
        self.assertEqual(missing, [])

    def test_every_module_that_uses_the_timeout_also_imports_it(self):
        """A missing import here is a NameError at the moment of the call, and
        nothing offline would reach it: `auth.py` has no test of its own and
        `python -m py_compile` is happy with an undefined name. This was a real
        miss in the first draft of this change -- nine uses in `auth.py`, no
        import -- so it is pinned rather than remembered.
        """
        import ast

        for entry in sorted(os.listdir(XERO_DIR)):
            if not entry.endswith(".py"):
                continue
            with io.open(os.path.join(XERO_DIR, entry), encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            uses = any(isinstance(n, ast.Name) and n.id == "XERO_HTTP_TIMEOUT"
                       for n in ast.walk(tree))
            if not uses:
                continue
            bound = entry == "__init__.py" or any(
                isinstance(n, (ast.Import, ast.ImportFrom))
                and any(a.name == "XERO_HTTP_TIMEOUT" for a in n.names)
                for n in ast.walk(tree)
            )
            self.assertTrue(bound, "%s uses XERO_HTTP_TIMEOUT without importing it" % entry)

    def test_the_timeout_is_a_connect_and_read_pair(self):
        module = _load("xero_package_under_test", os.path.join(XERO_DIR, "__init__.py"))
        connect, read = module.XERO_HTTP_TIMEOUT
        self.assertGreater(connect, 0)
        self.assertGreater(read, connect)


if __name__ == "__main__":
    unittest.main()
