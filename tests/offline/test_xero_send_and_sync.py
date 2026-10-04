# -*- coding: utf-8 -*-
"""The Xero module: an unrepeatable send, and a sync direction that cannot run.

This file pins the premises behind review-tray item **rev_5c3dfe6ff3** (what should
happen when a send to Xero fails without saying whether Xero got it). It asserts
nothing about today's behaviour being *correct* -- it records what the decision rests
on, so the item goes stale loudly if the code moves underneath it, and it locks in
the parts that are already right so either answer keeps them.

## Finding 1: the double-send guard cannot survive a lost reply

All four `send_to_xero` endpoints are shaped like this:

    if doc.xero_invoice_id:                      # <- the guard
        frappe.throw(_("...already been sent..."))
    xero_id = create_sales_invoice(doc)          # <- POSTs to Xero

and `xero_invoice_id` is written by `create_sales_invoice` only *after* Xero answers
200. So the guard's state is set one network round-trip after the invoice exists in
Xero, and the window is unbounded, because **no `requests` call in the module passes
a `timeout=`**. A POST that reaches Xero whose reply is lost therefore leaves:

  * an invoice in the owner's real Xero,
  * `xero_invoice_id` empty, so the guard is still open, and
  * the user looking at "Failed to send invoice to Xero: ...", whose obvious next
    action is to click the button again.

`test_a_lost_reply_...` and `test_the_retry_...` below run that sequence against the
real `sales_invoice.send_to_xero` and the real `erplite/xero/accounts.py` and count
what Xero received: **two invoices carrying one InvoiceNumber**.

Whether Xero *accepts* that second invoice or rejects it as a duplicate
`InvoiceNumber` is **not tested here and is not known**: finding out means POSTing to
the owner's live accounting system, which these tests exist to avoid. That is stated
as the open half of the tray item rather than guessed at.

Two things make the retry more likely rather than less:

  * the guard's own `frappe.throw` sits *inside* the `try` whose `except Exception`
    re-wraps everything, so when the guard finally does fire the user is told
    **"Failed to send invoice to Xero: This invoice has already been sent to Xero"** --
    the one safe outcome is reported as a failure.
  * `frappe.log_error("Sales Invoice", "Error sending ...")` passes a `message`, and
    in `frappe/utils/error.py` that means `traceback = message`, so
    `frappe.get_traceback()` is never called. Every Xero failure in this app reaches
    the Error Log as a single line with no stack -- so after a lost reply the log
    cannot tell you whether Xero got the invoice either.

Nothing in the send path checks DocType permissions, which is the one way this
differs from the rest of the app: `frappe.get_doc` returns the controller without a
check (`frappe/model/document.py`), `frappe.db.set_value` builds the UPDATE directly
("do not call the ORM triggers"), and the POST is a bare `requests.post`. The ORM --
which is what protected the 18 write-capable endpoints swept previously -- is never
entered, so `@frappe.whitelist()` is the whole gate: any logged-in Desk user.

## Finding 2: the pull-from-Xero direction calls five functions that do not exist

`test_no_intra_app_module_attribute_is_undefined` walks every `module.attr` reference
in the app that resolves to another app module, and checks the attribute is defined
there. It is a cheap, strict rule -- and the first time this suite's "check whether
the strict rule is free" test came back *free and unanimous*: of the four such
references in the whole app, four are broken.

    erplite/xero/api.py:15   auth.get_authorization_url   not in erplite/xero/auth.py
    erplite/xero/api.py:36   auth.get_tokens              not in erplite/xero/auth.py
    erplite/xero/api.py:87   accounts.sync_accounts       not in erplite/xero/accounts.py
    erplite/xero/api.py:91   accounts.sync_invoices       not in erplite/xero/accounts.py

plus two `from erplite.xero.accounts import ...` sites in
`setup/doctype/company/company.py` naming `sync_organization`, `sync_accounts` and
`sync_invoices`, none of which exist either.

So three of the five whitelisted endpoints in `xero/api.py` cannot succeed:
`get_authorization_url` dies on the missing attribute and reports it as
*"Please check the Xero settings"*; `handle_callback` can never get past its state
check, because `xero_oauth_state` is read in exactly one place and **set nowhere**, so
an admin who reaches it is told the request *"may have been tampered with"* about a
flow that was never wired; and `sync_all` writes an "In Progress" Xero Sync Log row,
hits the missing `accounts.sync_accounts`, and marks it Failed. `Company.connect_to_xero`
and `Company.sync_with_xero` raise ImportError at the import line.

The pattern is the same one as rev_0ee5b675ce: the OAuth2 authorization-code flow
`api.py` was written against was replaced by a client-credentials flow in `auth.py`,
and the old module was left whitelisted rather than removed. `api.py`'s `disconnect`
is the other half of that: it clears a `refresh_token` that **is not a field on Xero
Settings** (client credentials issue no refresh token) and leaves `tenant_id` set,
while the `disconnect` the UI actually calls lives on the DocType and clears
different fields.

Neither direction of that is decided here. The four broken references are pinned as a
BASELINE, the way test_post_save_field_writes.py pins the six invoice-status lines: a
*new* one is a failure, and when the owner decides whether the sync direction is wanted
or the module should go, this test goes red and is updated with it.

## What is already right and must stay

`test_the_guard_exists_...`, `test_tenant_id_is_checked_...` and
`test_all_four_xero_fields_exist_...`. The last one is worth stating plainly because
it is what the previous sweeps would have predicted and it is **not** what is wrong
here: `create_sales_invoice` writes four `xero_*` fields through one dict-form
`frappe.db.set_value`, and all four are declared on both invoice DocTypes. This is
not another lost write.
"""

import ast
import datetime
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from fake_frappe import (FakeFrappe, FakeDocumentBase, _dict, ValidationError,  # noqa: E402
                         doctype_fields)

XERO_DIR = os.path.join(APP_ROOT, "erplite", "xero")

# The four intra-app module attributes that do not exist, as of 6 Oct 2026.
# See "Finding 2" above. A new entry here is a regression; removing one means the
# decision landed and this list and the tray item move together.
KNOWN_UNDEFINED = {
    ("erplite/xero/api.py", "auth", "get_authorization_url"),
    ("erplite/xero/api.py", "auth", "get_tokens"),
    ("erplite/xero/api.py", "accounts", "sync_accounts"),
    ("erplite/xero/api.py", "accounts", "sync_invoices"),
}


# --------------------------------------------------------------------------
# stand-ins
# --------------------------------------------------------------------------

class LostReply(Exception):
    """Stands in for requests.exceptions.ReadTimeout: the POST reached Xero and
    created the invoice; the reply did not reach us."""


class Doc(object):
    """A document stand-in that is deliberately NOT a dict subclass.

    `fake_frappe._dict` inherits `dict.items`, and normal attribute lookup finds
    that bound method before `__getattr__` runs -- so a Sales Invoice built as a
    `_dict` makes `for item in sales_invoice.items` iterate the dict method and
    raise "'builtin_function_or_method' object is not iterable". The first run of
    this repro printed "invoices in Xero: 0" under a line claiming Xero had
    created one, which is a stub fault reading as a finding. Hence this class,
    and test_a_dict_subclass_cannot_carry_an_items_child_table below.
    """

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __contains__(self, key):
        return key in self.__dict__


class _Response(object):
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeXero(object):
    """Records every invoice Xero accepted, so "did Xero get it twice" is a number."""

    def __init__(self, lose_reply_on=()):
        self.posted = []
        self.lose_reply_on = set(lose_reply_on)
        self.calls = 0

    def post(self, url, headers=None, data=None, **kwargs):
        self.calls += 1
        body = json.loads(data)
        # Xero creates the invoice before the caller learns the outcome.
        for inv in body.get("Invoices", []):
            self.posted.append(inv)
        if self.calls in self.lose_reply_on:
            raise LostReply("read timeout waiting for Xero")
        inv = self.posted[-1]
        return _Response(200, {"Invoices": [{
            "InvoiceID": "xero-%d" % self.calls,
            "InvoiceNumber": inv.get("InvoiceNumber"),
            "Status": inv.get("Status"),
        }]})

    @property
    def invoice_numbers(self):
        return [i.get("InvoiceNumber") for i in self.posted]


def load_send_path(frappe, xero):
    """Load the real xero/accounts.py and the real sales_invoice.py controller."""
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
    utils.now_datetime = lambda: datetime.datetime(2026, 10, 6, 22, 30, 0)
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

    req = types.ModuleType("requests")
    req.post = xero.post
    req.get = lambda *a, **k: _Response(200, {})
    req.put = lambda *a, **k: _Response(200, {})
    exc = types.ModuleType("requests.exceptions")
    exc.ReadTimeout = LostReply
    req.exceptions = exc

    auth = types.ModuleType("erplite.xero.auth")
    auth.get_valid_token = lambda: "a-valid-token"

    sys.modules["frappe"] = pkg
    sys.modules["frappe.utils"] = utils
    sys.modules["frappe.model"] = model
    sys.modules["frappe.model.document"] = document
    sys.modules["requests"] = req
    sys.modules["requests.exceptions"] = exc
    for n in ("erplite", "erplite.xero"):
        m = types.ModuleType(n)
        m.__path__ = []
        sys.modules[n] = m
    sys.modules["erplite.xero.auth"] = auth

    import importlib.util

    def _load(name, relpath):
        spec = importlib.util.spec_from_file_location(name, os.path.join(APP_ROOT, relpath))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    accounts = _load("xero_accounts_ut", "erplite/xero/accounts.py")
    sys.modules["erplite.xero.accounts"] = accounts
    si = _load("sales_invoice_ut",
               "erplite/accounts/doctype/sales_invoice/sales_invoice.py")
    return accounts, si


def make_invoice_frappe():
    frappe = FakeFrappe(session_user="zeke@tierneymorris.com.au", roles=["System Manager"])
    frappe.fields["Sales Invoice"] = doctype_fields("accounts", "sales_invoice")
    frappe.tables["Sales Invoice"] = [
        Doc(name="SINV-00042", customer_name="Novalith Technologies",
            posting_date=datetime.date(2026, 10, 1), due_date=datetime.date(2026, 10, 31),
            status="Submitted", xero_invoice_id=None, xero_invoice_number=None,
            xero_status=None, xero_sync_date=None,
            items=[Doc(description="CCTP Systems Engineering support",
                       item_name="Engineering", qty=100, rate=140.0, tax_rate=10)]),
    ]
    settings = Doc(tenant_id="tenant-abc", access_token="tok", client_id="cid",
                   client_secret="secret", authorization_status="Authorized")
    frappe.get_single = lambda dt: settings

    def _get_doc(dt, dn=None, **kw):
        for row in frappe.tables.get(dt, []):
            if row.get("name") == dn:
                return row
        raise ValidationError("%s %s not found" % (dt, dn))

    frappe.get_doc = _get_doc
    return frappe, settings


# --------------------------------------------------------------------------
# self-tests of the stand-ins
# --------------------------------------------------------------------------

class StandInTestCase(unittest.TestCase):
    """A stub fault must not be able to read as a finding."""

    def test_a_dict_subclass_cannot_carry_an_items_child_table(self):
        row = _dict(name="SINV-1", items=[1, 2, 3])
        # dict.items wins over _dict.__getattr__ ...
        self.assertTrue(callable(row.items))
        self.assertNotEqual(row.items, [1, 2, 3])
        # ... which is why the document stand-in is a plain object.
        self.assertEqual(Doc(name="SINV-1", items=[1, 2, 3]).items, [1, 2, 3])

    def test_stand_in_set_value_takes_the_dict_form(self):
        """Real Frappe: "Property / field name or dictionary of values to be
        updated", with val=None (frappe/database/database.py). The stand-in used
        to require a single field and a value, which made erplite's four-field
        call look like a TypeError raised by the app."""
        frappe = FakeFrappe()
        frappe.fields["Sales Invoice"] = doctype_fields("accounts", "sales_invoice")
        frappe.tables["Sales Invoice"] = [_dict(name="SINV-1")]
        frappe.db.set_value("Sales Invoice", "SINV-1", {
            "xero_invoice_id": "x1", "xero_status": "AUTHORISED"})
        row = frappe.tables["Sales Invoice"][0]
        self.assertEqual(row["xero_invoice_id"], "x1")
        self.assertEqual(row["xero_status"], "AUTHORISED")
        self.assertIn(("Sales Invoice", "SINV-1", "xero_invoice_id", "x1"), frappe.values_set)

    def test_stand_in_set_value_still_refuses_an_undeclared_field(self):
        frappe = FakeFrappe()
        frappe.fields["Sales Invoice"] = doctype_fields("accounts", "sales_invoice")
        frappe.tables["Sales Invoice"] = [_dict(name="SINV-1")]
        from fake_frappe import UnknownField
        with self.assertRaises(UnknownField):
            frappe.db.set_value("Sales Invoice", "SINV-1", {"not_a_field": 1})

    def test_the_fake_xero_records_a_post_it_then_fails_to_answer(self):
        xero = FakeXero(lose_reply_on=(1,))
        with self.assertRaises(LostReply):
            xero.post("u", data=json.dumps({"Invoices": [{"InvoiceNumber": "A"}]}))
        self.assertEqual(xero.invoice_numbers, ["A"])


# --------------------------------------------------------------------------
# consequences: the sequence, against the real code
# --------------------------------------------------------------------------

class LostReplyTestCase(unittest.TestCase):
    def setUp(self):
        self.xero = FakeXero(lose_reply_on=(1,))
        self.frappe, self.settings = make_invoice_frappe()
        self.accounts, self.si = load_send_path(self.frappe, self.xero)

    def row(self):
        return self.frappe.tables["Sales Invoice"][0]

    def test_a_lost_reply_leaves_the_invoice_in_xero_and_the_guard_open(self):
        with self.assertRaises(ValidationError) as caught:
            self.si.send_to_xero("SINV-00042")
        # The user is told it failed ...
        self.assertIn("Failed to send invoice to Xero", str(caught.exception))
        # ... while Xero has the invoice ...
        self.assertEqual(len(self.xero.posted), 1)
        self.assertEqual(self.xero.invoice_numbers, ["SINV-00042"])
        # ... and the only thing the guard consults was never written.
        self.assertIsNone(self.row().get("xero_invoice_id"))

    def test_the_retry_sends_a_second_invoice_with_the_same_invoice_number(self):
        with self.assertRaises(ValidationError):
            self.si.send_to_xero("SINV-00042")
        # The user clicks again, because they were told it failed.
        self.assertTrue(self.si.send_to_xero("SINV-00042"))
        self.assertEqual(len(self.xero.posted), 2)
        self.assertEqual(self.xero.invoice_numbers, ["SINV-00042", "SINV-00042"])
        self.assertEqual(len(set(self.xero.invoice_numbers)), 1)
        # Both carry the same money.
        lines = [[(li["Quantity"], li["UnitAmount"]) for li in i["LineItems"]]
                 for i in self.xero.posted]
        self.assertEqual(lines[0], lines[1])
        # Whether Xero accepts the second one is NOT asserted: see the module
        # docstring. Testing that means writing to the owner's real accounts.

    def test_once_the_id_is_set_the_guard_fires_but_reports_a_failure(self):
        with self.assertRaises(ValidationError):
            self.si.send_to_xero("SINV-00042")
        self.si.send_to_xero("SINV-00042")
        before = len(self.xero.posted)
        with self.assertRaises(ValidationError) as caught:
            self.si.send_to_xero("SINV-00042")
        message = str(caught.exception)
        # It does stop the third send ...
        self.assertEqual(len(self.xero.posted), before)
        # ... but the guard's own throw was caught by the except around it, so the
        # safe outcome is presented as an error.
        self.assertIn("already been sent to Xero", message)
        self.assertIn("Failed to send invoice to Xero", message)

    def test_every_xero_failure_reaches_the_error_log_without_a_traceback(self):
        """frappe/utils/error.py: `if message: traceback = message`, so
        `frappe.get_traceback()` is never reached when a message is passed."""
        with self.assertRaises(ValidationError):
            self.si.send_to_xero("SINV-00042")
        self.assertTrue(self.frappe.errors)
        args, _kwargs = self.frappe.errors[-1]
        self.assertEqual(len(args), 2)
        title, message = args
        self.assertEqual(title, "Sales Invoice")
        self.assertNotIn("\n", title)       # so error.py does not swap them back
        self.assertIn("Error sending sales invoice to Xero", message)


# --------------------------------------------------------------------------
# premises the tray item rests on
# --------------------------------------------------------------------------

def _iter_py(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def _rel(path):
    return os.path.relpath(path, APP_ROOT).replace(os.sep, "/")


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


class PremiseTestCase(unittest.TestCase):
    def test_no_xero_http_call_sets_a_timeout(self):
        """The guard's window is as long as the slowest hung socket. If a timeout
        is ever added this goes red, which is the point: the tray item's premise
        changed."""
        untimed = []
        for path in _iter_py(XERO_DIR):
            tree = ast.parse(_read(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if not (isinstance(fn, ast.Attribute)
                        and isinstance(fn.value, ast.Name)
                        and fn.value.id == "requests"
                        and fn.attr in ("get", "post", "put", "delete", "patch", "request")):
                    continue
                if not any(kw.arg == "timeout" for kw in node.keywords):
                    untimed.append((_rel(path), node.lineno, fn.attr))
        self.assertTrue(untimed, "expected the unbounded calls this item is about")
        # Pinned as a count so a new call site is noticed too.
        self.assertEqual(
            21, len(untimed),
            "the number of unbounded Xero HTTP calls changed: %r" % (untimed,))

    def test_the_id_the_guard_reads_is_written_only_after_xero_answers(self):
        """In create_sales_invoice the set_value is inside the `status_code == 200`
        branch, so there is no state recorded before the POST."""
        path = os.path.join(XERO_DIR, "accounts.py")
        src = _read(path)
        tree = ast.parse(src)
        fn = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == "create_sales_invoice")
        posts = [n.lineno for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "post"]
        set_values = [n.lineno for n in ast.walk(fn)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                      and n.func.attr == "set_value"]
        self.assertTrue(posts and set_values)
        self.assertLess(min(posts), min(set_values),
                        "the POST must still precede the only write of xero_invoice_id")

    def test_the_send_path_never_checks_doctype_permissions(self):
        """Unlike the 18 write-capable endpoints swept previously, this path never
        enters the ORM, so Frappe gets no chance to check anything."""
        checks = []
        targets = {
            "erplite/accounts/doctype/sales_invoice/sales_invoice.py": "send_to_xero",
            "erplite/accounts/doctype/purchase_invoice/purchase_invoice.py": "send_to_xero",
            "erplite/crm/doctype/customer/customer.py": "send_to_xero",
            "erplite/crm/doctype/supplier/supplier.py": "send_to_xero",
        }
        for rel, name in targets.items():
            tree = ast.parse(_read(os.path.join(APP_ROOT, rel)))
            fn = next((n for n in tree.body
                       if isinstance(n, ast.FunctionDef) and n.name == name), None)
            self.assertIsNotNone(fn, "%s is gone from %s" % (name, rel))
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and node.func.attr in ("check_permission", "has_permission", "has_perm"):
                    checks.append((rel, node.lineno))
        self.assertEqual([], checks,
                         "a permission check appeared in the send path; the tray "
                         "item's severity paragraph needs rewriting: %r" % (checks,))

    def test_xero_oauth_state_is_read_and_never_set(self):
        reads, writes = [], []
        for path in _iter_py(os.path.join(APP_ROOT, "erplite")):
            src = _read(path)
            if "xero_oauth_state" not in src:
                continue
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    args = [a.value for a in node.args if isinstance(a, ast.Constant)]
                    if "xero_oauth_state" not in args:
                        continue
                    if node.func.attr == "get_value":
                        reads.append((_rel(path), node.lineno))
                    elif node.func.attr in ("set_value", "setex", "set"):
                        writes.append((_rel(path), node.lineno))
        self.assertEqual(1, len(reads), "expected the single cache read: %r" % (reads,))
        self.assertEqual([], writes,
                         "something now sets xero_oauth_state, so handle_callback "
                         "may be reachable: %r" % (writes,))


class UndefinedModuleAttributeTestCase(unittest.TestCase):
    """Whole-app guard: a `module.attr` reference must exist in that module.

    Python resolves it at call time, so a missing one is an AttributeError that
    only fires when the line runs -- and every one of these sits under a broad
    `except Exception` that turns it into an unrelated-sounding message.
    """

    @staticmethod
    def _top_level_names(path, cache={}):
        if path in cache:
            return cache[path]
        names = set()
        try:
            tree = ast.parse(_read(path))
        except (OSError, SyntaxError):
            cache[path] = None
            return None
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                names.update(t.id for t in node.targets if isinstance(t, ast.Name))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names.update((a.asname or a.name).split(".")[0] for a in node.names)
        cache[path] = names
        return names

    def _sweep(self):
        found = set()
        for path in _iter_py(os.path.join(APP_ROOT, "erplite")):
            dirpath = os.path.dirname(path)
            try:
                tree = ast.parse(_read(path))
            except SyntaxError:
                continue
            alias_to_path = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module is None and node.level:
                    for a in node.names:                      # from . import accounts
                        alias_to_path[a.asname or a.name] = os.path.join(dirpath, a.name + ".py")
                elif isinstance(node, ast.ImportFrom) and node.module \
                        and node.module.startswith("erplite"):
                    for a in node.names:
                        cand = os.path.join(APP_ROOT, *(node.module.split(".")), a.name + ".py")
                        if os.path.exists(cand):
                            alias_to_path[a.asname or a.name] = cand
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)):
                    continue
                target = alias_to_path.get(node.value.id)
                if not target or not os.path.exists(target):
                    continue
                names = self._top_level_names(target)
                if names is None or node.attr in names:
                    continue
                found.add((_rel(path), node.value.id, node.attr))
        return found

    def test_no_intra_app_module_attribute_is_undefined(self):
        found = self._sweep()
        new = found - KNOWN_UNDEFINED
        self.assertEqual(
            set(), new,
            "a module attribute that does not exist: %r" % sorted(new))

    def test_the_known_broken_references_are_all_still_broken(self):
        """A BASELINE, not an assertion that this is acceptable. When the owner
        decides whether the Xero sync direction is wanted (rev_5c3dfe6ff3), this
        goes red and moves with the item."""
        found = self._sweep()
        fixed = KNOWN_UNDEFINED - found
        self.assertEqual(
            set(), fixed,
            "fixed, so remove from KNOWN_UNDEFINED and update the tray "
            "item: %r" % sorted(fixed))

    def test_the_sync_functions_company_imports_do_not_exist_either(self):
        accounts = self._top_level_names(os.path.join(XERO_DIR, "accounts.py"))
        for missing in ("sync_organization", "sync_accounts", "sync_invoices"):
            self.assertNotIn(
                missing, accounts,
                "%s now exists, so Company.sync_with_xero may work: update the "
                "tray item" % missing)


# --------------------------------------------------------------------------
# already right, must stay right under either decision
# --------------------------------------------------------------------------

class AlreadyRightTestCase(unittest.TestCase):
    def test_all_four_xero_fields_exist_on_both_invoice_doctypes(self):
        """This is NOT another lost write, which is what the earlier sweeps would
        have predicted. The dict-form set_value names four fields and all four are
        declared."""
        for module, doctype in (("accounts", "sales_invoice"),
                                ("accounts", "purchase_invoice")):
            names = doctype_fields(module, doctype)
            for field in ("xero_invoice_id", "xero_invoice_number",
                          "xero_status", "xero_sync_date"):
                self.assertIn(field, names, "%s lost %s" % (doctype, field))

    def test_the_guard_exists_on_all_four_send_endpoints(self):
        """The guard is not missing -- it is just not durable. If one of these
        loses its check the problem is a different and worse one."""
        targets = {
            "erplite/accounts/doctype/sales_invoice/sales_invoice.py": "xero_invoice_id",
            "erplite/accounts/doctype/purchase_invoice/purchase_invoice.py": "xero_invoice_id",
            "erplite/crm/doctype/customer/customer.py": "xero_contact_id",
            "erplite/crm/doctype/supplier/supplier.py": "xero_contact_id",
        }
        for rel, field in targets.items():
            tree = ast.parse(_read(os.path.join(APP_ROOT, rel)))
            fn = next(n for n in tree.body
                      if isinstance(n, ast.FunctionDef) and n.name == "send_to_xero")
            guarded = any(isinstance(n, ast.Attribute) and n.attr == field
                          for test in [x.test for x in ast.walk(fn) if isinstance(x, ast.If)]
                          for n in ast.walk(test))
            self.assertTrue(guarded, "%s no longer checks %s before sending" % (rel, field))

    def test_tenant_id_is_checked_before_anything_is_sent(self):
        xero = FakeXero()
        frappe, settings = make_invoice_frappe()
        settings.tenant_id = None
        accounts, si = load_send_path(frappe, xero)
        with self.assertRaises(ValidationError):
            si.send_to_xero("SINV-00042")
        self.assertEqual([], xero.posted, "a send went out with no tenant")


if __name__ == "__main__":
    unittest.main(verbosity=2)
