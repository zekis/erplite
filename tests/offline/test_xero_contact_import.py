# -*- coding: utf-8 -*-
"""The Xero contact import: two whitelisted endpoints that cannot insert anything.

`erplite/crm/doctype/customer/customer.py` and `.../supplier/supplier.py` expose
`get_xero_customers` / `get_xero_suppliers` and `import_from_xero`. Unlike
`erplite/xero/api.py` -- whose module attributes are undefined, pinned in
test_xero_send_and_sync.py -- every function these two import really exists, so
these endpoints run. This file pins what they do when they run.

It asserts nothing about today's behaviour being *correct*. It records what each
finding rests on, so the findings go stale loudly if the code moves.

## Finding 1: the import can never create a Customer or a Supplier

`import_customer_from_xero` builds its record as a dict literal
(`erplite/xero/accounts.py:600`) and calls `insert()`. The dict never sets
`customer_type`, which on the Customer DocType is `reqd: 1` with **no default** and
not read-only. In frappe version-15:

  * `Document.insert()` calls `run_before_save_methods()` (which runs the app's own
    `validate`) and then `self._validate()` -- document.py:309-310;
  * `_validate()` calls `_validate_mandatory()` first -- document.py:624-625;
  * `_get_missing_mandatory_fields()` iterates **every** `reqd` field and counts one
    whose value `in (None, [])` as missing -- base_document.py:775-777;
  * which raises `frappe.MandatoryError` -- document.py:963.

So `insert()` raises before any row is written, on every call, for every Xero
contact. `Supplier` is the same via `supplier_type` (accounts.py:670).

What the user is told hides this. The MandatoryError is caught by
`except Exception` in `import_customer_from_xero`, re-thrown as "Error importing
customer from Xero: ...", caught again by `except Exception` in
`customer.import_from_xero`, and re-thrown as "Failed to import customer from
Xero: ..." -- so a local schema problem is reported twice over as a Xero problem.
And `frappe.log_error("Customer", msg)` passes a message, which in
`frappe/utils/error.py` sets `traceback = message`, so no stack is recorded either.

`test_no_dict_literal_get_doc_site_omits_a_mandatory_field` runs this as a rule over
the whole app rather than only here. The rule is **not** free: of every
`frappe.get_doc({...})` dict literal in erplite, exactly these two sites break it.

## Finding 2: the phone imported is the first slot, not the populated one

`contact.get("Phones", [{}])[0].get("PhoneNumber", "")` takes `Phones[0]` whatever
its `PhoneType` is. Verified read-only against the owner's live Xero: in every
contact returned, `Phones[0]` is the **DDI** slot, and DDI is empty; a contact's real
number sits in the **DEFAULT** slot. Of the 14 contacts matching `IsCustomer=true`,
two carry a phone number and in both it is in DEFAULT, so the import captures a phone
number for none of them.

## Finding 3: the address imported is the first slot, not the populated one

Same shape: `Addresses[0]`, whatever its `AddressType`. The order is not stable in
the owner's own data -- most contacts return STREET then POBOX, but some return POBOX
first, and at least one returns an **empty STREET first with the real address in the
POBOX entry behind it**. For that contact the import stores no address at all while
Xero holds one.

Findings 2 and 3 are pinned against the *shape* of the live responses (slot order and
which slot carries the value), with placeholder values rather than the owner's real
contact details, which have no business being in a test file.

## Finding 4: first_name and last_name are written and are not fields

Both import dicts set `first_name` and `last_name`; neither is a field on either
DocType, so frappe drops them. Two consequences worth their own tests:
`Customer.set_full_name` reads `getattr(self, 'first_name', None)` and so can never
fire, and `Customer.full_name` -- a read-only Data field -- is written by nothing in
the app, while `Supplier.full_name` is.

## Finding 5 (latent, not biting today): the contact list is silently capped

No contact request passes a `page`. Verified against live Xero: a Contacts request
with no `page` returns **no pagination envelope**, so a caller cannot tell a complete
answer from a truncated one, and Xero caps it at 100. Today the org has 14 customers
and ~60-70 suppliers against 1110 contacts in total, so nothing is being lost yet.
Recorded because the failure, when it arrives, is silent.

## Three things that are RIGHT, pinned so a fix does not break them

  * `where=IsCustomer=true` -- a single `=`, which looks like a typo for Xero's `==`
    equality operator. It is not: the request returns 14 of 1110 contacts, all with
    `IsCustomer: true`. Verified live. Do not "correct" it.
  * `country` is a `Link` to `Country`, and Xero sends the full name ("Australia"),
    which is how frappe's Country records are named (`autoname: field:country_name`).
    The link resolves; this is not a source of failure.
  * the import does **not** overwrite an existing record. It looks the contact up by
    `xero_contact_id` and refuses. Whatever is done about finding 1, keep that.
"""

import ast
import datetime
import importlib.util
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(os.path.dirname(HERE))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from fake_frappe import (FakeFrappe, FakeDocumentBase, _dict,  # noqa: E402
                         ValidationError, doctype_fields, make_doc)

ACCOUNTS = os.path.join(APP_ROOT, "erplite", "xero", "accounts.py")


# --------------------------------------------------------------------------
# stand-ins
# --------------------------------------------------------------------------

class Doc(object):
    """A document stand-in that is deliberately NOT a dict subclass.

    Same reason as in test_xero_send_and_sync.py: `_dict` inherits `dict.items`
    and `dict.get`, which win over `__getattr__`, so a dict subclass quietly
    misreports what a controller sees.
    """

    def __init__(self, **kw):
        self.__dict__.update(kw)
        self.inserted = False

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def insert(self, *a, **kw):
        self.inserted = True

    def save(self, *a, **kw):
        pass


class _Response(object):
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


# The structure of a real Xero contact, with placeholder values. What matters
# and what was verified live: Phones[0] is the DDI slot and is empty, the number
# is in DEFAULT; Addresses[0] is an EMPTY STREET and the real address is the
# POBOX entry behind it.
CONTACT_WITH_VALUE_IN_THE_SECOND_SLOT = {
    "ContactID": "contact-0001",
    "ContactStatus": "ACTIVE",
    "Name": "Placeholder Pty Ltd",
    "FirstName": "Placeholder",
    "LastName": "Person",
    "EmailAddress": "placeholder@example.com",
    "Addresses": [
        {"AddressType": "STREET", "AddressLine1": "", "AddressLine2": "",
         "City": "", "Region": "", "PostalCode": "", "Country": ""},
        {"AddressType": "POBOX", "AddressLine1": "1 Placeholder St",
         "AddressLine2": "", "City": "PLACEHOLDER", "Region": "WA",
         "PostalCode": "6000", "Country": "Australia"},
    ],
    "Phones": [
        {"PhoneType": "DDI", "PhoneNumber": "", "PhoneAreaCode": "", "PhoneCountryCode": ""},
        {"PhoneType": "DEFAULT", "PhoneNumber": "0400000000", "PhoneAreaCode": "",
         "PhoneCountryCode": "+61"},
        {"PhoneType": "FAX", "PhoneNumber": "", "PhoneAreaCode": "", "PhoneCountryCode": ""},
        {"PhoneType": "MOBILE", "PhoneNumber": "", "PhoneAreaCode": "", "PhoneCountryCode": ""},
    ],
}

THE_REAL_PHONE = "0400000000"
THE_REAL_STREET = "1 Placeholder St"


def load_contact_path(contact=None, existing=None):
    """Load the real accounts.py and the real Customer/Supplier controllers.

    Returns (accounts, customer_module, supplier_module, captured), where
    `captured` collects every dict handed to frappe.get_doc. Capturing the dict
    rather than letting the stand-in insert it is deliberate: in production this
    dict never reaches the database (finding 1), so a test that asserted "the
    import creates a customer with ..." would be asserting something that cannot
    happen. What the dict *contains* is still exactly what findings 2-4 are about.
    """
    for name in list(sys.modules):
        if name == "frappe" or name.startswith("frappe.") or name.startswith("erplite"):
            del sys.modules[name]

    frappe = FakeFrappe(session_user="zeke@tierneymorris.com.au",
                        roles=["System Manager"])
    frappe.fields["Customer"] = doctype_fields("crm", "customer")
    frappe.fields["Supplier"] = doctype_fields("crm", "supplier")
    frappe.tables["Customer"] = list(existing or [])
    frappe.tables["Supplier"] = list(existing or [])

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

    settings = Doc(tenant_id="a-tenant-id", client_id="id", client_secret="secret")
    pkg.get_single = lambda dt: settings

    captured = []

    def _get_doc(dt, dn=None, **kw):
        if isinstance(dt, dict):
            captured.append(dict(dt))
            return Doc(name="CUST-0001", **{k: v for k, v in dt.items()
                                            if k != "doctype"})
        for row in frappe.tables.get(dt, []):
            if row.get("name") == dn:
                return Doc(**row)
        raise ValidationError("%s %s not found" % (dt, dn))

    pkg.get_doc = _get_doc

    payload = {"Contacts": [contact]} if contact else {"Contacts": []}
    req = types.ModuleType("requests")
    req.get = lambda *a, **k: _Response(200, payload)
    req.post = lambda *a, **k: _Response(200, payload)
    req.put = lambda *a, **k: _Response(200, payload)
    exc = types.ModuleType("requests.exceptions")

    class _ReadTimeout(Exception):
        pass

    exc.ReadTimeout = _ReadTimeout
    req.exceptions = exc

    auth = types.ModuleType("erplite.xero.auth")
    auth.get_valid_token = lambda: "a-valid-token"

    sys.modules["frappe"] = pkg
    sys.modules["frappe.utils"] = utils
    sys.modules["frappe.model"] = model
    sys.modules["frappe.model.document"] = document
    sys.modules["requests"] = req
    sys.modules["requests.exceptions"] = exc
    for n in ("erplite", "erplite.xero", "erplite.crm", "erplite.crm.doctype"):
        m = types.ModuleType(n)
        m.__path__ = []
        sys.modules[n] = m
    sys.modules["erplite.xero.auth"] = auth

    def _load(name, relpath):
        spec = importlib.util.spec_from_file_location(
            name, os.path.join(APP_ROOT, relpath))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    accounts = _load("xero_accounts_ci", "erplite/xero/accounts.py")
    sys.modules["erplite.xero.accounts"] = accounts
    cust = _load("customer_ci", "erplite/crm/doctype/customer/customer.py")
    supp = _load("supplier_ci", "erplite/crm/doctype/supplier/supplier.py")
    return accounts, cust, supp, captured


# --------------------------------------------------------------------------
# the whole-app rule behind finding 1
# --------------------------------------------------------------------------

def dict_literal_get_doc_sites():
    """Every frappe.get_doc({...}) dict literal in the app, with its keys."""
    sites = []
    root = os.path.join(APP_ROOT, "erplite")
    for dirpath, _dirs, files in os.walk(root):
        if "tests" in dirpath.split(os.sep):
            continue
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(dirpath, fname)
            with open(path, "rb") as handle:
                try:
                    tree = ast.parse(handle.read().decode("utf-8", "replace"))
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if getattr(node.func, "attr", None) != "get_doc" or not node.args:
                    continue
                arg = node.args[0]
                if not isinstance(arg, ast.Dict):
                    continue
                keys = [k.value for k in arg.keys if isinstance(k, ast.Constant)]
                doctype = None
                for k, v in zip(arg.keys, arg.values):
                    if (isinstance(k, ast.Constant) and k.value == "doctype"
                            and isinstance(v, ast.Constant)):
                        doctype = v.value
                if doctype is None:
                    continue
                sites.append({
                    "file": os.path.relpath(path, APP_ROOT).replace(os.sep, "/"),
                    "line": node.lineno,
                    "doctype": doctype,
                    "keys": keys,
                })
    return sites


def app_doctype(name):
    """The DocType JSON for one of this app's DocTypes, or None if not ours."""
    root = os.path.join(APP_ROOT, "erplite")
    for dirpath, _dirs, files in os.walk(root):
        if os.path.basename(os.path.dirname(dirpath)) != "doctype":
            continue
        folder = os.path.basename(dirpath)
        path = os.path.join(dirpath, folder + ".json")
        if not os.path.exists(path):
            continue
        with open(path, "rb") as handle:
            definition = json.loads(handle.read().decode("utf-8"))
        if definition.get("doctype") == "DocType" and definition.get("name") == name:
            return definition
    return None


def mandatory_without_default(definition):
    return [f["fieldname"] for f in definition.get("fields", [])
            if f.get("reqd") and not f.get("default") and not f.get("read_only")]


# The two sites that break the rule today. Both are bugs, not approved
# behaviour: this list exists so a THIRD one fails the suite loudly, the same
# baseline pattern as KNOWN_UNDEFINED in test_xero_send_and_sync.py. Fixing
# either finding 1 means deleting its entry here in the same commit.
KNOWN_MISSING_MANDATORY = {
    ("erplite/xero/accounts.py", "Customer"): ["customer_type"],
    ("erplite/xero/accounts.py", "Supplier"): ["supplier_type"],
}

# Same, for fields written that the DocType does not have (finding 4).
KNOWN_NOT_A_FIELD = {
    ("erplite/xero/accounts.py", "Customer"): ["first_name", "last_name"],
    ("erplite/xero/accounts.py", "Supplier"): ["first_name", "last_name"],
}


class StandInTestCase(unittest.TestCase):
    """Prove the checkers in this file bite, before trusting what they report."""

    def test_the_mandatory_rule_bites_on_a_planted_omission(self):
        definition = {"fields": [
            {"fieldname": "customer_name", "reqd": 1},
            {"fieldname": "customer_type", "reqd": 1},
            {"fieldname": "status", "reqd": 1, "default": "Active"},
            {"fieldname": "notes"},
        ]}
        self.assertEqual(mandatory_without_default(definition),
                         ["customer_name", "customer_type"])
        keys = ["doctype", "customer_name"]
        missing = [f for f in mandatory_without_default(definition) if f not in keys]
        self.assertEqual(missing, ["customer_type"],
                         "the rule must notice a reqd field the dict omits")

    def test_the_mandatory_rule_does_not_fire_on_a_field_with_a_default(self):
        definition = {"fields": [{"fieldname": "status", "reqd": 1,
                                  "default": "Active"}]}
        self.assertEqual(mandatory_without_default(definition), [],
                         "a reqd field WITH a default is supplied by frappe, "
                         "so omitting it is not a fault")

    def test_the_site_scan_finds_the_real_import_dicts(self):
        sites = dict_literal_get_doc_sites()
        found = {(s["file"], s["doctype"]) for s in sites}
        self.assertIn(("erplite/xero/accounts.py", "Customer"), found)
        self.assertIn(("erplite/xero/accounts.py", "Supplier"), found)

    def test_the_capture_would_see_a_phone_in_the_first_slot(self):
        """If the import read a populated Phones[0], this harness would say so.

        Without this, test_the_imported_phone_... could pass because the capture
        is broken rather than because the import is wrong.
        """
        contact = json.loads(json.dumps(CONTACT_WITH_VALUE_IN_THE_SECOND_SLOT))
        contact["Phones"][0]["PhoneNumber"] = THE_REAL_PHONE
        accounts, _c, _s, captured = load_contact_path(contact=contact)
        accounts.import_customer_from_xero("contact-0001")
        self.assertEqual(captured[0]["phone"], THE_REAL_PHONE)


class CannotInsertTestCase(unittest.TestCase):
    """Finding 1."""

    def test_customer_import_omits_a_mandatory_field_with_no_default(self):
        definition = app_doctype("Customer")
        self.assertIsNotNone(definition)
        field = [f for f in definition["fields"]
                 if f["fieldname"] == "customer_type"][0]
        self.assertEqual(field.get("reqd"), 1)
        self.assertFalse(field.get("default"),
                         "a default would let frappe fill this in")
        self.assertFalse(field.get("read_only"))

        site = [s for s in dict_literal_get_doc_sites()
                if s["file"] == "erplite/xero/accounts.py"
                and s["doctype"] == "Customer"][0]
        self.assertNotIn("customer_type", site["keys"],
                         "insert() raises frappe.MandatoryError while this holds")

    def test_supplier_import_omits_a_mandatory_field_with_no_default(self):
        definition = app_doctype("Supplier")
        self.assertIsNotNone(definition)
        field = [f for f in definition["fields"]
                 if f["fieldname"] == "supplier_type"][0]
        self.assertEqual(field.get("reqd"), 1)
        self.assertFalse(field.get("default"))
        self.assertFalse(field.get("read_only"))

        site = [s for s in dict_literal_get_doc_sites()
                if s["file"] == "erplite/xero/accounts.py"
                and s["doctype"] == "Supplier"][0]
        self.assertNotIn("supplier_type", site["keys"])

    def test_no_dict_literal_get_doc_site_omits_a_mandatory_field(self):
        """The rule, over the whole app. Not free: two sites break it."""
        actual = {}
        for site in dict_literal_get_doc_sites():
            definition = app_doctype(site["doctype"])
            if definition is None:
                continue          # not one of ours; frappe owns its schema
            missing = [f for f in mandatory_without_default(definition)
                       if f not in site["keys"]]
            if missing:
                actual[(site["file"], site["doctype"])] = missing
        self.assertEqual(
            actual, KNOWN_MISSING_MANDATORY,
            "a get_doc dict literal that omits a mandatory field with no "
            "default cannot insert. Update KNOWN_MISSING_MANDATORY in the same "
            "commit that fixes or adds one.")

    def test_no_dict_literal_get_doc_site_writes_a_field_the_doctype_lacks(self):
        """Finding 4, as the same kind of whole-app rule."""
        actual = {}
        for site in dict_literal_get_doc_sites():
            definition = app_doctype(site["doctype"])
            if definition is None:
                continue
            known = {f.get("fieldname") for f in definition.get("fields", [])}
            unknown = [k for k in site["keys"] if k != "doctype" and k not in known]
            if unknown:
                actual[(site["file"], site["doctype"])] = unknown
        self.assertEqual(actual, KNOWN_NOT_A_FIELD,
                         "frappe silently drops a key that is not a field")


class WrongSlotTestCase(unittest.TestCase):
    """Findings 2 and 3: the import reads slot 0 regardless of type."""

    def test_the_imported_phone_is_the_first_slot_not_the_populated_one(self):
        accounts, _c, _s, captured = load_contact_path(
            contact=CONTACT_WITH_VALUE_IN_THE_SECOND_SLOT)
        accounts.import_customer_from_xero("contact-0001")
        self.assertEqual(len(captured), 1)
        self.assertEqual(
            captured[0]["phone"], "",
            "Phones[0] is the DDI slot in every contact this org returns; the "
            "number is in DEFAULT, so nothing is imported")

    def test_the_imported_address_is_the_first_slot_not_the_populated_one(self):
        accounts, _c, _s, captured = load_contact_path(
            contact=CONTACT_WITH_VALUE_IN_THE_SECOND_SLOT)
        accounts.import_customer_from_xero("contact-0001")
        record = captured[0]
        self.assertEqual(record["address_line1"], "")
        self.assertEqual(record["city"], "")
        self.assertEqual(record["postal_code"], "")
        self.assertNotEqual(
            record["address_line1"], THE_REAL_STREET,
            "the real address is the POBOX entry behind an empty STREET one")

    def test_the_import_does_not_look_at_phonetype_or_addresstype(self):
        """Why findings 2 and 3 are the same bug: nothing selects by type."""
        with open(ACCOUNTS, "rb") as handle:
            source = handle.read().decode("utf-8")
        start = source.index("def import_customer_from_xero")
        end = source.index("def import_supplier_from_xero")
        body = source[start:end]
        self.assertIn('contact.get("Phones", [{}])[0]', body)
        self.assertIn('contact.get("Addresses", [{}])[0]', body)
        self.assertNotIn("PhoneType", body)
        self.assertNotIn("AddressType", body)


class DeadCodeTestCase(unittest.TestCase):
    """Finding 4's two consequences."""

    def test_first_name_and_last_name_are_not_fields_on_either_doctype(self):
        for module, folder in (("crm", "customer"), ("crm", "supplier")):
            fields = doctype_fields(module, folder)
            self.assertNotIn("first_name", fields)
            self.assertNotIn("last_name", fields)

    def test_customer_set_full_name_can_never_fire(self):
        """Its own getattr default guarantees it: first_name is not a field.

        A new document has no attribute for a field the DocType does not
        declare, so `getattr(self, 'first_name', None)` is always None and the
        `if first_name and last_name` branch is unreachable -- the comment above
        it calls this defensive programming, and the defence is what hides it.

        Built through make_doc so the test follows the DocType rather than
        standing apart from it: the first version of this test constructed the
        controller directly, which made it pass whether or not first_name was a
        field, and planting the field did not fail it.
        """
        _a, cust, _s, _cap = load_contact_path()

        # Frappe would not set these either, which is the whole point.
        with self.assertRaises(AttributeError):
            make_doc(cust.Customer, "Customer", "crm", "customer",
                     {"customer_name": None, "first_name": "Placeholder",
                      "last_name": "Person"})

        doc = make_doc(cust.Customer, "Customer", "crm", "customer",
                       {"customer_name": None})
        self.assertFalse(hasattr(doc, "first_name"))
        doc.set_full_name()
        self.assertIsNone(doc.customer_name,
                          "nothing can populate customer_name from first/last name")

    def test_customer_full_name_is_written_by_nothing_while_suppliers_is(self):
        with open(os.path.join(APP_ROOT, "erplite", "crm", "doctype",
                               "customer", "customer.py"), "rb") as handle:
            customer_src = handle.read().decode("utf-8")
        with open(os.path.join(APP_ROOT, "erplite", "crm", "doctype",
                               "supplier", "supplier.py"), "rb") as handle:
            supplier_src = handle.read().decode("utf-8")
        self.assertIn("self.full_name =", supplier_src)
        self.assertNotIn("self.full_name =", customer_src)
        self.assertIn("full_name", doctype_fields("crm", "customer"))


class SilentCapTestCase(unittest.TestCase):
    """Finding 5: latent, and silent when it arrives."""

    def test_no_contact_request_passes_a_page_parameter(self):
        with open(ACCOUNTS, "rb") as handle:
            source = handle.read().decode("utf-8")
        contact_urls = [line for line in source.splitlines()
                        if "api.xro/2.0/Contacts" in line]
        self.assertTrue(contact_urls)
        for line in contact_urls:
            self.assertNotIn("page=", line,
                             "with no page, Xero caps the list at 100 and sends "
                             "no pagination envelope, so truncation is invisible")


class AlreadyRightTestCase(unittest.TestCase):
    """Three things today's code gets right. Pinned so a fix keeps them."""

    def test_the_contact_filter_uses_xeros_single_equals_and_that_is_correct(self):
        """Verified live: this returns 14 of 1110 contacts, all IsCustomer.

        A single `=` reads like a typo for Xero's `==` equality operator. It is
        not, and "correcting" it is a change nobody should make on the strength
        of how it looks.
        """
        with open(ACCOUNTS, "rb") as handle:
            source = handle.read().decode("utf-8")
        self.assertIn("Contacts?where=IsCustomer=true", source)
        self.assertIn("Contacts?where=IsSupplier=true", source)
        self.assertNotIn("IsCustomer==true", source)

    def test_country_is_a_link_whose_target_matches_what_xero_sends(self):
        definition = app_doctype("Customer")
        field = [f for f in definition["fields"] if f["fieldname"] == "country"][0]
        self.assertEqual(field["fieldtype"], "Link")
        self.assertEqual(field["options"], "Country")
        # frappe's Country is autonamed field:country_name ("Australia"), and
        # Xero's Address.Country carries the full name, so the link resolves.
        self.assertEqual(
            CONTACT_WITH_VALUE_IN_THE_SECOND_SLOT["Addresses"][1]["Country"],
            "Australia")

    def test_the_import_refuses_an_existing_contact_rather_than_overwriting(self):
        existing = [{"name": "CUST-0001", "customer_name": "Placeholder Pty Ltd",
                     "xero_contact_id": "contact-0001"}]
        accounts, _c, _s, captured = load_contact_path(
            contact=CONTACT_WITH_VALUE_IN_THE_SECOND_SLOT, existing=existing)
        with self.assertRaises(ValidationError) as caught:
            accounts.import_customer_from_xero("contact-0001")
        self.assertIn("already exists", str(caught.exception))
        self.assertEqual(captured, [],
                         "it must not build a replacement record either")


if __name__ == "__main__":
    unittest.main(verbosity=2)
