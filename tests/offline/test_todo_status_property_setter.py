# -*- coding: utf-8 -*-
"""The patch that declares the todo board's two extra ToDo statuses in code.

Pins the owner's decision of 5 Oct 2026 on review tray item rev_a007dfc7a8:
"Declare them in code. Backlog and Planned must stay supported." Scope is
ToDo/status options and the Backlog default, nothing else.

Two things are tested here and they are different in kind:

  * `options_with_extra_statuses` is pure, so it is tested directly against
    every starting point that matters -- the live site's five, frappe's three,
    one of the two already present, a Select with a leading blank option.
  * `execute()` is tested against stand-ins for `frappe.get_meta` and
    `make_property_setter`, which records **what the patch asks frappe to do**:
    two Property Setters, their doc_type, field, property, value, property_type
    and `is_system_generated`.

What that second kind cannot tell us, and the tests say so rather than implying
otherwise: whether frappe then applies those rows the way the patch's docstring
says it does. That was read out of frappe's own source at the installed tag
v15.52.0 (`meta.py:138` -> `apply_property_setters`, 360-387) and needs a bench
to demonstrate. These tests only pin our side of the contract.

`frappe` is stubbed by hand here instead of using `fake_frappe`, which models
queries and documents: the patch does neither, it reads one meta field and
calls one helper.
"""
import importlib.util
import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from test_string_references import patch_module_paths  # noqa: E402

APP_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
PATCH_PATH = os.path.join(APP_ROOT, "erplite", "patches", "declare_todo_status_options.py")
PATCHES_TXT = os.path.join(APP_ROOT, "erplite", "patches.txt")
PATCH_MODULE = "erplite.patches.declare_todo_status_options"

# Stock frappe version-15, from frappe/desk/doctype/todo/todo.json. What a frappe
# upgrade resets the field to, and so what the patch has to cope with.
FRAPPE_OPTIONS = "Open\nClosed\nCancelled"
FRAPPE_DEFAULT = "Open"

# crew.tierneymorris.com.au, measured read-only 5 Oct 2026 (DocField 549ll9q8br).
LIVE_OPTIONS = "Backlog\nPlanned\nOpen\nClosed\nCancelled"
LIVE_DEFAULT = "Backlog"


class _Field(object):
    def __init__(self, options, default):
        self.options = options
        self.default = default


class _Meta(object):
    def __init__(self, field):
        self._field = field

    def get_field(self, fieldname):
        return self._field if fieldname == "status" else None


class _Setter(object):
    """What make_property_setter returns: enough of a Document for db_set."""

    def __init__(self, **kw):
        self.__dict__.update(kw)
        self.db_sets = []

    def db_set(self, fieldname, value=None, update_modified=True, **kw):
        self.db_sets.append((fieldname, value, update_modified))
        setattr(self, fieldname, value)


def by_property(calls):
    """The Property Setters a run asked for, keyed on the property each sets.

    Keyed rather than indexed because the order of the two calls is not part of
    the contract: they are independent upserts into separately-named documents
    (`{doc_type}-{field_name}-{property}`, property_setter.py:34-37, each
    deleting only its own property's row), applied by one pass over the table
    (meta.py:379-387), with nothing reading the meta in between. Unpacking
    `calls` by position pinned the keystrokes instead -- swapping the two lines
    in `execute()` changes nothing and turned four tests red.
    """
    return {setter.property: setter for setter in calls}


def load_patch(status_options, status_default, asked=None):
    """Load the patch module on stand-in frappe modules; return it and a log.

    `asked` is appended to with every doctype `frappe.get_meta` is called for.
    The stub used to ignore its argument, so it answered for every DocType
    alike and reading the wrong one's meta was invisible.
    """
    calls = []

    def make_property_setter(doctype, fieldname, property, value, property_type,
                             for_doctype=False, validate_fields_for_doctype=True):
        setter = _Setter(doc_type=doctype, field_name=fieldname, property=property,
                         value=value, property_type=property_type,
                         doctype_or_field="DocType" if for_doctype else "DocField",
                         is_system_generated=0,
                         validate_fields_for_doctype=validate_fields_for_doctype)
        calls.append(setter)
        return setter

    for name in list(sys.modules):
        if name == "frappe" or name.startswith("frappe.") or name.startswith("erplite"):
            del sys.modules[name]

    frappe = types.ModuleType("frappe")
    frappe.__path__ = []
    def get_meta(doctype):
        if asked is not None:
            asked.append(doctype)
        return _Meta(_Field(status_options, status_default))

    frappe.get_meta = get_meta

    property_setter = types.ModuleType(
        "frappe.custom.doctype.property_setter.property_setter")
    property_setter.make_property_setter = make_property_setter

    packages = {"frappe": frappe}
    for dotted in ("frappe.custom", "frappe.custom.doctype",
                   "frappe.custom.doctype.property_setter"):
        module = types.ModuleType(dotted)
        module.__path__ = []
        packages[dotted] = module
    packages["frappe.custom.doctype.property_setter.property_setter"] = property_setter

    erplite = types.ModuleType("erplite")
    erplite.__path__ = []
    patches = types.ModuleType("erplite.patches")
    patches.__path__ = []
    packages.update({"erplite": erplite, "erplite.patches": patches})
    sys.modules.update(packages)

    spec = importlib.util.spec_from_file_location(PATCH_MODULE, PATCH_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[PATCH_MODULE] = module
    return module, calls


class TestOptionsWithExtraStatuses(unittest.TestCase):
    """The pure half: what list the patch pins, from each starting point."""

    def setUp(self):
        self.patch, _ = load_patch(LIVE_OPTIONS, LIVE_DEFAULT)

    def test_live_site_today_is_left_exactly_as_it_is(self):
        """The point of the patch on this site: pin, do not change.

        No option appears, disappears or moves, so no ToDo's status goes
        off-list and no board column changes on the deploy that lands it.
        """
        self.assertEqual(self.patch.options_with_extra_statuses(LIVE_OPTIONS), LIVE_OPTIONS)

    def test_frappes_three_get_both_statuses_back(self):
        """A site that has lost them, or a fresh install, ends up with all five."""
        self.assertEqual(
            self.patch.options_with_extra_statuses(FRAPPE_OPTIONS),
            "Backlog\nPlanned\nOpen\nClosed\nCancelled",
        )

    def test_only_the_missing_status_is_added(self):
        self.assertEqual(
            self.patch.options_with_extra_statuses("Planned\nOpen\nClosed\nCancelled"),
            "Backlog\nPlanned\nOpen\nClosed\nCancelled",
        )

    def test_options_the_site_has_added_itself_are_kept(self):
        """Nothing is narrowed to the list this patch knows about.

        Someone customising ToDo in Customize Form later is not undone by a
        re-run: their option stays, in its place.
        """
        self.assertEqual(
            self.patch.options_with_extra_statuses("Backlog\nPlanned\nOpen\nBlocked\nClosed"),
            "Backlog\nPlanned\nOpen\nBlocked\nClosed",
        )

    def test_a_leading_blank_option_is_preserved(self):
        """In frappe a leading empty line is what lets a Select hold no value."""
        self.assertEqual(
            self.patch.options_with_extra_statuses("\nOpen\nClosed"),
            "Backlog\nPlanned\n\nOpen\nClosed",
        )

    def test_no_options_at_all_does_not_leave_a_blank_one(self):
        for empty in (None, ""):
            self.assertEqual(
                self.patch.options_with_extra_statuses(empty), "Backlog\nPlanned")

    def test_an_option_that_differs_only_by_surrounding_space_is_not_duplicated(self):
        """`present` compares stripped, and that is load-bearing here.

        These five options exist at all because somebody hand-edited a
        `tabDocField` row, which is exactly where a trailing space comes from.
        Compared unstripped, `"Backlog "` is not `Backlog`, a second `Backlog`
        is prepended, and the board grows a duplicate column -- from a space
        nobody can see in the Select.
        """
        self.assertEqual(
            self.patch.options_with_extra_statuses("Backlog \nPlanned\nOpen"),
            "Backlog \nPlanned\nOpen",
        )
        self.assertEqual(
            self.patch.options_with_extra_statuses(" Backlog\n Planned \nOpen"),
            " Backlog\n Planned \nOpen",
        )

    def test_running_it_twice_changes_nothing_the_second_time(self):
        once = self.patch.options_with_extra_statuses(FRAPPE_OPTIONS)
        self.assertEqual(self.patch.options_with_extra_statuses(once), once)


class TestExecute(unittest.TestCase):
    """What the patch asks frappe to write."""

    def test_two_property_setters_on_todo_status(self):
        patch, calls = load_patch(LIVE_OPTIONS, LIVE_DEFAULT)
        patch.execute()

        self.assertEqual(len(calls), 2)
        for setter in calls:
            self.assertEqual(setter.doc_type, "ToDo")
            self.assertEqual(setter.field_name, "status")
            self.assertEqual(setter.doctype_or_field, "DocField")
            # The fieldtype of DocField.options and DocField.default; `cast()`
            # reads the value back with it.
            self.assertEqual(setter.property_type, "Small Text")

        # Both properties, once each. Not their order: see by_property.
        self.assertEqual(sorted(by_property(calls)), ["default", "options"])
        self.assertEqual(len(by_property(calls)), len(calls))

    def test_the_values_it_sets_on_the_live_site(self):
        patch, calls = load_patch(LIVE_OPTIONS, LIVE_DEFAULT)
        patch.execute()

        rows = by_property(calls)
        self.assertEqual(rows["options"].value, LIVE_OPTIONS)
        self.assertEqual(rows["default"].value, "Backlog")

    def test_it_reads_the_live_meta_rather_than_a_constant(self):
        """A site frappe has already reset still gets all five back.

        If the patch pinned MEASURED_OPTIONS instead of reading the meta, this
        would pass too -- so the next test is the one that tells them apart.
        """
        patch, calls = load_patch(FRAPPE_OPTIONS, FRAPPE_DEFAULT)
        patch.execute()

        self.assertEqual(by_property(calls)["options"].value,
                         "Backlog\nPlanned\nOpen\nClosed\nCancelled")

    def test_a_reset_site_gets_the_default_back(self):
        """The other half of the recovery, and it was asserted for neither row.

        `test_it_reads_the_live_meta_rather_than_a_constant` covers the options
        coming back on a site frappe has reset. The default is the half that
        decides where a *new* ToDo lands, and the patch forces it rather than
        reading it -- deliberately, because a reset site's default is `Open`.
        Preserving the site's own (`status.default or DEFAULT_STATUS`) left
        every test green while the board's first column stopped being the one
        a new ToDo goes to.
        """
        patch, calls = load_patch(FRAPPE_OPTIONS, FRAPPE_DEFAULT)
        patch.execute()

        self.assertEqual(by_property(calls)["default"].value, "Backlog")

    def test_it_asks_for_ToDos_meta_and_not_another_DocTypes(self):
        """The one thing `execute()` reads from the site.

        The stand-in used to ignore the doctype it was handed, so it answered
        for `Task` with ToDo's field and `frappe.get_meta("Task")` was a change
        no test could see -- a patch pinning one DocType's options onto
        another's field.
        """
        asked = []
        patch, _ = load_patch(LIVE_OPTIONS, LIVE_DEFAULT, asked=asked)
        patch.execute()

        self.assertEqual(asked, ["ToDo"])

    def test_an_option_the_site_added_survives_the_patch(self):
        """The one a hard-coded list would silently delete."""
        patch, calls = load_patch("Backlog\nPlanned\nOpen\nBlocked\nClosed", "Backlog")
        patch.execute()

        self.assertIn("Blocked", by_property(calls)["options"].value.split("\n"))

    def test_both_rows_are_marked_system_generated(self):
        """Customize Form's "Reset to defaults" must not drop the default.

        `reset_customization` (customize_form.py:675-685) deletes Property
        Setters filtered `is_system_generated: False`, with two exemptions:
        `property != "options"` and `field_name != "naming_series"`. So the
        `options` row is safe however it is marked, and the `default` row on
        `status` is covered by neither -- unmarked it would go, silently, and
        this patch runs once. Both are marked, because the app declares them.
        """
        patch, calls = load_patch(LIVE_OPTIONS, LIVE_DEFAULT)
        patch.execute()

        for setter in calls:
            self.assertEqual(setter.is_system_generated, 1)
            self.assertEqual(setter.db_sets, [("is_system_generated", 1, False)])

    def test_it_does_not_validate_the_whole_core_doctype(self):
        """A patch of ours should not abort a migrate over an unrelated problem
        in a core DocType it did not touch. Frappe skips this itself when
        `frappe.flags.in_patch`; the patch says so explicitly instead."""
        patch, calls = load_patch(LIVE_OPTIONS, LIVE_DEFAULT)
        patch.execute()

        for setter in calls:
            self.assertFalse(setter.validate_fields_for_doctype)

    def test_nothing_but_todo_status_is_touched(self):
        """Scope, as the owner set it: the status options and the default only."""
        patch, calls = load_patch(LIVE_OPTIONS, LIVE_DEFAULT)
        patch.execute()

        self.assertEqual({setter.doc_type for setter in calls}, {"ToDo"})
        self.assertEqual({setter.field_name for setter in calls}, {"status"})
        self.assertEqual({setter.property for setter in calls}, {"options", "default"})


class TestItIsWiredUp(unittest.TestCase):
    """A patch nothing runs protects nothing.

    patches.txt is parsed by test_string_references.py, which does it the way
    frappe does (configparser with `delimiters="\n"`, the first whitespace
    token, `execute:` and `finally:` handled). Two parsers of one file is how
    one of them goes stale -- and the one that was here had already drifted
    into reporting entries frappe accepts.
    """

    def test_patches_txt_runs_it_after_the_doctypes_are_migrated(self):
        """In `pre_model_sync` it would pin whatever the field held *before*
        frappe's own import reset it, which is the thing this patch exists to
        undo."""
        # Keyed on the path frappe resolves, not on the raw line: the entry may
        # legitimately carry a trailing date, and keying on the line made this
        # test red on an entry frappe runs perfectly well.
        sections = {dotted: section for section, _l, _e, dotted in patch_module_paths()}

        self.assertIn(PATCH_MODULE + ".execute", sections,
                      "patches.txt does not run this patch")
        self.assertEqual("post_model_sync", sections[PATCH_MODULE + ".execute"])

    def test_the_module_path_in_patches_txt_resolves_to_a_file(self):
        relative = os.path.join(*PATCH_MODULE.split(".")) + ".py"
        self.assertTrue(os.path.isfile(os.path.join(APP_ROOT, relative)))
        self.assertTrue(os.path.isfile(
            os.path.join(APP_ROOT, "erplite", "patches", "__init__.py")),
            "a patches package without __init__.py is not importable by frappe")

    def test_this_patchs_entry_resolves_the_way_frappe_resolves_it(self):
        """Narrowed on purpose, and the narrowing is the point.

        This used to sweep every entry in patches.txt with a parser of its own:
        strip the line, skip `#` and `[`, split on "." and ask for a file. That
        parser was wrong in both directions against
        `frappe.modules.patch_handler.execute_patch`, and both directions were
        measured:

          * **It reported correct code.** frappe resolves
            `patchmodule.split(maxsplit=1)[0]` (`patch_handler.py:166`), so the
            trailing date frappe's own patches.txt writes after the module is
            not part of the path -- and an `execute:` entry is `exec()`ed whole
            (`:161-163`) with no path in it at all. Both are entries frappe
            runs happily, and both turned this file red.
          * **It missed the failure that matters.** `os.path.isfile` says
            nothing about whether the module has an `execute` for
            `get_attr` to find, which is what actually stops the migrate.

        So the whole-file sweep is not duplicated here. It lives in
        test_string_references.py's `PatchPathsResolve`, parsed as frappe parses
        it, and this file asserts only its own patch -- through that same
        parser, so there is one answer to the question and not two.
        """
        resolved = [dotted for _s, _l, _e, dotted in patch_module_paths()]
        self.assertIn(PATCH_MODULE + ".execute", resolved)

        patch, _ = load_patch(LIVE_OPTIONS, LIVE_DEFAULT)
        self.assertTrue(callable(getattr(patch, "execute", None)),
                        "patches.txt names it, so get_attr must find an execute()")


class TestItAgreesWithTheSelectGuard(unittest.TestCase):
    """The guard in test_select_values.py mirrors the live options by hand.

    Two hand-kept records of the same five statuses is exactly how one goes
    stale, so they are compared rather than trusted.
    """

    def test_the_declared_statuses_are_in_the_guards_mirror(self):
        patch, _ = load_patch(LIVE_OPTIONS, LIVE_DEFAULT)

        sys.modules.pop("test_select_values", None)
        import test_select_values  # noqa: E402

        mirrored = test_select_values.KNOWN_CORE_SELECTS["ToDo"]["status"]
        for status in patch.EXTRA_STATUSES:
            self.assertIn(status, mirrored)
        self.assertIn(patch.DEFAULT_STATUS, mirrored)
        self.assertEqual(set(patch.MEASURED_OPTIONS.split("\n")), set(mirrored))

        # The mirror is a set, so it cannot see order -- and MEASURED_OPTIONS
        # is a record of what the live Select *looks like*, which is an ordered
        # thing: it is what a reviewer reads instead of the database, and the
        # order is the board's column order. LIVE_OPTIONS above is the same
        # measurement, written down twice, so compare them exactly.
        self.assertEqual(LIVE_OPTIONS, patch.MEASURED_OPTIONS)

    def test_the_default_is_one_of_the_options(self):
        patch, _ = load_patch(LIVE_OPTIONS, LIVE_DEFAULT)
        self.assertIn(patch.DEFAULT_STATUS,
                      patch.options_with_extra_statuses(FRAPPE_OPTIONS).split("\n"))


# The frappe the claims in the patch's docstring were read against, and the
# version installed on the bench. Named rather than matched by shape: the test
# below used to ask only for `v15.<n>.<n>`, so the one edit that makes the
# docstring misleading -- a tag the mechanisms were never read at -- was the
# one it could not see, in a test whose whole point is that the tag is what to
# re-check against.
FRAPPE_TAG = "v15.52.0"


class TestTheDocstringDoesNotDrift(unittest.TestCase):
    def test_it_names_the_frappe_tag_its_claims_were_read_at(self):
        """Every mechanism in that docstring was read at one tag. If someone
        upgrades frappe, the tag is the thing to re-check against.

        Verified at that tag, with the line each was read at:
        `apply_property_setters` on every meta load (`model/meta.py:138`, body
        at 360-387, `cast(ps.property_type, ps.value)` at 386); the DocType
        skip gate is `migration_hash` alone, the timestamp gate beside it being
        explicitly `and doc["doctype"] != "DocType"`
        (`modules/import_file.py:130-144`); `delete_old_doc` (`:258-276`)
        deleting with `ignore_doctypes = [""]` (`:40`), which spares no child
        table; `sync_all()` called with no arguments so `force=0`
        (`migrate.py:120`, `model/sync.py:39`); the name
        `{doc_type}-{field_name}-{property}` and the delete-then-insert upsert
        (`property_setter.py:34-37, 39-44, 90-98`); `is_system_generated` not
        being an argument to `make_property_setter` (`:63-71`); and
        `reset_customization` filtering `is_system_generated: False`
        (`customize_form.py:675-685`).
        """
        with open(PATCH_PATH) as handle:
            source = handle.read()

        self.assertIn(FRAPPE_TAG, source)
        self.assertEqual([FRAPPE_TAG], sorted(set(re.findall(r"v15\.\d+\.\d+", source))),
                         "the docstring names a frappe tag its claims were not read at")


if __name__ == "__main__":
    unittest.main()
