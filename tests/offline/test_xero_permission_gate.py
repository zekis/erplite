# -*- coding: utf-8 -*-
"""Who may push a record into the owner's real Xero ledger.

This file pins the owner's decision on review tray item **rev_c3343b2cf3**:
*"Enforce the DocType's own permissions."* It does not invent a policy. Every
rule asserted here is read out of the `permissions` rows the DocType JSONs in
this repo already ship, and the gate enforces those rows and nothing else.

## What was wrong

Six functions were `@frappe.whitelist()` with no permission check of any kind:

    erplite/accounts/doctype/sales_invoice/sales_invoice.py     send_to_xero
    erplite/accounts/doctype/purchase_invoice/purchase_invoice.py  send_to_xero
    erplite/crm/doctype/customer/customer.py                   send_to_xero
    erplite/crm/doctype/customer/customer.py                   import_from_xero
    erplite/crm/doctype/supplier/supplier.py                   send_to_xero
    erplite/crm/doctype/supplier/supplier.py                   import_from_xero

Whitelisted means any logged-in user can call the method by name, so the Desk
button is not the gate. All four DocTypes are restricted to System Manager,
Accounts Manager and Accounts User, so a Projects User -- somebody set up only
to book timesheets -- had no read and no write on any of them and could still
send one of the owner's real invoices to his real Xero ledger.

## Why nothing stopped it (frappe 15.52.0, read from source)

1. **`frappe.get_doc` does no permission check.** `frappe/__init__.py:1308`
   delegates to `frappe.model.document.get_doc`, and in `document.py`
   `check_permission` is called only from `insert` ("create", :300), `save`
   ("write", :404), `submit`/`cancel` (:895-909) and `delete` (:1115). Loading a
   document is not one of them. **Loading is free; only writing is checked.**
2. **`frappe.db.set_value` checks nothing** -- no permission, no `validate`, no
   hooks. The two invoice endpoints record the result that way
   (`xero/accounts.py:186` and `:297`, `purchase_invoice.py:83`), so the one
   write that would have been checked is not a `save()` and the invoice path had
   no checked write anywhere in it.
3. **The contact endpoints did check, too late.** `customer.py` and
   `supplier.py` call `create_customer()` / `create_supplier()` first and
   `save()` second. So for a user without write permission the sequence was:
   contact created in the real Xero -> `save()` raises -> `xero_contact_id`
   never stored. The external record exists and nothing local remembers it,
   which also defeats the `if customer.xero_contact_id` guard at the top and
   **duplicates the contact on the next attempt**.

## The gate, and why it is outside the `try`

    frappe.has_permission("Sales Invoice", "write", doc=docname, throw=True)

placed immediately *before* the function's `try`, never inside it.

`frappe.PermissionError` is `class PermissionError(Exception)` with
`http_status_code = 403` (`frappe/exceptions.py:34`). It is **not** a
`ValidationError` (`:18`, 417). Four of these six endpoints wrap their body in
`except Exception` and re-raise through `frappe.throw`, which raises
`ValidationError`. A gate inside one of those try blocks would therefore be
caught and relabelled *"Failed to send invoice to Xero"* -- reporting a refusal,
which sent nothing, as a failed send, which may have sent something. That is
exactly the mislabelling the comment in those handlers already warns about, and
it is what invites the retry that duplicates a record.

So "the gate exists" is not a strong enough guard. `TestTheGateIsBeforeTheTry`
asserts its *position*, because moving it three lines down would pass a test
that only looked for the call.

## `write` for a send, `create` for an import

The two `import_from_xero` endpoints insert a new record rather than modify a
named one, so `create` is the permission the operation actually needs, and there
is no `doc=` to pass. On all four DocTypes every role granted `write` is also
granted `create` (System Manager, Accounts Manager, Accounts User), so this
refuses and permits exactly the same people as `write` would --
`test_write_and_create_are_the_same_set_of_roles` pins that, so if the rows ever
diverge this choice stops being free and a test says so.

## What is NOT claimed here

* Who holds which role on `crew.tierneymorris.com.au`. That is the owner's data.
  If Accounts User is the only non-admin role in use the exposure was small; the
  code was wrong either way and roles change.
* That the contact path is now idempotent. It is not. The gate makes a *refusal*
  send nothing, which is what the owner approved. A permitted user whose
  `save()` fails for some other reason still leaves a Xero contact with its id
  unstored, and the next attempt still duplicates it. That is a separate defect
  with a separate fix (record the id with `db.set_value` as the invoice path
  does, rather than through `save()`), it affects users who are allowed to be
  there, and it is filed for the owner rather than changed here.
  `test_a_permitted_save_failure_still_strands_the_contact` pins the hazard as
  it stands, so the day it is fixed this test fails and names itself.
* Anything about the Xero wire format or retry behaviour, which
  `test_xero_invoice_send.py` already covers.

Runs without a bench.
"""
import ast
import datetime
import importlib.util
import io
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from fake_frappe import (  # noqa: E402
    DoesNotExistError, FakeDocumentBase, FakeFrappe, PermissionError,
    ValidationError, _dict, doctype_fields, doctype_permissions,
)

APP_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODULE_ROOT = os.path.join(APP_ROOT, "erplite")

SKIP_DIRS = {"node_modules", "__pycache__", ".git", "dist", "build"}

# The four DocTypes these endpoints write to Xero, and where their JSON lives.
GATED_DOCTYPES = {
    "Sales Invoice": ("accounts", "sales_invoice"),
    "Purchase Invoice": ("accounts", "purchase_invoice"),
    "Customer": ("crm", "customer"),
    "Supplier": ("crm", "supplier"),
}

# Helpers in erplite/xero/accounts.py that mutate something in Xero or record
# the result without a permission check. Read off that module rather than
# recalled: every one of these either calls requests.post/put or writes with
# frappe.db.set_value.
XERO_MUTATORS = {
    "create_sales_invoice", "create_purchase_invoice", "create_customer",
    "create_supplier", "import_customer_from_xero", "import_supplier_from_xero",
    "upload_attachments_to_xero_invoice",
}

# Every whitelisted endpoint that reaches one, with the gate it must carry.
# Asserted to be exactly this set, so a seventh cannot appear ungated.
EXPECTED_GATES = {
    ("erplite/accounts/doctype/sales_invoice/sales_invoice.py", "send_to_xero"):
        ("Sales Invoice", "write"),
    ("erplite/accounts/doctype/purchase_invoice/purchase_invoice.py", "send_to_xero"):
        ("Purchase Invoice", "write"),
    ("erplite/crm/doctype/customer/customer.py", "send_to_xero"):
        ("Customer", "write"),
    ("erplite/crm/doctype/customer/customer.py", "import_from_xero"):
        ("Customer", "create"),
    ("erplite/crm/doctype/supplier/supplier.py", "send_to_xero"):
        ("Supplier", "write"),
    ("erplite/crm/doctype/supplier/supplier.py", "import_from_xero"):
        ("Supplier", "create"),
}

# A role with no permission row on any of the four. Timesheets only.
UNPRIVILEGED_ROLE = "Projects User"


# --------------------------------------------------------------------------
# the sweep
# --------------------------------------------------------------------------

def _python_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                path = os.path.join(dirpath, fn)
                yield path, os.path.relpath(path, APP_ROOT).replace(os.sep, "/")


def _is_whitelisted(node):
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if dec.func.attr == "whitelist":
                return True
        if isinstance(dec, ast.Attribute) and dec.attr == "whitelist":
            return True
    return False


def _called_names(node):
    return {c.func.id for c in ast.walk(node)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}


def _gate_calls(node):
    """Every `<x>.has_permission(...)` in this function, with its arguments read.

    Returns a list of (lineno, doctype, ptype, kwargs_present). A doctype or
    ptype that is not a plain string literal comes back as None rather than
    being guessed at, so an unreadable gate is reported, not assumed good.
    """
    out = []
    for call in ast.walk(node):
        if not (isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "has_permission"):
            continue
        def literal(value):
            return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None
        doctype = literal(call.args[0]) if call.args else None
        ptype = literal(call.args[1]) if len(call.args) > 1 else None
        kwargs = {}
        for kw in call.keywords:
            if kw.arg == "ptype":
                ptype = literal(kw.value)
            elif kw.arg == "doctype":
                doctype = literal(kw.value)
            else:
                kwargs[kw.arg] = kw.value
        out.append((call.lineno, doctype, ptype, kwargs))
    return out


def _endpoints_reaching_xero():
    """(relpath, funcname) -> ast node, for whitelisted fns that mutate Xero."""
    found = {}
    for path, rel in _python_files(MODULE_ROOT):
        with io.open(path, "r", encoding="utf-8", newline="") as fh:
            tree = ast.parse(fh.read(), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and _is_whitelisted(node):
                if _called_names(node) & XERO_MUTATORS:
                    found[(rel, node.name)] = node
    return found


class TestEveryXeroWriteIsGated(unittest.TestCase):
    """The whole-app guard: no ungated path to the owner's real ledger."""

    @classmethod
    def setUpClass(cls):
        cls.endpoints = _endpoints_reaching_xero()

    def test_the_surface_is_exactly_the_six_known_endpoints(self):
        """A seventh endpoint reaching Xero fails this until it is considered.

        This is the half that stops the fix rotting. Adding a `send_to_xero` to
        another DocType is an ordinary-looking change that would otherwise ship
        with no gate and nothing to notice it.
        """
        self.assertEqual(
            sorted(self.endpoints), sorted(EXPECTED_GATES),
            "the set of whitelisted endpoints that write to Xero has changed. "
            "Add the new one to EXPECTED_GATES with the permission it needs, "
            "and gate it before its try block.")

    def test_every_one_of_them_checks_permission(self):
        for key in sorted(EXPECTED_GATES):
            with self.subTest(endpoint=key):
                gates = _gate_calls(self.endpoints[key])
                self.assertTrue(
                    gates,
                    "%s::%s can write to the owner's real Xero and calls no "
                    "has_permission" % key)

    def test_each_gate_names_its_own_doctype_and_the_right_permission(self):
        """A gate on the wrong DocType is worse than none: it reads as covered."""
        for key, (doctype, ptype) in sorted(EXPECTED_GATES.items()):
            with self.subTest(endpoint=key):
                gates = _gate_calls(self.endpoints[key])
                self.assertEqual(
                    [(g[1], g[2]) for g in gates], [(doctype, ptype)],
                    "%s::%s should check exactly %r/%r" % (key + (doctype, ptype)))

    def test_a_send_gate_checks_the_named_document_not_just_the_doctype(self):
        """`doc=docname` is what applies the document-level rules.

        Without it the check is DocType-wide and skips User Permissions,
        `if_owner` and sharing (`frappe/permissions.py:124-127`). The four
        DocTypes here declare no `if_owner` row today, so this costs nothing
        now and is the difference the day one is added.
        """
        for key, (_doctype, ptype) in sorted(EXPECTED_GATES.items()):
            if ptype != "write":
                continue
            with self.subTest(endpoint=key):
                (_lineno, _dt, _pt, kwargs), = _gate_calls(self.endpoints[key])
                self.assertIn("doc", kwargs, "%s::%s must pass doc=" % key)
                self.assertIsInstance(kwargs["doc"], ast.Name)
                self.assertEqual(kwargs["doc"].id, "docname")

    def test_every_gate_throws_rather_than_returning_a_falsy_answer(self):
        """`has_permission` returns False by default; it only raises with throw=True.

        A gate whose result is discarded is not a gate. This is the mistake that
        looks most like working code.
        """
        for key in sorted(EXPECTED_GATES):
            with self.subTest(endpoint=key):
                (_lineno, _dt, _pt, kwargs), = _gate_calls(self.endpoints[key])
                self.assertIn("throw", kwargs, "%s::%s must pass throw=True" % key)
                self.assertIs(kwargs["throw"].value, True)


class TestTheGateIsBeforeTheTry(unittest.TestCase):
    """Position, not just presence.

    `frappe.PermissionError` is not a `ValidationError`, so a gate moved inside
    one of these `try` blocks is caught by `except Exception` and re-raised by
    `frappe.throw` as "Failed to send ... to Xero". The refusal becomes a 417
    failure report about a send that never happened, and the user's obvious
    response to a failure is to try again.
    """

    @classmethod
    def setUpClass(cls):
        cls.endpoints = _endpoints_reaching_xero()

    def test_the_gate_runs_before_any_try_block(self):
        for key in sorted(EXPECTED_GATES):
            with self.subTest(endpoint=key):
                node = self.endpoints[key]
                gate_lines = [g[0] for g in _gate_calls(node)]
                try_lines = [s.lineno for s in ast.walk(node) if isinstance(s, ast.Try)]
                self.assertTrue(gate_lines)
                if try_lines:
                    self.assertLess(
                        max(gate_lines), min(try_lines),
                        "%s::%s gates inside its try, so `except Exception` will "
                        "relabel the refusal as a failed send" % key)

    def test_the_gate_is_a_statement_of_the_function_body(self):
        """Not nested in an `if`, a loop or a `with` -- it must always run."""
        for key in sorted(EXPECTED_GATES):
            with self.subTest(endpoint=key):
                node = self.endpoints[key]
                top = [s for s in node.body
                       if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
                       and isinstance(s.value.func, ast.Attribute)
                       and s.value.func.attr == "has_permission"]
                self.assertEqual(
                    len(top), 1,
                    "%s::%s must call has_permission unconditionally in its body" % key)

    def test_those_handlers_really_do_swallow_and_relabel(self):
        """The premise of this whole class, asserted rather than assumed.

        If someone removes the blanket `except Exception` the position rule stops
        being load-bearing -- and this test is where they find that out.
        """
        for (rel, name) in sorted(EXPECTED_GATES):
            with self.subTest(endpoint=(rel, name)):
                node = _endpoints_reaching_xero()[(rel, name)]
                blanket = [h for t in ast.walk(node) if isinstance(t, ast.Try)
                           for h in t.handlers
                           if isinstance(h.type, ast.Name) and h.type.id == "Exception"]
                self.assertTrue(
                    blanket,
                    "%s::%s no longer has a blanket `except Exception`. The gate "
                    "being outside the try is then merely tidy rather than "
                    "load-bearing; re-read TestTheGateIsBeforeTheTry before "
                    "relaxing it." % (rel, name))
                throws = [c for h in blanket for c in ast.walk(h)
                          if isinstance(c, ast.Call)
                          and isinstance(c.func, ast.Attribute)
                          and c.func.attr == "throw"]
                self.assertTrue(throws)


class TestThePermissionRowsAreWhatTheGateRestsOn(unittest.TestCase):
    """The rows come from this repo. The gate enforces them; it adds no policy."""

    def test_all_four_doctypes_grant_the_same_three_roles(self):
        for doctype, (module, directory) in sorted(GATED_DOCTYPES.items()):
            with self.subTest(doctype=doctype):
                rows = doctype_permissions(module, directory)
                self.assertEqual(
                    sorted(rows),
                    ["Accounts Manager", "Accounts User", "System Manager"])

    def test_the_unprivileged_role_has_no_row_at_all(self):
        """Not "has a row without write" -- no row. So it has no read either."""
        for doctype, (module, directory) in sorted(GATED_DOCTYPES.items()):
            with self.subTest(doctype=doctype):
                rows = doctype_permissions(module, directory)
                self.assertNotIn(UNPRIVILEGED_ROLE, rows)

    def test_write_and_create_are_the_same_set_of_roles(self):
        """Why `create` on the import endpoints is the owner's rule, precisely spelt.

        If these ever diverge, using `create` there stops being equivalent to
        the decision that was approved, and this test is the place that says so.
        """
        for doctype, (module, directory) in sorted(GATED_DOCTYPES.items()):
            with self.subTest(doctype=doctype):
                rows = doctype_permissions(module, directory)
                writers = {r for r, v in rows.items() if "write" in v["granted"]}
                creators = {r for r, v in rows.items() if "create" in v["granted"]}
                self.assertEqual(writers, creators)

    def test_none_of_them_is_restricted_by_owner(self):
        """`if_owner` would make a DocType-wide check unsafe; none is set."""
        for doctype, (module, directory) in sorted(GATED_DOCTYPES.items()):
            with self.subTest(doctype=doctype):
                rows = doctype_permissions(module, directory)
                self.assertEqual([r for r, v in rows.items() if v["if_owner"]], [])

    def test_permission_error_is_not_a_validation_error(self):
        """Pins the fact the gate's position depends on (frappe/exceptions.py:34)."""
        self.assertFalse(issubclass(PermissionError, ValidationError))
        self.assertFalse(issubclass(ValidationError, PermissionError))


# --------------------------------------------------------------------------
# driving the real endpoints
# --------------------------------------------------------------------------

class FakeLedger(object):
    """Xero, as far as these endpoints can tell. Records what reached it."""

    def __init__(self, fail_on_save=False):
        self.sent = []
        self.imported = []
        self.fail_on_save = fail_on_save
        self._n = 0

    def _id(self, kind):
        self._n += 1
        return "xero-%s-%d" % (kind, self._n)

    def create_sales_invoice(self, doc):
        self.sent.append(("Sales Invoice", doc.name))
        return self._id("sinv")

    def create_purchase_invoice(self, doc):
        self.sent.append(("Purchase Invoice", doc.name))
        return self._id("pinv")

    def create_customer(self, doc):
        self.sent.append(("Customer", doc.name))
        return self._id("cust")

    def create_supplier(self, doc):
        self.sent.append(("Supplier", doc.name))
        return self._id("supp")

    def import_customer_from_xero(self, contact_id):
        self.imported.append(("Customer", contact_id))
        return {"name": "CUST-9001"}

    def import_supplier_from_xero(self, contact_id):
        self.imported.append(("Supplier", contact_id))
        return {"name": "SUPP-9001"}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_endpoints(frappe, ledger):
    """Install the stand-ins and load the four real controllers on top.

    `erplite.xero.accounts` is stubbed by the ledger: this file is about the
    gate, not the Xero wire format, which test_xero_invoice_send.py covers.
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
    pkg.PermissionError = PermissionError
    pkg.DoesNotExistError = DoesNotExistError

    utils = types.ModuleType("frappe.utils")
    utils.now_datetime = lambda: datetime.datetime(2026, 10, 5, 12, 0, 0)
    utils.cstr = lambda v: "" if v is None else str(v)
    pkg.utils = utils

    model = types.ModuleType("frappe.model")
    model.__path__ = []
    document = types.ModuleType("frappe.model.document")
    document.Document = FakeDocumentBase
    model.document = document
    pkg.model = model

    accounts = types.ModuleType("erplite.xero.accounts")
    accounts.create_sales_invoice = ledger.create_sales_invoice
    accounts.create_purchase_invoice = ledger.create_purchase_invoice
    accounts.create_customer = ledger.create_customer
    accounts.create_supplier = ledger.create_supplier
    accounts.import_customer_from_xero = ledger.import_customer_from_xero
    accounts.import_supplier_from_xero = ledger.import_supplier_from_xero
    accounts.get_customers_from_xero = lambda: []
    accounts.get_suppliers_from_xero = lambda: []

    erplite = types.ModuleType("erplite")
    erplite.__path__ = []
    xero = types.ModuleType("erplite.xero")
    xero.__path__ = []

    sys.modules.update({
        "frappe": pkg, "frappe.utils": utils, "frappe.model": model,
        "frappe.model.document": document, "erplite": erplite,
        "erplite.xero": xero, "erplite.xero.accounts": accounts,
    })

    return {
        "Sales Invoice": _load(
            "sales_invoice_gate",
            os.path.join(APP_ROOT, "erplite/accounts/doctype/sales_invoice/sales_invoice.py")),
        "Purchase Invoice": _load(
            "purchase_invoice_gate",
            os.path.join(APP_ROOT, "erplite/accounts/doctype/purchase_invoice/purchase_invoice.py")),
        "Customer": _load(
            "customer_gate",
            os.path.join(APP_ROOT, "erplite/crm/doctype/customer/customer.py")),
        "Supplier": _load(
            "supplier_gate",
            os.path.join(APP_ROOT, "erplite/crm/doctype/supplier/supplier.py")),
    }


ROW_NAMES = {
    "Sales Invoice": "SINV-00042",
    "Purchase Invoice": "PINV-00007",
    "Customer": "CUST-0001",
    "Supplier": "SUPP-0001",
}


def world(roles, user="pat@tierneymorris.com.au"):
    """A FakeFrappe holding one record of each of the four DocTypes."""
    frappe = FakeFrappe(session_user=user, roles=roles)
    for doctype, (module, directory) in GATED_DOCTYPES.items():
        frappe.fields[doctype] = doctype_fields(module, directory)
        frappe.permissions[doctype] = doctype_permissions(module, directory)
        frappe.tables[doctype] = [{
            "name": ROW_NAMES[doctype],
            "owner": "zeke@tierneymorris.com.au",
            "xero_contact_id": None,
            "xero_invoice_id": None,
            "xero_sync_date": None,
        }]
    frappe.tables["Sales Invoice"][0]["status"] = "Draft"
    frappe.tables["Purchase Invoice"][0]["status"] = "Draft"
    return frappe


class TestAnUnprivilegedUserSendsNothing(unittest.TestCase):
    """The finding, as a test: a Projects User reaches the real ledger.

    Each of these fails against the code before this branch, because the send
    went through.
    """

    def setUp(self):
        self.ledger = FakeLedger()
        self.frappe = world([UNPRIVILEGED_ROLE])
        self.modules = load_endpoints(self.frappe, self.ledger)

    def test_sending_an_invoice_is_refused(self):
        for doctype in ("Sales Invoice", "Purchase Invoice"):
            with self.subTest(doctype=doctype):
                with self.assertRaises(PermissionError):
                    self.modules[doctype].send_to_xero(ROW_NAMES[doctype])

    def test_sending_a_contact_is_refused(self):
        for doctype in ("Customer", "Supplier"):
            with self.subTest(doctype=doctype):
                with self.assertRaises(PermissionError):
                    self.modules[doctype].send_to_xero(ROW_NAMES[doctype])

    def test_importing_a_contact_is_refused(self):
        for doctype in ("Customer", "Supplier"):
            with self.subTest(doctype=doctype):
                with self.assertRaises(PermissionError):
                    self.modules[doctype].import_from_xero("xero-contact-abc")

    def test_nothing_at_all_reached_xero(self):
        """The assertion that matters. A refusal that still sent is not a fix.

        Asserted separately from the raises above, because an endpoint could
        perfectly well post to Xero and *then* raise -- which is precisely what
        the contact path used to do.
        """
        # Any exception, not just PermissionError: this test asks only whether
        # anything reached the ledger. Which exception arrives is
        # test_sending_an_invoice_is_refused's question, and catching narrowly
        # here would turn that separate regression into a confusing error in
        # this test instead of a clear failure in that one.
        for doctype in GATED_DOCTYPES:
            try:
                self.modules[doctype].send_to_xero(ROW_NAMES[doctype])
            except Exception:
                pass
        for doctype in ("Customer", "Supplier"):
            try:
                self.modules[doctype].import_from_xero("xero-contact-abc")
            except Exception:
                pass
        self.assertEqual(self.ledger.sent, [])
        self.assertEqual(self.ledger.imported, [])

    def test_nothing_was_recorded_locally_either(self):
        for doctype in GATED_DOCTYPES:
            try:
                self.modules[doctype].send_to_xero(ROW_NAMES[doctype])
            except Exception:
                pass
        self.assertEqual(self.frappe.values_set, [])
        self.assertEqual(self.frappe.saves, [])
        self.assertEqual(self.frappe.inserts, [])
        self.assertEqual(self.frappe.commits, 0)

    def test_the_refusal_is_not_relabelled_as_a_failed_send(self):
        """A 403 must not arrive as "Failed to send invoice to Xero".

        This is the test that fails if the gate is moved inside the try, and it
        is the user-visible half of the position rule.
        """
        for doctype in GATED_DOCTYPES:
            with self.subTest(doctype=doctype):
                # Measured as a delta, not against an empty list: self.frappe is
                # shared across these subTests, so an absolute assertion would
                # blame whichever DocType ran second for the first one's entry.
                before = len(self.frappe.errors)
                with self.assertRaises(PermissionError):
                    self.modules[doctype].send_to_xero(ROW_NAMES[doctype])
                self.assertEqual(
                    self.frappe.errors[before:], [],
                    "%s wrote the refusal to the Error Log as a send failure, so "
                    "the gate is inside the try and `except Exception` relabelled "
                    "it" % doctype)


class TestAPermittedUserIsUnaffected(unittest.TestCase):
    """The other half: the gate enforces the rows, it does not narrow them.

    Without this, deleting the body of every endpoint would pass the class above.
    """

    def setUp(self):
        self.ledger = FakeLedger()
        self.frappe = world(["Accounts User"])
        self.modules = load_endpoints(self.frappe, self.ledger)

    def test_an_accounts_user_can_still_send_every_one(self):
        for doctype in GATED_DOCTYPES:
            with self.subTest(doctype=doctype):
                self.assertTrue(self.modules[doctype].send_to_xero(ROW_NAMES[doctype]))
        self.assertEqual(
            sorted(self.ledger.sent),
            sorted((d, ROW_NAMES[d]) for d in GATED_DOCTYPES))

    def test_an_accounts_user_can_still_import(self):
        for doctype in ("Customer", "Supplier"):
            with self.subTest(doctype=doctype):
                self.assertTrue(self.modules[doctype].import_from_xero("xero-contact-abc"))
        self.assertEqual(
            sorted(self.ledger.imported),
            [("Customer", "xero-contact-abc"), ("Supplier", "xero-contact-abc")])

    def test_a_system_manager_can_too(self):
        ledger = FakeLedger()
        frappe = world(["System Manager"], user="zeke@tierneymorris.com.au")
        modules = load_endpoints(frappe, ledger)
        for doctype in GATED_DOCTYPES:
            with self.subTest(doctype=doctype):
                self.assertTrue(modules[doctype].send_to_xero(ROW_NAMES[doctype]))

    def test_a_name_that_does_not_exist_is_not_reported_as_a_permission_problem(self):
        """A typo must not read as "no permission"; frappe loads the doc to check.

        `permissions.py:125-127` resolves a name through `get_doc`, so a missing
        record raises DoesNotExistError from inside the gate. The endpoints wrap
        their body, not the gate, so it arrives unwrapped.
        """
        with self.assertRaises(DoesNotExistError):
            self.modules["Sales Invoice"].send_to_xero("SINV-NOPE")
        self.assertEqual(self.ledger.sent, [])


class TestTheGateAloneIsNotIdempotency(unittest.TestCase):
    """Stating the limit of this change, as a test rather than a comment."""

    def test_a_permitted_save_failure_still_strands_the_contact(self):
        """Known, unfixed, and deliberately out of scope for rev_c3343b2cf3.

        The contact path posts to Xero first and `save()`s second. The gate
        removes the *permission* reason for that save to fail, which is what the
        owner approved. Any other reason still leaves a contact in Xero whose id
        was never stored -- so the `if customer.xero_contact_id` guard stays open
        and the next attempt creates a second one.

        Fixing it means recording the id with `db.set_value`, as the invoice path
        does since PR #12. That changes behaviour for users who are permitted, so
        it is the owner's call and is filed separately. **When it is fixed this
        test fails** -- which is the point: a waiver that cannot outlive what it
        waives.
        """
        ledger = FakeLedger()
        frappe = world(["Accounts User"])
        modules = load_endpoints(frappe, ledger)

        def refuse_to_save(*args, **kwargs):
            raise ValidationError("link validation failed")

        frappe.tables["Customer"][0]["_save_raises"] = True
        original = FakeDocumentBase.save if hasattr(FakeDocumentBase, "save") else None

        # Make the save fail the way any ordinary validation failure would.
        import fake_frappe
        saved = fake_frappe.FakeStoredDoc.save
        fake_frappe.FakeStoredDoc.save = refuse_to_save
        try:
            with self.assertRaises(ValidationError):
                modules["Customer"].send_to_xero(ROW_NAMES["Customer"])
        finally:
            fake_frappe.FakeStoredDoc.save = saved

        # The contact reached Xero and nothing local remembers its id.
        self.assertEqual(ledger.sent, [("Customer", "CUST-0001")])
        self.assertIsNone(frappe.tables["Customer"][0]["xero_contact_id"])
        del frappe.tables["Customer"][0]["_save_raises"]
        _ = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
