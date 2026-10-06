# -*- coding: utf-8 -*-
"""A read has to fit the *kind* of DocType it names, not just a real name.

`test_endpoint_wiring.py` judges whether a DocType literal names something that
exists. That is the name. This file judges the shape: given that the name is
real, is this the right way to read *that kind* of DocType? Three kinds behave
differently enough that the same call is correct on one and fatal on another:

* an **ordinary** DocType has a table of its own, one row per document;
* a **Single** (`issingle`) has no table at all -- its fields live as rows in
  `tabSingles`;
* a **child table** (`istable`) has a table, but every row in it belongs to some
  parent document, and a row means nothing without knowing whose it is.

## Why this is not guessable from the method names

This file exists because I got it backwards in writing, in a comment on main
(`test_endpoint_wiring.py`, corrected in the same commit that added this file).
I said `frappe.get_all("System Settings")` "would return nothing rather than
raise". It is the opposite, and the two halves are not symmetric the way the
names suggest:

* **`get_all` / `get_list` on a Single raise.** Both go to `DatabaseQuery`
  (`frappe/__init__.py:2020,2043`), whose `prepare_select_args` asks for the
  table's columns (`frappe/model/db_query.py:422`); that calls
  `frappe.db.get_table_columns`, which does `raise self.TableMissingError`
  when the table is not there (`frappe/database/database.py:1344`).
  `DatabaseQuery.get_table_columns` swallows it only when `ignore_ddl` is set
  (`db_query.py:924-931`), and these calls do not set it. A Single has no table,
  so this is a hard failure, the same class as the `Resource Role` reads -- not
  a silent empty list. `DatabaseQuery` has no notion of a Single anywhere: the
  only two mentions of `issingle` in `db_query.py` are a docstring example of
  SQL injection screening (line 664) and an unrelated parent check (line 1397).
  `frappe.db.get_all` and `frappe.db.get_list` are the same two functions --
  `database.py:761-766` forwards both to `frappe.get_all` / `frappe.get_list`.

* **`get_value` does not mind.** `frappe.db.get_value` with no filters goes
  straight to `get_values_from_single` (`database.py:656`), and even with
  filters it catches the missing table and falls back to the singles table --
  the comment there is literally "table not found, look in singles"
  (`database.py:648`). `frappe.get_value` is an alias for it
  (`frappe/__init__.py:2068`), and its own docstring documents the case:
  filters are "`None` if Single DocType".

* **`get_doc` on a Single ignores the name.** `Document.load_from_db` branches
  on `self.meta.issingle` and calls `frappe.db.get_singles_dict(self.doctype)`,
  never touching `self.name` (`frappe/model/document.py:158-159`). So
  `get_doc("Xero Settings")` is right -- frappe's own overload says so, "Retrieve
  Single DocType from DB" (`__init__.py:1283`) -- and `get_doc(dt, anything)` is
  too. `get_single(dt)` *is* `get_doc(dt, dt)` (`__init__.py:1349`).

So the safe-shape set is not what you would guess: `db.get_value` is fine on a
Single and `get_all` is fatal.

## The child-table half

An unparented child read does not fail. It returns rows belonging to every
parent document in the system, and nothing in the query layer narrows them:

* `frappe.get_all` does not check permissions at all -- its own docstring,
  `__init__.py:2044`;
* for an `istable` DocType, `build_match_conditions` cannot reach its
  `No permission to read` throw: the whole branch is guarded by
  `not self.doctype_meta.istable` (`db_query.py:1327-1337`);
* the row-level parent condition that would restrict child rows to parents the
  caller may see is applied only `if self.doctype_meta.istable and
  self.parent_doctype` (`db_query.py:1377`), and a plain `get_all("X Item")`
  passes no `parent_doctype`.

So restricting a child read to a parent is the caller's job, and the filter is
the only thing doing it. The app's three child reads all do it today: the one
`get_all` filters on `parent` (`supplier_quote.py:94`) and the two `Has Role`
reads filter on `parent` (`www/todo/index.py:33,525`). That is what this file
pins -- the fourth one is the one to worry about.

## What this file does NOT judge

* **Shapes nobody has verified.** `count`, `exists`, `set_value`, `delete`,
  `new_doc`, `delete_doc`, `rename_doc`, `has_permission` and the rest are not
  classified against a Single, because no call in this app writes one and I have
  not read frappe's source for each of them. An unclassified shape on a Single
  fails here, loudly, asking for the classification -- it does not pass quietly.
  Guessing is exactly the failure this file was written after.
* **Reads through an alias.** Same blind spot as `test_endpoint_wiring.py`, and
  its `test_no_module_aliases_frappe` is what keeps the blind spot empty.
* **Non-literal DocType names.** A name in a variable is unreadable statically.
* **Whether the parent filter is *correct*.** `filters={"parent": x}` is counted
  as parented whatever `x` is. The claim is that the read is scoped to a parent,
  not that it is scoped to the right one.

Runs without a bench.
"""

import ast
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ERPLITE = os.path.join(APP_ROOT, "erplite")
sys.path.insert(0, HERE)

from test_endpoint_wiring import (  # noqa: E402
    DOCTYPE_FIRST_ARG,
    FRAPPE_DOCTYPES,
    _doctype_sites,
    _literal,
    _receiver_and_method,
    _walk,
)

# frappe's own DocTypes, by kind. Their JSONs are not in this tree, so unlike
# the app's they cannot be read -- they are named here with where they were read
# from, on 6 Oct 2026, in frappe/frappe version-15:
#
#   System Settings  core/doctype/system_settings/system_settings.json  issingle=1
#   Has Role         core/doctype/has_role/has_role.json                istable=1
#
# test_frappe_kinds_are_known_frappe_doctypes below keeps these two consistent
# with test_endpoint_wiring's list rather than letting them drift apart.
FRAPPE_SINGLES = {"System Settings"}
FRAPPE_CHILD_TABLES = {"Has Role"}

# The two list queries, on both receivers. `frappe.db.get_all` and
# `frappe.db.get_list` are not separate implementations: database.py:761-766
# forwards each to the frappe-level one, so all four reach DatabaseQuery.
LIST_QUERIES = {
    ("frappe", "get_all"), ("frappe", "get_list"),
    ("frappe.db", "get_all"), ("frappe.db", "get_list"),
}

# Shapes verified to work on a Single, each with the source line in the module
# docstring above. `get_doc` and `get_cached_doc` are here whatever name they are
# given, because load_from_db ignores the name for a Single.
SINGLE_SAFE = {
    ("frappe", "get_single"),
    ("frappe", "get_single_value"),
    ("frappe", "get_doc"),
    ("frappe", "get_cached_doc"),
    ("frappe", "get_cached_value"),
    ("frappe", "get_value"),
    ("frappe", "get_meta"),
    ("frappe.db", "get_single_value"),
    ("frappe.db", "get_value"),
    ("frappe.db", "get_cached_value"),
}

# Keys in a `filters` dict that scope a child read to its parent, and the keyword
# argument that makes DatabaseQuery apply the parent's row-level permission.
PARENT_KEYS = {"parent", "parenttype"}
PARENT_KWARG = "parent_doctype"

# Measured, not rounded. 19 sites name a Single (17 Xero Settings, 2 System
# Settings) and 3 name a child table (1 Supplier Quote Item, 2 Has Role). An
# exact floor and ceiling: a count below this means a read was dropped and the
# rule now covers less than it says, a count above means a new one arrived and
# nobody looked at its shape.
EXPECTED_SINGLE_SITES = 19
EXPECTED_CHILD_SITES = 3


def _app_doctype_kinds():
    """({Single names}, {child-table names}, [unreadable JSONs]) for this app.

    Read off each DocType's own JSON rather than listed here, so the kinds follow
    the DocType as it changes -- the same reason fake_frappe reads field lists
    out of the JSONs. The third value is returned rather than swallowed for the
    reason test_undeclared_attributes gives for its own: a JSON this cannot parse
    silently shrinks what the rules below are measured against, and a missing
    kind is indistinguishable from an ordinary DocType, so it has to be asserted
    rather than skipped with a `continue`.
    """
    singles, child_tables, unreadable = set(), set(), []
    for path in _walk(".json"):
        if os.path.basename(path)[:-5] != os.path.basename(os.path.dirname(path)):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (ValueError, OSError) as problem:
            unreadable.append("%s: %s" % (os.path.relpath(path, APP_ROOT), problem))
            continue
        if data.get("doctype") != "DocType":
            continue
        name = data.get("name")
        if not name:
            continue
        if data.get("issingle"):
            singles.add(name)
        if data.get("istable"):
            child_tables.add(name)
    return singles, child_tables, unreadable


def _read_sites():
    """Every DocType-naming call, with its AST node kept.

    `test_endpoint_wiring._doctype_sites` finds the same calls but returns tuples
    of text, and the shape rules need the node: whether a child read is scoped to
    a parent is a fact about its `filters` argument.
    `test_the_two_walkers_see_the_same_calls` below pins the two to each other so
    a fix to one receiver list cannot leave this file reading a smaller app.
    """
    sites = []
    for path in _walk(".py"):
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        rel = os.path.relpath(path, APP_ROOT)
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            receiver, method = _receiver_and_method(node)
            if method not in DOCTYPE_FIRST_ARG.get(receiver, ()):
                continue
            argument = node.args[0] if node.args else None
            if argument is None:
                for keyword in node.keywords:
                    if keyword.arg == "doctype":
                        argument = keyword.value
            doctype = _literal(argument) if argument is not None else None
            if doctype is None:
                continue
            sites.append((rel, node.lineno, receiver, method, doctype, node))
    return sites


def _where(site):
    rel, line, receiver, method, doctype, _node = site
    return "%s:%d  %s.%s(%r)" % (rel, line, receiver, method, doctype)


def _is_parented(node):
    """True if this call scopes itself to a parent document.

    Either `parent_doctype=...`, which is what makes DatabaseQuery apply the
    parent's row-level permission (db_query.py:1377), or a `filters` dict with a
    `parent` or `parenttype` key, which is what the app's three child reads use.
    A filters value that is not a readable dict literal returns False: this
    declines to guess, and a child read whose scope cannot be read is exactly the
    one worth a human looking at.
    """
    for keyword in node.keywords:
        if keyword.arg == PARENT_KWARG:
            return True
    filters = None
    for keyword in node.keywords:
        if keyword.arg == "filters":
            filters = keyword.value
    if filters is None and len(node.args) > 1:
        filters = node.args[1]
    if not isinstance(filters, ast.Dict):
        return False
    return any(_literal(key) in PARENT_KEYS for key in filters.keys)


class TestKindsAreReadOffTheDoctypes(unittest.TestCase):
    """The classification the rules rest on, before the rules themselves."""

    def test_every_doctype_json_parses(self):
        _singles, _child, unreadable = _app_doctype_kinds()
        self.assertEqual(
            unreadable, [],
            "a DocType JSON could not be read, so its kind is unknown and every "
            "read of it below is judged as if it were an ordinary DocType:\n  "
            + "\n  ".join(unreadable))

    def test_the_app_still_declares_the_kinds_these_rules_are_about(self):
        """A rule with nothing to judge is a rule that cannot go red.

        If the app's last Single or last child table went, these sweeps would
        pass by finding nothing -- so the premise is asserted rather than assumed.
        The counts are not pinned here; which DocTypes exist is the owner's
        business and the floors below are about reads, not declarations.
        """
        singles, child_tables, _unreadable = _app_doctype_kinds()
        self.assertIn("Xero Settings", singles,
                      "the app's only Single is gone, so the Single rule now "
                      "judges only frappe's System Settings")
        self.assertTrue(
            child_tables,
            "the app declares no child tables, so the child-table rule has "
            "nothing to judge")

    def test_frappe_kinds_are_known_frappe_doctypes(self):
        """These two are named, not read, so they must not drift from the list.

        test_endpoint_wiring.FRAPPE_DOCTYPES is where frappe's DocTypes are
        recorded for this app. Naming a kind here for something not on that list
        means one of the two files was edited without the other.
        """
        for name in sorted(FRAPPE_SINGLES | FRAPPE_CHILD_TABLES):
            self.assertIn(
                name, FRAPPE_DOCTYPES,
                "%r is given a kind here but is not in "
                "test_endpoint_wiring.FRAPPE_DOCTYPES; add it there or drop it "
                "here" % name)

    def test_no_doctype_is_both_kinds(self):
        singles, child_tables, _unreadable = _app_doctype_kinds()
        both = (singles | FRAPPE_SINGLES) & (child_tables | FRAPPE_CHILD_TABLES)
        self.assertEqual(
            both, set(),
            "%s is declared both issingle and istable, so which rule applies to "
            "a read of it is undecidable" % sorted(both))

    def test_the_two_walkers_see_the_same_calls(self):
        """This file's walker and test_endpoint_wiring's must not diverge.

        Both read the same receiver/method table, so a call added to
        DOCTYPE_FIRST_ARG should appear in both. Keeping them pinned means the
        shape rules cannot quietly end up judging a smaller app than the name
        rule does.
        """
        mine = {(rel, line, "%s.%s" % (receiver, method), doctype)
                for rel, line, receiver, method, doctype, _node in _read_sites()}
        theirs = set(_doctype_sites())
        self.assertEqual(
            mine, theirs,
            "the two walkers disagree about which calls name a DocType:\n"
            "  only here: %s\n  only there: %s"
            % (sorted(mine - theirs), sorted(theirs - mine)))


class TestSingleReadShapes(unittest.TestCase):
    """A Single has no table of its own, so a row query is fatal, not empty."""

    def _single_sites(self):
        singles, _child, _unreadable = _app_doctype_kinds()
        singles = singles | FRAPPE_SINGLES
        return [site for site in _read_sites() if site[4] in singles]

    def test_no_list_query_names_a_single(self):
        """The rule this file was written for.

        `get_all`/`get_list` on a Single raises TableMissingError before it
        reaches the database -- database.py:1344 by way of db_query.py:422. The
        call site reads like a list of nothing; it is a 500.
        """
        offenders = [_where(site) for site in self._single_sites()
                     if (site[2], site[3]) in LIST_QUERIES]
        self.assertEqual(
            offenders, [],
            "a Single is being read with a list query, which raises "
            "frappe.db.TableMissingError rather than returning nothing. Read it "
            "with frappe.get_single, frappe.get_single_value or "
            "frappe.db.get_value:\n  " + "\n  ".join(offenders))

    def test_every_single_read_uses_a_verified_shape(self):
        """Unclassified shapes fail here rather than passing on trust.

        The list of safe shapes is short and each entry has a source line behind
        it in the module docstring. A shape that is not on it is not thereby
        wrong -- it is unexamined, which is how the claim this file corrects got
        written in the first place. So the test asks for the reading rather than
        assuming either answer.
        """
        unclassified = [
            "%s  (%s.%s is not in SINGLE_SAFE)" % (_where(site), site[2], site[3])
            for site in self._single_sites()
            if (site[2], site[3]) not in SINGLE_SAFE
            and (site[2], site[3]) not in LIST_QUERIES]
        self.assertEqual(
            unclassified, [],
            "a Single is read with a shape nothing here has verified against "
            "frappe's source. Read what that call does on an issingle DocType "
            "(frappe/database/database.py and frappe/model/document.py), then "
            "either add it to SINGLE_SAFE with the line you read, or fix the "
            "call:\n  " + "\n  ".join(unclassified))

    def test_the_single_read_count_is_the_measured_one(self):
        sites = self._single_sites()
        self.assertEqual(
            len(sites), EXPECTED_SINGLE_SITES,
            "%d sites name a Single, expected %d. More: a new one arrived -- "
            "check its shape and raise the number. Fewer: one was dropped, so "
            "say whether the read was meant to go and lower the number in the "
            "same commit.\n  %s"
            % (len(sites), EXPECTED_SINGLE_SITES,
               "\n  ".join(sorted(_where(site) for site in sites))))


class TestChildTableReadShapes(unittest.TestCase):
    """A child row belongs to a parent, and only the filter says which."""

    def _child_sites(self):
        _singles, child_tables, _unreadable = _app_doctype_kinds()
        child_tables = child_tables | FRAPPE_CHILD_TABLES
        return [site for site in _read_sites() if site[4] in child_tables]

    def test_every_child_read_is_scoped_to_a_parent(self):
        """Nothing in the query layer does this for you; see the docstring.

        get_all skips permissions outright (__init__.py:2044), the
        No-permission-to-read branch is guarded by `not istable`
        (db_query.py:1327) and the parent row-level condition needs a
        `parent_doctype` nobody passes (db_query.py:1377). An unparented read
        returns every parent's rows.
        """
        offenders = [_where(site) for site in self._child_sites()
                     if not _is_parented(site[5])]
        self.assertEqual(
            offenders, [],
            "a child table is read without being scoped to a parent, so it "
            "returns rows belonging to every parent document and nothing in the "
            "query layer narrows them. Add a `parent` filter (as "
            "supplier_quote.py:94 and www/todo/index.py do) or pass "
            "parent_doctype:\n  " + "\n  ".join(offenders))

    def test_the_child_read_count_is_the_measured_one(self):
        sites = self._child_sites()
        self.assertEqual(
            len(sites), EXPECTED_CHILD_SITES,
            "%d sites name a child table, expected %d. Same bargain as the "
            "Single floor: move the number in the commit that moves the "
            "reads.\n  %s"
            % (len(sites), EXPECTED_CHILD_SITES,
               "\n  ".join(sorted(_where(site) for site in sites))))

    def test_the_parent_scope_check_can_say_no(self):
        """A guard that cannot fail is not a guard.

        `_is_parented` is the whole child-table rule, so it is exercised on
        arguments written here rather than only on the app's three reads, which
        all pass. If it answered True for everything the sweep above would be
        green and empty.
        """
        def parsed(call):
            return ast.parse(call).body[0].value

        self.assertTrue(_is_parented(parsed(
            'frappe.get_all("Sales Invoice Item", filters={"parent": x})')))
        self.assertTrue(_is_parented(parsed(
            'frappe.get_all("Sales Invoice Item", filters={"parenttype": "X"})')))
        self.assertTrue(_is_parented(parsed(
            'frappe.get_all("Sales Invoice Item", parent_doctype="Sales Invoice")')))
        self.assertTrue(_is_parented(parsed(
            'frappe.get_all("Sales Invoice Item", {"parent": x})')),
            "filters as a positional argument must count too")
        self.assertFalse(_is_parented(parsed(
            'frappe.get_all("Sales Invoice Item")')))
        self.assertFalse(_is_parented(parsed(
            'frappe.get_all("Sales Invoice Item", filters={"item_name": n})')))
        self.assertFalse(_is_parented(parsed(
            'frappe.get_all("Sales Invoice Item", filters=built_elsewhere)')),
            "a filters value this cannot read must not be assumed parented")


if __name__ == "__main__":
    unittest.main()
