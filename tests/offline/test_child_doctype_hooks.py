# -*- coding: utf-8 -*-
"""Whole-app guard: a child DocType's controller must not define document hooks,
because Frappe never runs them.

A child DocType (`istable: 1`, the rows of a Table field) is a real Document
subclass with a real controller file, so a `validate()` on it looks exactly like a
`validate()` on its parent. Frappe never calls it. From `frappe/model/document.py`:

    def _validate(self):
        self._validate_mandatory()
        ...
        for d in self.get_all_children():
            d._validate_data_fields()
            d._validate_selects()
            d._validate_non_negative()
            ...                          # frappe's own _validate_* helpers only

Children get field-level validation and nothing else -- `d.validate()` and
`d.run_method(...)` appear nowhere in that loop. Every `run_method("validate")` in
`document.py` is called on `self`, the document being saved, which is the parent.
Nothing in the app calls `run_method` on a child row either.

So the code is syntactically fine, imports fine, reads fine, and never executes.
There is no error and nothing reaches the Error Log.

What this found when it was written (6 Oct 2026) -- three of the app's eight child
DocTypes:

  * `accounts/doctype/supplier_quote_item/supplier_quote_item.py` -- `validate()`
    called `calculate_amount()`, which was **the only server-side code that set
    `amount`**. `Supplier Quote.calculate_totals()` then read it:

        for item in self.items:
            if item.amount:
                self.total += flt(item.amount)

    `amount` is `read_only: 1` on the child DocType, so nobody could type it in
    either, and `init_valid_columns()` leaves an unsupplied field as `None`
    (`base_document.py`), so `if item.amount:` was simply falsy. **A Supplier
    Quote created anywhere but the Desk UI saved with `grand_total` of zero**, with
    nothing raised and nothing logged. `supplier_quote.js:88` sets `row.amount =
    row.qty * row.rate` in the browser, which is the only reason any quote in the
    system has a total at all. Fixed by deriving the line amount in the parent's
    `calculate_totals()`, which is what `sales_invoice.py` and `purchase_invoice.py`
    already do.

  * `accounts/doctype/sales_invoice_item/sales_invoice_item.py` and
    `accounts/doctype/purchase_invoice_item/purchase_invoice_item.py` --
    `validate()` called `calculate_amount()` and `calculate_tax_amount()`. Both
    parents already derive `amount` and `tax_amount` themselves, so these were
    harmless duplicates and removing them changed no behaviour. They are worth
    removing anyway: they are what made the Supplier Quote parent look covered.

The useful shape of this bug is the contrast inside one module. Three sibling
documents are written the same way; two parents compute their own line amounts and
one trusted a child hook, and only the third was wrong. The dead code did not merely
fail to run -- it is why the working code was never written.

## What counts as a hook

Only a method defined directly in the body of a class in the controller file, whose
name is one of the hooks Frappe actually invokes. The list below was read out of
Frappe 15's source (`run_method("...")` call sites in `model/document.py`,
`model/naming.py`, `model/delete_doc.py` and `desk/form/load.py`) rather than
recalled, because a hook name that Frappe does not call would make this guard
report code that is fine.

A nested `def validate` inside another method, and a module-level `def validate`,
are deliberately not hooks -- see `WalkerSelfTests`.
"""

import ast
import json
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from fake_frappe import (  # noqa: E402
    FakeDocumentBase, FakeFrappe, doctype_fields, make_doc, _dict,
)

SKIP_DIRS = {"public", "node_modules", "__pycache__", ".git", "dist", "build"}

# Read from Frappe 15's own run_method call sites, not from memory.
HOOKS = frozenset({
    "before_validate", "validate", "before_save", "before_submit", "before_cancel",
    "before_insert", "after_insert", "before_change", "on_change", "on_update",
    "on_submit", "on_cancel", "on_update_after_submit", "before_update_after_submit",
    "autoname", "on_trash", "after_delete", "onload",
})

# Empty on purpose. Every child DocType controller in the app is hook-free, so this
# guard is strict and costs nothing. Adding an entry here means accepting code that
# cannot run, which needs a reason written next to it.
ALLOWED = frozenset()


class Unparseable(Exception):
    """A controller file that does not compile. Reported as itself, not as a hook."""


def hooks_defined_in(source, where="<source>"):
    """Hook methods defined directly in a class body, as (class, hook, lineno).

    Only direct children of a ClassDef body count. A def nested inside another
    method is a local function, not a hook, and a def at module level is not a
    method at all.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        # Found while proving this guard bites: a bad file otherwise surfaced as a
        # traceback pointing into ast.py, which says nothing about which file.
        raise Unparseable("%s does not compile: %s" % (where, error))
    found = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and member.name in HOOKS:
                found.append((node.name, member.name, member.lineno))
    return found


def child_doctypes(app_root=APP_ROOT):
    """Every `istable: 1` DocType in the app, with its controller path if it has one."""
    out = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(app_root, "erplite")):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            if not filename.endswith(".json"):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, "rb") as handle:
                try:
                    definition = json.loads(handle.read().decode("utf-8"))
                except ValueError:
                    continue
            if not isinstance(definition, dict) or definition.get("doctype") != "DocType":
                continue
            if not definition.get("istable"):
                continue
            controller = path[:-len(".json")] + ".py"
            out.append((
                definition.get("name"),
                os.path.relpath(controller, app_root).replace(os.sep, "/"),
                controller if os.path.exists(controller) else None,
            ))
    return sorted(out)


def sweep_app(app_root=APP_ROOT):
    """Report every hook defined on a child DocType's controller."""
    reported = []
    for name, rel, controller in child_doctypes(app_root):
        if controller is None:
            continue
        with open(controller, "rb") as handle:
            source = handle.read().decode("utf-8")
        for class_name, hook, lineno in hooks_defined_in(source, rel):
            if rel in ALLOWED:
                continue
            reported.append((name, rel, class_name, hook, lineno))
    return reported


class ChildDoctypeHooks(unittest.TestCase):
    """The whole-app pass."""

    def test_no_child_doctype_controller_defines_a_hook(self):
        reported = sweep_app()
        if reported:
            lines = [
                "%s -- %s:%d defines %s.%s(), which Frappe never calls on a child row."
                % (name, rel, lineno, class_name, hook)
                for name, rel, class_name, hook, lineno in reported
            ]
            self.fail(
                "A child DocType's controller defines %d document hook(s) that cannot "
                "run:\n  %s\n\nFrappe's Document._validate() runs only its own "
                "_validate_* helpers on get_all_children(), and every "
                "run_method(\"...\") is called on the parent. Move the work into the "
                "parent's own hook -- see Supplier Quote.calculate_totals()."
                % (len(reported), "\n  ".join(lines))
            )

    def test_the_app_still_has_child_doctypes_to_check(self):
        """A guard that sweeps nothing passes for the wrong reason."""
        tables = child_doctypes()
        self.assertGreaterEqual(len(tables), 5, "expected the app's child DocTypes; found %r" % (tables,))
        self.assertIn("Supplier Quote Item", [name for name, _, _ in tables])

    def test_allowed_list_is_empty_or_explained(self):
        """If ALLOWED ever gains an entry, it must name a real controller."""
        for rel in ALLOWED:
            self.assertTrue(
                os.path.exists(os.path.join(APP_ROOT, rel)),
                "ALLOWED names %s, which does not exist" % rel,
            )


class WalkerSelfTests(unittest.TestCase):
    """What the walker must and must not report. Written before the sweep was run."""

    def test_an_unparseable_controller_says_which_file(self):
        with self.assertRaises(Unparseable) as caught:
            hooks_defined_in("class X(Document):\n\tpass\n    def validate(self):\n        pass\n",
                             "accounts/doctype/thing/thing.py")
        self.assertIn("accounts/doctype/thing/thing.py", str(caught.exception))

    def test_reports_a_hook_in_a_class_body(self):
        source = "class SupplierQuoteItem(Document):\n    def validate(self):\n        pass\n"
        self.assertEqual(hooks_defined_in(source), [("SupplierQuoteItem", "validate", 2)])

    def test_a_nested_def_is_not_this_hook(self):
        """The scope boundary. A local function named validate is not a hook."""
        source = (
            "class SupplierQuoteItem(Document):\n"
            "    def calculate_amount(self):\n"
            "        def validate(value):\n"
            "            return value or 0\n"
            "        self.amount = validate(self.qty) * validate(self.rate)\n"
        )
        self.assertEqual(hooks_defined_in(source), [])

    def test_a_module_level_function_is_not_a_hook(self):
        source = "def validate(doc):\n    pass\n"
        self.assertEqual(hooks_defined_in(source), [])

    def test_a_non_hook_method_is_not_reported(self):
        source = (
            "class SupplierQuoteItem(Document):\n"
            "    def calculate_amount(self):\n"
            "        self.amount = self.qty * self.rate\n"
        )
        self.assertEqual(hooks_defined_in(source), [])

    def test_reports_every_hook_not_just_the_first(self):
        source = (
            "class SalesInvoiceItem(Document):\n"
            "    def validate(self):\n"
            "        pass\n"
            "    def on_update(self):\n"
            "        pass\n"
        )
        self.assertEqual(
            [h for _, h, _ in hooks_defined_in(source)], ["validate", "on_update"])

    def test_async_hook_is_reported(self):
        source = "class X(Document):\n    async def on_submit(self):\n        pass\n"
        self.assertEqual([h for _, h, _ in hooks_defined_in(source)], ["on_submit"])

    def test_every_hook_name_is_one_frappe_calls(self):
        """Guards against a plausible-looking hook name that Frappe does not invoke."""
        for invented in ("after_save", "before_delete", "on_save", "after_validate"):
            self.assertNotIn(invented, HOOKS)
        for real in ("validate", "on_update", "before_save", "after_insert", "autoname"):
            self.assertIn(real, HOOKS)

    def test_only_child_doctypes_are_swept(self):
        """A hook on a normal DocType is correct code and must not be reported."""
        names = [name for name, _, _ in child_doctypes()]
        self.assertNotIn("Supplier Quote", names)
        self.assertNotIn("Sales Invoice", names)
        self.assertIn("Supplier Quote Item", names)


def load_controller(frappe, module_dir, doctype_dir):
    """Load a real controller with `frappe` replaced by the stand-in."""
    for name in list(sys.modules):
        if name == "frappe" or name.startswith("frappe."):
            del sys.modules[name]

    frappe_pkg = types.ModuleType("frappe")
    frappe_pkg.__path__ = []
    for attr in dir(frappe):
        if not attr.startswith("__"):
            setattr(frappe_pkg, attr, getattr(frappe, attr))
    frappe_pkg._dict = _dict

    model = types.ModuleType("frappe.model")
    model.__path__ = []
    document = types.ModuleType("frappe.model.document")
    document.Document = FakeDocumentBase
    model.document = document
    frappe_pkg.model = model

    utils = types.ModuleType("frappe.utils")

    def flt(value, precision=None):
        """frappe.utils.flt: anything uncastable becomes 0.0."""
        try:
            number = float(value or 0)
        except (TypeError, ValueError):
            number = 0.0
        return round(number, precision) if precision is not None else number

    utils.flt = flt
    utils.nowdate = lambda: "2026-10-06"
    utils.cint = lambda value: int(flt(value))
    utils.now_datetime = lambda: "2026-10-06 09:00:00"
    frappe_pkg.utils = utils
    # frappe._ is the translation function and is a no-op here. Both
    # invoice controllers import it at module level, so without it they
    # fail to load and the tests below would report the import as the
    # defect rather than whatever they were asking about.
    frappe_pkg._ = lambda text, *args, **kwargs: text

    sys.modules["frappe"] = frappe_pkg
    sys.modules["frappe.model"] = model
    sys.modules["frappe.model.document"] = document
    sys.modules["frappe.utils"] = utils

    import importlib.util
    path = os.path.join(APP_ROOT, "erplite", module_dir, "doctype",
                        doctype_dir, doctype_dir + ".py")
    spec = importlib.util.spec_from_file_location(
        "erplite_%s_under_test" % doctype_dir, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SupplierQuoteTotals(unittest.TestCase):
    """The regression tests for the bug this guard was written for.

    These drive the real `Supplier Quote` controller, so they fail if the fix is
    reverted -- the whole-app pass above would not notice that on its own.
    """

    def setUp(self):
        self.frappe = FakeFrappe(session_user="pat@company.test",
                                 roles=["System Manager"])
        self.frappe.tables["Supplier"] = [
            _dict(name="SUP-0001", supplier_name="Northwind Technologies"),
        ]
        self.module = load_controller(self.frappe, "accounts", "supplier_quote")

    class _ChildRow(FakeDocumentBase):
        """Stands in for the Supplier Quote Item controller, which is now hook-free."""

    def quote(self, rows):
        doc = make_doc(self.module.SupplierQuote, "Supplier Quote",
                       "accounts", "supplier_quote",
                       {"supplier": "SUP-0001", "status": "Received"})
        doc.items = [
            make_doc(self._ChildRow, "Supplier Quote Item",
                     "accounts", "supplier_quote_item", row)
            for row in rows
        ]
        return doc

    LINES = [
        {"item_name": "Senior systems engineer hours", "qty": 100, "rate": 140.0},
        {"item_name": "Travel", "qty": 2, "rate": 250.0},
    ]

    def test_total_is_right_from_qty_and_rate_alone(self):
        """The bug: no `amount` supplied, as for any server-side or REST creation."""
        doc = self.quote(self.LINES)
        doc.calculate_totals()
        self.assertEqual(doc.total, 14500.0)
        self.assertEqual(doc.grand_total, 14500.0)

    def test_line_amounts_are_filled_in(self):
        doc = self.quote(self.LINES)
        doc.calculate_totals()
        self.assertEqual([item.amount for item in doc.items], [14000.0, 500.0])

    def test_browser_supplied_amount_gives_the_same_answer(self):
        """The path in use today (supplier_quote.js:88) must not change."""
        rows = [dict(row, amount=row["qty"] * row["rate"]) for row in self.LINES]
        doc = self.quote(rows)
        doc.calculate_totals()
        self.assertEqual(doc.grand_total, 14500.0)

    def test_a_line_with_no_rate_contributes_nothing_and_does_not_raise(self):
        doc = self.quote([{"item_name": "To be quoted", "qty": 3}])
        doc.calculate_totals()
        self.assertEqual(doc.grand_total, 0.0)
        self.assertEqual(doc.items[0].amount, 0.0)

    def test_string_qty_and_rate_are_cast_not_concatenated(self):
        """flt() each operand: `2 * "250"` would be the string "250250"."""
        doc = self.quote([{"item_name": "Travel", "qty": "2", "rate": "250.0"}])
        doc.calculate_totals()
        self.assertEqual(doc.grand_total, 500.0)

    def test_no_items_totals_zero(self):
        doc = self.quote([])
        doc.calculate_totals()
        self.assertEqual(doc.grand_total, 0)


class SiblingParentsDeriveTheirOwnLineAmounts(unittest.TestCase):
    """The claim this file's reasoning rests on, which nothing was holding.

    Sales Invoice Item and Purchase Invoice Item had the same dead
    `validate()`/`calculate_amount()` pair removed from their controllers, and
    the reason recorded in the module docstring above is that "Both parents
    already derive `amount` and `tax_amount` themselves, so these were harmless
    duplicates and removing them changed no behaviour."

    That is the sentence that made removing them safe, and on 7 Oct 2026
    nothing in the repository was checking it. Reinstating the exact Supplier
    Quote bug in both parents -- `item.amount = item.amount or 0` in place of
    the derivation -- left this file's 21 tests green and the whole offline
    suite's 687 green. The two sibling parents are named in the docstring as
    the contrast that makes the bug legible, so an unchecked claim about them
    is an unchecked claim about why this file exists.

    Note what these tests do *not* say. `supplier_quote.py` casts both operands
    with `flt()`; these two multiply the raw attributes, so a line with no rate
    raises TypeError here where a Supplier Quote line totals zero. That is
    today's behaviour, characterised below rather than quietly fixed: changing
    it is a change to the invoice totals, which is the owner's call, not a
    test's.
    """

    PARENTS = (
        ("sales_invoice", "SalesInvoice", "Sales Invoice", "customer",
         "sales_invoice_item", "Sales Invoice Item"),
        ("purchase_invoice", "PurchaseInvoice", "Purchase Invoice", "supplier",
         "purchase_invoice_item", "Purchase Invoice Item"),
    )

    LINES = [
        {"item_name": "Senior systems engineer hours", "qty": 100, "rate": 154.0},
        {"item_name": "Travel", "qty": 2, "rate": 250.0},
    ]

    class _ChildRow(FakeDocumentBase):
        """Stands in for the item controller, which is now hook-free."""

    def invoice(self, parent_dir, class_name, doctype, party_field,
                child_dir, child_doctype, rows):
        frappe = FakeFrappe(session_user="pat@company.test",
                            roles=["System Manager"])
        frappe.tables["Company"] = [_dict(name="Tierney Morris Pty Ltd")]
        module = load_controller(frappe, "accounts", parent_dir)
        doc = make_doc(getattr(module, class_name), doctype,
                       "accounts", parent_dir,
                       {party_field: "PARTY-0001", "status": "Draft"})
        doc.items = [
            make_doc(self._ChildRow, child_doctype, "accounts", child_dir, row)
            for row in rows
        ]
        return doc

    def test_the_total_comes_from_qty_and_rate_alone(self):
        """No `amount` supplied, as for any server-side or REST creation."""
        for args in self.PARENTS:
            with self.subTest(doctype=args[2]):
                doc = self.invoice(*args, self.LINES)
                doc.calculate_totals()
                self.assertEqual(doc.total, 15900.0)
                self.assertEqual(doc.grand_total, 15900.0)

    def test_line_amounts_are_filled_in(self):
        for args in self.PARENTS:
            with self.subTest(doctype=args[2]):
                doc = self.invoice(*args, self.LINES)
                doc.calculate_totals()
                self.assertEqual([item.amount for item in doc.items],
                                 [15400.0, 500.0])

    def test_tax_is_derived_from_the_derived_line_amount(self):
        """tax_amount reads item.amount, so it inherits whatever that is."""
        rows = [dict(self.LINES[0], tax_rate=10)]
        for args in self.PARENTS:
            with self.subTest(doctype=args[2]):
                doc = self.invoice(*args, rows)
                doc.calculate_totals()
                self.assertEqual(doc.items[0].tax_amount, 1540.0)
                self.assertEqual(doc.total_tax, 1540.0)
                self.assertEqual(doc.grand_total, 16940.0)

    def test_no_tax_rate_leaves_the_tax_total_at_nought(self):
        for args in self.PARENTS:
            with self.subTest(doctype=args[2]):
                doc = self.invoice(*args, self.LINES)
                doc.calculate_totals()
                self.assertEqual(doc.total_tax, 0)

    def test_a_line_with_no_rate_raises_here_but_not_on_a_supplier_quote(self):
        """Characterising today's behaviour, not endorsing it.

        The operands are not cast, so an unsupplied rate is None and the
        multiplication raises. The same line on a Supplier Quote totals zero,
        because `calculate_totals()` there casts with flt(). Both documents are
        reachable over the REST API with a line that has no rate yet.
        """
        for args in self.PARENTS:
            with self.subTest(doctype=args[2]):
                doc = self.invoice(*args, [{"item_name": "To be quoted",
                                            "qty": 3}])
                with self.assertRaises(TypeError):
                    doc.calculate_totals()

    def test_a_string_rate_is_concatenated_onto_the_row_then_raises(self):
        """The other half of the same missing cast, and where it surfaces.

        REST and the import tool both send numbers as strings. `2 * "250.0"`
        is not an error in Python, it is the string "250.0250.0", so the wrong
        value is written to the row first and the raise comes one line later
        from `self.total += item.amount`. The row is what a reader checks, so
        this pins both: the bad value lands, and the accumulation stops it
        reaching the database.
        """
        for args in self.PARENTS:
            with self.subTest(doctype=args[2]):
                doc = self.invoice(*args, [{"item_name": "Travel", "qty": 2,
                                            "rate": "250.0"}])
                with self.assertRaises(TypeError):
                    doc.calculate_totals()
                self.assertEqual(doc.items[0].amount, "250.0250.0")

    def test_rounded_total_is_the_grand_total_rounded(self):
        rows = [{"item_name": "Part hour", "qty": 1, "rate": 154.49}]
        for args in self.PARENTS:
            with self.subTest(doctype=args[2]):
                doc = self.invoice(*args, rows)
                doc.calculate_totals()
                self.assertEqual(doc.grand_total, 154.49)
                self.assertEqual(doc.rounded_total, 154)


class Premises(unittest.TestCase):
    """The facts the fix rests on, read from the DocType JSONs themselves."""

    def _field(self, module, doctype_dir, fieldname):
        path = os.path.join(APP_ROOT, "erplite", module, "doctype",
                            doctype_dir, doctype_dir + ".json")
        with open(path, "rb") as handle:
            definition = json.loads(handle.read().decode("utf-8"))
        for field in definition.get("fields", []):
            if field.get("fieldname") == fieldname:
                return field
        return None

    def test_amount_is_read_only_so_a_user_cannot_type_it(self):
        """Why the browser was the only thing filling it, and why that matters."""
        field = self._field("accounts", "supplier_quote_item", "amount")
        self.assertIsNotNone(field)
        self.assertEqual(field.get("read_only"), 1)

    def test_qty_and_rate_are_the_inputs(self):
        for fieldname in ("qty", "rate"):
            self.assertIsNotNone(self._field("accounts", "supplier_quote_item", fieldname))

    def test_supplier_quote_item_fields_include_amount(self):
        self.assertIn("amount", doctype_fields("accounts", "supplier_quote_item"))


if __name__ == "__main__":
    unittest.main()
