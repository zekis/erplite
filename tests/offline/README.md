# Offline tests

Tests that run without a Frappe bench, a site or a database. `frappe` is
replaced by a small in-memory stand-in (`fake_frappe.py`), so these can run on
a laptop or in CI:

    python3 -m unittest discover -s tests/offline -p 'test_*.py' -v

They are deliberately kept out of the `erplite` package so that
`bench run-tests --app erplite` does not pick them up and try to run them
against a real site, where the stand-in would be wrong.

## Why the stand-in is stricter than Frappe

`frappe.get_all` in Frappe 15 does not check field names against the DocType
at all. `DatabaseQuery.sanitize_fields` only screens for SQL injection and
`Engine._apply_filter` only rejects special characters in a filter name;
neither compares the name to the DocType's fields. The name goes into the SQL,
so what happens next is the database's decision, not Frappe's:

| query | real Frappe | this stand-in |
|---|---|---|
| unknown field in `fields` | stale value if the column is still there, otherwise `Unknown column` | raises `UnknownField` |
| unknown field in `filters` | valid SQL, matches nothing | raises `UnknownField` |
| unknown `order_by` | accepted, orders by an unmaintained column | raises `UnknownField` |
| unknown field in `db.set_value` | writes into the orphaned column, or fails | raises `UnknownField` |

An earlier version of this file said an unknown field "returns the key with
value `None`". That was the comfortable version and it was wrong: `None` is
just what an empty orphaned column happens to hold. Which of the two outcomes
you get depends on the site's migration history rather than on the code, and
neither reaches the Error Log. That is how the Activity `subject` /
`assigned_to` bug stayed invisible: the columns are still in `tabActivity` but
are no longer fields on the DocType. Raising here turns that class of bug into
a red test.

Writes were unchecked here for the same reason reads were unchecked in Frappe,
until the Schedule Entry work needed them: a `set_value` naming a removed
field is worse than a dead read, because it puts a value into a column nothing
maintains.

## Documents, not just queries

`make_doc()` builds a DocType controller the way Frappe builds a new document,
because *which attributes a document has* is its own source of bugs. Frappe
gives a document an attribute only for a field the DocType actually declares:
`BaseDocument.__init__` sets what is in the dict it is handed,
`init_valid_columns()` fills in the rest from `meta.get_valid_columns()` (the
DocType's field list, not the table's columns), and neither `BaseDocument` nor
`Document` defines `__getattr__`.

So the two cases differ, and the difference decides the symptom:

- a document **built in memory** has no attribute for a removed field, and
  `self.<field>` raises `AttributeError` - so creating a record fails outright;
- a document **loaded from the database** picks the orphaned column up through
  `load_from_db`'s `SELECT *`, so `self.<field>` quietly returns a stale value.

Every new record goes through the first case. That is why the leftover
`self.task` in the Schedule Entry controller broke creation rather than merely
reading nonsense.

`fake_frappe.doctype_fields()` reads the field list out of the DocType's own
JSON in this repo rather than hard-coding it, so these tests follow the
DocType as it changes.

There is deliberately no `frappe.db.sql`. Raw SQL goes straight to the table,
so it reads orphaned columns without complaint and cannot be checked against
the DocType at all - which is how the scheduler ended up selecting six of
them. Code that needs to be covered here queries through `get_all`.

## `test_post_save_field_writes.py` — a field write in a post-save hook is lost

Frappe writes the parent row in the *middle* of a save, not at the end.
`Document._save()` runs `run_before_save_methods()`, then `db_update()`, then
`run_post_save_methods()`; `insert()` runs `db_insert()`, then `after_insert()`.
Nothing after the write touches the parent row again. So `self.field = value` in
`on_update`, `on_submit`, `on_cancel`, `on_change`, `on_update_after_submit` or
`after_insert` changes only the in-memory document and is then discarded.

Nothing errors and nothing reaches the Error Log, and the attribute reads back
correctly for the rest of the request — so it looks like it worked. The next load
shows the old value.

The case it was written for: `Timesheet Entry.on_update` set `status = "Submitted"`
once check-out completed, and `approve_timesheet()` opens with `if timesheet.status
!= "Submitted": frappe.throw("Only submitted timesheets can be approved")`. The
approval path could never be entered. The giveaway is in the same file: `validate()`
sets `is_active` and `duration_hours` and both persist; `on_update` set `status` and
it did not.

A post-save hook that also calls `self.db_update()`, `self.db_set()`, `self.save()`
or `frappe.db.set_value()` is not reported — `Payment Entry` does this correctly.
That check is per hook rather than per field, so a hook that persists one field and
loses another is a false negative. That is the right way round: the first version of
this walker reported `Payment Entry`'s two correct lines as bugs, and reading the
file is what caught it. A missed case costs nothing; a confidently wrong finding
sends someone to rewrite working code.

`PENDING_DECISION` pins the four Sales Invoice / Purchase Invoice entries that are
awaiting an owner decision (review tray **rev_7b11901cfb**): making their status
persist changes whether an invoice reaches Xero as DRAFT or AUTHORISED, which is a
question about real accounts rather than about code. Pinning the exact set keeps the
guard green today while still turning red on a *new* lost write, and
`test_pending_decision_entries_still_exist` fails if the list outlives what it
documents.

## `test_afterz_timesheet_workflow.py` — the consumer the suite could not see

Erplite is not the only app writing these records. **Afterz**
(`crew.tierneymorris.com.au/afterz`, repo `zekis/afterz`) is used every day to
book and approve time. It never calls erplite's Python, but it creates and saves
`Timesheet Entry`, `Project` and `Activity` documents directly, so every
controller hook in this app runs on its rows.

That makes erplite's real interface the *documents*, not its function signatures,
and a guard built only from the inside cannot see it. The commit this file was
written for proves the point: moving the status write out of `on_update` and into
`before_save` satisfied every check in this suite and broke five Afterz paths,
because `before_save` fires on the way through every save and so overrode the
status the caller had just set:

| afterz/afterz_api.py | symptom |
|---|---|
| `create_timesheet_entry` | locked to Submitted on creation |
| `update_timesheet_entry` | locked to Submitted on the first edit |
| `submit_week_entries` | filters `status == "Draft"`, finds nothing |
| `reject_entry_with_reason` | sets Draft, saved back to Submitted in the same save |
| `unapprove_entry` | sets Draft, saved back to Submitted in the same save |

The last two are the worst of them: the save succeeds and the rejection notes are
written, so it reads as though the approver's click did nothing while the entry is
silently re-queued for approval.

The rule that follows, and what this file pins: **a workflow state is not a derived
field.** `status` is set explicitly by several different callers, and a save hook
cannot tell which caller it is inside, so no hook may own it. `check_out()` sets
Submitted itself, because that is the one caller that means it.

These tests drive the real controller through the stand-in's save ordering over all
five Afterz paths plus the full Draft → Submitted → Approved round trip. They are
written against the **workflow** rather than against line numbers, because Afterz
has its own release cycle and the deployed copy may differ from GitHub's.
## Whole-app guards

`test_undeclared_attributes.py` does not test one module. It parses the whole
app and fails if anything reads a field its DocType does not declare, in
either of the two places that failure lives:

- `self.<x>` in a DocType's own controller, with the call graph walked out
  from the new-document hooks (`validate`, `before_insert`, ...) so a helper
  that `validate()` calls is reported as the creation-breaking kind rather
  than the merely stale kind;
- `doc = frappe.new_doc("X")` ... `doc.<y>` anywhere in the app, which is
  where the whitelisted endpoints live.

Both are deliberately conservative: a name is only reported if it is declared
nowhere in the DocType JSON, is never assigned on the object, and is not a
Frappe `Document` attribute. A failure is therefore a real finding, and the
right response is to fix the read rather than to add an exception for it.

Neither guard can see a DocType this app does not define, because the field
list of a Frappe core DocType is not in this repo. The second one skips those
rather than guessing at them.

`test_client_scripts.py` is the same idea on the browser side, and the failure
there is louder. Frappe's `frm.set_value` ends its inner `_set` with

    frappe.msgprint(__("Field {0} not found.", [f]));
    throw "frm.set_value";

for a fieldname the form does not know, so setting a field the DocType no
longer declares is a modal error dialog plus an aborted handler - not the
silent stale read that a query gives you. Note that only the string form is
dangerous: `frm.set_value({x: 1})` is guarded by `me.get_field(f)` and skips
quietly, while `frm.set_value('x', 1)` goes straight through.

A client script's DocType is taken from where it lives -
`erplite/<module>/doctype/<x>/<x>.js` belongs to the DocType defined by
`<x>.json` beside it - which is what makes the check exact rather than a grep.

Its own blind spots are listed in the module docstring and are worth reading
before concluding this class is gone: `frm.doc.<field>` reads (inert, and a
product question on Activity), `frappe.model.set_value(cdt, cdn, ...)` on
child tables (the DocType is a runtime variable), and JS outside the doctype
folders - `public/js`, `www`, and the Vue app - which uses the REST API
instead and is not covered here at all.
