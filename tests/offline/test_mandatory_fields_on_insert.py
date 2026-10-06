# -*- coding: utf-8 -*-
"""A `frappe.get_doc({...}).insert()` must supply the DocType's mandatory fields.

## What this found (7 Oct 2026)

`erplite/xero/accounts.py`, `import_customer_from_xero` and
`import_supplier_from_xero`, each built its document from a dict literal that
omitted `customer_type` / `supplier_type`. Both fields are `reqd: 1` on their
DocType with **no default**, so there was no second chance to fill them in:
`insert()` raised `MandatoryError` for every contact Xero returned.
Neither endpoint could create a single Customer or Supplier, for any input.

Traced through frappe-version-15 rather than recalled: `insert()` calls
`_validate()` (`frappe/model/document.py:309-310`), which calls
`_validate_mandatory()` first (`:624-625`); that calls
`_get_missing_mandatory_fields` (`frappe/model/base_document.py:776`), which
raises at `:963` for any `reqd` field where:

    self.get(df.fieldname) in (None, []) or not has_content(df)

**Both clauses matter, and the second is the one that is easy to leave out.**
`has_content` (`:760-771`) is `strip_html(cstr(value)).strip()`, so `""`,
`"   "` and `"<p></p>"` are missing too. A field is not supplied because its key
is in the dict; it is supplied because its *value* survives that test. This rule
therefore reads each key's value expression, and treats an expression it cannot
read as content -- a runtime value is not its business, only one that is
provably empty.

Two exemptions this rule does **not** grant, both measured rather than reasoned:
`read_only` is not exempt (`_get_missing_mandatory_fields` does not exempt it,
and a server-side dict can set it), and a `default` exempts a field only when it
is *truthy*, because `create_new.py:101` applies it only `if df.get("default")`
-- so `"default": ""` is no default at all.

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
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ERPLITE = os.path.join(APP_ROOT, "erplite")

SKIP_DIRS = ("__pycache__", "node_modules", "public", "dist")

# DocTypes this app inserts but does not own. Each is frappe's, so its JSON is
# not in this tree and the rule cannot be evaluated against it.
FOREIGN_DOCTYPES = {"ToDo"}

# The insert sites in the app today. An exact count, not a floor: a floor set
# below the real number is slack, and one site can disappear from the walker's
# reach -- which is how a widened shape used to go unnoticed -- without a word
# being said. Changing this number is a deliberate act; dropping it is not.
EXPECTED_INSERT_SITES = 6


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


def _get_doc_aliases(tree):
    """Local names bound to frappe's get_doc: `_new = frappe.get_doc`."""
    aliases = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "get_doc"):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    aliases.add(target.id)
    return aliases


def _get_doc_calls(tree):
    """Every call that reaches get_doc, by attribute or through a local alias."""
    aliases = _get_doc_aliases(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "get_doc":
            yield node
        elif isinstance(func, ast.Name) and func.id in aliases:
            yield node


_TAG = re.compile(r"<[^>]*>")


def _has_content(text):
    """frappe's has_content, for a string we can read statically.

    base_document.py:760-771: `strip_html(cstr(value)).strip()`, or any `<img`.
    The Text Editor and Code/HTML branches only ever widen this, so a literal
    this says is empty is empty for every fieldtype.
    """
    if "<img" in text:
        return True
    return bool(_TAG.sub("", text).strip())


# What a dict literal's value tells us about the field having content at insert.
CONTENT = "content"            # cannot be empty, or is not ours to judge
EMPTY = "empty"                # empty for every input: insert always raises
CONDITIONAL = "conditional"    # empty exactly when the source dict omits the key

_NO_DOCTYPE = object()


def _value_kind(value):
    """Apply frappe's missing-value test to the expression a dict supplies.

    frappe asks `self.get(f) in (None, []) or not has_content(df)` -- so the
    *value* decides, never the key's presence. Anything we cannot read is
    CONTENT: a runtime value is not this rule's business, only a value that is
    provably empty, or provably defaulted to empty.
    """
    if isinstance(value, ast.Constant):
        if value.value is None:
            return EMPTY
        if isinstance(value.value, str):
            return CONTENT if _has_content(value.value) else EMPTY
        # cstr(0) is "0" and cstr(False) is "False": both have content.
        return CONTENT
    if isinstance(value, (ast.List, ast.Tuple)):
        # `[]` is named in frappe's test directly; ["x"] stringifies to "['x']".
        return EMPTY if not value.elts else CONTENT
    if isinstance(value, ast.Dict) and not value.keys:
        # Deliberately CONTENT: cstr({}) is "{}", which strip_html keeps.
        return CONTENT
    if isinstance(value, ast.JoinedStr):
        if all(isinstance(v, ast.Constant) for v in value.values):
            joined = "".join(str(v.value) for v in value.values)
            return CONTENT if _has_content(joined) else EMPTY
        return CONTENT
    if isinstance(value, ast.BoolOp) and isinstance(value.op, ast.Or):
        # `x or "Company"`: the last operand is the fallback, so it decides.
        return _value_kind(value.values[-1])
    if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
            and value.func.attr == "get"):
        if len(value.args) == 1:
            return CONDITIONAL          # .get(k) defaults to None
        if len(value.args) == 2 and _value_kind(value.args[1]) == EMPTY:
            return CONDITIONAL          # .get(k, "") is empty when k is absent
    return CONTENT


def _supplied_from_dict_literal(literal):
    """name -> kind for a dict literal, plus its doctype expression."""
    supplied, doctype = {}, _NO_DOCTYPE
    for key, value in zip(literal.keys, literal.values):
        if key is None:
            return None, None           # {**base, ...}: contents unreadable
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            continue
        if key.value == "doctype":
            doctype = value
            continue
        supplied[key.value] = _value_kind(value)
    return supplied, doctype


def _supplied_from_dict_call(call):
    """The same, for `dict(doctype="X", ...)` instead of a literal."""
    supplied, doctype = {}, _NO_DOCTYPE
    for keyword in call.keywords:
        if keyword.arg is None:
            return None, None           # dict(**base): contents unreadable
        if keyword.arg == "doctype":
            doctype = keyword.value
            continue
        supplied[keyword.arg] = _value_kind(keyword.value)
    return supplied, doctype


def _get_doc_dict_sites():
    """Every get_doc call that builds its document from a dict in place.

    Each site is (relpath, lineno, doctype or None, name -> kind, written-as).
    `doctype is None` means the call builds a document here and this rule
    cannot tell which -- reported, never dropped, because an unreadable site
    and a site with nothing wrong are not the same fact.
    """
    sites = []
    for path in _walk(".py"):
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in _get_doc_calls(tree):
            if not node.args:
                continue
            argument = node.args[0]
            if isinstance(argument, ast.Dict):
                supplied, doctype = _supplied_from_dict_literal(argument)
            elif (isinstance(argument, ast.Call)
                    and isinstance(argument.func, ast.Name)
                    and argument.func.id == "dict"):
                supplied, doctype = _supplied_from_dict_call(argument)
            else:
                continue                # get_doc("Customer", name): a load
            rel = os.path.relpath(path, APP_ROOT)
            if supplied is None:
                sites.append((rel, node.lineno, None, {}, "a dict it spreads "
                              "another mapping into"))
                continue
            if doctype is _NO_DOCTYPE:
                continue                # not an insert dict at all
            if isinstance(doctype, ast.Constant) and isinstance(doctype.value, str):
                sites.append((rel, node.lineno, doctype.value, supplied, None))
            else:
                sites.append((rel, node.lineno, None, supplied,
                              "doctype=%s" % ast.dump(doctype).split("(")[0]))
    return sites


def _caller_supplied_mandatory_fields(doctype_json):
    """`reqd` fields whose value has to come from the caller.

    A field frappe fills in itself is not the caller's fault. Only a *truthy*
    default is ever applied -- `create_new.py:101` guards on `if df.get(
    "default")` -- so `"default": ""` exempts nothing and is not treated as a
    default here either.

    read_only is deliberately NOT an exemption: _get_missing_mandatory_fields
    does not exempt it, and a server-side dict can set it, so a read_only reqd
    field with no default raises exactly like any other.
    """
    for field in doctype_json.get("fields", []):
        if not field.get("reqd"):
            continue
        if field.get("default"):
            continue
        yield field["fieldname"]


def _unsatisfiable_mandatory_fields(doctype_json, supplied):
    """Fields this dict can never give content to: insert() always raises."""
    missing = []
    for fieldname in _caller_supplied_mandatory_fields(doctype_json):
        if supplied.get(fieldname, EMPTY) == EMPTY:
            missing.append(fieldname)
    return missing


def _conditionally_empty_mandatory_fields(doctype_json, supplied):
    """Fields supplied as `.get(key, "")`: empty whenever the source omits it."""
    return [fieldname
            for fieldname in _caller_supplied_mandatory_fields(doctype_json)
            if supplied.get(fieldname) == CONDITIONAL]


class TestEveryGetDocDictSuppliesItsMandatoryFields(unittest.TestCase):
    def setUp(self):
        self.doctypes = _doctype_index()
        self.sites = _get_doc_dict_sites()

    def test_the_walkers_found_something_to_check(self):
        """A rule that checks nothing is broken, not green."""
        self.assertGreaterEqual(len(self.doctypes), 40,
                                "DocType index collapsed; the rule below would "
                                "pass by finding no JSON to compare against")
        self.assertEqual(
            len(self.sites), EXPECTED_INSERT_SITES,
            "the walker finds %d insert sites, not the %d this app has. Fewer "
            "means a site is written in a shape it cannot read and is now "
            "unchecked; more means a new site to account for here."
            % (len(self.sites), EXPECTED_INSERT_SITES))

    def test_no_insert_site_can_raise_mandatory_error_for_every_input(self):
        failures = []
        for rel, lineno, doctype, supplied, note in sorted(
                self.sites, key=lambda s: (s[0], s[1])):
            if doctype is None:
                failures.append(
                    "%s:%d builds a document from %s, so this rule cannot tell "
                    "which DocType it is and the site goes unchecked. Name the "
                    "doctype literally, or add it here as a stated exception."
                    % (rel, lineno, note))
                continue
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
            missing = _unsatisfiable_mandatory_fields(doctype_json, supplied)
            if missing:
                failures.append(
                    "%s:%d builds a %s without %s. Each is reqd on the DocType "
                    "with no default that frappe would apply, and is given no "
                    "value with content here, so insert() raises MandatoryError "
                    "for every input -- this call site can never create a "
                    "record."
                    % (rel, lineno, doctype, ", ".join(sorted(missing))))
            conditional = _conditionally_empty_mandatory_fields(
                doctype_json, supplied)
            if conditional:
                failures.append(
                    "%s:%d builds a %s whose %s is taken from another mapping "
                    "with an empty default, so it is empty exactly when that "
                    "mapping omits the key and insert() raises MandatoryError "
                    "for those inputs. A mandatory field cannot default to "
                    "nothing: give it a real fallback, or let the lookup raise."
                    % (rel, lineno, doctype, ", ".join(sorted(conditional))))
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_the_skip_list_is_still_needed_and_still_small(self):
        """So FOREIGN_DOCTYPES cannot quietly become a way to silence the rule."""
        inserted = {s[2] for s in self.sites if s[2] is not None}
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
                supplied = dict(site[3])

                self.assertEqual(supplied.get(fieldname), CONTENT,
                                 "%s must pass %s, with a value that has "
                                 "content" % (rel, fieldname))
                self.assertEqual(
                    _unsatisfiable_mandatory_fields(doctype_json, supplied), [],
                    "with the fix in place there is nothing missing")

                supplied.pop(fieldname)
                self.assertEqual(
                    _unsatisfiable_mandatory_fields(doctype_json, supplied),
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
