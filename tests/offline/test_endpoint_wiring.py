# -*- coding: utf-8 -*-
"""A button must call a method that exists, and new_doc must name a real DocType.

Two whole-app rules and one narrow guard, all from review item **rev_0ee5b675ce**.

## What this found (7 Oct 2026)

`supplier_quote.py` whitelisted `create_purchase_order_from_quote`, which opened
with `frappe.new_doc("Purchase Order")`. **No app on this bench declares a
Purchase Order DocType** -- not erplite, not afterz, not frappe itself (it is an
ERPNext DocType, and this is not ERPNext). So `new_doc` raised
`DoesNotExistError` before the first assignment: a whitelisted endpoint that
could not succeed for any input, reached by a "Create Purchase Order" button that
`supplier_quote.js` showed on every Accepted quote. Its own comment admitted it:
*"this would need the Purchase Order doctype to exist"*.

The owner's decision was to remove the endpoint and the button rather than build
the DocType. Removing one half and leaving the other is the obvious way to get
this wrong in either direction, so `TestEveryClientCallResolves` below pins both
halves to each other.

`activity.js` carried the other half of the same item: a `progress_percent` form
handler, a validation branch and a list-view formatter for a field the Activity
DocType does not declare. The owner decided an Activity should not get one, so
they are gone rather than kept as a record of what was intended.

## Why these are rules and not three assertions

A client script naming a server method it cannot reach, and a controller naming a
DocType nothing declares, are both statically decidable and neither is specific to
Supplier Quote. Across the app that is 22 `frappe.call` methods and 7 `new_doc`
literals checked, and either goes red the day somebody deletes a function a button
still points at.

## What these rules do NOT cover

* **Dynamic method names.** Only `method: 'erplite....'` string literals are
  readable. `frappe.call` with a built string, and calls into frappe's own
  endpoints, are skipped -- the second deliberately, since frappe's source is not
  in this tree.
* **Whether the method is whitelisted.** The rule proves the function exists, not
  that `@frappe.whitelist()` is on it. A missing decorator is a permission error
  rather than an "attribute does not exist" error, and it is a different class.
* **`new_doc` with a variable**, and `get_doc({...})` dict literals, which
  `test_mandatory_fields_on_insert.py` covers from the mandatory-field angle.
* **The other three undeclared fields activity.js still reads.** `priority`,
  `due_date` and `estimated_hours` are not fields on Activity either. They are
  inert (`undefined` is falsy, so their branches never run) and whether Activity
  should have them is a product question the owner has not been asked. Only
  `progress_percent` was decided, so only `progress_percent` is asserted here.
  `test_client_scripts.py` records the full list.

Runs without a bench.
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

CALL_METHOD = re.compile(r"""method\s*:\s*['"](erplite\.[\w.]+)['"]""")
NEW_DOC = re.compile(r"""new_doc\(\s*['"]([^'"]+)['"]""")


def _walk(ext):
    for root, dirs, files in os.walk(ERPLITE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(ext):
                yield os.path.join(root, name)


def _declared_doctypes():
    """Every DocType name this app declares, from <dir>/<dir>.json."""
    names = set()
    for path in _walk(".json"):
        if os.path.basename(path)[:-5] != os.path.basename(os.path.dirname(path)):
            continue
        with open(path, encoding="utf-8") as fh:
            try:
                doc = json.load(fh)
            except ValueError:
                continue
        if doc.get("doctype") == "DocType" and doc.get("name"):
            names.add(doc["name"])
    return names


def _module_level_functions(path):
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    return {node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _client_calls():
    """(js file, dotted method) for every erplite method a client script calls."""
    found = set()
    for path in _walk(".js"):
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        for match in CALL_METHOD.finditer(source):
            found.add((os.path.relpath(path, APP_ROOT), match.group(1)))
    return found


def _resolve(dotted):
    """None if the method resolves; otherwise why it does not."""
    module, _, function = dotted.rpartition(".")
    rel = os.path.join(*module.split(".")) + ".py"
    path = os.path.join(APP_ROOT, rel)
    if not os.path.exists(path):
        return "there is no module %s" % rel
    if function not in _module_level_functions(path):
        return "%s defines no %s()" % (rel, function)
    return None


class TestEveryClientCallResolves(unittest.TestCase):
    """A button that calls a method that is not there fails only when clicked.

    `frappe.call` resolves the dotted path at request time, so a button pointing
    at a deleted function raises `AttributeError` server-side on the click and
    nothing before it. Nothing in a build, a migrate or a test run notices.
    """

    def test_the_walker_found_calls_to_check(self):
        calls = _client_calls()
        self.assertGreaterEqual(len(calls), 20,
                                "the frappe.call walker is broken, so the rule "
                                "below would pass by finding nothing")

    def test_every_method_a_client_script_calls_exists(self):
        failures = []
        for rel, dotted in sorted(_client_calls()):
            why = _resolve(dotted)
            if why:
                failures.append(
                    "%s calls %s and %s -- the button will raise on the click "
                    "and nowhere else" % (rel, dotted, why))
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_no_button_is_left_pointing_at_the_removed_purchase_order_endpoint(self):
        """The specific half-removal this item was about, from both sides."""
        name = "create_purchase_order_from_quote"
        controller = os.path.join(
            ERPLITE, "accounts", "doctype", "supplier_quote", "supplier_quote.py")
        self.assertNotIn(name, _module_level_functions(controller),
                         "the endpoint was removed by rev_0ee5b675ce; adding it "
                         "back needs a Purchase Order DocType first")
        for rel, dotted in _client_calls():
            self.assertNotIn(name, dotted,
                             "%s still calls the removed endpoint" % rel)


class TestEveryNewDocNamesADeclaredDoctype(unittest.TestCase):
    def test_the_walker_found_new_doc_sites(self):
        sites = []
        for path in _walk(".py"):
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            sites += [(os.path.relpath(path, APP_ROOT), m.group(1))
                      for m in NEW_DOC.finditer(source)]
        self.assertGreaterEqual(len(sites), 7,
                                "the new_doc walker is broken")

    def test_no_new_doc_names_a_doctype_nothing_declares(self):
        declared = _declared_doctypes()
        self.assertGreaterEqual(len(declared), 40,
                                "the DocType index collapsed, so this rule "
                                "would fail for the wrong reason")
        failures = []
        for path in _walk(".py"):
            with open(path, encoding="utf-8") as fh:
                source = fh.read()
            for match in NEW_DOC.finditer(source):
                doctype = match.group(1)
                if doctype in declared:
                    continue
                line = source[:match.start()].count("\n") + 1
                failures.append(
                    "%s:%d calls new_doc(%r), and no DocType JSON in this app "
                    "declares it -- the call raises DoesNotExistError for every "
                    "input" % (os.path.relpath(path, APP_ROOT), line, doctype))
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_purchase_order_is_still_not_a_doctype_anywhere_in_this_app(self):
        """So the rule above is testing something, not passing vacuously."""
        self.assertNotIn("Purchase Order", _declared_doctypes(),
                         "if a Purchase Order DocType is added, the endpoint "
                         "this item removed becomes buildable and the removal "
                         "is worth revisiting")


class TestAnActivityDoesNotTrackProgress(unittest.TestCase):
    """The owner's answer: no progress field on Activity (rev_0ee5b675ce)."""

    ACTIVITY_DIR = os.path.join(ERPLITE, "projects", "doctype", "activity")

    def _js(self):
        with open(os.path.join(self.ACTIVITY_DIR, "activity.js"),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_the_doctype_declares_no_progress_field(self):
        with open(os.path.join(self.ACTIVITY_DIR, "activity.json"),
                  encoding="utf-8") as fh:
            fields = {f["fieldname"] for f in json.load(fh)["fields"]}
        self.assertNotIn("progress_percent", fields)
        self.assertFalse([f for f in fields if "progress" in f],
                         "the owner's answer was that an Activity does not "
                         "track progress; a new progress field means that "
                         "decision changed and this file should change with it")

    def test_the_client_script_has_no_progress_handler_or_formatter(self):
        """Checked against code lines only, so the comment saying why may stay.

        Deliberately matched on `progress_percent` and `add_progress` rather
        than on "progress": the status indicator maps still contain the string
        `In Progress`, so a bare substring check would pass or fail on
        capitalisation rather than on anything real.
        """
        offenders = []
        for number, line in enumerate(self._js().splitlines(), start=1):
            if line.strip().startswith("//"):
                continue
            for needle in ("progress_percent", "add_progress"):
                if needle in line:
                    offenders.append("line %d names %s" % (number, needle))
        self.assertEqual(
            offenders, [],
            "activity.js must not watch, validate or format a field the "
            "DocType does not declare: " + "; ".join(offenders))

    def test_add_fields_no_longer_asks_the_list_view_for_it(self):
        """`add_fields` goes into the list query, so a dead name is not inert.

        This is the part that was not merely dead code: frappe's
        `DatabaseQuery` does not check field names against the DocType, so the
        name reached the SQL and what happened next was the database's decision.
        """
        match = re.search(r"add_fields\s*:\s*\[([^\]]*)\]", self._js())
        self.assertIsNotNone(match, "activity.js has no listview add_fields; if "
                                    "it was restructured, re-check this by hand")
        requested = re.findall(r"""['"](\w+)['"]""", match.group(1))
        self.assertNotIn("progress_percent", requested)
        self.assertIn("status", requested,
                      "the list view still needs status for its indicator")


if __name__ == "__main__":
    unittest.main()
