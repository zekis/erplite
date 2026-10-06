# -*- coding: utf-8 -*-
"""Afterz's timesheet workflow, driven through erplite's real controller.

Afterz (crew.tierneymorris.com.au/afterz, repo zekis/afterz) is used every day and
must always work. It never calls erplite code -- but it creates and saves
`Timesheet Entry`, `Project` and `Activity` rows directly, so erplite's controller
hooks, fields and permissions all reach it. That makes Afterz a **gate on erplite
changes**, not a downstream consumer of them, and nothing in this repo's test suite
represented it until this file.

## What this caught

Commit e585a5b (mine) moved the check-out auto-submit out of `on_update` into
`before_save`:

    if self.check_in_time and self.check_out_time and self.status == "Draft":
        self.status = "Submitted"

The move was right about the mechanism -- an assignment in `on_update` lands after
`db_update()` has written the row and is discarded -- and wrong about the hook.
`before_save` runs on **every** save of the document, by anyone, and Afterz hands
it a Draft row with both times already set on all five of its timesheet paths:

| Afterz call (afterz/afterz_api.py)         | what it does                        | under e585a5b                              |
|--------------------------------------------|-------------------------------------|--------------------------------------------|
| `create_timesheet_entry` (:44)             | insert Draft, both times set        | **locked Submitted on creation**           |
| `update_timesheet_entry` (:88)             | move/resize the block, save         | **locked Submitted on first edit**         |
| `submit_week_entries` (:271)               | filter `status == "Draft"`          | **finds nothing: "No draft entries found"**|
| `reject_entry_with_reason` (:443)          | `status = "Draft"`, then `save()`   | **back to Submitted in the same save**     |
| `unapprove_entry` (:477)                   | `status = "Draft"`, then `save()`   | **back to Submitted in the same save**     |

The last two are the worst of it, and worse than "could not go back to Draft":
the save succeeds, the rejection notes are written, and the status the hook leaves
behind is `Submitted` -- so a reject silently **re-queues the entry it just
rejected**, and it reads as if the approver's click did nothing. No exception,
nothing in the Error Log.

The fix is not to put the rule in a different hook. It is that `status` is a
workflow state other apps own, not a derived field, so no hook on the save path
may assign it. erplite's `check_out()` is the one caller that genuinely means
"submit this now", and it now says so itself, before it saves.

## What is NOT asserted here

That these are the exact lines Afterz runs today. The tests below pin the
**workflow Afterz performs** -- a Draft entry with both times can be created,
edited, submitted in a week batch, rejected back to Draft and un-approved back to
Draft -- rather than any line number in it. Those five states are what the UI is
built on; a change in Afterz's internals does not change them.

That choice has since paid for itself, and the measurement is worth recording
because the version it replaces was wrong. This file used to say Afterz "was last
pushed 15 Aug 2025 (dd78fe0), so the deployed copy may differ" -- a date read off
GitHub at the time. Afterz is now one of the office's repositories and it moves
daily: its default branch is **develop**, whose tip was `caa000d` on 6 Oct 2026,
three merged pull requests after that claim. Every line number in the table above
had moved with it (`create_timesheet_entry` 38 -> 44, `update_timesheet_entry`
82 -> 88, `submit_week_entries` 246 -> 271, `reject_entry_with_reason` 360 -> 443,
`unapprove_entry` 394 -> 477). **Not one of the five behaviours had.** Read from
`origin/develop` at `caa000d`: `submit_week_entries` still filters
`'status': 'Draft'`, and `reject_entry_with_reason` and `unapprove_entry` still
assign `doc.status = 'Draft'` and save.

So the line numbers below are a sketch of where to look, not a claim, and they
are the part of this file to distrust. The five states are the claim.

`TestNoSaveHookOwnsStatus` is the general form, and it is the one that stops this
recurring: it fails if any pre-save hook on Timesheet Entry assigns `status` again,
whichever hook it is.

These tests run without a bench. See fake_frappe.py for the stand-in.
"""

import ast
import copy
import datetime
import importlib.util
import os
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

DOCTYPE_DIR = os.path.join(APP_ROOT, "erplite", "projects", "doctype", "timesheet_entry")
CONTROLLER = os.path.join(DOCTYPE_DIR, "timesheet_entry.py")

NOW = datetime.datetime(2026, 10, 7, 17, 30, 0)


class TickingClock(object):
    """`now_datetime()` must advance between calls, not be frozen.

    erplite's own flow is check_in() then check_out(), and each calls
    now_datetime() once. With a frozen clock the two timestamps are equal and
    validate_times() throws "Check Out Time must be after Check In Time" -- so a
    frozen clock makes the check-out test fail for a reason that has nothing to
    do with what it is testing. Still deterministic: fixed start, fixed step.
    """

    STEP = datetime.timedelta(hours=1)

    def __init__(self, start=NOW):
        self.at = start

    def __call__(self):
        value = self.at
        self.at = self.at + self.STEP
        return value

# A working day inside the submit-week window, both ends set -- the shape Afterz
# creates when an activity is dragged onto the calendar.
DAY_IN = datetime.datetime(2026, 10, 6, 9, 0, 0)
DAY_OUT = datetime.datetime(2026, 10, 6, 10, 0, 0)

EMPLOYEE = "pat@company.test"
APPROVER = "pat@company.test"


def load_controller(frappe, clock):
    """Import the real timesheet_entry.py against the stand-in."""
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

    def get_datetime(value):
        if isinstance(value, datetime.datetime):
            return value
        return datetime.datetime.fromisoformat(str(value))

    utils = types.ModuleType("frappe.utils")
    utils.now_datetime = clock
    utils.get_datetime = get_datetime
    utils.getdate = lambda v: get_datetime(v).date()
    utils.nowdate = lambda: NOW.date().isoformat()
    utils.time_diff_in_hours = lambda a, b: (
        (get_datetime(a) - get_datetime(b)).total_seconds() / 3600.0
    )
    frappe_pkg.utils = utils
    frappe_pkg.now_datetime = utils.now_datetime

    sys.modules["frappe"] = frappe_pkg
    sys.modules["frappe.model"] = model
    sys.modules["frappe.model.document"] = document
    sys.modules["frappe.utils"] = utils

    spec = importlib.util.spec_from_file_location(
        "erplite_timesheet_entry_under_test", CONTROLLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, frappe_pkg


class WorkflowTestCase(unittest.TestCase):
    """Drives frappe's save() ordering over the real controller.

    Ported from frappe-version-15 `Document._save()` / `Document.insert()`:

        insert():  run_before_save_methods() -> db_insert()  -> run_post_save_methods()
        _save():   check_if_latest() -> run_before_save_methods() -> db_update()
                   -> run_post_save_methods()

    Only the pre-save half can persist a field, which is the whole point.
    """

    def setUp(self):
        self.frappe = FakeFrappe(session_user=EMPLOYEE)
        self.clock = TickingClock()
        self.module, self.frappe_pkg = load_controller(self.frappe, self.clock)
        self.rows = {}
        self.counter = 0
        self.frappe.tables["Timesheet Entry"] = []
        self.frappe.tables["Project"] = [
            _dict(name="5gofgdoomv", project_name="Novalith", status="Open",
                  timesheet_approver=APPROVER),
        ]
        # The controller's module-level functions use frappe.get_doc; the stand-in
        # does not provide one, so serve it from our own row store.
        self.frappe_pkg.get_doc = self._get_doc

    # -- the driver ----------------------------------------------------------

    def _blank(self, is_new=True, **data):
        """A controller instance, standing for an insert or for a later save.

        `is_new` is not decoration: frappe sets `__islocal` only inside
        `insert()` (document.py:390), so a hook guarded by `self.is_new()` runs
        on creation and never on a save of a stored row. A harness that built
        both the same way would drive an insert-only rule on every save -- and
        it did: the first version of this method made every document new, and
        the approver tests below then failed on a rule that cannot reach them.
        """
        return make_doc(self.module.TimesheetEntry, "Timesheet Entry",
                        "projects", "timesheet_entry", data, is_new=is_new)

    def _get_doc(self, arg, name=None):
        """frappe.get_doc, both shapes: a dict (new doc) or (doctype, name)."""
        if isinstance(arg, dict):
            data = {k: v for k, v in arg.items() if k != "doctype"}
            doc = self._blank(**data)
            doc.insert = lambda: self.insert(doc)
            doc.save = lambda: self.save(doc)
            return doc
        if arg == "Project":
            for row in self.frappe.tables["Project"]:
                if row.name == name:
                    project = _dict(copy.deepcopy(dict(row)))
                    # Serving only what the DocType declares. The live Project
                    # declares timesheet_approver and project_lead, never
                    # project_manager, so a controller reading the removed field
                    # fails here rather than quietly reading an orphan column.
                    return project
            raise ValidationError("no Project %r" % (name,))
        stored = self.rows.get(name)
        if stored is None:
            raise ValidationError("no Timesheet Entry %r" % (name,))
        # A stored row is NOT new, whatever is done to it next.
        doc = self._blank(is_new=False, **copy.deepcopy(stored))
        doc.insert = lambda: self.insert(doc)
        doc.save = lambda: self.save(doc)
        return doc

    def _run_pre_save(self, doc):
        for hook in ("before_validate", "validate", "before_save"):
            fn = getattr(type(doc), hook, None)
            if callable(fn):
                fn(doc)

    def _run_post_save(self, doc):
        for hook in ("on_update", "on_change"):
            fn = getattr(type(doc), hook, None)
            if callable(fn):
                fn(doc)

    def _persist(self, doc):
        snapshot = {k: v for k, v in vars(doc).items()
                    if not k.startswith("_")
                    and k not in ("doctype", "save", "insert")}
        self.rows[doc.name] = snapshot
        self.frappe.tables["Timesheet Entry"] = [
            _dict(copy.deepcopy(r)) for r in self.rows.values()
        ]

    def insert(self, doc):
        self.counter += 1
        doc.name = doc.name or "TSE-2026-%05d" % self.counter
        doc._doc_before_save = None          # load_doc_before_save: None when new
        self._run_pre_save(doc)
        self._persist(doc)                   # db_insert(): the row is written HERE
        self._run_post_save(doc)
        self._persist_nothing_after_write(doc)
        return doc

    def save(self, doc):
        stored = self.rows.get(doc.name)
        doc._doc_before_save = (
            self._blank(**copy.deepcopy(stored)) if stored is not None else None)
        self._run_pre_save(doc)
        self._persist(doc)                   # db_update(): the row is written HERE
        self._run_post_save(doc)
        self._persist_nothing_after_write(doc)
        return doc

    def _persist_nothing_after_write(self, doc):
        """Post-save hooks do not write the parent row again. Deliberately a no-op.

        Named rather than omitted because its absence is the bug e585a5b was
        fixing: anything a post-save hook assigns is discarded here.
        """
        return None

    def stored(self, name):
        return _dict(copy.deepcopy(self.rows[name]))

    # -- Afterz's five calls, as afterz/afterz_api.py performs them -----------

    def afterz_create(self, **overrides):
        """afterz_api.create_timesheet_entry (:44 at caa000d): get_doc({...}).insert()."""
        data = dict(employee=EMPLOYEE, project="5gofgdoomv", activity="g68cfomvvu",
                    check_in_time=DAY_IN, check_out_time=DAY_OUT,
                    duration_hours=1, description="Working on: PO-0392",
                    status="Draft")
        data.update(overrides)
        doc = self._get_doc(dict(doctype="Timesheet Entry", **data))
        return doc.insert()

    def afterz_update(self, name, **kwargs):
        """afterz_api.update_timesheet_entry (:88 at caa000d): setattr then save()."""
        doc = self._get_doc("Timesheet Entry", name)
        for key, value in kwargs.items():
            if hasattr(doc, key) and key != "name":
                setattr(doc, key, value)
        return doc.save()

    def afterz_submit_week(self, employee, start, end):
        """afterz_api.submit_week_entries (:271 at caa000d)."""
        names = [r.name for r in self.frappe.get_all(
            "Timesheet Entry", fields=["name"],
            filters={"employee": employee, "status": "Draft",
                     "check_in_time": ["between", [start, end]]})]
        for name in names:
            doc = self._get_doc("Timesheet Entry", name)
            doc.status = "Submitted"
            doc.save()
        return len(names)

    def afterz_approve(self, name):
        """afterz_api.approve_all_entries, one entry's worth."""
        doc = self._get_doc("Timesheet Entry", name)
        doc.status = "Approved"
        doc.approved_by = APPROVER
        doc.save()
        return doc

    def afterz_reject(self, name, reason):
        """afterz_api.reject_entry_with_reason (:443 at caa000d)."""
        doc = self._get_doc("Timesheet Entry", name)
        doc.status = "Draft"
        doc.approved_by = APPROVER
        doc.approval_notes = "Rejected: %s" % reason
        doc.save()
        return doc

    def afterz_unapprove(self, name):
        """afterz_api.unapprove_entry (:477 at caa000d)."""
        doc = self._get_doc("Timesheet Entry", name)
        if doc.status != "Approved":
            raise ValidationError("Only approved entries can be un-approved")
        doc.status = "Draft"
        doc.approved_by = ""
        doc.approval_notes = "Un-approved by %s" % APPROVER
        doc.save()
        return doc


class TestAfterzWorkflow(WorkflowTestCase):
    """The workflow the owner described, step by step, each step asserted."""

    def test_create_leaves_the_entry_in_draft(self):
        """Dragging an activity onto the calendar must not lock it."""
        doc = self.afterz_create()
        self.assertEqual(
            self.stored(doc.name).status, "Draft",
            "Afterz inserts a Draft entry with both times; a save hook that "
            "auto-submits locks it the moment it is created, so it can never be "
            "edited or batch-submitted.")

    def test_create_still_derives_the_fields_that_are_derived(self):
        """The fix must not stop validate() doing its real job."""
        doc = self.afterz_create()
        row = self.stored(doc.name)
        self.assertEqual(row.duration_hours, 1.0)
        self.assertEqual(row.is_active, 0)
        self.assertEqual(row.employee, EMPLOYEE)

    def test_editing_a_draft_entry_keeps_it_draft(self):
        """Moving or resizing the block saves it again. Still the employee's."""
        doc = self.afterz_create()
        later_out = DAY_OUT + datetime.timedelta(hours=2)
        self.afterz_update(doc.name, check_out_time=later_out)
        row = self.stored(doc.name)
        self.assertEqual(row.status, "Draft")
        self.assertEqual(row.duration_hours, 3.0,
                         "the edit must still recalculate the duration")

    def test_many_edits_never_submit(self):
        doc = self.afterz_create()
        for hours in (2, 3, 4, 5):
            self.afterz_update(
                doc.name, check_out_time=DAY_IN + datetime.timedelta(hours=hours))
            self.assertEqual(self.stored(doc.name).status, "Draft")

    def test_submit_week_finds_the_draft_entries(self):
        """The regression the owner named: submit week found nothing."""
        first = self.afterz_create()
        second = self.afterz_create(
            check_in_time=DAY_IN + datetime.timedelta(days=1),
            check_out_time=DAY_OUT + datetime.timedelta(days=1))
        count = self.afterz_submit_week(
            EMPLOYEE, "2026-10-05 00:00:00", "2026-10-11 23:59:59")
        self.assertEqual(count, 2, "submit week must find both Draft entries")
        for name in (first.name, second.name):
            self.assertEqual(self.stored(name).status, "Submitted")

    def test_submit_week_persists_the_status(self):
        """Not only found -- the Submitted must survive the save.

        This is the half of e585a5b that was right: before the move, the status
        was assigned in on_update and discarded. Submit week does set it itself,
        before save(), so it persists either way -- but assert it, because it is
        the state approve/reject are gated on.
        """
        doc = self.afterz_create()
        self.afterz_submit_week(EMPLOYEE, "2026-10-05 00:00:00",
                                "2026-10-11 23:59:59")
        self.assertEqual(self.stored(doc.name).status, "Submitted")

    def test_reject_goes_back_to_draft_and_stays_there(self):
        """The silent one: reject landed on Submitted, re-queueing the entry."""
        doc = self.afterz_create()
        self.afterz_submit_week(EMPLOYEE, "2026-10-05 00:00:00",
                                "2026-10-11 23:59:59")
        self.afterz_reject(doc.name, "wrong activity")
        row = self.stored(doc.name)
        self.assertEqual(
            row.status, "Draft",
            "reject sets Draft then saves; a save hook that re-submits makes the "
            "rejection invisible and silently re-queues the entry for approval.")
        self.assertEqual(row.approval_notes, "Rejected: wrong activity")

    def test_a_rejected_entry_can_be_edited_and_resubmitted(self):
        """Reject is only useful if the employee can act on it."""
        doc = self.afterz_create()
        self.afterz_submit_week(EMPLOYEE, "2026-10-05 00:00:00",
                                "2026-10-11 23:59:59")
        self.afterz_reject(doc.name, "wrong activity")
        self.afterz_update(doc.name, activity="other-activity")
        self.assertEqual(self.stored(doc.name).status, "Draft")
        count = self.afterz_submit_week(EMPLOYEE, "2026-10-05 00:00:00",
                                        "2026-10-11 23:59:59")
        self.assertEqual(count, 1, "the corrected entry must be submittable again")
        self.assertEqual(self.stored(doc.name).status, "Submitted")

    def test_unapprove_goes_back_to_draft(self):
        doc = self.afterz_create()
        self.afterz_submit_week(EMPLOYEE, "2026-10-05 00:00:00",
                                "2026-10-11 23:59:59")
        self.afterz_approve(doc.name)
        self.assertEqual(self.stored(doc.name).status, "Approved")
        self.afterz_unapprove(doc.name)
        self.assertEqual(
            self.stored(doc.name).status, "Draft",
            "un-approve sets Draft then saves; a save hook that re-submits sends "
            "it straight back into the approval queue.")

    def test_the_whole_round_trip(self):
        """Create, edit, submit week, reject, fix, submit, approve, un-approve."""
        doc = self.afterz_create()
        week = ("2026-10-05 00:00:00", "2026-10-11 23:59:59")
        seen = [self.stored(doc.name).status]

        self.afterz_update(doc.name, description="PO-0392 systems engineering")
        seen.append(self.stored(doc.name).status)
        self.afterz_submit_week(EMPLOYEE, *week)
        seen.append(self.stored(doc.name).status)
        self.afterz_reject(doc.name, "book it to the right activity")
        seen.append(self.stored(doc.name).status)
        self.afterz_submit_week(EMPLOYEE, *week)
        seen.append(self.stored(doc.name).status)
        self.afterz_approve(doc.name)
        seen.append(self.stored(doc.name).status)
        self.afterz_unapprove(doc.name)
        seen.append(self.stored(doc.name).status)

        self.assertEqual(
            seen,
            ["Draft", "Draft", "Submitted", "Draft", "Submitted", "Approved",
             "Draft"],
            "the full Afterz round trip")


class TestErpliteCheckOutStillSubmits(WorkflowTestCase):
    """The behaviour e585a5b was fixing must still work, in its own flow."""

    def test_check_in_leaves_a_draft_active_entry(self):
        result = self.module.check_in("5gofgdoomv", "g68cfomvvu")
        self.assertTrue(result["success"], result)
        row = self.stored(result["timesheet_id"])
        self.assertEqual(row.status, "Draft")
        self.assertEqual(row.is_active, 1)

    def test_check_out_submits_and_the_status_persists(self):
        """The original bug: status assigned in on_update was discarded, so
        approve_timesheet() could never be entered."""
        created = self.module.check_in("5gofgdoomv", "g68cfomvvu")
        result = self.module.check_out(created["timesheet_id"])
        self.assertTrue(result["success"], result)
        self.assertEqual(
            self.stored(created["timesheet_id"]).status, "Submitted",
            "checking out is the explicit finish action, so it must submit -- and "
            "the value must survive the save, or approve_timesheet() refuses it "
            "with 'Only submitted timesheets can be approved'.")

    def test_check_out_does_not_overwrite_a_status_someone_else_set(self):
        """check_out only promotes a Draft, so it cannot undo an approval."""
        created = self.module.check_in("5gofgdoomv", "g68cfomvvu")
        doc = self._get_doc("Timesheet Entry", created["timesheet_id"])
        doc.status = "Approved"
        doc.save()
        self.module.check_out(created["timesheet_id"])
        self.assertEqual(self.stored(created["timesheet_id"]).status, "Approved")


class TestNoSaveHookOwnsStatus(unittest.TestCase):
    """The general rule, so this cannot come back in a different hook.

    `status` on Timesheet Entry is a workflow state that Afterz sets explicitly on
    five different paths. A hook on the save path cannot know which of them it is
    running inside, so no hook may assign it -- not `before_save`, not `validate`,
    not `on_update`. The callers that mean it say so themselves.
    """

    SAVE_HOOKS = (
        "before_validate", "validate", "before_save", "before_insert",
        "before_submit", "on_update", "on_change", "after_insert",
        "on_update_after_submit",
    )

    def test_no_hook_assigns_status(self):
        with open(CONTROLLER, "rb") as handle:
            tree = ast.parse(handle.read().decode("utf-8"))
        offenders = []
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            for meth in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
                if meth.name not in self.SAVE_HOOKS:
                    continue
                for node in ast.walk(meth):
                    targets = []
                    if isinstance(node, ast.Assign):
                        targets = node.targets
                    elif isinstance(node, ast.AugAssign):
                        targets = [node.target]
                    for tgt in targets:
                        if (isinstance(tgt, ast.Attribute)
                                and isinstance(tgt.value, ast.Name)
                                and tgt.value.id == "self"
                                and tgt.attr == "status"):
                            offenders.append(
                                "%s.%s() line %d" % (cls.name, meth.name,
                                                     tgt.lineno))
        self.assertEqual(
            offenders, [],
            "a save hook on Timesheet Entry assigns self.status: %s\n\n"
            "`status` is a workflow state Afterz sets explicitly on five paths "
            "(create, update, submit week, reject, un-approve), and a hook runs "
            "on all of them. Deriving it here locks entries on creation and turns "
            "reject and un-approve into no-ops that land back on Submitted.\n"
            "Put the rule in the caller that means it -- check_out() does."
            % ", ".join(offenders))

    def test_before_save_exists_and_is_a_no_op(self):
        """Keep the hook, so the next person finds the note in it."""
        with open(CONTROLLER, "rb") as handle:
            source = handle.read().decode("utf-8")
        tree = ast.parse(source)
        hooks = {m.name: m
                 for cls in tree.body if isinstance(cls, ast.ClassDef)
                 for m in cls.body if isinstance(m, ast.FunctionDef)}
        self.assertIn("before_save", hooks,
                      "before_save carries the note explaining why it is empty")
        body = [n for n in hooks["before_save"].body
                if not isinstance(n, ast.Expr)
                or not isinstance(n.value, ast.Constant)]
        self.assertTrue(
            all(isinstance(n, ast.Pass) for n in body),
            "before_save must stay a no-op; whatever it does runs on every "
            "Afterz save too")

    def test_check_out_is_where_the_submit_lives(self):
        """Pin the location, so a future tidy-up does not move it back."""
        with open(CONTROLLER, "rb") as handle:
            tree = ast.parse(handle.read().decode("utf-8"))
        check_out = next(
            (n for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name == "check_out"), None)
        self.assertIsNotNone(check_out, "check_out() has gone")
        submits = [
            n for n in ast.walk(check_out)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute) and t.attr == "status"
                    for t in n.targets)
        ]
        self.assertTrue(
            submits,
            "check_out() no longer sets status, so checking out leaves the entry "
            "Draft and approve_timesheet() refuses it")


class TestTheApprovalGate(WorkflowTestCase):
    """Who may approve a timesheet: `timesheet_approver`, not `project_manager`.

    `approve_timesheet` and `reject_timesheet` read the Project to decide who is
    allowed. They read `project_manager`, which 8126278 removed from the
    DocType, so the person Afterz shows an Approve button to -- the project's
    `timesheet_approver` -- was the one person refused. The owner chose
    `timesheet_approver` (review tray rev_e73092bfb5), which is the field Afterz
    already reads, so the two agree rather than merely stop erroring.

    How it failed before depended on the site, and neither way was visible:
    `Document.load_from_db` selects `*`, so where the orphan column survives in
    `tabProject` the gate compared against a stale value nothing maintains, and
    where it was never created the attribute lookup raised -- swallowed by the
    function's own `except Exception` into `{"success": False}`.

    `has_permission` is injected False throughout, so these measure the field
    rather than the `or not frappe.has_permission(...)` hatch beside it. One
    test pins that hatch on purpose.
    """

    STRANGER = "approver@company.test"
    NOBODY = "nobody@company.test"

    def setUp(self):
        super(TestTheApprovalGate, self).setUp()
        # APPROVER == EMPLOYEE in this file; the gate only means anything when
        # the approver is somebody other than whoever filled the timesheet in.
        self.frappe.tables["Project"] = [
            _dict(name="5gofgdoomv", project_name="Novalith", status="Open",
                  timesheet_approver=self.STRANGER),
        ]
        self.frappe_pkg.has_permission = lambda *a, **k: False

    def _submitted_entry(self):
        created = self.module.check_in("5gofgdoomv", "g68cfomvvu")
        name = created["timesheet_id"]
        self.module.check_out(name)
        self.assertEqual(
            self.stored(name).status, "Submitted",
            "the entry must be Submitted before approval is even reachable")
        return name

    def test_the_timesheet_approver_can_approve(self):
        name = self._submitted_entry()
        self.frappe.session.user = self.STRANGER
        result = self.module.approve_timesheet(name, "Looks right")
        self.assertTrue(result["success"], result["message"])
        row = self.stored(name)
        self.assertEqual(row.status, "Approved")
        self.assertEqual(row.approved_by, self.STRANGER)
        self.assertEqual(row.approval_notes, "Looks right")

    def test_the_timesheet_approver_can_reject(self):
        name = self._submitted_entry()
        self.frappe.session.user = self.STRANGER
        result = self.module.reject_timesheet(name, "Wrong activity")
        self.assertTrue(result["success"], result["message"])
        self.assertEqual(self.stored(name).status, "Rejected")

    def test_somebody_who_is_not_the_approver_is_refused(self):
        name = self._submitted_entry()
        self.frappe.session.user = self.NOBODY
        result = self.module.approve_timesheet(name)
        self.assertFalse(result["success"])
        self.assertIn("timesheet approver", result["message"])
        self.assertEqual(
            self.stored(name).status, "Submitted",
            "a refused approval must leave the entry where it was")

    def test_the_employee_is_not_the_approver_just_by_owning_the_entry(self):
        name = self._submitted_entry()
        result = self.module.approve_timesheet(name)   # session.user is EMPLOYEE
        self.assertFalse(result["success"])
        self.assertEqual(self.stored(name).status, "Submitted")

    def test_write_permission_still_approves_without_being_the_approver(self):
        """The `or not frappe.has_permission(...)` branch, pinned as it stands.

        Unchanged by this fix, and recorded so that changing it is a decision
        rather than an accident.
        """
        name = self._submitted_entry()
        self.frappe.session.user = self.NOBODY
        self.frappe_pkg.has_permission = lambda *a, **k: True
        result = self.module.approve_timesheet(name)
        self.assertTrue(result["success"], result["message"])

    # -- the reject half of the same gate ----------------------------------
    # Every test above drives `approve_timesheet`. `reject_timesheet` applies
    # the same rule from its own copy of the same two lines -- byte-identical
    # except for the word in the refusal -- and had one test, the happy path.
    # Fault injection found five regressions only reject could have, all green:
    # its gate deleted, inverted, warning instead of refusing, its
    # write-permission hatch removed, and its Submitted requirement dropped.
    # Two copies of a rule need two sets of tests; the second copy is free to
    # be wrong for exactly as long as nobody asks it the questions.

    def test_somebody_who_is_not_the_approver_cannot_reject(self):
        name = self._submitted_entry()
        self.frappe.session.user = self.NOBODY
        result = self.module.reject_timesheet(name, "not mine to judge")
        self.assertFalse(result["success"])
        self.assertIn("timesheet approver", result["message"])
        self.assertEqual(
            self.stored(name).status, "Submitted",
            "a refused rejection must leave the entry where it was -- a reject "
            "that half-happens takes the entry out of the approval queue "
            "without telling anyone it was rejected")

    def test_the_employee_is_not_the_rejecter_just_by_owning_the_entry(self):
        name = self._submitted_entry()
        result = self.module.reject_timesheet(name)   # session.user is EMPLOYEE
        self.assertFalse(result["success"])
        self.assertEqual(self.stored(name).status, "Submitted")

    def test_write_permission_still_rejects_without_being_the_approver(self):
        """reject's `or not frappe.has_permission(...)` hatch, pinned as it
        stands -- the mirror of the approve test above."""
        name = self._submitted_entry()
        self.frappe.session.user = self.NOBODY
        self.frappe_pkg.has_permission = lambda *a, **k: True
        result = self.module.reject_timesheet(name)
        self.assertTrue(result["success"], result["message"])

    def test_reject_records_who_rejected_and_why(self):
        name = self._submitted_entry()
        self.frappe.session.user = self.STRANGER
        self.module.reject_timesheet(name, "Wrong activity")
        row = self.stored(name)
        self.assertEqual(
            row.approved_by, self.STRANGER,
            "the entry must say who rejected it: the employee is being asked "
            "to change it and has to know who to ask about it")
        self.assertEqual(row.approval_notes, "Wrong activity")

    # -- both halves act only on a Submitted entry --------------------------
    # Nothing above ever offered either function an entry in another state, so
    # dropping the `!= "Submitted"` guard from either one was invisible. It
    # matters in both directions: approving a Draft signs off hours the
    # employee has not finished entering, and rejecting one sends back
    # something never submitted.

    def test_approve_refuses_an_entry_that_was_never_submitted(self):
        doc = self.afterz_create()
        self.assertEqual(self.stored(doc.name).status, "Draft")
        self.frappe.session.user = self.STRANGER
        result = self.module.approve_timesheet(doc.name)
        self.assertFalse(result["success"])
        self.assertIn("Only submitted", result["message"])
        self.assertEqual(self.stored(doc.name).status, "Draft")

    def test_reject_refuses_an_entry_that_was_never_submitted(self):
        doc = self.afterz_create()
        self.frappe.session.user = self.STRANGER
        result = self.module.reject_timesheet(doc.name)
        self.assertFalse(result["success"])
        self.assertIn("Only submitted", result["message"])
        self.assertEqual(self.stored(doc.name).status, "Draft")

    def test_the_gate_does_not_name_the_removed_field(self):
        """The fault-injection half, so a green run above means something.

        The stand-in serves Project only what the DocType declares, so putting
        `project_manager` back makes every test in this class fail. Asserting
        both halves: the field really is gone, and the controller really does
        read the chosen one.
        """
        self.assertNotIn("project_manager", self.frappe.fields["Project"])
        with open(CONTROLLER, "rb") as handle:
            source = handle.read().decode("utf-8")
        self.assertNotIn("project_manager", source)
        self.assertIn("project.timesheet_approver", source)



class TestCheckOutGuards(WorkflowTestCase):
    """check_out's two refusals, and the two validate() calls nothing drove.

    Found by fault injection (`tests/faultinject`, target `afterz_workflow`):
    deleting check_out's ownership check, its is_active check, the
    `validate_times()` call or the `check_overlapping_entries()` call left all
    22 tests in this file passing. Every entry the tests above build is
    well-formed, owned by the session user and alone on the clock, so the
    guards against the other cases were never asked anything.

    These are guards Afterz depends on rather than erplite niceties: Afterz
    inserts and saves Timesheet Entry rows directly, so the controller's checks
    are the only ones its rows meet.
    """

    OTHER = "someone.else@company.test"

    def _open_entry(self, when):
        """An entry with a check-in and no check-out: `is_active` 1."""
        doc = self._get_doc(dict(
            doctype="Timesheet Entry", employee=EMPLOYEE, project="5gofgdoomv",
            activity="g68cfomvvu", check_in_time=when, status="Draft"))
        return doc.insert()

    def test_check_out_refuses_somebody_elses_entry(self):
        created = self.module.check_in("5gofgdoomv", "g68cfomvvu")
        name = created["timesheet_id"]
        self.frappe.session.user = self.OTHER
        result = self.module.check_out(name, "finishing your work for you")
        self.assertFalse(result["success"])
        self.assertIn("your own", result["message"])
        row = self.stored(name)
        self.assertFalse(
            row.get("check_out_time"),
            "a refused check-out must not write a check-out time: it would "
            "close somebody else's entry and fix their billable hours")
        self.assertEqual(row.status, "Draft")
        self.assertEqual(row.is_active, 1)

    def test_check_out_refuses_an_entry_that_is_already_finished(self):
        created = self.module.check_in("5gofgdoomv", "g68cfomvvu")
        name = created["timesheet_id"]
        first = self.module.check_out(name)
        self.assertTrue(first["success"], first)
        finished = self.stored(name)

        again = self.module.check_out(name, "second go")
        self.assertFalse(again["success"])
        self.assertIn("not active", again["message"])
        self.assertEqual(
            self.stored(name).check_out_time, finished.check_out_time,
            "a second check-out must not rewrite the time: the clock has moved "
            "on, so it would silently inflate the hours on a submitted entry")

    def test_check_out_before_check_in_is_refused(self):
        """validate_times(). Every entry above is well-ordered, so dropping the
        call from validate() changed nothing any test could see."""
        with self.assertRaises(ValidationError) as caught:
            self._get_doc(dict(
                doctype="Timesheet Entry", employee=EMPLOYEE,
                project="5gofgdoomv", activity="g68cfomvvu",
                check_in_time=DAY_OUT, check_out_time=DAY_IN,
                status="Draft")).insert()
        self.assertIn("Check Out Time must be after", str(caught.exception))

    def test_a_second_open_entry_is_refused_as_an_overlap(self):
        """check_overlapping_entries().

        Driven by inserting directly rather than by calling check_in() twice,
        and that is the whole point: check_in() has an active-entry guard of its
        own, so going through it measures that guard and leaves the
        controller's untested. Afterz never calls check_in(), so the
        controller's is the only one its rows meet.
        """
        first = self._open_entry(DAY_IN)
        with self.assertRaises(ValidationError) as caught:
            self._open_entry(DAY_IN + datetime.timedelta(hours=3))
        message = str(caught.exception)
        self.assertIn("already has an active timesheet entry", message)
        self.assertIn(first.name, message,
                      "the refusal must name the entry to check out first")

    def test_a_finished_entry_is_not_an_overlap(self):
        """The other side of the same rule, so the fix for it cannot be
        'refuse everything': a closed entry must not block the next check-in."""
        self.afterz_create()
        later = self._open_entry(DAY_OUT + datetime.timedelta(hours=1))
        self.assertEqual(self.stored(later.name).is_active, 1)


class TestWhoseHoursTheseAre(WorkflowTestCase):
    """`employee` answers "whose hours are these", on every save Afterz makes.

    Both faults below were green across all 22 tests. The second is the one
    worth the class: all four of Afterz's approval-side calls save an entry
    whose `employee` is somebody else, so a `set_employee_default` that
    assigned instead of only filling a blank would re-book the hours against
    whoever clicked -- an approver's click silently transferring the time to
    themselves, with the entry still reading Approved.
    """

    OTHER = "someone.else@company.test"

    def test_a_blank_employee_becomes_the_session_user(self):
        doc = self.afterz_create(employee="")
        self.assertEqual(
            self.stored(doc.name).employee, EMPLOYEE,
            "an entry saved with no employee must be booked to whoever saved "
            "it; `employee` is what every week view and dashboard filters on, "
            "so a blank one is hours that belong to nobody")

    def test_saving_somebody_elses_entry_does_not_move_their_hours_to_you(self):
        doc = self.afterz_create()
        self.frappe.session.user = self.OTHER
        self.frappe_pkg.has_permission = lambda *a, **k: True
        self.afterz_approve(doc.name)
        row = self.stored(doc.name)
        self.assertEqual(row.status, "Approved")
        self.assertEqual(
            row.employee, EMPLOYEE,
            "approving an entry must not re-book it against the approver: "
            "`employee` is only ever defaulted when it is blank, never "
            "assigned, because every approval-side save in Afterz is a save of "
            "somebody else's row")

    def test_submitting_a_week_does_not_move_the_hours_either(self):
        """The same claim on the path that saves the most rows at once."""
        doc = self.afterz_create()
        self.frappe.session.user = self.OTHER
        self.frappe_pkg.has_permission = lambda *a, **k: True
        count = self.afterz_submit_week(
            EMPLOYEE, "2026-10-05 00:00:00", "2026-10-11 23:59:59")
        self.assertEqual(count, 1)
        self.assertEqual(self.stored(doc.name).employee, EMPLOYEE)


if __name__ == "__main__":
    unittest.main()
