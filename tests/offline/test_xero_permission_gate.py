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
* That the contact path has been exercised against the live site. It has not.
  The duplicate-contact defect this file used to waive is **fixed** as of
  5 Oct 2026 (rev_6c9dc08cf7): see `TestTheContactIdIsRecordedAndSurvives`,
  which replaced the waiver after it failed, as it was written to. The
  mechanism behind that fix is read off frappe 15.52.0 and this app's source,
  not observed on `crew.tierneymorris.com.au`, and what is reproduced here is
  the stand-in's model of it. `TestNoStaleDocumentIsSavedAfterASend` reads the
  four controllers instead, so the rule holds even if that model is wrong --
  and it was wrong until this change, which is why these endpoints were green
  on a path that could not work.
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
    TimestampMismatchError, ValidationError, _dict, doctype_fields,
    doctype_permissions,
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
    """Xero, as far as these endpoints can tell. Records what reached it.

    These four stand in for `erplite/xero/accounts.py`, and each one of them
    **records the Xero id against the row before it returns**, with
    `frappe.db.set_value`, because that is what the real functions do:
    `create_sales_invoice` at `accounts.py:186`, `create_purchase_invoice` at
    `:297`, `create_customer` at `:511`, `create_supplier` at `:591`.

    That was missing here until 5 Oct 2026, and it was not a cosmetic gap. The
    callers then set the same fields on a document they loaded *before* this
    write and save it, so the real write is what makes that save stale. A
    stand-in that posted to Xero and recorded nothing made every such save
    succeed, which is why these tests were green on a path that cannot work.
    Do not simplify this back to a bare return.
    """

    def __init__(self, frappe=None, fail_on_save=False):
        self.sent = []
        self.imported = []
        self.fail_on_save = fail_on_save
        self._frappe = frappe
        self._n = 0

    def _id(self, kind):
        self._n += 1
        return "xero-%s-%d" % (kind, self._n)

    def _record(self, doctype, name, fields):
        """What accounts.py does on a successful post, and when it does it."""
        if self._frappe is not None:
            self._frappe.db.set_value(doctype, name, fields)

    def create_sales_invoice(self, doc):
        self.sent.append(("Sales Invoice", doc.name))
        xero_id = self._id("sinv")
        self._record("Sales Invoice", doc.name, {
            "xero_invoice_id": xero_id,
            "xero_invoice_number": "INV-%s" % xero_id,
            "xero_status": "AUTHORISED",
            "xero_sync_date": "2026-10-06 09:00:00",
        })
        return xero_id

    def create_purchase_invoice(self, doc):
        self.sent.append(("Purchase Invoice", doc.name))
        xero_id = self._id("pinv")
        self._record("Purchase Invoice", doc.name, {
            "xero_invoice_id": xero_id,
            "xero_invoice_number": "BILL-%s" % xero_id,
            "xero_status": "AUTHORISED",
            "xero_sync_date": "2026-10-06 09:00:00",
        })
        return xero_id

    def create_customer(self, doc):
        self.sent.append(("Customer", doc.name))
        xero_id = self._id("cust")
        self._record("Customer", doc.name, {
            "xero_contact_id": xero_id,
            "xero_sync_date": "2026-10-06 09:00:00",
        })
        return xero_id

    def create_supplier(self, doc):
        self.sent.append(("Supplier", doc.name))
        xero_id = self._id("supp")
        self._record("Supplier", doc.name, {
            "xero_contact_id": xero_id,
            "xero_sync_date": "2026-10-06 09:00:00",
        })
        return xero_id

    def import_customer_from_xero(self, contact_id):
        self.imported.append(("Customer", contact_id))
        return {"name": "CUST-9001"}

    def import_supplier_from_xero(self, contact_id):
        self.imported.append(("Supplier", contact_id))
        return {"name": "SUPP-9001"}


def ledger_names(ledger, doctype):
    """How many records of one DocType reached Xero. One is the whole point."""
    return len([d for d, _name in ledger.sent if d == doctype])


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
    # accounts.py records the Xero id against the row with db.set_value
    # before returning, so the ledger needs the database to do that to. Wiring
    # it here rather than at each call site means no test can forget.
    ledger._frappe = frappe

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
    pkg.TimestampMismatchError = TimestampMismatchError

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
            # Every real row has a `modified`, and the stale-document check
            # compares against it. Without one here the comparison would be
            # against None, which reaches the right verdict for the wrong
            # reason and reads like a missing field rather than a moved row.
            "modified": "2026-10-06 08:00:00",
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


class TestTheContactIdIsRecordedAndSurvives(unittest.TestCase):
    """rev_6c9dc08cf7: a send records the Xero id durably, so a retry is refused.

    This class replaces TestTheGateAloneIsNotIdempotency, which asserted the
    opposite and was written to fail the day this was fixed. It has now failed
    for that reason, so it is gone rather than deleted quietly: the assertions
    below are its inverse, over the same mechanism.

    What the old class waived, and what the owner then decided (rev_6c9dc08cf7):
    the contact path posted to Xero and then saved a document it had loaded
    BEFORE `create_customer` recorded the id with db.set_value. That save could
    not succeed -- `modified` had moved -- so every successful post ended in a
    rolled-back request, an id that nothing local remembered, and a duplicate
    contact on the next attempt.

    The honest limit, stated here rather than only in the pull request: the
    mechanism is read off frappe 15.52.0 and this app, NOT observed on the live
    site. What is reproduced below is the stand-in's model of it -- see
    fake_frappe.FakeStoredDoc.save and _FakeDb.set_value, which were taught
    `modified` for exactly this reason. TestNoStaleDocumentIsSavedAfterASend
    below checks the source instead, and does not depend on that model at all.
    """

    def setUp(self):
        self.ledger = FakeLedger()
        self.frappe = world(["Accounts User"])
        self.modules = load_endpoints(self.frappe, self.ledger)

    def test_a_send_records_the_id_against_the_row(self):
        """Red against main: the send raised TimestampMismatchError instead."""
        for doctype in ("Customer", "Supplier"):
            with self.subTest(doctype=doctype):
                self.assertTrue(
                    self.modules[doctype].send_to_xero(ROW_NAMES[doctype]))
                row = self.frappe.tables[doctype][0]
                self.assertIsNotNone(row["xero_contact_id"])
                self.assertIsNotNone(row["xero_sync_date"])

    def test_nothing_saves_the_document_after_the_post(self):
        """The fix, stated as the absence it is.

        accounts.py has already written both fields with db.set_value by the
        time the endpoint regains control. A save() here would be a write from
        a document read before that one -- which is the whole bug, so its
        absence is the thing worth pinning.
        """
        for doctype in ("Customer", "Supplier"):
            with self.subTest(doctype=doctype):
                self.modules[doctype].send_to_xero(ROW_NAMES[doctype])
        self.assertEqual(
            [s.doctype for s in self.frappe.saves], [],
            "a document was saved after the Xero post; that save is stale by "
            "construction and is what duplicated the contact")

    def test_the_transaction_is_committed(self):
        """The commit is kept, not removed with the save.

        Deleting both would leave the id to the request's own commit and undo
        it on any later failure in the same request -- the same class of bug,
        moved rather than fixed.
        """
        self.modules["Customer"].send_to_xero(ROW_NAMES["Customer"])
        self.assertGreaterEqual(self.frappe.commits, 1)

    def test_a_second_send_is_refused_and_reaches_xero_once(self):
        """The duplicate, as a test: the recorded id must stop the retry.

        This is what the owner's decision was actually for. Recording the id is
        only worth anything because the `if ...xero_contact_id` guard reads it
        on the next attempt.
        """
        for doctype in ("Customer", "Supplier"):
            with self.subTest(doctype=doctype):
                self.modules[doctype].send_to_xero(ROW_NAMES[doctype])
                with self.assertRaises(ValidationError):
                    self.modules[doctype].send_to_xero(ROW_NAMES[doctype])
        # One contact per DocType reached Xero across both attempts.
        self.assertEqual(
            sorted(self.ledger.sent),
            [("Customer", ROW_NAMES["Customer"]),
             ("Supplier", ROW_NAMES["Supplier"])])

    def test_a_failure_after_the_post_still_leaves_the_id_recorded(self):
        """The original hazard, now harmless, driven rather than argued.

        A later failure in the same request used to take the recorded id with
        it. db.set_value has already written the row, so the guard still reads
        the id and the retry is refused rather than duplicating the contact.
        """
        self.modules["Customer"].send_to_xero(ROW_NAMES["Customer"])
        recorded = self.frappe.tables["Customer"][0]["xero_contact_id"]
        self.assertIsNotNone(recorded)

        with self.assertRaises(ValidationError):
            self.modules["Customer"].send_to_xero(ROW_NAMES["Customer"])
        self.assertEqual(
            self.frappe.tables["Customer"][0]["xero_contact_id"], recorded)
        self.assertEqual(ledger_names(self.ledger, "Customer"), 1)


class TestNoStaleDocumentIsSavedAfterASend(unittest.TestCase):
    """The same rule read off the source, so it does not rest on the stand-in.

    The stand-in models `modified`, and that model could be wrong -- it was
    absent until 5 Oct 2026, which is why these endpoints were green on a path
    that cannot work. This class reads the four controllers instead and asserts
    the shape directly, so the rule survives a stand-in that is mistaken.

    The rule: in a `send_to_xero`, once the Xero create has been called, the
    document must not be assigned to and saved. accounts.py has already written
    those fields with db.set_value, so any such save is from a stale read.
    """

    CREATORS = {
        "Sales Invoice": "create_sales_invoice",
        "Purchase Invoice": "create_purchase_invoice",
        "Customer": "create_customer",
        "Supplier": "create_supplier",
    }

    def test_no_send_to_xero_saves_after_calling_the_creator(self):
        checked = []
        for doctype, (module, directory) in sorted(GATED_DOCTYPES.items()):
            rel = os.path.join(
                "erplite", module, "doctype", directory, directory + ".py")
            path = os.path.join(APP_ROOT, rel)
            with io.open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), rel)

            fn = next(
                (n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "send_to_xero"),
                None)
            self.assertIsNotNone(fn, "%s has no send_to_xero" % rel)

            creator = self.CREATORS[doctype]
            creator_line = next(
                (n.lineno for n in ast.walk(fn)
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == creator),
                None)
            self.assertIsNotNone(
                creator_line, "%s: send_to_xero never calls %s" % (rel, creator))

            saves = [
                n.lineno for n in ast.walk(fn)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == "save"
                and n.lineno > creator_line
            ]
            self.assertEqual(
                saves, [],
                "%s: send_to_xero calls .save() at line(s) %s, after %s() at "
                "line %d. That document was read before %s recorded the Xero "
                "id with db.set_value, so the save is stale: frappe raises "
                "TimestampMismatchError, the except Exception below re-labels "
                "it as a failed send, and the request rolls back -- leaving the "
                "record in Xero with its id unstored and duplicating it on the "
                "next attempt (rev_6c9dc08cf7). Commit instead; accounts.py has "
                "already written the fields."
                % (rel, saves, creator, creator_line, creator))
            checked.append(doctype)

        # The assertion is only worth anything if it looked at all four.
        self.assertEqual(sorted(checked), sorted(GATED_DOCTYPES))


if __name__ == "__main__":
    unittest.main(verbosity=2)
