# -*- coding: utf-8 -*-
"""Trip status: a derived field that a user is also allowed to set by hand.

`Trip.before_save` derives `status` from `departure_datetime` / `arrival_datetime`.
But `status` is not purely derived: `trip/trip.js` adds a **"Start Trip"** and a
**"Complete Trip"** button, each of which does

    frm.set_value('status', <value>); frm.save();

and the Select itself (`Planned / In Progress / Completed / Cancelled`) is editable.

## What this found (6 Oct 2026), and whose fault it was

Mine. Commit e585a5b moved the derivation out of `on_update` into `before_save`,
because an assignment in `on_update` happens after `db_update()` has written the
row and is discarded (that is what `test_post_save_field_writes.py` guards). The
move was right for the lost write and wrong for the buttons: `before_save` runs
*before* the write, so deriving unconditionally overwrote whatever the user had
just chosen.

Measured against the real controller, both versions, with `now` frozen:

| click               | dates            | pre-e585a5b stored | after e585a5b stored |
|---------------------|------------------|--------------------|----------------------|
| Start Trip          | departure future | `In Progress`      | **`Planned`**        |
| Complete Trip       | trip running     | `Completed`        | **`In Progress`**    |

So the buttons went from "works, though the form briefly displays the derived
value" to "silently does nothing". No exception, nothing in the Error Log: the
save succeeds and the field simply is not what was asked for.

Worth being precise about why the earlier guard test did not catch it. That guard
pins a *mechanism* -- do not assign a field after the row is written. The fix
satisfied it. What broke was a *behaviour* -- a user's explicit choice survives
the save -- which nothing pinned. A green mechanism guard is not evidence that
the feature still works.

## What I expected to find and did not

I expected `supplier_quote.py` to have the same bug, since its `before_save` is
the pattern e585a5b copied. It does not. Its guard is

    if self.valid_until and self.valid_until < nowdate() and self.status not in ["Accepted", "Rejected"]:

and its two buttons set exactly `Accepted` and `Rejected`. It protects precisely
the values its buttons set, so its buttons work. Trip's guard protects only
`Cancelled`, while its buttons set `In Progress` and `Completed` -- and those are
also the values derivation produces, so extending the exclusion list the way
Supplier Quote does would have disabled most of the derivation. That asymmetry is
the finding, and it is why the fix consults the pre-save document instead.

`TestNoButtonSetSelectIsSilentlyOverwritten` below is the whole-app form of the
rule, and it accepts either remedy, because both are correct.

## The owner's answer, and what it did and did not settle

The question above went to the owner as review item **rev_f9dce41f7f**, asking
whether a status set by hand should survive *later* saves. The answer was narrow:
**"a Completed trip stays Completed"**. So `TERMINAL_STATUSES` was added to
`trip.py` and `before_save` now also returns early when the *stored* status is
`Completed` or `Cancelled`.

What that settled: clicking "Complete Trip" on a trip whose arrival is still in
the future used to persist `Completed` and then lose it on the next unrelated save
of that document, which derived it back to `In Progress`. It no longer does.
`TestATerminalStatusIsNotDerivedAway` below pins that.

What it deliberately did not settle: a hand-set **non**-terminal status still goes
stale. Clicking "Start Trip" on a trip that has not departed persists
`In Progress`, and the next save that does not touch the status re-derives it to
`Planned`. `test_a_stale_status_is_refreshed_when_the_save_does_not_touch_it`
still pins that, and it is the behaviour the owner left in place.

The guard reads the *previous* document's status, not the current one, and that
distinction is load-bearing: a brand-new trip created as `Completed` with dates in
the future still derives to `Planned`, because there is no stored status to
protect. `test_a_new_trip_in_the_future_is_planned` pins it from the other side.
Only `Cancelled` is honoured on insert, by the per-branch checks in the three
derivation arms, which this change left alone.

## What fault injection added (6 Oct 2026)

Forty faults, against the file as it stood. Thirty-four behaved; the six
that did not are the reason for every change in this file since:

* **Two of the three derivation arms were unguarded.** The docstring above
  says Cancelled is honoured on insert "by the per-branch checks in the
  three derivation arms". Only the past arm was tested. Dropping the
  exclusion from the future or the running arm was green.
* **Neither instant where the arms meet was tested.** Every date here sat
  in the middle of a window, so `now < departure` -> `<=` and
  `departure <= now <= arrival` -> `< arrival` were both green.
* **`arrival <= departure` was pinned only as `<`.** The refusal test used
  dates days apart the wrong way round, so a trip arriving at the instant
  it departs would have been accepted.
* **One fault was simply wrong, and that was the useful part.** Swapping
  the two guards in `before_save` is an equivalence, not a regression --
  see `test_a_terminal_trip_can_still_be_reopened_by_hand`, whose docstring
  claimed the opposite.

These tests run without a bench. See fake_frappe.py for the stand-in.
"""

import ast
import copy
import datetime
import importlib.util
import json
import os
import re
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from fake_frappe import (  # noqa: E402
    FakeDocumentBase,
    FakeFrappe,
    ValidationError,
    _dict,
    make_doc,
)

DOCTYPE_DIR = os.path.join(APP_ROOT, "erplite", "projects", "doctype", "trip")
CONTROLLER = os.path.join(DOCTYPE_DIR, "trip.py")
DOCTYPE_JSON = os.path.join(DOCTYPE_DIR, "trip.json")

# Frozen so the tests do not depend on the clock. Everything below is positioned
# relative to this instant.
NOW = datetime.datetime(2026, 10, 6, 17, 0, 0)

FUTURE_DEP = datetime.datetime(2026, 10, 20, 8, 0, 0)
FUTURE_ARR = datetime.datetime(2026, 10, 24, 18, 0, 0)
RUNNING_DEP = datetime.datetime(2026, 10, 5, 8, 0, 0)
RUNNING_ARR = datetime.datetime(2026, 10, 9, 18, 0, 0)
PAST_DEP = datetime.datetime(2026, 9, 1, 8, 0, 0)
PAST_ARR = datetime.datetime(2026, 9, 5, 18, 0, 0)

# The three derivation arms are `now < departure`, `departure <= now <=
# arrival` and `now > arrival`, so both instants where they meet belong to
# the running arm. Every date above sits in the middle of a window, which
# pins "somewhere inside it" and not the edge: a trip positioned exactly on
# each instant is the only thing that notices either comparison loosened by
# one tick. Found by fault injection, not review.
ONE_SECOND = datetime.timedelta(seconds=1)


class FrozenDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


def load_trip(frappe):
    """Import the real trip.py against the stand-in, with the clock frozen."""
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
    utils.get_datetime = lambda v: (
        v if isinstance(v, datetime.datetime)
        else datetime.datetime.fromisoformat(str(v))
    )
    utils.getdate = lambda v: utils.get_datetime(v).date()
    utils.nowdate = lambda: NOW.date().isoformat()
    frappe_pkg.utils = utils

    sys.modules["frappe"] = frappe_pkg
    sys.modules["frappe.model"] = model
    sys.modules["frappe.model.document"] = document
    sys.modules["frappe.utils"] = utils

    spec = importlib.util.spec_from_file_location(
        "erplite_trip_under_test", CONTROLLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # trip.py does `from datetime import datetime` and calls datetime.now()
    module.datetime = FrozenDatetime
    return module


class TripTestCase(unittest.TestCase):
    """Drives frappe's save() ordering over the real controller.

    The ordering is ported from frappe-version-15 `Document._save()`:

        check_if_latest()           -> load_doc_before_save()
        run_before_save_methods()   -> validate, before_save   (PERSISTED)
        db_update()                 -> the row is written HERE
        run_post_save_methods()     -> on_update               (NOT persisted)
    """

    def setUp(self):
        self.frappe = FakeFrappe(session_user="zeke@tierneymorris.com.au")
        self.module = load_trip(self.frappe)
        self.rows = {}        # name -> stored dict, stands in for tabTrip
        self.hooks_run = []

    # -- the driver ----------------------------------------------------------
    def new_trip(self, **data):
        base = dict(name="TRIP-2026-00001", trip_name="Novalith site visit",
                    destination="Perth", primary_traveler="Zeke Tierney",
                    status="Planned", naming_series="TRIP-.YYYY.-")
        base.update(data)
        return make_doc(self.module.Trip, "Trip", "projects", "trip", base)

    def save(self, doc):
        self.hooks_run = []
        # check_if_latest() -> load_doc_before_save(): None when the row is new
        stored = self.rows.get(doc.name)
        if stored is None:
            doc._doc_before_save = None
        else:
            doc._doc_before_save = self.new_trip(**copy.deepcopy(stored))

        for hook in ("validate", "before_save"):
            fn = getattr(type(doc), hook, None)
            if callable(fn):
                fn(doc)
                self.hooks_run.append(hook)

        self.rows[doc.name] = {
            k: v for k, v in vars(doc).items()
            if not k.startswith("_") and k not in ("doctype",)
        }
        self.hooks_run.append("db_update")

        fn = getattr(type(doc), "on_update", None)
        if callable(fn):
            fn(doc)
            self.hooks_run.append("on_update")
        return doc

    def stored(self, name="TRIP-2026-00001", field="status"):
        return self.rows[name][field]


# ---------------------------------------------------------------------------
# 1. Self-tests: is the stand-in faithful to frappe?
# ---------------------------------------------------------------------------
class TestTheStandInIsFaithful(TripTestCase):
    def test_row_is_written_after_before_save_and_before_on_update(self):
        doc = self.new_trip(departure_datetime=FUTURE_DEP,
                            arrival_datetime=FUTURE_ARR)
        self.save(doc)
        self.assertEqual(self.hooks_run, ["validate", "before_save", "db_update"])
        self.assertIsNone(getattr(type(doc), "on_update", None),
                          "trip.py has no on_update; if one is added, this "
                          "ordering assertion must grow an 'on_update' entry")

    def test_doc_before_save_is_none_on_insert_and_set_on_update(self):
        doc = self.new_trip(departure_datetime=FUTURE_DEP,
                            arrival_datetime=FUTURE_ARR)
        self.save(doc)
        self.assertIsNone(doc.get_doc_before_save(),
                          "load_doc_before_save returns early when is_new()")

        again = self.new_trip(**copy.deepcopy(self.rows[doc.name]))
        self.save(again)
        self.assertIsNotNone(again.get_doc_before_save())
        self.assertEqual(again.get_doc_before_save().status, "Planned")

    def test_has_value_changed_is_true_without_a_previous_document(self):
        """The trap the fix avoids: True on insert, for every field.

        frappe document.py:508-509. A hook that used has_value_changed to mean
        "the user edited this" would skip derivation on creation, which is the
        one case that most needs it.
        """
        doc = self.new_trip(departure_datetime=PAST_DEP, arrival_datetime=PAST_ARR)
        doc._doc_before_save = None
        self.assertTrue(doc.has_value_changed("status"))
        self.assertTrue(doc.has_value_changed("trip_name"))

        doc._doc_before_save = self.new_trip(status="Planned")
        self.assertFalse(doc.has_value_changed("status"))

    def test_the_two_buttons_in_trip_js_set_the_values_these_tests_use(self):
        """Pin the premise: if trip.js changes, these tests go stale loudly."""
        with open(os.path.join(DOCTYPE_DIR, "trip.js"), encoding="utf-8") as fh:
            js = fh.read()
        self.assertIn("__('Start Trip')", js)
        self.assertIn("frm.set_value('status', 'In Progress')", js)
        self.assertIn("__('Complete Trip')", js)
        self.assertIn("frm.set_value('status', 'Completed')", js)
        self.assertIn("frm.save()", js)

    def test_status_is_a_select_offering_the_four_values(self):
        with open(DOCTYPE_JSON, encoding="utf-8") as fh:
            meta = json.load(fh)
        status = [f for f in meta["fields"] if f["fieldname"] == "status"][0]
        self.assertEqual(status["fieldtype"], "Select")
        self.assertEqual(status["options"].split("\n"),
                         ["Planned", "In Progress", "Completed", "Cancelled"])
        self.assertEqual(status.get("default"), "Planned")
        self.assertEqual(status.get("reqd"), 1,
                         "reqd with a default, so no MandatoryError on insert")


# ---------------------------------------------------------------------------
# 2. The bug: an explicit change must survive the save that makes it
# ---------------------------------------------------------------------------
class TestAnExplicitStatusChangeSurvivesTheSave(TripTestCase):
    def _existing(self, stored_status, dep, arr):
        doc = self.new_trip(status=stored_status,
                            departure_datetime=dep, arrival_datetime=arr)
        self.rows[doc.name] = {k: v for k, v in vars(doc).items()
                               if not k.startswith("_") and k != "doctype"}
        return self.new_trip(**copy.deepcopy(self.rows[doc.name]))

    def test_start_trip_button_persists_in_progress(self):
        """Departure is a fortnight away, so derivation wants 'Planned'."""
        doc = self._existing("Planned", FUTURE_DEP, FUTURE_ARR)
        doc.status = "In Progress"          # what frm.set_value does
        self.save(doc)                      # what frm.save does
        self.assertEqual(self.stored(), "In Progress")

    def test_complete_trip_button_persists_completed(self):
        """The trip is running, so derivation wants 'In Progress'."""
        doc = self._existing("In Progress", RUNNING_DEP, RUNNING_ARR)
        doc.status = "Completed"
        self.save(doc)
        self.assertEqual(self.stored(), "Completed")

    def test_a_hand_picked_status_persists_too(self):
        """The Select is editable; the buttons are not a special case.

        Deliberately NOT "Cancelled": the pre-existing exclusion in before_save
        protects that value anyway, so a Cancelled version of this test passed
        with the fix reverted and proved nothing. "In Progress" on a trip that is
        over is a value derivation actively wants to change.
        """
        doc = self._existing("Completed", PAST_DEP, PAST_ARR)
        doc.status = "In Progress"
        self.save(doc)
        self.assertEqual(self.stored(), "In Progress")

    def test_reopening_a_completed_trip_persists(self):
        doc = self._existing("Completed", PAST_DEP, PAST_ARR)
        doc.status = "Planned"
        self.save(doc)
        self.assertEqual(self.stored(), "Planned")


# ---------------------------------------------------------------------------
# 3. Already right: derivation itself must keep working
# ---------------------------------------------------------------------------
class TestDerivationStillWorks(TripTestCase):
    def test_a_new_trip_in_the_future_is_planned(self):
        self.save(self.new_trip(status="Completed",
                                departure_datetime=FUTURE_DEP,
                                arrival_datetime=FUTURE_ARR))
        self.assertEqual(self.stored(), "Planned",
                         "on insert there is no prior status to respect, so "
                         "the dates decide")

    def test_a_new_trip_already_running_is_in_progress(self):
        self.save(self.new_trip(departure_datetime=RUNNING_DEP,
                                arrival_datetime=RUNNING_ARR))
        self.assertEqual(self.stored(), "In Progress")

    def test_a_new_trip_already_over_is_completed(self):
        self.save(self.new_trip(departure_datetime=PAST_DEP,
                                arrival_datetime=PAST_ARR))
        self.assertEqual(self.stored(), "Completed")

    def test_a_stale_status_is_refreshed_when_the_save_does_not_touch_it(self):
        """A trip saved as Planned that has since departed."""
        doc = self.new_trip(status="Planned", departure_datetime=RUNNING_DEP,
                            arrival_datetime=RUNNING_ARR)
        self.rows[doc.name] = {k: v for k, v in vars(doc).items()
                               if not k.startswith("_") and k != "doctype"}
        again = self.new_trip(**copy.deepcopy(self.rows[doc.name]))
        again.notes = "edited something else"
        self.save(again)
        self.assertEqual(self.stored(), "In Progress")

    def test_cancelled_survives_a_save_that_does_not_touch_the_status(self):
        doc = self.new_trip(status="Cancelled", departure_datetime=RUNNING_DEP,
                            arrival_datetime=RUNNING_ARR)
        self.rows[doc.name] = {k: v for k, v in vars(doc).items()
                               if not k.startswith("_") and k != "doctype"}
        again = self.new_trip(**copy.deepcopy(self.rows[doc.name]))
        self.save(again)
        self.assertEqual(self.stored(), "Cancelled",
                         "the explicit Cancelled guard in before_save")

    def test_a_trip_with_no_arrival_date_is_left_alone(self):
        self.save(self.new_trip(status="Planned",
                                departure_datetime=RUNNING_DEP,
                                arrival_datetime=None))
        self.assertEqual(self.stored(), "Planned")
        self.assertIsNone(self.stored(field="duration_days"))

    def test_the_instants_where_the_arms_meet_belong_to_the_running_arm(self):
        """Both of the running arm's comparisons are inclusive; pin both.

        Four positions: the tick before departure, the departure instant,
        the arrival instant, the tick after arrival. Without the two middle
        ones, `now < departure` could become `<=` and the running arm could
        stop at `< arrival` with nothing in this file going red -- measured,
        both were green before this test existed.
        """
        for label, dep, arr, expected in (
                ("the tick before departure", NOW + ONE_SECOND, FUTURE_ARR,
                 "Planned"),
                ("the departure instant", NOW, FUTURE_ARR, "In Progress"),
                ("the arrival instant", PAST_DEP, NOW, "In Progress"),
                ("the tick after arrival", PAST_DEP, NOW - ONE_SECOND,
                 "Completed")):
            with self.subTest(label):
                self.rows.clear()
                self.save(self.new_trip(status="Planned",
                                        departure_datetime=dep,
                                        arrival_datetime=arr))
                self.assertEqual(self.stored(), expected)

    def test_duration_days_is_computed_from_the_two_dates(self):
        self.save(self.new_trip(departure_datetime=RUNNING_DEP,
                                arrival_datetime=RUNNING_ARR))
        self.assertAlmostEqual(self.stored(field="duration_days"),
                               4 + 10 / 24.0, places=6)

    def test_arrival_before_departure_is_refused(self):
        doc = self.new_trip(departure_datetime=RUNNING_ARR,
                            arrival_datetime=RUNNING_DEP)
        with self.assertRaises(ValidationError):
            self.save(doc)
        self.assertNotIn(doc.name, self.rows, "the throw aborts the save")

    def test_arrival_equal_to_departure_is_refused(self):
        """The window has to be open, not merely non-negative.

        The test above uses two dates days apart the wrong way round, so it
        passes with `arrival <= departure` loosened to `<` -- which accepts
        a trip arriving at the instant it departs. The equal case is the
        only one that pins the `=`. Measured: that loosening was green
        before this test existed.
        """
        doc = self.new_trip(departure_datetime=RUNNING_DEP,
                            arrival_datetime=RUNNING_DEP)
        with self.assertRaises(ValidationError):
            self.save(doc)
        self.assertNotIn(doc.name, self.rows, "the throw aborts the save")


# ---------------------------------------------------------------------------
# 4. Whole-app rule
# ---------------------------------------------------------------------------
PRE_SAVE_HOOKS = {"validate", "before_save", "before_validate", "before_submit"}

ERPLITE = os.path.join(APP_ROOT, "erplite")


def _button_set_values(js_src):
    """{field: {values}} for set_value calls inside an add_custom_button callback.

    Brace-matched rather than line-based, because a field-change handler
    recomputing a dependent value is the server being authoritative and is
    correct; a custom button is a deliberate user decision. Only the second is
    in scope.
    """
    out = {}
    for match in re.finditer(r"add_custom_button\s*\(", js_src):
        start = js_src.index("(", match.end() - 1)
        depth, i = 0, start
        while i < len(js_src):
            if js_src[i] == "(":
                depth += 1
            elif js_src[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = js_src[start:i]
        for field, value in re.findall(
                r"""set_value\(\s*['"]([a-z0-9_]+)['"]\s*,\s*['"]([^'"]+)['"]""", body):
            out.setdefault(field, set()).add(value)
    return out


def _pre_save_assignments_and_guards(py_path):
    """Returns (fields assigned in a pre-save hook, values those hooks compare
    the field against, whether the hook consults the pre-save document)."""
    with open(py_path, encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    assigned, guarded_values, consults = {}, {}, False
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        fns = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        reachable = set(PRE_SAVE_HOOKS) & set(fns)
        # one level of self.helper(), which is how these controllers are written
        for hook in list(reachable):
            for node in ast.walk(fns[hook]):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "self"
                        and node.func.attr in fns):
                    reachable.add(node.func.attr)
        for hook in reachable:
            for node in ast.walk(fns[hook]):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if (isinstance(target, ast.Attribute)
                                and isinstance(target.value, ast.Name)
                                and target.value.id == "self"):
                            assigned.setdefault(target.attr, set()).add(hook)
                if isinstance(node, ast.Compare):
                    left = node.left
                    if not (isinstance(left, ast.Attribute)
                            and isinstance(left.value, ast.Name)
                            and left.value.id == "self"):
                        continue
                    for comparator in node.comparators:
                        for const in ast.walk(comparator):
                            if isinstance(const, ast.Constant) and isinstance(const.value, str):
                                guarded_values.setdefault(left.attr, set()).add(const.value)
            # Must be a real call in a real hook. Detecting this by searching the
            # file text instead matched this module's own docstring, so reverting
            # the fix left the rule green -- found by fault injection, not review.
            for node in ast.walk(fns[hook]):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "self"
                        and node.func.attr in ("get_doc_before_save",
                                               "has_value_changed")):
                    consults = True
    return assigned, guarded_values, consults


def _select_fields(doctype_dir):
    for name in os.listdir(doctype_dir):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(doctype_dir, name), encoding="utf-8") as fh:
            try:
                meta = json.load(fh)
            except ValueError:
                continue
        if meta.get("doctype") == "DocType":
            return {f["fieldname"] for f in meta.get("fields", [])
                    if f.get("fieldtype") == "Select"}
    return set()


class TestNoButtonSetSelectIsSilentlyOverwritten(unittest.TestCase):
    """Whole-app rule: if a custom button sets a Select field and a pre-save hook
    re-derives that field, the hook must protect the button's value.

    Two remedies count, because both are correct and the app uses one of each:

      * consult the pre-save document (`get_doc_before_save`) and leave an
        explicitly changed field alone -- `projects/doctype/trip`;
      * exclude the button's values by name in the guard condition --
        `accounts/doctype/supplier_quote`, whose two buttons set `Accepted` and
        `Rejected` and whose guard is `status not in ["Accepted", "Rejected"]`.

    Deliberately narrow. The broad version of this rule ("a .js sets a field the
    .py re-derives") had 8 hits across the app and almost all were legitimate:
    `purchase_invoice` recomputing `grand_total`, `schedule_entry` recomputing
    `end_time`, `schedule_template` normalising `template_code`. In those the
    server is meant to win. Restricting it to a Select set from an explicit
    button cut it to the 2 real cases.
    """

    def test_every_button_set_select_value_is_protected(self):
        checked, failures = [], []
        for root, dirs, files in os.walk(ERPLITE):
            dirs[:] = [d for d in dirs
                       if d not in ("public", "node_modules", "__pycache__", "dist")]
            for name in files:
                if not name.endswith(".js"):
                    continue
                js_path = os.path.join(root, name)
                py_path = js_path[:-3] + ".py"
                if not os.path.exists(py_path):
                    continue
                with open(js_path, encoding="utf-8") as fh:
                    buttons = _button_set_values(fh.read())
                if not buttons:
                    continue
                selects = _select_fields(root)
                assigned, guarded, consults = _pre_save_assignments_and_guards(py_path)
                for field, values in sorted(buttons.items()):
                    if field not in selects or field not in assigned:
                        continue
                    rel = os.path.relpath(py_path, APP_ROOT)
                    checked.append((rel, field))
                    if consults:
                        continue
                    unprotected = sorted(values - guarded.get(field, set()))
                    if unprotected:
                        failures.append(
                            "%s: a button sets %s to %s, and %s re-derives %s "
                            "without protecting %s -- the button will silently "
                            "do nothing"
                            % (rel, field, sorted(values),
                               sorted(assigned[field]), field, unprotected))
        self.assertTrue(checked, "the walker found nothing to check, so it is "
                                 "broken rather than green")
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_the_walker_catches_the_bug_it_was_written_for(self):
        """Fault injection: the pre-e585a5b-fix shape must be reported.

        Keeps the rule honest -- a walker that reports nothing is green for the
        wrong reason.
        """
        js = """
        frappe.ui.form.on('Thing', {
            refresh: function(frm) {
                frm.add_custom_button(__('Start'), function() {
                    frm.set_value('status', 'In Progress');
                    frm.save();
                });
            }
        });
        """
        self.assertEqual(_button_set_values(js), {"status": {"In Progress"}})

        unguarded = os.path.join(HERE, "_trip_fault.py")
        with open(unguarded, "w", encoding="utf-8") as fh:
            fh.write(
                "class Thing:\n"
                "    def before_save(self):\n"
                "        if self.status != 'Cancelled':\n"
                "            self.status = 'Planned'\n")
        try:
            assigned, guarded, consults = _pre_save_assignments_and_guards(unguarded)
            self.assertIn("status", assigned)
            self.assertEqual(guarded.get("status"), {"Cancelled"})
            self.assertFalse(consults)
            self.assertEqual(sorted({"In Progress"} - guarded["status"]),
                             ["In Progress"], "the rule must flag this shape")
        finally:
            os.remove(unguarded)

    def test_the_real_controller_now_consults_the_previous_document(self):
        _, _, consults = _pre_save_assignments_and_guards(CONTROLLER)
        self.assertTrue(consults, "trip.py must keep consulting "
                                  "get_doc_before_save, or the buttons break again")


# ---------------------------------------------------------------------------
# 5. The owner's rule: a terminal status is not derived away (rev_f9dce41f7f)
# ---------------------------------------------------------------------------
class TestATerminalStatusIsNotDerivedAway(TripTestCase):
    """Once a stored trip is Completed or Cancelled, the dates stop deciding.

    The two halves of `TERMINAL_STATUSES` are not guarded alike, and cannot
    be. Dropping "Completed" from it turns three tests red. Dropping
    "Cancelled" turns exactly one red --
    `test_terminal_statuses_are_real_options_on_the_doctype`, which reads the
    tuple rather than exercising it -- because the three derivation arms
    already skip a Cancelled trip on their own. So the Cancelled half of the
    owner's rule makes no behavioural difference while those arms stand, and
    no behavioural test can be written for it. Keeping it is still right: it
    states the rule where the rule is read, and the arms are what the next
    change might remove. But the asymmetry is real, and without it someone
    will eventually read "1 red" as a gap and go looking for a test that
    cannot exist.
    """

    def _stored(self, status, dep, arr):
        """A trip already in the database with `status`, reloaded for editing."""
        doc = self.new_trip(status=status,
                            departure_datetime=dep, arrival_datetime=arr)
        self.rows[doc.name] = {k: v for k, v in vars(doc).items()
                               if not k.startswith("_") and k != "doctype"}
        return self.new_trip(**copy.deepcopy(self.rows[doc.name]))

    def test_a_completed_trip_still_running_by_the_clock_stays_completed(self):
        """The bug the owner's answer fixes.

        "Complete Trip" on a trip that is running persists Completed (that is
        TestAnExplicitStatusChangeSurvivesTheSave). This is the *next* save of
        that document -- someone edits the notes -- where the status is
        unchanged, so the explicit-change guard does not fire and derivation
        used to put it back to In Progress.
        """
        doc = self._stored("Completed", RUNNING_DEP, RUNNING_ARR)
        doc.notes = "receipts attached"
        self.save(doc)
        self.assertEqual(self.stored(), "Completed")

    def test_a_completed_trip_whose_departure_is_in_the_future_stays_completed(self):
        doc = self._stored("Completed", FUTURE_DEP, FUTURE_ARR)
        doc.notes = "cut short"
        self.save(doc)
        self.assertEqual(self.stored(), "Completed")

    def test_a_cancelled_trip_stays_cancelled_for_every_date_window(self):
        for dep, arr in ((FUTURE_DEP, FUTURE_ARR),
                         (RUNNING_DEP, RUNNING_ARR),
                         (PAST_DEP, PAST_ARR)):
            with self.subTest(dep=dep):
                self.rows.clear()
                doc = self._stored("Cancelled", dep, arr)
                doc.notes = "edited"
                self.save(doc)
                self.assertEqual(self.stored(), "Cancelled")

    def test_a_terminal_trip_can_still_be_reopened_by_hand(self):
        """The rule must not turn Completed into a one-way door.

        This is the explicit-change guard, and what it needs is to *exist*:
        deleting it goes red. An earlier version of this docstring said it
        also had to run *before* the terminal check, or that check "would
        also refuse the user's own correction". That was wrong. Both guards
        do nothing but `return`, so whichever of them fires, derivation is
        skipped and the hand-set value is what gets written -- swapping them
        is an equivalence, and `faults.py` carries it as a control rather
        than a fault. Fault injection is what said so; reading it did not.
        """
        doc = self._stored("Completed", RUNNING_DEP, RUNNING_ARR)
        doc.status = "In Progress"
        self.save(doc)
        self.assertEqual(self.stored(), "In Progress")

    def test_a_non_terminal_status_is_still_refreshed(self):
        """What the owner's answer deliberately left alone."""
        doc = self._stored("Planned", RUNNING_DEP, RUNNING_ARR)
        doc.notes = "edited"
        self.save(doc)
        self.assertEqual(self.stored(), "In Progress")

    def test_a_new_trip_created_as_cancelled_keeps_it(self):
        """Insert has no previous document, so the per-branch checks carry it.

        Pins the part of the old guard this change left in place: if those
        `!= "Cancelled"` arms were removed on the strength of the new
        previous-status check, a trip created as Cancelled would silently be
        derived to whatever its dates say.

        One case per arm. The rule is written out three times -- once in each
        arm -- and this test used to exercise only the past one: dropping the
        exclusion from the future arm or the running arm left this whole file
        green. A rule written three times is guarded three times or not at
        all.
        """
        for dep, arr in ((FUTURE_DEP, FUTURE_ARR),
                         (RUNNING_DEP, RUNNING_ARR),
                         (PAST_DEP, PAST_ARR)):
            with self.subTest(dep=dep):
                self.rows.clear()
                self.save(self.new_trip(status="Cancelled",
                                        departure_datetime=dep,
                                        arrival_datetime=arr))
                self.assertEqual(self.stored(), "Cancelled")

    def test_terminal_statuses_are_real_options_on_the_doctype(self):
        module = self.module
        with open(DOCTYPE_JSON, encoding="utf-8") as fh:
            fields = json.load(fh)["fields"]
        options = next(f for f in fields
                       if f["fieldname"] == "status")["options"].split("\n")
        self.assertEqual(sorted(module.TERMINAL_STATUSES),
                         ["Cancelled", "Completed"])
        for value in module.TERMINAL_STATUSES:
            self.assertIn(value, options,
                          "a terminal status the Select cannot hold would "
                          "never be reached")


if __name__ == "__main__":
    unittest.main()
