# -*- coding: utf-8 -*-
"""Whole-app guards on the field references inside the DocType JSONs themselves.

The other sweeps in this folder cover code that names a field the DocType does not declare:
queries (silent stale read), `self.<x>` in a controller on a new document (AttributeError), and
`frm.set_value('<x>')` in a form script (modal error dialog). The DocType JSON is a fourth
surface, and it has its own symptom again -- the same cause, a fourth distinct failure:

  * `fetch_from: "<link_field>.<source_field>"` whose source field no longer exists ends in
    `BaseDocument.set_fetch_from_value`, which for a Data/Text/Small Text target does
    `get_default_df(src) or frappe.get_meta(doctype).get_field(src)` and, finding neither,
    calls `frappe.throw(... title="Wrong Fetch From value")`. That runs inside
    `_validate_links` during save, so **every save of a document whose link field is set fails**.
    Note the fieldtype gate: on other fieldtypes the stale value is assigned quietly instead.

That is what broke `scheduler.api.create_schedule_row_entry`: Schedule Row's `activity_name`
fetched `activity.subject`, and `subject` was removed from Activity in the Task -> Activity
rename, so the live scheduler could not create a schedule row with an activity attached at all.
Fixed by pointing it at `activity.activity_name`.

Both halves of the orphan-column question give the same answer here, which is why this needed no
access to the live site: if `tabActivity.subject` still exists as an orphan column the fetch
retrieves a stale value and then throws on the meta lookup; if it does not, `frappe.db.get_value`
throws `Unknown column` first. It fails either way, and the correct field is the same.

The passes below are mechanical and exact -- a DocType JSON's references resolve against that
same JSON, so there is no name matching and no scope guessing, unlike a grep.

KNOWN BLIND SPOT, stated so it is a place to look rather than a place to stop: a reference whose
target DocType this app does not define is skipped, because a Frappe core DocType's field list is
not in this repo. There are 18 such references (User, Country, Communication, Contact, Letter
Head, ToDo). The four `fetch_from` ones among them were checked by hand against frappe/frappe
version-15 on 5 Oct 2026 and all resolve: Contact.email_id, Contact.phone, Communication.sender,
Communication.subject. Re-check them when the Frappe version moves.
"""

import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODULE_ROOT = os.path.join(APP_ROOT, "erplite")

# Fieldtypes that carry no column on the record, so they are not fields for our purposes.
LAYOUT_FIELDTYPES = {
    "Section Break", "Column Break", "Tab Break", "HTML", "Heading", "Button", "Image", "Fold",
}

# Frappe's standard columns, present on every DocType and absent from its JSON.
STANDARD_FIELDS = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "_assign", "_comments", "_user_tags", "_liked_by", "parent", "parentfield", "parenttype",
}

LINK_FIELDTYPES = {"Link", "Table", "Table MultiSelect"}
CHILD_FIELDTYPES = {"Table", "Table MultiSelect"}


def _load_doctypes():
    """{DocType name: (relative path, parsed JSON)} for every DocType this app defines."""
    out = {}
    for dirpath, _dirs, names in os.walk(MODULE_ROOT):
        if os.sep + "public" + os.sep in dirpath or "node_modules" in dirpath:
            continue
        for n in sorted(names):
            if not n.endswith(".json"):
                continue
            p = os.path.join(dirpath, n)
            try:
                with open(p, encoding="utf-8") as fh:
                    d = json.load(fh)
            except (ValueError, OSError):
                continue
            if isinstance(d, dict) and d.get("doctype") == "DocType" and d.get("name"):
                out[d["name"]] = (os.path.relpath(p, APP_ROOT), d)
    return out


DOCTYPES = _load_doctypes()


def _real_fields(d):
    return {
        f["fieldname"]: f
        for f in d.get("fields", [])
        if f.get("fieldname") and f.get("fieldtype") not in LAYOUT_FIELDTYPES
    }


FIELDS = {name: _real_fields(d) for name, (_p, d) in DOCTYPES.items()}


def _has_field(doctype, fieldname):
    return fieldname in FIELDS.get(doctype, {}) or fieldname in STANDARD_FIELDS


class TestDoctypeJsonIsSane(unittest.TestCase):
    """The app's own DocType JSONs, swept as a whole. Each test reports every offender at once."""

    def setUp(self):
        self.assertGreater(
            len(DOCTYPES), 40, "loaded almost no DocTypes; the walk is wrong, not the app"
        )

    def test_every_fetch_from_resolves(self):
        """`fetch_from` must name a Link field on this DocType and a real field on its target."""
        bad = []
        for dt, (path, d) in sorted(DOCTYPES.items()):
            fields = FIELDS[dt]
            for f in d.get("fields", []):
                expr = f.get("fetch_from")
                if not expr:
                    continue
                where = "{}  {}.{}".format(path, dt, f.get("fieldname"))
                if "." not in expr:
                    bad.append("{}: fetch_from {!r} has no dot".format(where, expr))
                    continue
                link_field, source = expr.split(".", 1)
                target = fields.get(link_field)
                if target is None:
                    bad.append(
                        "{}: fetch_from {!r} -- {!r} is not a field of {}".format(
                            where, expr, link_field, dt
                        )
                    )
                elif target.get("fieldtype") != "Link":
                    bad.append(
                        "{}: fetch_from {!r} -- {!r} is a {} field, not a Link".format(
                            where, expr, link_field, target.get("fieldtype")
                        )
                    )
                else:
                    options = (target.get("options") or "").strip()
                    if options not in DOCTYPES:
                        continue  # the documented blind spot; see the module docstring
                    if not _has_field(options, source):
                        bad.append(
                            "{}: fetch_from {!r} -- {} has no field {!r}".format(
                                where, expr, options, source
                            )
                        )
        self.assertEqual(
            [],
            sorted(set(bad)),
            "These fetch_from references do not resolve. On a Data/Text/Small Text field this "
            "makes frappe.throw('Wrong Fetch From value') fire on every save where the link is "
            "set:\n  " + "\n  ".join(sorted(set(bad))),
        )

    def test_link_and_table_options_name_a_real_doctype(self):
        """A Table field must point at a DocType this app defines and marks `istable`."""
        bad = []
        for dt, (path, d) in sorted(DOCTYPES.items()):
            for f in d.get("fields", []):
                ft = f.get("fieldtype")
                options = (f.get("options") or "").strip()
                if ft not in LINK_FIELDTYPES or not options:
                    continue
                if options not in DOCTYPES:
                    continue  # the documented blind spot
                if ft in CHILD_FIELDTYPES and not DOCTYPES[options][1].get("istable"):
                    bad.append(
                        "{}  {}.{}: {} field points at {!r}, which is not istable".format(
                            path, dt, f.get("fieldname"), ft, options
                        )
                    )
        self.assertEqual([], sorted(set(bad)), "\n  ".join(sorted(set(bad))))

    def test_sort_title_and_search_fields_exist(self):
        """`sort_field` reaches the list-view ORDER BY, so a stale name there orders by nothing."""
        bad = []
        for dt, (path, d) in sorted(DOCTYPES.items()):
            for key in ("sort_field", "search_fields"):
                for part in (d.get(key) or "").split(","):
                    part = part.strip()
                    if not part:
                        continue
                    nm = part.split()[0]  # sort_field may carry "fieldname desc"
                    if not _has_field(dt, nm):
                        bad.append(
                            "{}  {}: {} names {!r}, which is not a field of {}".format(
                                path, dt, key, nm, dt
                            )
                        )
            title = (d.get("title_field") or "").strip()
            if title and not _has_field(dt, title):
                bad.append(
                    "{}  {}: title_field names {!r}, which is not a field of {}".format(
                        path, dt, title, dt
                    )
                )
        self.assertEqual([], sorted(set(bad)), "\n  ".join(sorted(set(bad))))

    def test_field_order_matches_the_declared_fields(self):
        """A field missing from `field_order` does not render; an extra name is a stale leftover."""
        bad = []
        for dt, (path, d) in sorted(DOCTYPES.items()):
            order = d.get("field_order")
            if order is None:
                continue
            declared = {
                f["fieldname"] for f in d.get("fields", []) if f.get("fieldname")
            }
            for nm in order:
                if nm not in declared:
                    bad.append(
                        "{}  {}: field_order lists {!r}, which is not in fields[]".format(
                            path, dt, nm
                        )
                    )
            for nm in sorted(declared - set(order)):
                bad.append(
                    "{}  {}: field {!r} is declared but missing from field_order, so it does "
                    "not render".format(path, dt, nm)
                )
        self.assertEqual([], sorted(set(bad)), "\n  ".join(sorted(set(bad))))

    def test_depends_on_expressions_name_real_fields(self):
        """`depends_on` on a removed field is always falsy, so the section silently never shows."""
        import re

        bad = []
        for dt, (path, d) in sorted(DOCTYPES.items()):
            for f in d.get("fields", []):
                for key in ("depends_on", "mandatory_depends_on", "read_only_depends_on"):
                    expr = f.get(key)
                    if not expr:
                        continue
                    names = set(re.findall(r"\bdoc\.([A-Za-z_][A-Za-z0-9_]*)", expr))
                    if not expr.startswith("eval:") and not names:
                        names = {expr.strip()}
                    for nm in sorted(names):
                        if not _has_field(dt, nm):
                            bad.append(
                                "{}  {}.{}: {} refers to {!r}, which is not a field of {}".format(
                                    path, dt, f.get("fieldname"), key, nm, dt
                                )
                            )
        self.assertEqual([], sorted(set(bad)), "\n  ".join(sorted(set(bad))))


if __name__ == "__main__":
    unittest.main(verbosity=2)
