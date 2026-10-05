# -*- coding: utf-8 -*-
"""A `frappe.get_doc({...}).insert()` must supply the DocType's mandatory fields.

## What this found (7 Oct 2026)

`erplite/xero/accounts.py`, `import_customer_from_xero` and
`import_supplier_from_xero`, each built its document from a dict literal that
omitted `customer_type` / `supplier_type`. Both fields are `reqd: 1` on their
DocType with **no default and not read_only**, so there was no second chance to
fill them in: `insert()` raised `MandatoryError` for every contact Xero returned.
Neither endpoint could create a single Customer or Supplier, for any input.

Traced through frappe-version-15 rather than recalled: `insert()` calls
`_validate()` (`frappe/model/document.py:309-310`), which calls
`_validate_mandatory()` first (`:624-625`); that calls
`_get_missing_mandatory_fields`, which counts any `reqd` field whose value is
`in (None, [])` (`frappe/model/base_document.py:775-777`) and raises at `:963`.

Why it stayed invisible: both call sites sit inside two nested
`except Exception` layers that report a local schema problem as
`"Failed to import customer from Xero"`, and `log_error(title, message)` records
no stack. So the failure looked like a Xero problem from the outside.

The fix is the owner's rule from review item **rev_f9dce41f7f**: imported contacts
default to `Company`. The value is one of the five Select options on both
DocTypes and is editable on the record afterwards.

## Why this is a whole-app rule rather than two assertions

The class is "a dict literal that must be complete at insert time", and nothing
about it is specific to Xero. Run across every `frappe.get_doc({...})` in the app
it checks 5 call sites against 47 DocType JSONs, and it goes red the day somebody
adds a `reqd` field to a DocType that an existing insert site does not pass.

## What this does NOT assert

* **That every key in the dict is a real field.** Writing a key no DocType
  declares is the separate lost-write class (`test_post_save_field_writes.py`,
  `test_undeclared_attributes.py`). Both import dicts still write `first_name`
  and `last_name`, which are fields on neither Customer nor Supplier -- raised,
  not touched here, because it is a different question and a different decision.
* **Anything about DocTypes frappe owns.** `erplite/www/todo/index.py` inserts a
  `ToDo`, whose JSON lives in frappe, not in this app. Skipped by name rather
  than silently, and counted, so the skip cannot quietly grow.
* **Documents built by assignment** (`doc = frappe.new_doc(...)` then
  `doc.x = ...`). Only dict literals are readable statically.

Runs without a bench. See fake_frappe.py for the stand-in these tests share.
"""

import ast
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ERPLITE = os.path.join(APP_ROOT, "erplite")

SKIP_DIRS = ("__pycache__", "node_modules", "public", "dist")

# DocTypes this app inserts but does not own. Each is frappe's, so its JSON is
# not in this tree and the rule cannot be evaluated against it.
FOREIGN_DOCTYPES = {"ToDo"}


def _walk(ext):
    for root, dirs, files in os.walk(ERPLITE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(ext):
                yield os.path.join(root, name)


def _doctype_index():
    """name -> (path, parsed JSON) for every DocType this app declares."""
    index = {}
    for path in _walk(".json"):
        # a DocType's JSON is <doctype_dir>/<doctype_dir>.json
        if os.path.basename(path)[:-5] != os.path.basename(os.path.dirname(path)):
            continue
        with open(path, encoding="utf-8") as fh:
            try:
                doc = json.load(fh)
            except ValueError:
                continue
        if doc.get("doctype") == "DocType" and doc.get("name"):
            index[doc["name"]] = (path, doc)
    return index


def _get_doc_dict_sites():
    """Every `*.get_doc({...})` whose dict names its doctype literally."""
    sites = []
    for path in _walk(".py"):
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get_doc"):
                continue
            if not node.args or not isinstance(node.args[0], ast.Dict):
                continue
            literal = node.args[0]
            keys = {k.value for k in literal.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            doctype = None
            for key, value in zip(literal.keys, literal.values):
                if (isinstance(key, ast.Constant) and key.value == "doctype"
                        and isinstance(value, ast.Constant)):
                    doctype = value.value
            if doctype:
                sites.append((os.path.relpath(path, APP_ROOT),
                              node.lineno, doctype, keys))
    return sites


def _unsatisfiable_mandatory_fields(doctype_json, supplied):
    """`reqd` fields the dict must carry: no default, and not read_only.

    A `reqd` field with a `default` is filled in by frappe before validation, and
    a `read_only` one cannot be passed in anyway -- neither can be the caller's
    fault, so neither belongs in this rule.
    """
    missing = []
    for field in doctype_json.get("fields", []):
        if not field.get("reqd"):
            continue
        if field.get("default") is not None:
            continue
        if field.get("read_only"):
            continue
        if field["fieldname"] in supplied:
            continue
        missing.append(field["fieldname"])
    return missing


class TestEveryGetDocDictSuppliesItsMandatoryFields(unittest.TestCase):
    def setUp(self):
        self.doctypes = _doctype_index()
        self.sites = _get_doc_dict_sites()

    def test_the_walkers_found_something_to_check(self):
        """A rule that checks nothing is broken, not green."""
        self.assertGreaterEqual(len(self.doctypes), 40,
                                "DocType index collapsed; the rule below would "
                                "pass by finding no JSON to compare against")
        self.assertGreaterEqual(len(self.sites), 5,
                                "no get_doc dict literals found, so the AST "
                                "walker is broken")

    def test_no_insert_site_can_raise_mandatory_error_for_every_input(self):
        failures = []
        for rel, lineno, doctype, keys in sorted(self.sites):
            if doctype in FOREIGN_DOCTYPES:
                continue
            if doctype not in self.doctypes:
                failures.append(
                    "%s:%d builds a %r, and no DocType JSON in this app "
                    "declares it. Either the name is wrong or it belongs in "
                    "FOREIGN_DOCTYPES with a reason."
                    % (rel, lineno, doctype))
                continue
            _, doctype_json = self.doctypes[doctype]
            missing = _unsatisfiable_mandatory_fields(doctype_json, keys)
            if missing:
                failures.append(
                    "%s:%d builds a %s without %s. Each is reqd on the DocType "
                    "with no default and is not read_only, so insert() raises "
                    "MandatoryError for every input -- this call site can never "
                    "create a record."
                    % (rel, lineno, doctype, ", ".join(sorted(missing))))
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_the_skip_list_is_still_needed_and_still_small(self):
        """So FOREIGN_DOCTYPES cannot quietly become a way to silence the rule."""
        inserted = {dt for _, _, dt, _ in self.sites}
        for doctype in FOREIGN_DOCTYPES:
            self.assertIn(doctype, inserted,
                          "%s is skipped but nothing inserts it any more; "
                          "remove it from FOREIGN_DOCTYPES" % doctype)
            self.assertNotIn(doctype, self.doctypes,
                             "%s is skipped as frappe's, but this app now "
                             "declares it -- it must be checked" % doctype)
        self.assertLessEqual(len(FOREIGN_DOCTYPES), 3,
                             "a growing skip list is the rule being switched "
                             "off one DocType at a time")


class TestTheRuleCatchesTheBugItWasWrittenFor(unittest.TestCase):
    """Fault injection: the two fixed call sites, as they were before the fix."""

    CASES = (
        ("Customer", "customer_type",
         "erplite/xero/accounts.py", "import_customer_from_xero"),
        ("Supplier", "supplier_type",
         "erplite/xero/accounts.py", "import_supplier_from_xero"),
    )

    def test_removing_the_type_key_makes_the_rule_red(self):
        doctypes = _doctype_index()
        for doctype, fieldname, rel, _func in self.CASES:
            with self.subTest(doctype=doctype):
                self.assertIn(doctype, doctypes)
                _, doctype_json = doctypes[doctype]

                site = next(
                    (s for s in _get_doc_dict_sites()
                     if s[0].replace(os.sep, "/") == rel and s[2] == doctype),
                    None)
                self.assertIsNotNone(
                    site, "%s no longer builds a %s from a dict literal; this "
                          "fault injection has nothing to inject into"
                          % (rel, doctype))
                keys = set(site[3])

                self.assertIn(fieldname, keys,
                              "%s must pass %s" % (rel, fieldname))
                self.assertEqual(
                    _unsatisfiable_mandatory_fields(doctype_json, keys), [],
                    "with the fix in place there is nothing missing")

                keys.discard(fieldname)
                self.assertEqual(
                    _unsatisfiable_mandatory_fields(doctype_json, keys),
                    [fieldname],
                    "with %s removed the rule must name it, or it would not "
                    "have caught the original bug" % fieldname)

    def test_company_is_a_value_the_select_can_hold(self):
        """The fix is only correct if the DocType offers the value it sets."""
        doctypes = _doctype_index()
        for doctype, fieldname, _rel, _func in self.CASES:
            with self.subTest(doctype=doctype):
                _, doctype_json = doctypes[doctype]
                field = next(f for f in doctype_json["fields"]
                             if f["fieldname"] == fieldname)
                self.assertEqual(field["fieldtype"], "Select")
                self.assertIn("Company", field["options"].split("\n"))
                self.assertFalse(
                    field.get("read_only"),
                    "a read_only %s could not be set from the import dict at "
                    "all, and the fix would be silently dropped" % fieldname)


if __name__ == "__main__":
    unittest.main()
