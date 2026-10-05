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
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
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
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AugAssign):
                    targets = [node.target]
                else:
                    continue
                for tgt in targets:
                    if (isinstance(tgt, ast.Attribute)
                            and isinstance(tgt.value, ast.Name)
                            and tgt.value.id == "self"
                            and tgt.attr in fieldnames):
                        found.append((cls.name, meth.name, tgt.attr, tgt.lineno))
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

    # --- must NOT be findings ----------------------------------------------

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
