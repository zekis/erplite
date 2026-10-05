# -*- coding: utf-8 -*-
"""Whole-app guard: a controller must not assign to a DocType field in a hook that
runs *after* the row has been written.

Frappe writes the parent row in the middle of a save, not at the end. From
`frappe/model/document.py`, `Document._save()`:

    run_before_save_methods()   # before_validate, validate, before_save  -> persisted
    db_update()                 # <-- the row is written HERE
    update_children()
    run_post_save_methods()     # on_update, on_submit, on_cancel, on_change

and `Document.insert()` is the same shape: `db_insert()` first, then
`after_insert()`, then `run_post_save_methods()`. Nothing after the write touches
the parent row again -- `clear_cache`, `notify_update`, `update_global_search`,
`save_version` and `on_change` are all it does.

So `self.some_field = value` in a post-save hook changes the in-memory document
*after* its row has been written, and is then discarded. There is no error, nothing
reaches the Error Log, and the attribute reads back correctly for the rest of that
request -- so it looks like it worked. The next load of the document shows the old
value.

What this found when it was written (6 Oct 2026):

  * `projects/doctype/timesheet_entry/timesheet_entry.py` -- `on_update` set
    `status = "Submitted"` once check-out completed. Lost, so a checked-out
    timesheet stayed `Draft`, and `approve_timesheet()` opens with
    `if timesheet.status != "Submitted": frappe.throw("Only submitted timesheets
    can be approved")`. **The approval path could never be entered.**

    First fixed by moving the line into the existing (empty) `before_save`, and
    **that fix was wrong** -- see the correction below. It is now in `check_out()`,
    the one caller that means it, set before `save()`.
  * `projects/doctype/trip/trip.py` -- `on_update` derived
    `Planned`/`In Progress`/`Completed` from the trip's dates. Lost. Fixed the same
    way.
  * `accounts/doctype/sales_invoice/sales_invoice.py` and
    `accounts/doctype/purchase_invoice/purchase_invoice.py` -- `on_submit` sets
    `status = "Submitted"` (or `"Paid"`) and `on_cancel` sets `"Cancelled"`.
    **Still present on purpose**: see BASELINE below.

The giveaway in the timesheet case is worth keeping, because it is what makes this
class findable by reading: `validate()` sets `is_active` and `duration_hours` and
both persist; `on_update()` set `status` and it did not. Same document, same save,
two different outcomes, no error either way.

## The correction: a pre-save hook is not always the right home

This guard pins a **mechanism** -- do not assign a field after the row is written.
Satisfying it says nothing about whether the hook you moved the line *into* is the
right one, and twice now it was not:

  * **Timesheet Entry.** `before_save` runs on every save of the document, by
    anyone. Afterz (repo `zekis/afterz`) never calls erplite code but saves
    `Timesheet Entry` rows directly, and all five of its timesheet paths hand the
    hook a `Draft` row that already has both times -- so the rule locked entries
    on creation, left submit-week with nothing to find, and turned reject and
    un-approve into no-ops that landed back on `Submitted` in the same save.
    Pinned by `test_afterz_timesheet_workflow.py`.
  * **Trip.** The same commit broke the "Start Trip" / "Complete Trip" buttons,
    for the same underlying reason: deriving unconditionally before the write
    overwrote the value the user had just chosen. Pinned by `test_trip_status.py`.

Both are the same mistake. `status` in each case is a **workflow state someone
else sets explicitly**, not a derived field, and a save hook cannot tell which
caller it is running inside. The remedy is not a different hook: it is to put the
rule in the caller that means it, or to consult the pre-save document.

So a green run of this file is **not** evidence that a feature still works. It
only means no field write is being silently dropped.

## What counts as persisting

A post-save hook *may* legitimately write a field -- it just has to say so. If the
hook also calls `self.db_update()`, `self.db_set(...)`, `self.save()` or
`frappe.db.set_value(...)`, this guard treats the whole hook as persisting and does
not report it. `accounts/doctype/payment_entry/payment_entry.py` does exactly that:
it assigns `payment_status` in `on_submit`/`on_cancel` and calls `self.db_update()`
immediately after.

That check is deliberately coarse -- per hook, not per field -- so a hook that
persists one field and loses another is a false negative. Coarse-and-silent is the
right way round for a guard like this: a missed case costs nothing, and a
confidently wrong finding sends someone to rewrite working code. The first version
of this walker reported those two `payment_entry` lines as lost writes, and reading
the file is what caught it.

It is coarse on two more axes than "per hook" says, both measured on 6 Oct 2026
and both left as they are: the persisting call need not come **after** the
assignment, and it need not be **reachable**. Moving `self.db_update()` above the
line it was there to persist, or putting it under `if False:`, loses the write and
keeps this file green. Closing either means reading control flow, which is how a
guard like this starts producing confidently wrong findings, so they are named here
instead.

## What this cannot see

Everything below loses a field write and leaves this file green. Each one is known,
measured by `tests/faultinject` target `post_save_writes`, and left open on
purpose -- the fix needs control-flow or data-flow reasoning, and a wrong finding
costs more here than a missed one. They are listed so that a green run is read for
what it is.

  * `self.db_update()` before, or unreachable from, the assignment (above).
  * The write moved into a closure the hook calls immediately --
    `def _go(): self.status = x` then `_go()`. `walk_scope` skips nested scopes
    because a nested def may be a callback run somewhere else entirely, which is
    the right call for a callback and the wrong one here. Telling the two apart
    needs a call graph.
  * `self` bound to a local first -- `doc = self; doc.status = x`. Needs data flow.
  * A field named by anything but a string literal in a setter call:
    `self.set(fieldname, v)`, `self.update(values)`. Skipped rather than guessed
    at, for the same reason `test_select_values.py` skips a non-literal DocType.
  * A post-save hook attached through `doc_events` in `hooks.py` rather than
    declared on the controller. Such a hook is a **module-level function** taking
    `doc`, not `self`, so `test_a_module_level_function_is_not_a_hook` is pinning
    the right thing only while `doc_events` is unused. It is commented out in
    `erplite/hooks.py` today; if it is ever filled in, this sweep stops covering
    the app and that test's name becomes wrong.

## BASELINE, and why this test is green with known lost writes in the tree

The six Sales Invoice / Purchase Invoice lines are a **pending decision**, not an
oversight: `erplite/xero/accounts.py` chooses between a DRAFT and an AUTHORISED
invoice in Xero based on `status == "Submitted"`, so making the status persist
changes what appears in the owner's real accounts. That question is in the review
tray as **rev_7b11901cfb** with three options.

Rather than leave this guard unwritten until the answer lands, or make it pass by
asserting the bug is correct, the whole-app pass pins the *exact* set of lost
writes that are known and pending. So:

  * today it is green, with the pending set documented in code where it is visible;
  * a **new** lost write anywhere in the app turns it red immediately;
  * when rev_7b11901cfb is answered, `PENDING_DECISION` goes to `set()` and this
    paragraph goes with it.
"""

import ast
import json
import os
import unittest

APP_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "erplite")
)

# Hooks frappe runs after the parent row has been written.
# _save():   db_update()  -> run_post_save_methods() -> on_update / on_submit /
#                             on_cancel / on_update_after_submit / on_change
# insert():  db_insert()  -> after_insert() -> run_post_save_methods()
POST_SAVE_HOOKS = frozenset({
    "on_update",
    "on_submit",
    "on_cancel",
    "on_change",
    "on_update_after_submit",
    "after_insert",
})

# Calls that make a post-save write reach the database after all.
PERSISTING_CALLS = frozenset({
    "self.db_update",
    "self.db_set",
    "self.save",
    "frappe.db.set_value",
})

# Calls that set a field **in memory only**, so in a post-save hook they are
# lost exactly as a plain assignment is. A sweep that reads only `ast.Assign`
# sees none of them, which is what the fault run of 6 Oct 2026 found: each of
# these turned the whole file green with a field write being discarded.
#
#   self.set("status", x)          BaseDocument.set, base_document.py:228 --
#                                  ends in `self.__dict__[key] = value`
#   self.update({"status": x})     base_document.py:169-186, a loop into set()
#   self.update_if_missing({...})  base_document.py:189, the same loop
#
# `self.set` is deliberately NOT in PERSISTING_CALLS above: the names are one
# character apart and the behaviours are opposite -- `db_set` writes the row,
# `set` does not.
KEY_SETTERS = frozenset({"self.set"})
DICT_SETTERS = frozenset({"self.update", "self.update_if_missing"})

# Known lost writes awaiting the owner's decision in rev_7b11901cfb.
# (path relative to erplite/, class, hook, field)
PENDING_DECISION = frozenset({
    ("accounts/doctype/sales_invoice/sales_invoice.py",
     "SalesInvoice", "on_submit", "status"),
    ("accounts/doctype/sales_invoice/sales_invoice.py",
     "SalesInvoice", "on_cancel", "status"),
    ("accounts/doctype/purchase_invoice/purchase_invoice.py",
     "PurchaseInvoice", "on_submit", "status"),
    ("accounts/doctype/purchase_invoice/purchase_invoice.py",
     "PurchaseInvoice", "on_cancel", "status"),
})


def _dotted(node):
    """'self.db_update' for a Call's func, or None if it isn't a plain dotted name."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def walk_scope(node):
    """Yield nodes inside `node`, NOT descending into a nested def/lambda/class.

    A nested function is a different scope with its own `self` binding, and it may
    be a callback invoked somewhere else entirely, so an assignment inside one is
    not this hook's lost write. Skipping it costs a false negative and avoids a
    confidently wrong finding; `test_a_nested_function_is_not_this_hook` pins the
    boundary, because this is the third walker in this suite and the other two both
    got their scope boundary wrong first.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.Lambda, ast.ClassDef)):
            continue
        yield child
        for sub in walk_scope(child):
            yield sub


def _attr_targets(node):
    """Yield the `self.x` nodes a single binding statement writes to.

    Assignment is not the only way to bind a name, and the first version of this
    walker read `ast.Assign` and `ast.AugAssign` only. Tuple unpacking is the
    shape that matters in real code: `self.a, self.b = x, y` puts a single
    `ast.Tuple` in `targets`, and `isinstance(tgt, ast.Attribute)` on that Tuple
    is simply false -- so two lost writes on one line were invisible.

    `ast.NamedExpr` is absent on purpose rather than by oversight: Python will
    not parse `self.x := v` at all ("cannot use assignment expressions with
    attribute"), so there is no walrus case to cover.
    """
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.For, ast.AsyncFor)):
        targets = [node.target]
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        targets = [item.optional_vars for item in node.items if item.optional_vars]
    else:
        return
    while targets:
        tgt = targets.pop()
        if isinstance(tgt, (ast.Tuple, ast.List)):
            targets.extend(tgt.elts)
        elif isinstance(tgt, ast.Starred):
            targets.append(tgt.value)
        elif (isinstance(tgt, ast.Attribute)
                and isinstance(tgt.value, ast.Name)
                and tgt.value.id == "self"):
            yield tgt


def _setter_fields(node):
    """Yield the fieldnames a `self.set` / `self.update` / `setattr` call writes.

    A field named by anything but a string literal is skipped rather than
    guessed at -- `self.set(fieldname, v)` is unreadable offline, and a guess
    here would be a finding against code nobody can check by reading it.
    """
    if not isinstance(node, ast.Call):
        return
    dotted = _dotted(node.func)
    if dotted in KEY_SETTERS:
        if node.args and _str_literal(node.args[0]) is not None:
            yield _str_literal(node.args[0])
    elif dotted in DICT_SETTERS:
        if node.args and isinstance(node.args[0], ast.Dict):
            for key in node.args[0].keys:
                if _str_literal(key) is not None:
                    yield _str_literal(key)
    elif dotted == "setattr":
        if (len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "self"
                and _str_literal(node.args[1]) is not None):
            yield _str_literal(node.args[1])


def _str_literal(node):
    """The value of a string-literal node, or None if it is not one."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def is_doctype_controller_class(cls):
    """Whether a top-level class in a controller file can carry a frappe hook.

    A post-save hook is only a hook on a `Document`: frappe calls it through
    `run_post_save_methods`, so an `on_update` on a plain helper class is an
    ordinary method nobody calls, and reporting it would be the one outcome
    this file's rule rules out -- a confidently wrong finding.

    What this pins is narrow and deliberately so: **a class with no base class
    at all is not a DocType controller.** It does not try to decide whether a
    base *is* `Document`, because the safe answer when a base cannot be
    resolved offline is to keep looking at the class. Matching on a base named
    "Document" would silently stop reading a controller that inherits through
    any other name, and silent under-detection is the one failure a sweep
    cannot report. A helper class that does declare a base is therefore still
    reported; `test_a_helper_class_with_a_base_is_still_reported` pins that as
    the remaining false-positive surface rather than leaving it implied.
    """
    return bool(cls.bases)


def doctype_fields(doctype_dir):
    """Fieldnames declared by the DocType JSON sitting beside the controller."""
    for name in sorted(os.listdir(doctype_dir)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(doctype_dir, name), "rb") as fh:
                meta = json.loads(fh.read().decode("utf-8"))
        except (ValueError, OSError):
            continue
        if isinstance(meta, dict) and "fields" in meta:
            return {
                f["fieldname"]
                for f in meta["fields"]
                if isinstance(f, dict) and f.get("fieldname")
            }
    return set()


def lost_writes_in_source(source, fieldnames):
    """[(class, hook, field, lineno)] for assignments a post-save hook loses."""
    found = []
    tree = ast.parse(source)
    for cls in [n for n in tree.body
                if isinstance(n, ast.ClassDef) and is_doctype_controller_class(n)]:
        # only direct methods of the class: a method of a nested class is not a hook
        for meth in [n for n in cls.body
                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            if meth.name not in POST_SAVE_HOOKS:
                continue
            persists = any(
                isinstance(n, ast.Call) and _dotted(n.func) in PERSISTING_CALLS
                for n in walk_scope(meth)
            )
            if persists:
                continue
            for node in walk_scope(meth):
                for tgt in _attr_targets(node):
                    if tgt.attr in fieldnames:
                        found.append((cls.name, meth.name, tgt.attr, tgt.lineno))
                for field in _setter_fields(node):
                    if field in fieldnames:
                        found.append((cls.name, meth.name, field, node.lineno))
    return found


def sweep_app(app_root=APP_ROOT):
    """[(relpath, class, hook, field, lineno)] across every DocType controller."""
    results = []
    for dirpath, dirnames, filenames in os.walk(app_root):
        dirnames[:] = [d for d in dirnames if d not in ("public", "__pycache__", "node_modules")]
        if os.path.basename(os.path.dirname(dirpath)) != "doctype":
            continue
        fieldnames = doctype_fields(dirpath)
        if not fieldnames:
            continue
        for filename in sorted(filenames):
            if (not filename.endswith(".py")
                    or filename.startswith("test_")
                    or filename == "__init__.py"):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, "rb") as fh:
                source = fh.read().decode("utf-8", "replace")
            try:
                hits = lost_writes_in_source(source, fieldnames)
            except SyntaxError as exc:
                raise AssertionError("%s does not parse: %s" % (path, exc))
            rel = os.path.relpath(path, app_root).replace(os.sep, "/")
            for cls, hook, field, lineno in hits:
                results.append((rel, cls, hook, field, lineno))
    return results


class PostSaveFieldWrites(unittest.TestCase):
    """The whole-app pass."""

    def test_no_new_lost_writes(self):
        found = sweep_app()
        keys = {(rel, cls, hook, field) for rel, cls, hook, field, _ in found}
        new = keys - PENDING_DECISION
        if new:
            lines = []
            for rel, cls, hook, field, lineno in sorted(found):
                if (rel, cls, hook, field) in PENDING_DECISION:
                    continue
                lines.append(
                    "  %s:%d\n"
                    "      %s.%s() assigns self.%s, a field of its DocType, but that\n"
                    "      hook runs after db_update()/db_insert(), so the value is\n"
                    "      discarded. Move it into validate() or before_save(), or\n"
                    "      call self.db_set(\"%s\", ...) here."
                    % (rel, lineno, cls, hook, field, field)
                )
            self.fail(
                "%d field write(s) lost in a post-save hook:\n\n%s\n"
                % (len(lines), "\n".join(lines))
            )

    def test_pending_decision_entries_still_exist(self):
        """If an entry in PENDING_DECISION has gone, shrink the list.

        Stops the baseline outliving the thing it documents.
        """
        keys = {(rel, cls, hook, field) for rel, cls, hook, field, _ in sweep_app()}
        stale = PENDING_DECISION - keys
        self.assertEqual(
            stale, set(),
            "PENDING_DECISION names lost writes that are no longer in the tree: %s\n"
            "They have been fixed -- remove them from the list (and if it is now "
            "empty, delete it and the BASELINE note in this file's docstring)."
            % sorted(stale),
        )

    def test_the_pending_set_is_the_six_lines_it_documents(self):
        """Four entries stand for six lines, so count the lines as well.

        PENDING_DECISION keys a finding by (file, class, hook, field), and
        `SalesInvoice.on_submit` assigns `status` on two lines of its own -- one
        unconditionally, one under `if self.is_paid`. Both collapse into one
        key, so removing either was invisible to both tests above: the key
        survived, nothing went stale, and the pending set had quietly changed.
        The docstring's BASELINE note claims six lines; this is the claim.
        """
        lines = [row for row in sweep_app()
                 if (row[0], row[1], row[2], row[3]) in PENDING_DECISION]
        self.assertEqual(
            len(lines), 6,
            "the pending set is %d lines, not the six this file documents:\n%s\n"
            "If a pending lost write has been fixed or added, say so here and in "
            "the BASELINE note -- PENDING_DECISION keys cannot show it, because "
            "SalesInvoice.on_submit and PurchaseInvoice.on_submit each assign "
            "status twice under one key."
            % (len(lines), "\n".join("  %s:%d %s.%s -> %s"
                                     % (r[0], r[4], r[1], r[2], r[3])
                                     for r in sorted(lines, key=lambda r: (r[0], r[4])))),
        )

    def test_the_two_fixed_controllers_stay_fixed(self):
        """Neither may bring back an `on_update` that assigns a field.

        Note what this does and does not say. It pins that the lost-write
        mechanism has not returned. It does NOT say the remedy is `before_save`:
        for Timesheet Entry the rule now lives in `check_out()`, because a hook
        here runs on Afterz's saves too. `before_save` is still required to exist
        on both, since each carries the note explaining what belongs in it --
        for Timesheet Entry that note is the only warning against putting the
        auto-submit back. The behaviour is pinned by
        test_afterz_timesheet_workflow.py and test_trip_status.py.
        """
        for rel in ("projects/doctype/timesheet_entry/timesheet_entry.py",
                    "projects/doctype/trip/trip.py"):
            path = os.path.join(APP_ROOT, *rel.split("/"))
            with open(path, "rb") as fh:
                tree = ast.parse(fh.read().decode("utf-8"))
            hooks = {
                m.name
                for cls in tree.body if isinstance(cls, ast.ClassDef)
                for m in cls.body if isinstance(m, ast.FunctionDef)
            }
            self.assertIn("before_save", hooks, "%s lost its before_save" % rel)
            self.assertNotIn(
                "on_update", hooks,
                "%s has an on_update again -- a field assigned there is lost. "
                "Move it before the write, but check WHICH caller should own it: "
                "an unconditional rule in before_save runs on every save, "
                "including other apps' (see this file's correction note)" % rel,
            )


class WalkerSelfTests(unittest.TestCase):
    """The walker's own behaviour, including the cases that must NOT be findings."""

    FIELDS = {"status", "total", "note"}

    def found(self, source):
        return [(c, h, f) for c, h, f, _ in lost_writes_in_source(source, self.FIELDS)]

    # --- must be findings ---------------------------------------------------

    def test_plain_assignment_in_on_update(self):
        self.assertEqual(
            self.found(
                "class D(Document):\n"
                "    def on_update(self):\n"
                "        self.status = 'Submitted'\n"
            ),
            [("D", "on_update", "status")],
        )

    def test_every_post_save_hook_is_covered(self):
        for hook in sorted(POST_SAVE_HOOKS):
            with self.subTest(hook=hook):
                self.assertEqual(
                    self.found(
                        "class D(Document):\n"
                        "    def %s(self):\n"
                        "        self.status = 'x'\n" % hook
                    ),
                    [("D", hook, "status")],
                )

    def test_assignment_nested_in_control_flow(self):
        self.assertEqual(
            self.found(
                "class D(Document):\n"
                "    def on_submit(self):\n"
                "        if self.note:\n"
                "            for x in self.items:\n"
                "                try:\n"
                "                    self.status = 'Paid'\n"
                "                except Exception:\n"
                "                    pass\n"
            ),
            [("D", "on_submit", "status")],
        )

    def test_augmented_assignment_counts(self):
        self.assertEqual(
            self.found(
                "class D(Document):\n"
                "    def on_update(self):\n"
                "        self.total += 1\n"
            ),
            [("D", "on_update", "total")],
        )

    def test_frappes_own_setters_are_bindings(self):
        """`self.set`/`update`/`update_if_missing`/`setattr` lose the value the
        same way a plain assignment does -- see this file's KEY_SETTERS note."""
        for call, fields in (
            ("self.set('status', 'x')", [("D", "on_update", "status")]),
            ("setattr(self, 'status', 'x')", [("D", "on_update", "status")]),
            ("self.update({'status': 'x'})", [("D", "on_update", "status")]),
            ("self.update_if_missing({'status': 'x'})",
             [("D", "on_update", "status")]),
        ):
            with self.subTest(call=call):
                self.assertEqual(
                    self.found("class D(Document):\n"
                               "    def on_update(self):\n"
                               "        %s\n" % call),
                    fields,
                )

    def test_a_dict_setter_reports_every_field_in_the_dict(self):
        """The one shape that loses several fields on one line."""
        self.assertEqual(
            sorted(self.found(
                "class D(Document):\n"
                "    def on_update(self):\n"
                "        self.update({'status': 'x', 'total': 1, 'other': 2})\n")),
            [("D", "on_update", "status"), ("D", "on_update", "total")],
        )

    def test_tuple_and_list_unpacking_count(self):
        for target in ("self.status, self.total",
                       "[self.status, self.total]",
                       "self.status, (self.total,)",
                       "self.status, *self.total"):
            with self.subTest(target=target):
                self.assertEqual(
                    sorted(self.found(
                        "class D(Document):\n"
                        "    def on_update(self):\n"
                        "        %s = x\n" % target)),
                    [("D", "on_update", "status"), ("D", "on_update", "total")],
                )

    def test_an_annotated_assignment_counts(self):
        self.assertEqual(
            self.found("class D(Document):\n"
                       "    def on_update(self):\n"
                       "        self.status: str = 'x'\n"),
            [("D", "on_update", "status")],
        )

    def test_a_loop_or_with_target_counts(self):
        self.assertEqual(
            self.found("class D(Document):\n"
                       "    def on_update(self):\n"
                       "        for self.status in ['x']:\n"
                       "            break\n"),
            [("D", "on_update", "status")],
        )
        self.assertEqual(
            self.found("class D(Document):\n"
                       "    def on_update(self):\n"
                       "        with open('f') as self.note:\n"
                       "            pass\n"),
            [("D", "on_update", "note")],
        )

    # --- must NOT be findings ----------------------------------------------

    def test_a_setter_whose_field_is_not_a_literal_is_skipped(self):
        """Unreadable offline, so not guessed at. A false negative on purpose:
        the alternative is a finding nobody can check by reading the code."""
        for call in ("self.set(fieldname, 'x')",
                     "setattr(self, fieldname, 'x')",
                     "self.update(values)",
                     "self.update({fieldname: 'x'})"):
            with self.subTest(call=call):
                self.assertEqual(
                    self.found("class D(Document):\n"
                               "    def on_update(self):\n"
                               "        %s\n" % call),
                    [],
                )

    def test_self_set_is_not_treated_as_persisting(self):
        """`self.set` and `self.db_set` are one character apart and opposite.
        A hook that calls `set` has NOT persisted, so its write is still lost
        -- and the other assignment in the hook must still be reported."""
        self.assertEqual(
            sorted(self.found("class D(Document):\n"
                              "    def on_update(self):\n"
                              "        self.set('status', 'x')\n"
                              "        self.total = 1\n")),
            [("D", "on_update", "status"), ("D", "on_update", "total")],
        )

    def test_a_class_with_no_base_is_not_a_controller(self):
        """The false positive the 6 Oct fault run found: a plain helper class
        beside the controller, whose on_update frappe never calls."""
        self.assertEqual(
            self.found("class _Totals:\n"
                       "    def on_update(self):\n"
                       "        self.status = 'x'\n"),
            [],
        )

    def test_a_helper_class_with_a_base_is_still_reported(self):
        """The remaining false-positive surface, pinned rather than implied.

        `is_doctype_controller_class` only rules out a class with no bases,
        because deciding that a base *is* a Document cannot be done offline and
        guessing wrong would silently stop reading a real controller. So a
        helper class that subclasses anything is still swept. If this ever
        reports something real, the fix is to name the class, not to start
        matching base names.
        """
        self.assertEqual(
            self.found("class _Totals(object):\n"
                       "    def on_update(self):\n"
                       "        self.status = 'x'\n"),
            [("_Totals", "on_update", "status")],
        )

    def test_pre_save_hooks_are_fine(self):
        for hook in ("validate", "before_save", "before_submit", "before_insert"):
            with self.subTest(hook=hook):
                self.assertEqual(
                    self.found(
                        "class D(Document):\n"
                        "    def %s(self):\n"
                        "        self.status = 'x'\n" % hook
                    ),
                    [],
                )

    def test_a_hook_that_persists_is_fine(self):
        for call in ("self.db_update()",
                     "self.db_set('status', self.status)",
                     "self.save()",
                     "frappe.db.set_value('D', self.name, 'status', self.status)"):
            with self.subTest(call=call):
                self.assertEqual(
                    self.found(
                        "class D(Document):\n"
                        "    def on_submit(self):\n"
                        "        self.status = 'Submitted'\n"
                        "        %s\n" % call
                    ),
                    [],
                )

    def test_a_non_field_attribute_is_fine(self):
        """Post-save hooks legitimately set flags that are not DocType fields."""
        self.assertEqual(
            self.found(
                "class D(Document):\n"
                "    def on_update(self):\n"
                "        self.flags.ignore_x = True\n"
                "        self._cached = 1\n"
                "        self.not_a_field = 2\n"
            ),
            [],
        )

    def test_reading_a_field_is_fine(self):
        self.assertEqual(
            self.found(
                "class D(Document):\n"
                "    def on_update(self):\n"
                "        if self.status == 'Draft':\n"
                "            other.status = self.status\n"
            ),
            [],
        )

    def test_a_nested_function_is_not_this_hook(self):
        """The scope boundary. A nested def has its own `self`, and may be a
        callback run somewhere else, so its assignment is not this hook's."""
        self.assertEqual(
            self.found(
                "class D(Document):\n"
                "    def on_update(self):\n"
                "        def later(self):\n"
                "            self.status = 'Submitted'\n"
                "        register(later)\n"
            ),
            [],
        )

    def test_a_method_of_a_nested_class_is_not_a_hook(self):
        self.assertEqual(
            self.found(
                "class D(Document):\n"
                "    class Inner:\n"
                "        def on_update(self):\n"
                "            self.status = 'Submitted'\n"
            ),
            [],
        )

    def test_a_module_level_function_is_not_a_hook(self):
        self.assertEqual(
            self.found(
                "def on_update(self):\n"
                "    self.status = 'Submitted'\n"
            ),
            [],
        )

    def test_persisting_call_detection_is_per_hook_not_per_class(self):
        """db_update() in one hook must not excuse another hook."""
        self.assertEqual(
            self.found(
                "class D(Document):\n"
                "    def on_submit(self):\n"
                "        self.status = 'Submitted'\n"
                "        self.db_update()\n"
                "    def on_cancel(self):\n"
                "        self.status = 'Cancelled'\n"
            ),
            [("D", "on_cancel", "status")],
        )

    def test_dotted_helper_ignores_non_name_bases(self):
        self.assertIsNone(_dotted(ast.parse("f()[0].g").body[0].value))
        self.assertEqual(_dotted(ast.parse("self.db_update").body[0].value),
                         "self.db_update")


if __name__ == "__main__":
    unittest.main()
