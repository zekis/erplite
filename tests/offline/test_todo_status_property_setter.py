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


def load_patch(status_options, status_default):
    """Load the patch module on stand-in frappe modules; return it and a log."""
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
    frappe.get_meta = lambda doctype: _Meta(_Field(status_options, status_default))

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

        self.assertEqual([setter.property for setter in calls], ["options", "default"])

    def test_the_values_it_sets_on_the_live_site(self):
        patch, calls = load_patch(LIVE_OPTIONS, LIVE_DEFAULT)
        patch.execute()

        options, default = calls
        self.assertEqual(options.value, LIVE_OPTIONS)
        self.assertEqual(default.value, "Backlog")

    def test_it_reads_the_live_meta_rather_than_a_constant(self):
        """A site frappe has already reset still gets all five back.

        If the patch pinned MEASURED_OPTIONS instead of reading the meta, this
        would pass too -- so the next test is the one that tells them apart.
        """
        patch, calls = load_patch(FRAPPE_OPTIONS, FRAPPE_DEFAULT)
        patch.execute()

        self.assertEqual(calls[0].value, "Backlog\nPlanned\nOpen\nClosed\nCancelled")

    def test_an_option_the_site_added_survives_the_patch(self):
        """The one a hard-coded list would silently delete."""
        patch, calls = load_patch("Backlog\nPlanned\nOpen\nBlocked\nClosed", "Backlog")
        patch.execute()

        self.assertIn("Blocked", calls[0].value.split("\n"))

    def test_both_rows_are_marked_system_generated(self):
        """Customize Form's "Reset to defaults" must not drop the default.

        `reset_customization` deletes Property Setters filtered on
        `is_system_generated: False`, exempting only `property != "options"`.
        An unmarked `default` row would go, silently, and this patch runs once.
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
    """A patch nothing runs protects nothing."""

    def test_patches_txt_lists_it_after_the_doctypes_are_migrated(self):
        with open(PATCHES_TXT) as handle:
            text = handle.read()

        post = text.split("[post_model_sync]", 1)
        self.assertEqual(len(post), 2, "patches.txt has no [post_model_sync] section")

        entries = [line.strip() for line in post[1].splitlines()
                   if line.strip() and not line.strip().startswith("#")]
        self.assertIn(PATCH_MODULE, entries)
        self.assertNotIn(PATCH_MODULE, post[0], "it reads ToDo's meta, so it is not a pre-sync patch")

    def test_the_module_path_in_patches_txt_resolves_to_a_file(self):
        relative = os.path.join(*PATCH_MODULE.split(".")) + ".py"
        self.assertTrue(os.path.isfile(os.path.join(APP_ROOT, relative)))
        self.assertTrue(os.path.isfile(
            os.path.join(APP_ROOT, "erplite", "patches", "__init__.py")),
            "a patches package without __init__.py is not importable by frappe")

    def test_every_entry_in_patches_txt_resolves(self):
        """Guards the file itself, not just this patch: a typo'd module path
        fails a `bench migrate` on the owner's site, not here."""
        with open(PATCHES_TXT) as handle:
            entries = [line.strip() for line in handle
                       if line.strip() and not line.strip().startswith(("#", "["))]

        for entry in entries:
            path = os.path.join(APP_ROOT, *entry.split(".")) + ".py"
            self.assertTrue(os.path.isfile(path), "patches.txt names %s, which is not a file" % entry)


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

    def test_the_default_is_one_of_the_options(self):
        patch, _ = load_patch(LIVE_OPTIONS, LIVE_DEFAULT)
        self.assertIn(patch.DEFAULT_STATUS,
                      patch.options_with_extra_statuses(FRAPPE_OPTIONS).split("\n"))


class TestTheDocstringDoesNotDrift(unittest.TestCase):
    def test_it_names_the_frappe_tag_its_claims_were_read_at(self):
        """Every mechanism in that docstring was read at one tag. If someone
        upgrades frappe, the tag is the thing to re-check against."""
        with open(PATCH_PATH) as handle:
            source = handle.read()

        self.assertTrue(re.search(r"v15\.\d+\.\d+", source))


if __name__ == "__main__":
    unittest.main()
