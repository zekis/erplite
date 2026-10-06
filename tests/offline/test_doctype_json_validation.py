# -*- coding: utf-8 -*-
"""Whole-app guard: the checks frappe makes on a DocType, which deploying never runs.

Every other sweep in this folder asks whether the app's *code* is consistent with its
DocTypes. This one asks a question one level down: **is the DocType itself valid?** Frappe
has twenty-three such checks already written, in `validate_fields` and `validate_permissions`
(`frappe/core/doctype/doctype/doctype.py`). They are good checks. They do not run on this
app's DocTypes, ever, and the reason is worth reading once because it is not an oversight
and it will not be fixed upstream.

**Nothing validates a shipped DocType JSON on deploy.** Three separate mechanisms, each
verified against frappe 15.52.0 -- the version on the live site, not the version-15 branch.
The third was found later than the other two, by `TheStatesBlockIsUsable` below, and it is
the one that stops the obvious generalisation: **not every skipped check is skipped by
`ignore_validate`, and a check reached outside `validate` is not therefore reached.**

  1. `bench migrate` imports each `<doctype>.json` through
     `frappe/model/sync.py:111` -> `import_file_by_path(...)`, which leaves `data_import`
     at its default of `False`, so `frappe/modules/import_file.py:235` sets
     `doc.flags.ignore_validate = True` before `doc.insert()`. `Document.run_before_save_methods`
     (`frappe/model/document.py:1099`) then does `if self.flags.ignore_validate: return`
     **before** `self.run_method("validate")`. So `DocType.validate` (`doctype.py:180`) never
     runs, and neither does the `validate_fields(self)` on `doctype.py:203`. That alone
     accounts for nine checks.
  2. The other fourteen are skipped a second time, deliberately: `validate_fields` guards
     them with `if not frappe.flags.in_migrate:` (`doctype.py:1646` and `:1659`). Frappe's
     authors decided migrate-time is the wrong moment to refuse a deploy over a field
     property -- which is a defensible call, and it is why this file exists. If the framework
     has decided not to check at deploy time, the repository is the only place left.
  3. A check can also be skipped from the inside, with `ignore_validate` never consulted.
     `_validate()` is called on `document.py:296`, *after* `run_before_save_methods()` has
     returned early, so it does run on a migrate, and it does reach child rows --
     `document.py:601` is `d._validate_selects()` for every child. What stops it is a guard
     within the method: `base_document.py:878` is `if frappe.flags.in_import: return`, and
     `import_file.py:212` sets `frappe.flags.in_import = True` just before the `doc.insert()`
     on `:239`. `TheStatesBlockIsUsable.test_every_state_colour_is_one_frappe_renders` is the
     check standing where that leaves a hole.

The consequence is that these checks only ever fire when a **human saves the DocType in the
Desk UI in developer mode**. That is how most of these JSONs were first written, which is why
the app is clean today (0 findings across 47 DocTypes, 595 fields and 99 permission rows when
this was written). The exposure is not the Desk; it is the hand-edit. Every one of these
files is ordinary JSON in a git repository, and a rename, a merge resolution or a
search-and-replace that touches one is subject to no check of any kind between the editor and
production.

Three symptoms, which is the part worth knowing, because the checks look interchangeable and
are not:

  * **Fails the deploy.** A fieldname longer than 64 characters or carrying a special
    character is rejected by `validate_column_name` / `validate_column_length`
    (`frappe/database/schema.py:303`, `:315`) when the *column* is created, not when the
    DocType is validated -- so this one does stop `bench migrate`, just later and with a
    database error rather than the readable message `check_illegal_characters` would have
    given.
  * **Fails at runtime, for everyone, on a page that used to work.** A `search_fields` or
    `title_field` naming a field that no longer exists reaches the link-search query as a
    column name. A `Dynamic Link` whose `options` does not point at a `Link(DocType)` field
    cannot resolve its target doctype at all.
  * **Silently does nothing.** A `Select` field whose `default` is not in its `options`
    saves a value the field cannot hold -- the same class
    `test_status_literals.py` sweeps on the client side, arriving here through metadata
    instead of JavaScript. A field that is `hidden` and `reqd` with no default makes every
    save of that DocType fail with a mandatory error pointing at a field the user cannot
    see. `in_list_view` on a Section Break is simply ignored.

A note on fidelity, since a reimplementation that drifts from the original is worse than no
check: every constant below is copied from frappe 15.52.0 with the file and line it came
from, and every check names the frappe function it stands in for. Where a check needs the
database (`check_unique_and_text`'s scan for existing non-unique values) or another app's
field list, it is not reimplemented, and `test_blind_spots_are_named` pins what is left out
so the gap is a place to look rather than a place to stop.

WHAT THIS DOES NOT COVER, deliberately: `scrub_options_in_select` and
`validate_data_field_type` mutate or `msgprint` rather than throw, so they are not failures;
`check_width`, `remove_rights_for_single` and `validate_permission_for_all_role` depend on
session state or are advisory. `validate_fetch_from`'s field-resolution half is already
`test_doctype_metadata.py`'s subject -- only the self-reference half frappe checks is here.
"""

import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODULE_ROOT = os.path.join(APP_ROOT, "erplite")

# ---------------------------------------------------------------------------
# Constants, copied from frappe 15.52.0. Each carries where it came from so the
# next person can check it moved rather than trusting this file.
# ---------------------------------------------------------------------------

# frappe/model/__init__.py:53
NO_VALUE_FIELDS = {
    "Section Break", "Column Break", "Tab Break", "Attachment Gallery", "HTML",
    "Table", "Table MultiSelect", "Button", "Image", "Fold", "Heading",
}
# frappe/model/__init__.py:101
TABLE_FIELDS = {"Table", "Table MultiSelect"}
# frappe/model/__init__.py:84
DEFAULT_FIELDS = {
    "doctype", "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
}
# frappe/model/__init__.py, child_table_fields
CHILD_TABLE_FIELDS = {"parent", "parentfield", "parenttype"}
# frappe/model/base_document.py:114, reached as Document._reserved_keywords
RESERVED_KEYWORDS = {
    "doctype", "meta", "flags", "parent_doc", "_table_fields", "_valid_columns",
    "_doc_before_save", "_table_fieldnames", "_reserved_keywords",
    "permitted_fieldnames", "dont_update_if_missing",
}
# frappe/database/schema.py:7 and frappe/database/mariadb/database.py MAX_COLUMN_LENGTH
SPECIAL_CHAR_PATTERN = re.compile(r"[\W]", flags=re.UNICODE)
MAX_COLUMN_LENGTH = 64
# frappe/core/doctype/doctype/doctype.py:42
DEPENDS_ON_PATTERN = re.compile(r'[\w\.:_]+\s*={1}\s*[\w\.@\'"]+')
# frappe/permissions.py:30-32. Read, not guessed: SYSTEM_USER_ROLE is "Desk User",
# which is not a name anyone would arrive at from the constant.
GUEST_ROLE = "Guest"
ALL_USER_ROLE = "All"
SYSTEM_USER_ROLE = "Desk User"
# frappe/core/doctype/doctype_state/doctype_state.json, the `color` Select's options.
# Ten, and the list is worth reading rather than recalling: there is no Black, and there
# is a Light Blue. Both halves of that caught the author of this check.
DOCTYPE_STATE_COLORS = {
    "Blue", "Cyan", "Gray", "Green", "Light Blue", "Orange", "Pink", "Purple", "Red",
    "Yellow",
}
# frappe/public/scss/common/indicator.scss:50, $indicator-colors. Twelve, generated into
# `.indicator.<colour>` and `.indicator-pill.<colour>` by the @each loop on :51. This is
# the second, independent reason the set above is not advisory: a colour outside it
# reaches the DOM as a class with no rule behind it. `grey` and `darkgrey` are here and
# not in the Select, so the Select is the narrower authority and the one to check.
INDICATOR_CSS_COLORS = {
    "green", "cyan", "blue", "orange", "yellow", "gray", "grey", "red", "pink",
    "darkgrey", "purple", "light-blue",
}
# doctype.py:1515, the four keys check_illegal_depends_on_conditions reads
DEPENDS_ON_KEYS = (
    "depends_on", "collapsible_depends_on", "mandatory_depends_on", "read_only_depends_on",
)

# The DocTypes a Link or Table field in this app points at that this app does not
# declare. Pinned as an exact set, not skipped as "probably frappe's": that is what
# turns this from an exemption into a check. `Contacts` for `Contact` would change
# this set and fail, which is the typo the sweep is for -- frappe's full DocType list
# is not in this repository, so a name is otherwise unjudgeable.
LINK_TARGETS_OUTSIDE_THIS_APP = {
    "Communication", "Contact", "Country", "Letter Head", "ToDo", "User",
}

# `check_precision` (doctype.py:1356) allows 1-6 and this app ships a 9. Pinned as an exact
# exception rather than dropped from the sweep, with what was measured, because it is a
# decision and not a mistake:
#
#   * `Currency.exchange_rate` is a Float with `"precision": "9"`.
#   * It works today, and the reason is worth stating so nobody "fixes" it on the strength of
#     the framework's limit alone. `get_field_precision` (frappe/model/meta.py:800) is
#     `if df.precision: precision = cint(df.precision)` -- no clamp, no fallback. And a Float
#     column is `decimal(21,9)` (frappe/database/mariadb/database.py:170), so nine decimals is
#     exactly the width the column already has. Nothing truncates and nothing rounds it away.
#   * What it does cost: the Desk UI cannot save this DocType any more. Opening Currency in
#     developer mode and pressing Update throws "Precision should be between 1 and 6" on a
#     field the person did not touch.
#
# Nine decimal places on an exchange rate is a reasonable thing to want, so whether to keep it
# is the owner's call, not this file's. Raised for that decision; until it is made, the sweep
# records the one it knows about and would still catch a second.
KNOWN_PRECISION_EXCEPTIONS = {("Currency", "exchange_rate"): "9"}

# An exact floor for the states sweep, measured. Only two DocTypes coloured their own
# statuses when this was written -- Activity (5 rows) and Project (4) -- so both checks
# below would pass on an empty sweep, which is the one way they could fail silently.
EXPECTED_STATE_ROWS = 9
EXPECTED_DOCTYPES_WITH_STATES = {"Activity", "Project"}

# What is not reimplemented here, and why. Pinned so the list cannot grow in silence.
NOT_REIMPLEMENTED = {
    "check_unique_and_text (existing-rows half)": "needs the live table's contents",
    "check_table_multiselect_option (outside this app)": "needs another app's field list",
    "scrub_options_in_select": "mutates, never throws",
    "validate_data_field_type": "msgprint only, never throws",
    "check_width": "advisory, Currency width",
    "remove_rights_for_single": "mutates, never throws",
    "validate_permission_for_all_role": "depends on frappe.session.user",
}


def _load_doctypes():
    """Every DocType this app ships, by name -> (json, path)."""
    out = {}
    for dirpath, _dirnames, filenames in os.walk(MODULE_ROOT):
        if "__pycache__" in dirpath:
            continue
        for filename in filenames:
            if not filename.endswith(".json"):
                continue
            path = os.path.join(dirpath, filename)
            if os.sep + "doctype" + os.sep not in path:
                continue
            with open(path, encoding="utf-8") as handle:
                try:
                    doc = json.load(handle)
                except ValueError:
                    continue
            if isinstance(doc, dict) and doc.get("doctype") == "DocType" and doc.get("name"):
                out[doc["name"]] = (doc, path)
    return out


DOCTYPES = _load_doctypes()

# An exact floor, measured. A DocType that leaves the walker's reach says so here
# rather than quietly reducing what every test below covers.
EXPECTED_DOCTYPE_COUNT = 47


def _rel(path):
    return os.path.relpath(path, APP_ROOT)


def _fields(doc):
    return doc.get("fields") or []


def _fieldnames(doc):
    return [f.get("fieldname") for f in _fields(doc) if f.get("fieldname")]


def _not_allowed_in_list_view(doc):
    """doctype.py:1730 get_fields_not_allowed_in_list_view."""
    out = set(NO_VALUE_FIELDS) | {"Attach Image"}
    if int(doc.get("istable") or 0):
        out -= {"Button", "HTML"}
    return out


class DocTypeInventory(unittest.TestCase):
    def test_every_doctype_is_reached(self):
        self.assertEqual(
            len(DOCTYPES), EXPECTED_DOCTYPE_COUNT,
            "found %d DocType JSONs, expected %d. If a DocType was added or removed, update "
            "EXPECTED_DOCTYPE_COUNT; if the walker stopped reaching one, every check in this "
            "file just got quietly narrower." % (len(DOCTYPES), EXPECTED_DOCTYPE_COUNT))

    def test_blind_spots_are_named(self):
        """The gaps are a place to look, not a place to stop."""
        self.assertTrue(NOT_REIMPLEMENTED)
        for name, why in NOT_REIMPLEMENTED.items():
            self.assertTrue(why, "%s is listed as not reimplemented with no reason" % name)


class FieldnameRules(unittest.TestCase):
    """The checks that run on every DocType save and are skipped by `ignore_validate`."""

    def test_no_illegal_characters_in_a_fieldname(self):
        """doctype.py:1224 check_illegal_characters -> schema.py:303."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for field in _fields(doc):
                fieldname = field.get("fieldname") or ""
                if not fieldname:
                    continue
                found = SPECIAL_CHAR_PATTERN.findall(fieldname)
                if found:
                    bad.append("%s: %s.%s has %s" % (_rel(path), name, fieldname, sorted(set(found))))
        self.assertEqual(bad, [], "a fieldname with a special character becomes an invalid "
                                  "column name, so it fails when the column is created:\n" + "\n".join(bad))

    def test_no_fieldname_is_a_reserved_keyword(self):
        """doctype.py:1227 check_invalid_fieldnames -> base_document.py:114."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for field in _fields(doc):
                if field.get("fieldname") in RESERVED_KEYWORDS:
                    bad.append("%s: %s.%s" % (_rel(path), name, field.get("fieldname")))
        self.assertEqual(bad, [], "a fieldname that shadows one of Document's own attributes "
                                  "overwrites it on every instance:\n" + "\n".join(bad))

    def test_no_fieldname_is_too_long(self):
        """doctype.py:1249 check_fieldname_length -> schema.py:315."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for field in _fields(doc):
                fieldname = field.get("fieldname") or ""
                if len(fieldname) > MAX_COLUMN_LENGTH:
                    bad.append("%s: %s.%s is %d characters" % (_rel(path), name, fieldname, len(fieldname)))
        self.assertEqual(bad, [], "a fieldname over %d characters cannot be a column:\n%s"
                                  % (MAX_COLUMN_LENGTH, "\n".join(bad)))

    def test_no_duplicate_fieldname_within_a_doctype(self):
        """doctype.py:1237 check_unique_fieldname."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            seen = {}
            for index, field in enumerate(_fields(doc), 1):
                fieldname = field.get("fieldname")
                if not fieldname:
                    continue
                if fieldname in seen:
                    bad.append("%s: %s.%s in rows %d and %d"
                               % (_rel(path), name, fieldname, seen[fieldname], index))
                else:
                    seen[fieldname] = index
        self.assertEqual(bad, [], "two fields sharing a fieldname means one of them silently "
                                  "wins, and which one is an ordering accident:\n" + "\n".join(bad))

    def test_no_field_is_hidden_and_mandatory_without_a_default(self):
        """doctype.py:1293 check_hidden_and_mandatory.

        Skipped twice over: frappe's own check excludes `frappe.flags.in_migrate`, and
        `ignore_validate` means it would not have run anyway. The symptom is the worst kind
        of unfixable-by-the-user error -- every save fails with a mandatory-field message
        naming a field that is not on the form.
        """
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for field in _fields(doc):
                if field.get("hidden") and field.get("reqd") and not field.get("default"):
                    bad.append("%s: %s.%s" % (_rel(path), name, field.get("fieldname")))
        self.assertEqual(bad, [], "hidden and mandatory with no default makes every save of "
                                  "the DocType fail:\n" + "\n".join(bad))

    def test_no_unique_or_indexed_field_of_the_wrong_type(self):
        """doctype.py:1364 check_unique_and_text, the half that needs no database."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            if int(doc.get("is_virtual") or 0):
                continue
            issingle = int(doc.get("issingle") or 0)
            for field in _fields(doc):
                fieldtype = field.get("fieldtype")
                if field.get("unique") and not issingle:
                    if fieldtype not in ("Data", "Link", "Read Only", "Int"):
                        bad.append("%s: %s.%s is unique but %s"
                                   % (_rel(path), name, field.get("fieldname"), fieldtype))
                if field.get("search_index") and fieldtype in (
                        "Text", "Long Text", "Small Text", "Code", "Text Editor"):
                    bad.append("%s: %s.%s has search_index but %s"
                               % (_rel(path), name, field.get("fieldname"), fieldtype))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_no_fetch_from_is_self_referential(self):
        """doctype.py:1556 validate_fetch_from. The resolution half is test_doctype_metadata's."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for field in _fields(doc):
                fetch_from = (field.get("fetch_from") or "").strip()
                if "." not in fetch_from:
                    continue
                if fetch_from.split(".", 1)[0] == field.get("fieldname"):
                    bad.append("%s: %s.%s fetches from %s"
                               % (_rel(path), name, field.get("fieldname"), fetch_from))
        self.assertEqual(bad, [], "\n".join(bad))


class FieldPropertyRules(unittest.TestCase):
    """The checks frappe gates behind `if not frappe.flags.in_migrate` (doctype.py:1646)."""

    def test_link_and_table_fields_name_a_doctype(self):
        """doctype.py:1259 check_link_table_options."""
        bad = []
        outside = set()
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for field in _fields(doc):
                fieldtype = field.get("fieldtype")
                if fieldtype != "Link" and fieldtype not in TABLE_FIELDS:
                    continue
                options = field.get("options")
                if not options:
                    bad.append("%s: %s.%s (%s) has no options"
                               % (_rel(path), name, field.get("fieldname"), fieldtype))
                    continue
                if options in ("[Select]", name) or options in DOCTYPES:
                    continue
                outside.add(options)
        self.assertEqual(bad, [], "a Link or Table field with no options cannot resolve "
                                  "anything:\n" + "\n".join(bad))
        self.assertEqual(
            outside, LINK_TARGETS_OUTSIDE_THIS_APP,
            "the set of DocTypes this app links to but does not declare changed. Frappe's own "
            "DocType list is not in this repository, so these names are judged by being "
            "exactly the expected set and no other way. A new name here is either a real new "
            "dependency to add to LINK_TARGETS_OUTSIDE_THIS_APP, or the typo this check is "
            "for.\n  expected: %s\n  found:    %s"
            % (sorted(LINK_TARGETS_OUTSIDE_THIS_APP), sorted(outside)))

    def test_no_valueless_field_is_mandatory(self):
        """doctype.py:1252 check_illegal_mandatory."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for field in _fields(doc):
                fieldtype = field.get("fieldtype")
                if fieldtype in NO_VALUE_FIELDS and fieldtype not in TABLE_FIELDS and field.get("reqd"):
                    bad.append("%s: %s.%s is a mandatory %s"
                               % (_rel(path), name, field.get("fieldname"), fieldtype))
        self.assertEqual(bad, [], "a layout element carries no value, so marking it mandatory "
                                  "either does nothing or blocks every save:\n" + "\n".join(bad))

    def test_dynamic_links_point_at_a_doctype_field(self):
        """doctype.py:1319 check_dynamic_link_options."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            fields = _fields(doc)
            for field in fields:
                if field.get("fieldtype") != "Dynamic Link":
                    continue
                pointer = [f for f in fields if f.get("fieldname") == field.get("options")]
                ok = (pointer
                      and pointer[0].get("fieldtype") in ("Link", "Select")
                      and not (pointer[0].get("fieldtype") == "Link"
                               and pointer[0].get("options") != "DocType"))
                if not ok:
                    bad.append("%s: %s.%s options=%r"
                               % (_rel(path), name, field.get("fieldname"), field.get("options")))
        self.assertEqual(bad, [], "a Dynamic Link whose options does not name a Link(DocType) "
                                  "or Select field on the same DocType cannot resolve its "
                                  "target:\n" + "\n".join(bad))

    def test_list_view_and_global_search_flags_are_on_real_values(self):
        """doctype.py:1306 check_in_list_view and :1313 check_in_global_search."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            nalv = _not_allowed_in_list_view(doc)
            for field in _fields(doc):
                fieldtype = field.get("fieldtype")
                if field.get("in_list_view") and fieldtype in nalv:
                    bad.append("%s: %s.%s has in_list_view but %s"
                               % (_rel(path), name, field.get("fieldname"), fieldtype))
                if field.get("in_global_search") and fieldtype in NO_VALUE_FIELDS:
                    bad.append("%s: %s.%s has in_global_search but %s"
                               % (_rel(path), name, field.get("fieldname"), fieldtype))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_defaults_are_values_the_field_can_hold(self):
        """doctype.py:1333 check_illegal_default.

        The Select half is the same rule as test_status_literals.py, reached through
        metadata rather than JavaScript: a default outside `options` puts a value in the
        field that nothing comparing against the options will ever match.
        """
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for field in _fields(doc):
                fieldtype, default = field.get("fieldtype"), field.get("default")
                if fieldtype == "Check" and default not in (None, "", 0, 1, "0", "1"):
                    bad.append("%s: %s.%s is a Check with default %r"
                               % (_rel(path), name, field.get("fieldname"), default))
                if fieldtype == "Select" and default:
                    options = field.get("options") or ""
                    if not options:
                        bad.append("%s: %s.%s is a Select with default %r and no options"
                                   % (_rel(path), name, field.get("fieldname"), default))
                    elif default not in options.split("\n"):
                        bad.append("%s: %s.%s default %r is not in its options %r"
                                   % (_rel(path), name, field.get("fieldname"), default,
                                      options.split("\n")))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_table_fields_name_a_child_table(self):
        """doctype.py:1589 check_child_table_option and :1528 check_table_multiselect_option."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            is_virtual = int(doc.get("is_virtual") or 0)
            for field in _fields(doc):
                if field.get("fieldtype") not in TABLE_FIELDS:
                    continue
                options = field.get("options")
                if options not in DOCTYPES:
                    continue  # outside this app: pinned by test_link_and_table_fields_name_a_doctype
                child = DOCTYPES[options][0]
                if not int(child.get("istable") or 0):
                    bad.append("%s: %s.%s options=%r is not a child table"
                               % (_rel(path), name, field.get("fieldname"), options))
                if int(child.get("is_virtual") or 0) != is_virtual:
                    bad.append("%s: %s.%s options=%r disagrees on is_virtual"
                               % (_rel(path), name, field.get("fieldname"), options))
                if field.get("fieldtype") == "Table MultiSelect":
                    if not [f for f in _fields(child) if f.get("fieldtype") == "Link"]:
                        bad.append("%s: %s.%s options=%r has no Link field"
                                   % (_rel(path), name, field.get("fieldname"), options))
        self.assertEqual(bad, [], "\n".join(bad))

    def test_depends_on_conditions_are_not_assignments(self):
        """doctype.py:1515 check_illegal_depends_on_conditions."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for field in _fields(doc):
                for key in DEPENDS_ON_KEYS:
                    condition = field.get(key)
                    if condition and "=" in condition and DEPENDS_ON_PATTERN.match(condition):
                        bad.append("%s: %s.%s %s=%r"
                                   % (_rel(path), name, field.get("fieldname"), key, condition))
        self.assertEqual(bad, [], "a single `=` in a depends_on is an assignment, not a "
                                  "comparison:\n" + "\n".join(bad))

    def test_numeric_field_properties_are_in_range(self):
        """doctype.py:1356 check_precision, :1615 check_max_height, :1619 check_no_of_ratings."""
        bad = []
        seen_exceptions = set()
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for field in _fields(doc):
                fieldname, fieldtype = field.get("fieldname"), field.get("fieldtype")
                precision = field.get("precision")
                if fieldtype in ("Currency", "Float", "Percent") and precision not in (None, ""):
                    if not 1 <= int(precision) <= 6:
                        if KNOWN_PRECISION_EXCEPTIONS.get((name, fieldname)) == str(precision):
                            seen_exceptions.add((name, fieldname))
                        else:
                            bad.append("%s: %s.%s precision %r (frappe allows 1-6)"
                                       % (_rel(path), name, fieldname, precision))
                max_height = field.get("max_height")
                if max_height and str(max_height)[-2:] not in ("px", "em"):
                    bad.append("%s: %s.%s max_height %r" % (_rel(path), name, fieldname, max_height))
                if fieldtype == "Rating" and field.get("options"):
                    count = int(field.get("options"))
                    if count < 3 or count > 10:
                        bad.append("%s: %s.%s has %d ratings" % (_rel(path), name, fieldname, count))
        self.assertEqual(bad, [], "\n".join(bad))
        self.assertEqual(
            seen_exceptions, set(KNOWN_PRECISION_EXCEPTIONS),
            "KNOWN_PRECISION_EXCEPTIONS lists something the sweep no longer finds. If the "
            "precision was corrected, delete the entry -- a stale exception is a hole.\n"
            "  listed: %s\n  found:  %s"
            % (sorted(KNOWN_PRECISION_EXCEPTIONS), sorted(seen_exceptions)))


class DocumentLevelRules(unittest.TestCase):
    """doctype.py:1659, the eight checks made once per DocType rather than per field."""

    def test_meta_fields_name_a_field_that_exists(self):
        """check_title_field (:1431), check_timeline_field (:1491), check_sort_field (:1502),
        check_image_field (:1461), check_is_published_field (:1472),
        check_website_search_field (:1479), check_search_fields (:1414).

        These seven are the ones `test_doctype_metadata.py` does not reach: it sweeps the
        references inside a *field*, and these sit on the DocType itself.
        """
        bad = []
        sortable = DEFAULT_FIELDS | CHILD_TABLE_FIELDS
        for name, (doc, path) in sorted(DOCTYPES.items()):
            fieldnames = _fieldnames(doc)
            by_name = {f.get("fieldname"): f for f in _fields(doc)}
            for key in ("title_field", "is_published_field", "website_search_field"):
                value = doc.get(key)
                if value and value not in fieldnames:
                    bad.append("%s: %s %s=%r names no field" % (_rel(path), name, key, value))
            timeline = doc.get("timeline_field")
            if timeline:
                if timeline not in fieldnames:
                    bad.append("%s: %s timeline_field=%r names no field" % (_rel(path), name, timeline))
                elif by_name[timeline].get("fieldtype") not in ("Link", "Dynamic Link"):
                    bad.append("%s: %s timeline_field=%r is a %s, not a Link"
                               % (_rel(path), name, timeline, by_name[timeline].get("fieldtype")))
            image = doc.get("image_field")
            if image:
                if image not in fieldnames:
                    bad.append("%s: %s image_field=%r names no field" % (_rel(path), name, image))
                elif by_name[image].get("fieldtype") != "Attach Image":
                    bad.append("%s: %s image_field=%r is a %s, not Attach Image"
                               % (_rel(path), name, image, by_name[image].get("fieldtype")))
            sort_field = doc.get("sort_field")
            if sort_field:
                parts = ([d.split(maxsplit=1)[0] for d in sort_field.split(",")]
                         if "," in sort_field else [sort_field])
                for part in parts:
                    if part not in fieldnames and part not in sortable:
                        bad.append("%s: %s sort_field=%r names no field" % (_rel(path), name, part))
            search_fields = doc.get("search_fields")
            if search_fields:
                for part in [p.strip() for p in search_fields.split(",") if p.strip()]:
                    if part not in fieldnames:
                        bad.append("%s: %s search_fields names %r, which is no field"
                                   % (_rel(path), name, part))
                    elif by_name[part].get("fieldtype") in NO_VALUE_FIELDS:
                        bad.append("%s: %s search_fields names %r, a %s, which holds no value"
                                   % (_rel(path), name, part, by_name[part].get("fieldtype")))
        self.assertEqual(bad, [], "a DocType-level field reference that no longer resolves "
                                  "reaches a query as a column name:\n" + "\n".join(bad))

    def test_at_most_one_fold_and_not_at_the_end(self):
        """doctype.py:1400 check_fold."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            fields = _fields(doc)
            folds = [i for i, f in enumerate(fields) if f.get("fieldtype") == "Fold"]
            if len(folds) > 1:
                bad.append("%s: %s has %d Folds" % (_rel(path), name, len(folds)))
            for index in folds:
                if index == len(fields) - 1:
                    bad.append("%s: %s ends with a Fold" % (_rel(path), name))
                elif fields[index + 1].get("fieldtype") != "Section Break":
                    bad.append("%s: %s has a Fold not followed by a Section Break" % (_rel(path), name))
        self.assertEqual(bad, [], "\n".join(bad))


class PermissionRules(unittest.TestCase):
    """doctype.py:1701 validate_permissions, which `ignore_validate` skips with the rest.

    These matter more than the field checks, because a permission row that frappe would have
    rejected does not fail loudly -- it grants or withholds access, quietly, in production.
    """

    def test_every_permission_row_grants_something(self):
        """doctype.py:1715 check_atleast_one_set."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for index, row in enumerate(doc.get("permissions") or [], 1):
                if not any(int(row.get(k) or 0)
                           for k in ("select", "read", "write", "submit", "cancel", "create")):
                    bad.append("%s: %s row %d (%s) grants nothing"
                               % (_rel(path), name, index, row.get("role")))
        self.assertEqual(bad, [], "a row with no basic permission is dead weight that reads "
                                  "as access:\n" + "\n".join(bad))

    def test_no_duplicate_permission_row(self):
        """doctype.py:1719 check_double: one rule per role, level and if_owner."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            rows = doc.get("permissions") or []
            seen = {}
            for index, row in enumerate(rows, 1):
                key = (row.get("role"), int(row.get("permlevel") or 0), int(row.get("if_owner") or 0))
                if key in seen:
                    bad.append("%s: %s rows %d and %d are both %s at level %d"
                               % (_rel(path), name, seen[key], index, key[0], key[1]))
                else:
                    seen[key] = index
        self.assertEqual(bad, [], "two rules for the same role and level means one is "
                                  "ignored, and which one is undefined:\n" + "\n".join(bad))

    def test_higher_permlevels_have_a_level_zero(self):
        """doctype.py:1736 check_level_zero_is_set."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            rows = doc.get("permissions") or []
            for index, row in enumerate(rows, 1):
                if int(row.get("permlevel") or 0) <= 0:
                    continue
                if row.get("role") in (ALL_USER_ROLE, SYSTEM_USER_ROLE):
                    continue
                if not any(other is not row
                           and other.get("role") == row.get("role")
                           and int(other.get("permlevel") or 0) == 0
                           for other in rows):
                    bad.append("%s: %s row %d gives %s level %s with no level 0"
                               % (_rel(path), name, index, row.get("role"), row.get("permlevel")))
        self.assertEqual(bad, [], "a permlevel above 0 without a level 0 row for the same role "
                                  "grants nothing at all:\n" + "\n".join(bad))

    def test_permission_flags_do_not_contradict_each_other(self):
        """doctype.py:1755 check_permission_dependency, :1776 check_if_submittable,
        :1782 check_if_importable."""
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            submittable = int(doc.get("is_submittable") or 0)
            importable = int(doc.get("allow_import") or 0)
            for index, row in enumerate(doc.get("permissions") or [], 1):
                where = "%s: %s row %d (%s)" % (_rel(path), name, index, row.get("role"))
                if row.get("cancel") and not row.get("submit"):
                    bad.append("%s has cancel without submit" % where)
                if (row.get("submit") or row.get("cancel") or row.get("amend")) and not row.get("write"):
                    bad.append("%s has submit/cancel/amend without write" % where)
                if row.get("import") and not row.get("create"):
                    bad.append("%s has import without create" % where)
                if row.get("submit") and not submittable:
                    bad.append("%s has submit but the DocType is not submittable" % where)
                if row.get("amend") and not submittable:
                    bad.append("%s has amend but the DocType is not submittable" % where)
                if row.get("import") and not importable:
                    bad.append("%s has import but the DocType is not importable" % where)
        self.assertEqual(bad, [], "\n".join(bad))


class TheStatesBlockIsUsable(unittest.TestCase):
    """The `states` block, which frappe does not check at all and the Desk half-checks.

    `states` is how a DocType colours its own status, and `frappe.get_indicator` reads it
    **before** any `get_indicator` a list view defines: `indicator.js:82` is
    `doc.status && meta.states && meta.states.find((d) => d.title === doc.status)`, and
    `:88` is the custom hook. So this block is the authority on a status's colour in every
    view -- list, form heading, report, link preview -- not just the list.

    Nothing in `doctype.py` validates it. `states` appears there exactly once, as the type
    annotation `states: DF.Table[DocTypeState]` on `:169`. There is no `check_states`, which
    is why the title half below stands in for no frappe function and is justified on its
    consequence instead.

    The colour half does have a frappe check, and it is skipped on deploy by a **third**
    mechanism, separate from the two this file's docstring describes. `color` on DocType
    State is a Select, and child rows are validated: `document.py:601` runs
    `d._validate_selects()` for every child. That is not gated by `ignore_validate` --
    `_validate()` is called on `document.py:296`, *after* `run_before_save_methods()` has
    already returned early. The guard is inside the method instead:
    `base_document.py:878` is `if frappe.flags.in_import: return`, and
    `import_file.py:212` sets `frappe.flags.in_import = True` immediately before
    `doc.insert()` on `:239`. So the check runs, reaches the states rows, and returns
    without looking at them.
    """

    def test_the_sweep_still_reaches_the_states_blocks(self):
        """Both checks below iterate `states`, so an app with none passes them for free."""
        rows = [s for _n, (d, _p) in DOCTYPES.items() for s in (d.get("states") or [])]
        named = {n for n, (d, _p) in DOCTYPES.items() if d.get("states")}
        self.assertEqual(
            len(rows), EXPECTED_STATE_ROWS,
            "found %d state rows, expected %d. If a DocType gained or lost a states block, "
            "update EXPECTED_STATE_ROWS; if it dropped to 0, the two checks below are "
            "passing without reading anything." % (len(rows), EXPECTED_STATE_ROWS))
        self.assertEqual(named, EXPECTED_DOCTYPES_WITH_STATES)

    def test_every_state_names_a_status_the_field_can_hold(self):
        """No frappe equivalent: `states` is unvalidated (`doctype.py:169` is the only
        mention). The consequence is the silent-no-op class, and it is exact rather than
        likely. `indicator.js:82` finds a state by `d.title === doc.status`, so a title that
        is not one of the status field's options can never match any document. The state is
        inert, the search falls through to `guess_colour(doc.status)` on `:100`, and the
        status gets a colour guessed from its words -- which is the condition the block was
        added to replace. Nothing raises, nothing logs, and the list looks deliberate.
        """
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            states = doc.get("states") or []
            if not states:
                continue
            status = next((f for f in _fields(doc) if f.get("fieldname") == "status"), None)
            if status is None:
                bad.append("%s: %s has %d states but no status field for them to match"
                           % (_rel(path), name, len(states)))
                continue
            if status.get("fieldtype") != "Select":
                bad.append("%s: %s has states but status is a %s, not a Select"
                           % (_rel(path), name, status.get("fieldtype")))
                continue
            options = (status.get("options") or "").split("\n")
            for state in states:
                title = state.get("title")
                if title not in options:
                    bad.append("%s: %s state %r is not one of status's options %r"
                               % (_rel(path), name, title, options))
        self.assertEqual(bad, [], "a state whose title is not a status the field can hold is "
                                  "never found by indicator.js:82, so it silently does "
                                  "nothing:\n" + "\n".join(bad))

    def test_every_state_colour_is_one_frappe_renders(self):
        """Stands in for `_validate_selects` (`base_document.py:877`) on the states child
        rows, skipped on deploy by `frappe.flags.in_import` (`:878`, set at
        `import_file.py:212`).

        Two consequences, both measured, because either alone would be worth the check:

          * **The Desk stops being able to save the DocType.** `_validate_selects` throws
            when a human opens it in developer mode and presses Update -- on a row they did
            not touch. This is the same cost as `KNOWN_PRECISION_EXCEPTIONS` above, and it
            arrives the same way: from a file that deployed cleanly.
          * **The pill loses its colour in the browser.** `indicator.js:84` is
            `frappe.scrub(state.color, "-")` and hands the result straight out as the
            colour class. `.indicator-pill.<colour>` only exists for the twelve in
            `INDICATOR_CSS_COLORS`, generated by the `@each` loop on
            `indicator.scss:51`. A colour outside them renders as a class with no rule.
        """
        bad = []
        for name, (doc, path) in sorted(DOCTYPES.items()):
            for state in doc.get("states") or []:
                colour = state.get("color")
                where = "%s: %s state %r" % (_rel(path), name, state.get("title"))
                if not colour:
                    bad.append("%s has no colour, so indicator.js:84 scrubs %r into the "
                               "class attribute" % (where, colour))
                    continue
                if colour not in DOCTYPE_STATE_COLORS:
                    bad.append("%s has colour %r, which is not one of DocType State's "
                               "options %r" % (where, colour, sorted(DOCTYPE_STATE_COLORS)))
                    continue
                scrubbed = colour.lower().replace(" ", "-")
                if scrubbed not in INDICATOR_CSS_COLORS:
                    bad.append("%s has colour %r, which scrubs to %r and has no CSS rule"
                               % (where, colour, scrubbed))
        self.assertEqual(bad, [], "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
