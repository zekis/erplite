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
either of the two places an *attribute* read lives (the field names inside a
**query** are a separate surface with its own sweep, `test_query_fields.py`
below — this file does not cover them and never did):

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

## The DocType JSONs themselves

`test_doctype_metadata.py` is the fourth surface: the DocType JSONs
themselves. Same cause as the three above - a name that outlived the field it
pointed at - and a fourth distinct symptom. A `fetch_from: "<link>.<src>"`
whose source no longer exists reaches `BaseDocument.set_fetch_from_value`,
which on a Data/Text/Small Text target does

    get_default_df(src) or frappe.get_meta(doctype).get_field(src)

and, finding neither, calls `frappe.throw(title="Wrong Fetch From value")`.
That runs inside `_validate_links` during save, so every save of a document
whose link field is set fails. Mind the fieldtype gate: on any other fieldtype
the stale value is assigned quietly instead, so the same broken reference is
loud or silent depending on the field it lands in.

The five passes check that every `fetch_from` resolves, that `Table` options
name an `istable` DocType, that `sort_field`/`title_field`/`search_fields`
exist, that `field_order` and `fields[]` agree in both directions, and that
`depends_on` expressions name real fields. These are exact rather than
grep-like, because a DocType JSON's references resolve against that same JSON.

Its blind spot is references to DocTypes this app does not define (18 of them:
User, Country, Communication, Contact, Letter Head, ToDo), since a core
DocType's field list is not in this repo. That is a place to look, not a place
to stop - the four `fetch_from` references among them were checked by hand
against frappe/frappe version-15 and all resolve (Contact.email_id,
Contact.phone, Communication.sender, Communication.subject). Re-check them when
the Frappe version moves.

`test_undeclared_attributes.py` now has a third pass, and the reason is worth
recording. Its first two both filter on `ast.Load`, because the symptom being
hunted was `AttributeError`. WRITING an undeclared attribute has no symptom at
all: `doc.<x> = v` is an ordinary setattr, and `get_valid_dict()` then builds
the INSERT from `meta.get_valid_columns()` - the DocType's declared fields - so
the value is dropped with no error, no log line and no failed save, and the
caller is told it worked. Two whitelisted endpoints had been doing exactly that
in `schedule_row.py` for as long as the rename has existed, and they survived
three sweeps because every sweep filtered on the symptom rather than the cause.
The `ast.Store` twin found the second of them on its first run.

A loaded document is in scope for the write pass and out of scope for the two
read passes, and the asymmetry is the point. `frappe.get_doc("X", name)`
genuinely does carry orphan columns through `SELECT *`, so **reading** one is a
stale value rather than a bug the DocType JSON can prove. A **write** is
dropped either way, because `get_valid_dict()` builds the UPDATE from
`meta.get_valid_columns()` no matter how the document arrived — so every
load-then-modify endpoint was unguarded while the write pass inherited the read
sweep's scope. The write pass now resolves `get_doc("X", name)` as well.

Its safety rule also moved from "the name is bound exactly once" to "every
binding of the name agrees on the DocType". The old rule threw away the
unambiguous case of a name assigned twice from the same DocType, which is how a
dropped write to `Timesheet Entry.date` sat under this guard for several
sweeps: the update branch and the insert branch of one function each assigned
`timesheet_doc`, agreeing on the DocType, and the count rule skipped the
variable entirely. Anything unresolvable — a `for`, `with`, comprehension or
`except` binding, an import, an augmented assignment, a call no literal can be
read out of — still marks the name unresolved and drops it, so a disagreement
is never reported.

## String references: does the name point at anything at all?

`test_string_references.py` asks a different question from every sweep above
it. Those all ask "does this code name a field its DocType declares?". This one
asks "does this string name anything that exists?", because Frappe resolves a
lot of wiring by string at request time. A wrong name is not a syntax error and
not a failed import; it is a working app with a dead button.

Three passes, each verified against frappe/frappe version-15 rather than
reasoned about:

1. **Asset URLs.** Every `/assets/erplite/...` in live code must be a file the
   app ships. `sites/assets/<app>` is a *symlink* to `<app>/<app>/public`
   (`frappe/build.py`), so a file missing from the repo is missing on the live
   site - this is not a build-staleness question. `app_include_css` had been
   naming `css/timesheet-calendar.css`, deleted along with the rest of that
   feature in 8126278. `frappe/www/app.py:48` collects it, `app.html:25`
   renders it through `jinja_globals.include_style`, and `bundled_asset` passes
   a path starting with `/assets` and containing no `.bundle.` straight through
   to `abs_url`. Because `include_style` defaults to `preload=True` the path is
   also added to `frappe.local.preload_assets["style"]`, which
   `frappe/website/utils.py:586` turns into an HTTP `rel=preload` header, so it
   was **two 404s on every desk page load for every user** - and no exception,
   nothing in the Error Log. The mildest symptom of any surface swept so far,
   and by far the widest blast radius. Severity and blast radius are
   independent; it is worth not ranking one by the other.

2. **Dotted method paths resolve, at module level.**
   `frappe.handler.execute_cmd` does `method = get_attr(cmd)` and on any
   exception calls `frappe.throw(_("Failed to get method for command {0} with
   {1}"))`. `frappe.get_attr` is `getattr(get_module(modulename), methodname)`,
   so **the name must exist at module level**. A perfectly good, even
   `@frappe.whitelist()`-decorated, *class* method is unreachable this way.
   That trap accounted for four of the six findings, and it is the kind that
   survives review because the code looks right.

3. **Argument names.** Once pass 2 is green, the caller's argument names must
   be ones the function declares, or `frappe.call` raises `TypeError` when it
   maps `form_dict` onto the parameters. This pass exists because the Vue
   scheduler's bulk create was wrong *twice*: the method name was transposed
   (`create_bulk_schedule_entries` for `bulk_create_entries`) and the argument
   was `entries` where the function takes `entries_data`. Fixing only the name
   would have moved the failure rather than removing it.

The findings, all of them live and user-facing:
`create_bulk_schedule_entries` (called by the *deployed* Vue bundle, so pass 2
deliberately covers the minified bundles as well as the source);
`update_activity_progress` on every Schedule Entry status change, which has
never existed in any commit; and `extend_entries`, `duplicate_entry` and
`move_to_resource`, all class methods reached by dotted path. The last two were
already `@frappe.whitelist()`, so the server side was right and only the call
form was wrong - they now go through `run_doc_method` via `frm.call` with the
doc, which also meant dropping a `name` argument neither method accepts. All
six fixes are already in this branch's history (PR #5); what this file adds is
the guard that stops them coming back.

**Comments are stripped before anything is matched**, using `tokenize` for
Python and a string-aware scanner for JavaScript. This is not a detail: the
first draft reported 26 missing methods and 24 were Frappe's own commented-out
boilerplate in `hooks.py`. A naive `//` strip would also have eaten every line
containing `https://`. A sweep that cannot tell code from a comment gets
ignored, and one that is mostly false positives deserves to be.

Blind spots, stated so they are places to look rather than places to stop: a
method path assembled at runtime from a variable is invisible to all three
passes; pass 3 skips the minified bundles and any call form it cannot read
exactly, rather than guessing; and pass 1 only resolves this app's own
`/assets/erplite/...` prefix.

A note on checking JavaScript syntax after editing it: `esprima` (used to
confirm nothing was broken) is too old for ES2020, so it rejects optional
chaining (`?.`) and `static` class fields. Eight files in this app use them and
fail to parse under it *at HEAD, unmodified*. That is the tool's limit, not
breakage - but it means esprima cannot be used as a blanket "everything still
parses" check without that control run to compare against.

## Shadowing an import: Python's own scoping, not Frappe's

`test_shadowed_imports.py` is the sixth surface and the first that is about
**Python's rules rather than Frappe's**. A name assigned anywhere in a function
body is local for the *whole* body, so a function that imports a name at module
level, uses it, and only later assigns it raises `UnboundLocalError: cannot
access local variable 'x' where it is not associated with a value`. Nothing is
undefined: the name exists at module level and locally, and only the order is
wrong.

In a Frappe app the name this happens to is `_`. Every module does
`from frappe import _`, and `mime_type, _ = mimetypes.guess_type(x)` is ordinary
Python for throwing a value away.

    @frappe.whitelist()
    def download_file(file_path=None):
        try:
            ...
            if not file_path:
                frappe.throw(_("File path is required"))   # line 274: UnboundLocalError
            ...
            mime_type, _ = mimetypes.guess_type(filename)  # line 298: makes _ local
        except Exception as e:
            return {"success": False, "error": f"Download failed: {str(e)}"}

The blanket `except Exception` then reports it, so a download requested with no
path answered `Download failed: cannot access local variable '_' where it is
not associated with a value` instead of the message that was written and
translated for exactly that case. **The symptom misdirects: it reads like a
bug in the error handling rather than in the line that throws.**

Two passes. Pass A fails on a module-level import *used before* being assigned
locally, app-wide. Pass B is stricter and fails on **any** shadowing of `_`,
reachable or not, because the gap between latent and live is one added line
that nobody would think to check - the app had one of each, in neighbouring
functions of the same file.

Both are fixed by naming the discarded value (`_encoding`), which reads better
anyway.

Blind spots, as always stated as places to look: pass A compares line numbers,
not control flow, so a use reached first at runtime but written after the
assignment (a loop re-entry) is not flagged; only module-level *imports* are
considered, not module-level constants; and a nested `def _()` binds the name
without being flagged, since the nested scope is skipped.

`TestTheSweepItselfWorks` carries the two real shapes reduced to their smallest
source, plus the cases that must *not* be findings. That class earned its keep
immediately: `test_a_nested_function_is_its_own_scope` failed on the first run
and the bug was in the walker, not the app - it skipped nested functions when
expanding children but not when a nested `def` was a direct statement of the
body, so the inner function's assignment was attributed to the outer one. The
same class of mistake as any walker that confuses `ast.walk`'s "every node
below here" with "every node in this scope". **A walker that decides what
counts as "this scope" needs a test for the scope boundary itself.**

## `test_select_values.py` — a value the Select cannot hold

A Select field carries its whole permitted set in its own `options`, so this is
decidable from the DocType JSON. The two ways of getting it wrong have opposite
symptoms, which is why both halves are worth a guard.

A **write** of an unlisted value aborts the save: `_validate_selects`
(`base_document.py:892`) ends in `frappe.throw`, reached from `_validate()`
(`document.py:627`) on both the insert path (`:310`) and the save path (`:417`)
— after the controller's own hooks have run, so nothing a controller does can
rescue it. A **filter** on an unlisted value is never checked: it is valid SQL
against a value no row holds, so `==` matches nothing and `!=` matches
everything. One name, one loud failure and one silent one.

The sweep resolves the DocType from the call rather than guessing it from the
field name, and that narrowing is the work: an earlier version keyed by field
name and reported two false positives, because `reference_type` is a Link on
ToDo and a Select on Payment Entry.

The stand-in enforces the same rule, which is the uncomfortable half. It
refuses to serve a fixture row, or accept a filter or a write, carrying an
impossible Select value — and that turned existing tests red when it went in.
`test_projects_api` and `test_scheduler_api` each built a
`Project(status="Cancelled")` fixture to prove `!= "Cancelled"` excluded it,
and both passed. **The fixture described a row the real database cannot
contain, so the tests were green about a world that cannot happen.**

Fault injection then caught a weak test that review had not.
`test_archived_projects_are_excluded` asserted only `assertNotIn("dead01")`,
and it passed with the filter reverted, because the endpoint's
`except Exception` returns an error dict in which `"dead01"` is also absent.
**A test that asserts only an absence is satisfied by the endpoint failing
outright.** It names the projects that must be present as well now.

One measured blind spot: `get_daily_metrics` builds its filter in a variable
rather than a dict literal in the call, so a static rule cannot see it.

## `test_query_fields.py` — the field names inside a query

The surface every other sweep here left alone, and the one this app gets wrong
most often: two instances had been fixed one at a time
(`Activity.subject`/`assigned_to`, then `Timesheet Entry.date`) with nothing to
stop a third. This parses the whole app and checks every field name a query
names — `fields`, `pluck`, `filters` and `or_filters` in both the dict and the
list form, `order_by`, `group_by`, and the positional fieldname of
`get_value` / `get_values` / `set_value` / `get_single_value` — against the
DocType's declared fields plus the standard columns.

**The same mistake fails three different ways, and which one you get depends on
the call rather than on the mistake.** Line numbers below are frappe 15,
checked at 15.121.3:

| the field | the call | what happens |
|---|---|---|
| removed from the DocType | anything | **silent**: the column is still there, so the SQL is valid and reads a stale orphan. `frappe.model.delete_fields` is frappe's only `DROP COLUMN` and runs only from a hand-written patch, and this app's `patches.txt` declares none (just the two section headers) |
| never existed | `frappe.db.exists` | **silent, as None**: `exists` passes `ignore=True` (`database.py:1267`) and `get_values` turns a missing column into `out = None` when `ignore` is set (`:641-646`), which is indistinguishable from "no such record" |
| never existed | anything else | **loud**: `get_values` re-raises (`:654`) and `frappe.get_all` has no missing-column handling at all, so the caller's `except Exception` usually turns it into `{"success": False}` with no stack |

The second row is the nastiest, because a guard written as
`if frappe.db.exists(...): frappe.throw(...)` is then permanently off and looks
like it is working.

A filter on a *removed* field has a second effect worth stating separately: new
rows have NULL in the orphan column, because `get_valid_dict()` never writes a
column the DocType does not declare. So `filters={"<orphan>": ["between", ...]}`
silently excludes **every row written since the field was removed** — which is
what made the week timesheet view and the CSV export come back empty while
saving an entry reported success, since the endpoint echoes the date back out of
its own input rather than out of the record. Fixing the filter without fixing
the reads would have turned that empty list into an exception: rows with a NULL
date start matching, and `entry.date.strftime(...)` was unguarded. **The two
halves of an orphan have to be fixed together.** (That one is fixed earlier in
this chain; the sweep pins it so it cannot come back.)

Conservative in the same way as the other sweeps: it judges only a bare
identifier, so `count(name) as n`, `tabFoo.name`, `*`, `name as id` and
`distinct status` are skipped rather than guessed at, and only DocTypes this app
defines are judged. It also distinguishes the positional arguments per function,
because they disagree — the second positional of `get_all` is `fields`
(`DatabaseQuery.execute(fields, filters, ...)`), while the second positional of
`get_value` is the name or filters and a **list** there is a list of names, not
of fields. Reading that one as fields is how a sweep invents findings.

Four findings are pinned open rather than fixed, because each needs a schema or
product decision that is not a test's to make — either the field goes onto the
DocType or the feature reading it comes out:

- `Account.on_trash` (`account.py:82`) guards against deleting an Account linked
  to a Xero Account via `db.exists("Xero Account", {"account": ...})`. `Xero
  Account` has never had an `account` field — it has `account_name`,
  `account_code` and `xero_account_id` — and there is no field linking the two
  DocTypes at all.
  Row two of the table above: the guard returns None and never fires.
- `TermsandConditions.validate_disabled` (`terms_and_conditions.py:19`) and
  `get_default_terms` (`:33`) both read `Company.default_terms`; Company has
  `default_currency`, `default_letter_head`, `default_holiday_list` and
  `is_default`, and has never had `default_terms`.
- `FinanceBook.get_default_finance_book` (`finance_book.py:33`) reads
  `Company.default_finance_book`, same again.

Each is pinned twice: once in `KNOWN`, so a **new** finding fails, and once as a
test of the schema fact it rests on, so adding the field fails too and says
which list to edit. The fix that shipped with this sweep is pinned the same way
(`Account` declares `currency`, never `account_currency`, so
`PaymentEntry.validate_accounts` asked on every save for a column that has never
existed — row three, loud: a Payment Entry with `paid_from` or `paid_to` set
could not be saved at all).

`TheSweepBites` holds 18 self-tests: every call shape and argument position that
must be reported, and every expression that must not be.
