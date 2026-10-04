# -*- coding: utf-8 -*-
"""Whole-app guard: this app must not reuse the NAME of a Frappe core DocType.

A DocType name is global. There is one `tabDocType` row and one table per name, so
when two installed apps ship a DocType with the same name the loser is erased
rather than merged, and nothing warns anyone:

  * `sync_all` walks `frappe.get_installed_apps()` in order (model/sync.py:42-44) and
    frappe is always first, so the other app syncs last.
  * `import_doc` does `if frappe.db.exists(...): delete_old_doc(doc, ...)` and then
    `doc.insert()` (modules/import_file.py:230-239). There is no collision check: the
    last app to sync simply replaces the DocType definition.
  * The table is NOT rebuilt to match. Frappe's schema sync adds columns and never
    drops them, so the fields the replaced DocType declared survive as orphan
    columns -- the same mechanism as the Activity `subject` / `assigned_to` bug, and
    see the stand-in's README for why that makes the failure invisible.
  * `import_controller` reads `module` from the DocType ROW (model/base_document.py:
    82-86), so the winning app's controller class also takes over, and the replaced
    app's `validate` / `on_update` hooks stop running.

So a collision is three silent changes at once: fields vanish from the DocType while
their data stays in the table, mandatory flags from the new definition start applying
to rows that predate them, and a controller is swapped out.

THE ONE KNOWN COLLISION: `Currency`. This app ships `erplite/setup/doctype/currency`
(module Setup) and Frappe ships `frappe/geo/doctype/currency` (module Geo). erplite's
wins. What that costs, all of it mechanical from the two JSONs:

  * Five fields leave the DocType: `fraction`, `fraction_units`,
    `smallest_currency_fraction_value`, `number_format`, `symbol_on_right`. Frappe
    core reads four of them by name -- `utils/data.py:1195` (`rounded`), `:1273`
    (`money_in_words`), `:1314` (`fmt_money`) and `boot.py:476-478`. Those reads keep
    working only because the columns orphan instead of being dropped.
  * `currency_code` is `reqd` with no default, and it is a new column, so it is NULL
    on every currency row that already existed. Saving any of them therefore aborts
    on mandatory validation. Nothing in this app saves a Currency document, so what
    this bites is the Currency form and any future code path.
  * Frappe's `Currency.validate` exists only to call `frappe.clear_cache()`, because
    `fmt_money` and `money_in_words` read currency values with `cache=True`. erplite's
    controller replaces it and does not clear the cache, so an edited currency can go
    on being formatted with its old values.
  * The two fields erplite added Currency for, `is_base_currency` and `exchange_rate`,
    and both helpers on its controller (`get_base_currency`, `get_exchange_rate`), are
    referenced by nothing else in the app -- while Currency itself is the link target
    of seven fields across Sales Invoice, Purchase Invoice, Payment Entry, Supplier
    Quote, Account and Company.

Fault injection, 7 Oct 2026: adding the five fields back also breaks
test_doctype_metadata.test_field_order_matches_the_declared_fields, because a field added
to `fields` has to be added to `field_order` as well. Worth knowing before starting that fix.

This is left as it is on purpose: resolving it is a schema decision on a live
accounting system (rename erplite's DocType, or make it a superset of Frappe's, or
drop it and use Custom Fields), and that is the owner's call, not a test's. The tests
below pin the collision exactly, so a NEW collision fails, and so does resolving this
one -- in which case read the failure message and update the expectation.

The core DocType names come from `frappe_core_doctypes.json`, vendored because the
offline suite has no bench to ask (the same blind spot test_doctype_metadata.py
records). It was dumped from the version-15 branch at 15.121.3; the live site runs
15.52.0, and Currency has lived in frappe/geo since well before either, so the
collision holds for both. Regenerate with tools/dump_core_doctypes.py.
"""

import glob
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODULE_ROOT = os.path.join(APP_ROOT, "erplite")
CORE = os.path.join(HERE, "frappe_core_doctypes.json")

# The collision that exists today, and the five core fields it drops from the DocType.
KNOWN_COLLISIONS = {"Currency"}
CURRENCY_FIELDS_LOST = {
    "fraction", "fraction_units", "smallest_currency_fraction_value",
    "number_format", "symbol_on_right",
}


def load_core():
    with open(CORE, encoding="utf-8") as fh:
        return json.load(fh)


def app_doctypes():
    """name -> (relative path, parsed JSON) for every DocType this app defines."""
    found = {}
    for path in glob.glob(os.path.join(MODULE_ROOT, "**", "doctype", "*", "*.json"), recursive=True):
        # A DocType's own JSON is <folder>/<folder>.json; skip child JSONs beside it.
        if os.path.basename(path)[:-5] != os.path.basename(os.path.dirname(path)):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except ValueError:
            continue
        if doc.get("doctype") != "DocType" or not doc.get("name"):
            continue
        found[doc["name"]] = (os.path.relpath(path, APP_ROOT), doc)
    return found


def fieldnames(doc):
    return {f["fieldname"] for f in doc.get("fields", []) if f.get("fieldname")}


class TestCoreDoctypeCollisions(unittest.TestCase):
    def setUp(self):
        self.core = load_core()
        self.app = app_doctypes()
        self.assertTrue(self.app, "found no DocType JSONs under %s" % MODULE_ROOT)
        self.assertTrue(self.core["doctype_names"], "vendored core DocType list is empty")

    def test_no_new_core_doctype_collisions(self):
        """Reusing a core DocType name replaces it. Only the documented one may exist."""
        core_names = set(self.core["doctype_names"])
        collisions = {n for n in self.app if n in core_names}
        unexpected = collisions - KNOWN_COLLISIONS
        self.assertFalse(
            unexpected,
            "these DocTypes reuse the name of a Frappe core DocType, which replaces it "
            "on the next migrate and silently drops its fields from the DocType while "
            "leaving their columns in the table: %s. Rename them, or make the definition "
            "a superset of the core one. See this module's docstring."
            % ", ".join("%s (%s)" % (n, self.app[n][0]) for n in sorted(unexpected)),
        )
        resolved = KNOWN_COLLISIONS - collisions
        self.assertFalse(
            resolved,
            "good news, but update this test: %s no longer collides with a core DocType. "
            "Remove it from KNOWN_COLLISIONS (and drop CURRENCY_FIELDS_LOST with it if "
            "that was the Currency fix)." % ", ".join(sorted(resolved)),
        )

    def test_currency_collision_still_drops_the_core_money_fields(self):
        """Pin exactly which core fields erplite's Currency removes from the DocType."""
        self.assertIn("Currency", self.app, "this app no longer defines Currency; see the other test")
        rel, ours = self.app["Currency"]
        theirs = self.core.get("currency")
        self.assertTrue(theirs, "vendored core Currency definition is missing")

        lost = {f["fieldname"] for f in theirs["fields"]} - fieldnames(ours)
        self.assertEqual(
            lost, CURRENCY_FIELDS_LOST,
            "which core Currency fields %s drops has changed (was %s, now %s). If fields "
            "were added back, frappe's fmt_money / money_in_words / rounded / boot payload "
            "can read them from the DocType again instead of relying on orphaned columns -- "
            "update CURRENCY_FIELDS_LOST. If fields were newly removed, check what in frappe "
            "core reads them first."
            % (rel, sorted(CURRENCY_FIELDS_LOST), sorted(lost)),
        )

    def test_currency_mandatory_fields_are_new_columns(self):
        """A reqd field the core definition never had cannot be satisfied by existing rows."""
        _rel, ours = self.app["Currency"]
        theirs_fields = {f["fieldname"] for f in self.core["currency"]["fields"]}
        offenders = sorted(
            f["fieldname"] for f in ours.get("fields", [])
            if f.get("reqd") and not f.get("default") and f.get("fieldname") not in theirs_fields
        )
        self.assertEqual(
            offenders, ["currency_code"],
            "which mandatory-and-new Currency fields exist has changed (now %s). Every one of "
            "these is NULL on every currency row that predates this app, so saving those rows "
            "aborts on mandatory validation. Giving the field a default, or clearing reqd, "
            "removes that; either way update this expectation." % offenders,
        )
