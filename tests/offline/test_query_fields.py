# -*- coding: utf-8 -*-
"""Whole-app guard on the field names inside QUERIES.

Every other sweep in this folder checks a field name somewhere else: `self.<x>` in a
controller, `doc.<x> = v` on a document, a Select value, a `fetch_from`, a DocType's own
JSON, a string in a form script. The query is the surface none of them covered, and it is
the one this app gets wrong most often -- twice fixed one instance at a time
(`Activity.subject`/`assigned_to`, then `Timesheet Entry.date`) with nothing to stop the
third. This sweeps the whole app so there cannot be a third.

A query naming a field the DocType does not declare fails in three different ways, and
which one you get depends on the call, not on the mistake. All three are from
frappe-version-15 source:

  * **Silently, reading a stale value.** If the field was REMOVED from the DocType, the
    column is still there: `bench migrate` never drops one. `frappe.model.delete_fields`
    (`frappe/model/__init__.py:198-211`) is the only DROP COLUMN in frappe and it runs
    only from a patch somebody writes by hand, and this app's `patches.txt` declares none. So the
    SQL is valid, the orphan is read, and nothing is logged. New rows have NULL there,
    because `get_valid_dict()` never writes a column the DocType does not declare -- so
    a filter on the orphan silently excludes every row written since the removal.

  * **Silently, as None.** `frappe.db.exists()` passes `ignore=True`
    (`frappe/database/database.py:1294`), and `get_values` turns a missing column into
    `out = None` when `ignore` is set (`:640-646`). So `db.exists` on a field that never
    existed returns None -- indistinguishable from "no such record". A guard written as
    `if frappe.db.exists(...): frappe.throw(...)` is then permanently off.

  * **Loudly.** Every other path leaves `ignore` unset, so `get_values` re-raises
    (`:652`), and `frappe.get_all` has no missing-column handling at all. The caller's
    `except Exception` usually turns it into `{"success": False}` with no stack.

The sweep is deliberately conservative. It judges only a bare identifier -- anything with
a bracket, dot, space, comma or star is SQL or an alias and is skipped rather than
guessed at -- and only for DocTypes this app defines, since a core DocType's field list
is not in this repo.

The four findings still open are pinned below rather than excused: each has its own test
asserting the schema fact it rests on, so resolving one FAILS here and says what to edit.
"""

import ast
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODULE_ROOT = os.path.join(APP_ROOT, "erplite")
sys.path.insert(0, HERE)

from test_undeclared_attributes import _app_doctypes  # noqa: E402

# Columns every table has, from frappe/model/__init__.py default_fields plus the optional
# ones frappe adds to a DocType that uses them.
STANDARD = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "parent", "parentfield", "parenttype",
    "_user_tags", "_comments", "_assign", "_liked_by", "_seen",
}

# Second positional argument is `fields` (DatabaseQuery.execute(fields, filters, ...)).
FIELDS_FIRST = {"get_all", "get_list"}
# Fieldname(s) come as the third positional: get_value("DT", name, "field"),
# set_value("DT", name, "field", v), set_value("DT", name, {"field": v}).
FIELD_THIRD = {"get_value", "get_values", "set_value", "get_cached_value"}
# get_single_value("DT", "field").
FIELD_SECOND = {"get_single_value"}
# Everything whose first keyword-less dict argument is `filters`.
FILTER_SECOND = FIELDS_FIRST | FIELD_THIRD | {"count", "exists"}

QUERIES = FIELDS_FIRST | FIELD_THIRD | FIELD_SECOND | {"count", "exists"}


def _str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _bare(token):
    """The token if it is a bare field name, else None.

    Anything else -- `count(name) as n`, `tabFoo.name`, `*`, `a, b` -- is SQL or an alias
    this sweep must not judge.
    """
    token = token.strip()
    if not token or not token.replace("_", "").isalnum():
        return None
    if not (token[0].isalpha() or token[0] == "_"):
        return None
    return token


def _kwarg(call, name):
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def scan_tree(tree, doctypes):
    """Every undeclared field name a query in `tree` names.

    Returns a list of (lineno, doctype, where, field).
    """
    out = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        fname = func.attr if isinstance(func, ast.Attribute) else None
        if fname not in QUERIES:
            continue
        # The DocType is the first positional, or the `doctype` keyword -- a
        # call written entirely in keywords has no positional arguments at all,
        # and skipping those made every field in it invisible.
        doctype = _str(node.args[0]) if node.args else _str(_kwarg(node, "doctype"))
        if doctype not in doctypes:
            continue
        declared = set(doctypes[doctype]) | STANDARD

        def report(value, where, lineno):
            field = _bare(value)
            if field and field not in declared:
                out.append((lineno, doctype, where, field))

        def report_fields(node_, where):
            if isinstance(node_, (ast.List, ast.Tuple)):
                for element in node_.elts:
                    value = _str(element)
                    if value:
                        report(value, where, element.lineno)
            elif isinstance(node_, ast.Dict):
                for key in node_.keys:
                    value = _str(key)
                    if value:
                        report(value, where, key.lineno)
            else:
                value = _str(node_)
                if value:
                    report(value, where, node_.lineno)

        # fields
        fields = _kwarg(node, "fields")
        if fields is None and fname in FIELDS_FIRST and len(node.args) > 1:
            if isinstance(node.args[1], (ast.List, ast.Tuple)) or _str(node.args[1]):
                fields = node.args[1]
        if fields is not None:
            report_fields(fields, "fields")
        report_fields(_kwarg(node, "pluck"), "pluck")

        # the positional fieldname forms
        if fname in FIELD_THIRD and len(node.args) > 2:
            report_fields(node.args[2], "fieldname argument")
        if fname in FIELD_SECOND and len(node.args) > 1:
            report_fields(node.args[1], "fieldname argument")
        # ... or by keyword. `frappe.db.get_value(dt, filters=..., fieldname=...)`
        # is the form erplite/xero/api.py:50 already uses, so reading only the
        # positional forms left a shape that is live in this app unswept.
        if fname in FIELD_THIRD or fname in FIELD_SECOND:
            report_fields(_kwarg(node, "fieldname"), "fieldname argument")

        # filters
        for key in ("filters", "or_filters"):
            filters = _kwarg(node, key)
            if filters is None and key == "filters" and fname in FILTER_SECOND \
                    and len(node.args) > 1 and isinstance(node.args[1], ast.Dict):
                filters = node.args[1]
            if isinstance(filters, ast.Dict):
                for k in filters.keys:
                    value = _str(k)
                    if value:
                        report(value, "%s key" % key, k.lineno)
            elif isinstance(filters, (ast.List, ast.Tuple)):
                # [["field", "op", v]] or [["DocType", "field", "op", v]]
                for element in filters.elts:
                    if not (isinstance(element, (ast.List, ast.Tuple)) and element.elts):
                        continue
                    first = _str(element.elts[0])
                    if first in doctypes and len(element.elts) > 1:
                        second = _str(element.elts[1])
                        if second:
                            report(second, "%s list" % key, element.lineno)
                    elif first:
                        report(first, "%s list" % key, element.lineno)

        # order_by / group_by
        for key in ("order_by", "group_by"):
            clause = _str(_kwarg(node, key))
            if not clause:
                continue
            for part in clause.split(","):
                part = part.strip()
                for suffix in (" asc", " desc"):
                    if part.lower().endswith(suffix):
                        part = part[: -len(suffix)].strip()
                report(part, key, _kwarg(node, key).lineno)

    return out


def scan_app(doctypes):
    """(sorted findings as readable strings, number of files parsed)."""
    findings, parsed = [], 0
    for dirpath, _dirs, names in os.walk(MODULE_ROOT):
        for n in sorted(names):
            if not n.endswith(".py"):
                continue
            path = os.path.join(dirpath, n)
            rel = os.path.relpath(path, APP_ROOT).replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read(), filename=path)
            except (SyntaxError, OSError) as exc:
                # Swallowing this made the sweep's coverage shrink in silence:
                # a file it cannot read contributes no findings and says
                # nothing, so a bad query inside one reads as a clean sweep.
                findings.append(
                    "%s:0  [-]  the sweep cannot read this file, so no query in "
                    "it is checked: %s" % (rel, exc.__class__.__name__))
                continue
            parsed += 1
            for lineno, doctype, where, field in scan_tree(tree, doctypes):
                findings.append(
                    "%s:%d  [%s]  %s names %r, which the DocType does not declare"
                    % (rel, lineno, doctype, where, field)
                )
    return sorted(set(findings)), parsed


# Each of these is a real finding with a decision behind it that is not a test's to make:
# either the field goes onto the DocType or the feature that reads it comes out. They are
# pinned so the sweep stays useful, and the schema each one rests on is pinned separately
# below, so fixing one turns this list red and says so.
KNOWN = [
    "erplite/accounts/doctype/account/account.py:82  [Xero Account]  filters key names "
    "'account', which the DocType does not declare",
    "erplite/setup/doctype/finance_book/finance_book.py:33  [Company]  fieldname argument "
    "names 'default_finance_book', which the DocType does not declare",
    "erplite/setup/doctype/terms_and_conditions/terms_and_conditions.py:19  [Company]  "
    "filters key names 'default_terms', which the DocType does not declare",
    "erplite/setup/doctype/terms_and_conditions/terms_and_conditions.py:33  [Company]  "
    "fieldname argument names 'default_terms', which the DocType does not declare",
]


def _doctypes():
    doctypes = _app_doctypes()
    doctypes.pop("__paths__", None)
    return doctypes


class TestNoQueryNamesAnUndeclaredField(unittest.TestCase):
    def test_no_query_names_a_field_its_doctype_does_not_declare(self):
        doctypes = _doctypes()
        findings, parsed = scan_app(doctypes)

        self.assertGreater(parsed, 50, "sweep parsed almost nothing; the walk is wrong")
        self.assertGreater(len(doctypes), 40, "sweep found almost no DocTypes")

        new = [f for f in findings if f not in KNOWN]
        self.assertEqual(
            [],
            new,
            "A query names a field its DocType does not declare. Depending on the call "
            "this reads a stale orphan column, returns None from db.exists, or raises:\n  "
            + "\n  ".join(new),
        )
        fixed = [f for f in KNOWN if f not in findings]
        self.assertEqual(
            [],
            fixed,
            "These were pinned as open findings and are no longer in the sweep. If you "
            "fixed them, delete them from KNOWN in this file and from the report:\n  "
            + "\n  ".join(fixed),
        )


class TestAFileTheSweepCannotReadIsReported(unittest.TestCase):
    """A sweep that cannot read a file used to say nothing about it, so its
    coverage could shrink to nothing without a single test going red."""

    def test_an_unparseable_file_in_the_app_is_a_finding(self):
        import tempfile

        with tempfile.TemporaryDirectory(dir=MODULE_ROOT) as tmp:
            path = os.path.join(tmp, "broken.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("def f(:\n")
            findings, _parsed = scan_app(_doctypes())

        said = [f for f in findings if "broken.py" in f]
        self.assertEqual(1, len(said), "an unreadable file was swept in silence")
        self.assertIn("cannot read this file", said[0])

    def test_a_readable_file_is_counted_as_parsed(self):
        _findings, parsed = scan_app(_doctypes())
        self.assertGreater(parsed, 50)


class TestTheSchemaBehindEachPinnedFinding(unittest.TestCase):
    """The pins. Each asserts the schema fact its finding rests on, so adding the field
    fails here and names the list to update rather than leaving a stale exception."""

    def test_xero_account_has_no_field_linking_it_to_an_account(self):
        fields = _doctypes()["Xero Account"]
        self.assertNotIn(
            "account", fields,
            "Xero Account now has an 'account' field, so account.py:82's delete guard may "
            "work. Re-check it and update KNOWN.",
        )
        self.assertIn("xero_account_id", fields)

    def test_company_has_no_default_terms_or_default_finance_book(self):
        fields = _doctypes()["Company"]
        for field in ("default_terms", "default_finance_book"):
            self.assertNotIn(
                field, fields,
                "Company now declares %r, so the reader of it may work. Update KNOWN." % field,
            )
        self.assertIn("default_currency", fields, "the Company defaults section is gone entirely")


class TestTheTwoFieldsFixedWithThisSweepStayFixed(unittest.TestCase):
    def test_timesheet_entry_has_no_date_field_so_nothing_may_query_one(self):
        self.assertNotIn(
            "date", _doctypes()["Timesheet Entry"],
            "Timesheet Entry declares 'date' again; the queries pointed at check_in_time "
            "could go back to it, but decide deliberately rather than by accident.",
        )
        self.assertIn("check_in_time", _doctypes()["Timesheet Entry"])

    def test_account_declares_currency_and_not_account_currency(self):
        fields = _doctypes()["Account"]
        self.assertIn("currency", fields)
        self.assertNotIn(
            "account_currency", fields,
            "Account declares 'account_currency' again. payment_entry.validate_accounts "
            "reads 'currency'; make them agree.",
        )


class TestTheSweepBites(unittest.TestCase):
    """Fault injection. Each shape is planted and has to be reported, and each thing the
    sweep must NOT judge is planted too. Without these the sweep above passing says
    nothing: a sweep that reports nothing because it reads nothing also passes."""

    DT = {"Activity": ("activity_name", "project", "status"), "Project": ("status",)}

    def bite(self, src):
        return [(w, f) for _l, _d, w, f in scan_tree(ast.parse(src), self.DT)]

    def test_fields_keyword(self):
        self.assertEqual(
            [("fields", "subject")],
            self.bite('frappe.get_all("Activity", fields=["activity_name", "subject"])'),
        )

    def test_fields_as_second_positional_of_get_all(self):
        self.assertEqual(
            [("fields", "subject")],
            self.bite('frappe.get_all("Activity", ["subject"])'),
        )

    def test_filters_dict_key(self):
        self.assertEqual(
            [("filters key", "assigned_to")],
            self.bite('frappe.get_all("Activity", filters={"assigned_to": u})'),
        )

    def test_filters_list_form_with_and_without_the_doctype(self):
        self.assertEqual(
            [("filters list", "assigned_to")],
            self.bite('frappe.get_all("Activity", filters=[["assigned_to", "=", u]])'),
        )
        self.assertEqual(
            [("filters list", "assigned_to")],
            self.bite('frappe.get_all("Activity", filters=[["Activity", "assigned_to", "=", u]])'),
        )

    def test_or_filters(self):
        self.assertEqual(
            [("or_filters key", "subject")],
            self.bite('frappe.get_all("Activity", or_filters={"subject": x})'),
        )

    def test_order_by_and_group_by(self):
        self.assertEqual(
            [("order_by", "subject")],
            self.bite('frappe.get_all("Activity", order_by="subject desc")'),
        )
        self.assertEqual(
            [("group_by", "subject")],
            self.bite('frappe.get_all("Activity", group_by="subject")'),
        )

    def test_order_by_accepts_a_standard_column_and_a_declared_one(self):
        self.assertEqual([], self.bite('frappe.get_all("Activity", order_by="modified desc")'))
        self.assertEqual([], self.bite('frappe.get_all("Activity", order_by="status, creation asc")'))

    def test_get_value_third_positional(self):
        """The form that hid two of the four findings until the sweep was extended."""
        self.assertEqual(
            [("fieldname argument", "subject")],
            self.bite('frappe.get_value("Activity", name, "subject")'),
        )
        self.assertEqual(
            [("fieldname argument", "subject")],
            self.bite('frappe.db.get_value("Activity", name, ["status", "subject"], as_dict=1)'),
        )

    def test_set_value_dict_and_scalar_forms(self):
        self.assertEqual(
            [("fieldname argument", "subject")],
            self.bite('frappe.db.set_value("Activity", name, "subject", v)'),
        )
        self.assertEqual(
            [("fieldname argument", "subject")],
            self.bite('frappe.db.set_value("Activity", name, {"subject": v})'),
        )

    def test_get_single_value_second_positional(self):
        self.assertEqual(
            [("fieldname argument", "subject")],
            self.bite('frappe.db.get_single_value("Activity", "subject")'),
        )

    def test_exists_and_count_filters(self):
        self.assertEqual(
            [("filters key", "subject")],
            self.bite('frappe.db.exists("Activity", {"subject": v})'),
        )
        self.assertEqual(
            [("filters key", "subject")],
            self.bite('frappe.db.count("Activity", {"subject": v})'),
        )

    def test_pluck(self):
        self.assertEqual(
            [("pluck", "subject")],
            self.bite('frappe.get_all("Activity", pluck="subject")'),
        )

    def test_the_doctype_may_be_named_by_keyword(self):
        """A call written entirely in keywords has no positional arguments, and
        skipping those made every field in it invisible."""
        self.assertEqual(
            [("fields", "subject")],
            self.bite('frappe.get_all(doctype="Activity", fields=["subject"])'))

    def test_the_fieldname_may_be_given_by_keyword(self):
        """erplite/xero/api.py:50 already writes get_value this way."""
        self.assertEqual(
            [("fieldname argument", "subject")],
            self.bite('frappe.db.get_value("Activity", filters={}, fieldname="subject")'))
        self.assertEqual(
            [("fieldname argument", "subject")],
            self.bite('frappe.db.get_single_value("Activity", fieldname="subject")'))

    def test_filters_built_by_concatenation_are_not_judged(self):
        """A documented limit, and the same rule as a non-literal DocType: this
        sweep reads literals. Recorded so it is a decision, not a surprise."""
        self.assertEqual(
            [], self.bite('frappe.get_all("Activity", filters=[["subject", "=", 1]] + extra)'))

    def test_a_declared_field_is_never_reported(self):
        self.assertEqual(
            [],
            self.bite('frappe.get_all("Activity", fields=["activity_name", "project"], '
                      'filters={"status": "Open"})'),
        )

    def test_sql_and_aliases_are_not_judged(self):
        for expression in ("count(name) as n", "sum(duration) as total", "`tabActivity`.`name`",
                           "tabActivity.name", "*", "name as id", "distinct status"):
            self.assertEqual(
                [], self.bite('frappe.get_all("Activity", fields=[%r])' % expression),
                "%r is SQL or an alias; the sweep must skip it, not guess" % expression,
            )

    def test_an_unknown_doctype_is_not_judged(self):
        self.assertEqual([], self.bite('frappe.get_all("User", fields=["anything_at_all"])'))

    def test_a_non_literal_doctype_is_not_judged(self):
        self.assertEqual([], self.bite('frappe.get_all(dt, fields=["subject"])'))

    def test_the_second_positional_of_get_value_is_filters_not_fields(self):
        """get_value("DT", ["a", "b"], f) passes NAMES, not fields. Reading it as fields
        is how a sweep invents findings."""
        self.assertEqual(
            [], self.bite('frappe.db.get_value("Activity", ["one", "two"], "status")'),
        )

    def test_a_dict_second_positional_of_get_value_is_filters(self):
        self.assertEqual(
            [("filters key", "subject")],
            self.bite('frappe.db.get_value("Activity", {"subject": v}, "status")'),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
