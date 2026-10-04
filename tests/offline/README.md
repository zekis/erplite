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

`test_doctype_metadata.py` is the fourth surface: the DocType JSONs themselves.
Same cause as the three above - a name that outlived the field it pointed at -
and a fourth distinct symptom. A `fetch_from: "<link>.<src>"` whose source no
longer exists reaches `BaseDocument.set_fetch_from_value`, which on a
Data/Text/Small Text target does

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

A loaded document is deliberately still out of scope: `frappe.get_doc(...)`
genuinely does carry orphan columns through `SELECT *`, so reading one there is
a stale value rather than a bug the DocType JSON can prove.

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
doc, which also meant dropping a `name` argument neither method accepts.

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
same shape as the `ast.walk`-descends-into-classes flaw in
`test_string_references.py`'s first draft. **A walker that decides what counts
as "this scope" needs a test for the scope boundary itself.**

## `test_raw_sql.py` - the query handed to `db.sql` must be a literal

The seventh surface guarded here, and the first where the fault is a security
bug rather than a broken feature. One blunt rule: **the first argument to
`frappe.db.sql` (and `sql_list` / `sql_value` / `multisql`) must be a plain
string literal** - never an f-string, a `.format()` call, a `%` expression, a
concatenation or a variable. Everything that varies belongs in the second
argument, `values`, which is the only thing Frappe escapes.

That is not a style preference. `db.sql`'s own docstring describes `values` as
"to be escaped and substituted in the query", and the query text reaches
`self._cursor.execute(query, values)` (frappe `database/database.py:230`) after
nothing but a `.strip()` and an `ifnull` -> `coalesce` regex. With no values
given, `values = None` and the driver executes the string verbatim. **Anything
spliced into the query string is SQL syntax, not data.**

It found one site, reachable from the browser:
`erplite/projects/doctype/activity/activity.py:30`, in the `@frappe.whitelist()`
function `get_activity_summary(project=None)`, interpolated the caller's
`project` straight into a quoted SQL string. Captured by running the real
function against a stub `frappe` that records the query - no database needed:

    project = "5gofgdoomv"           -> WHERE docstatus < 2 AND project = '5gofgdoomv'
    project = "O'Brien Engineering"  -> WHERE docstatus < 2 AND project = 'O'Brien ...'
    project = "x' OR '1'='1"         -> WHERE docstatus < 2 AND project = 'x' OR '1'='1'

Note the middle line before the dramatic one: **an ordinary business name with
an apostrophe breaks the query.** That is a correctness bug with no attacker in
the picture, and it is the cheaper half of the argument for fixing it.

Fixed by routing the query through `frappe.get_all`, which parameterises - the
same move commit 2eb630e made on this app's other raw queries.
`fields=["status", "count(*) as count"]` with `group_by="status"` is Frappe
core's own idiom for this shape (`frappe/desk/listview.py:72` and six more) and
`count` is in `ALLOWED_SQL_FUNCTIONS`. The `filters` dict the original author
had started building and then left unused is what the fix fills in, so it
honours the intent rather than replacing it.

**Why literal-or-not rather than "don't interpolate caller input":** deciding
whether a spliced value is caller-reachable needs dataflow, and a guard that
attempts it will be wrong in both directions. Literal-or-not is exact from the
AST alone, and the exception list is currently empty - the other 11 `db.sql`
sites in the app are already plain literals. If a query ever needs a dynamic
*identifier* (a table or column name, which cannot be parameterised), add an
explicit documented exception rather than loosening the rule, because at that
point someone has to think about escaping, which is the point.

Blind spots: only receivers that look like a database handle are swept
(`<x>.db.sql(...)` or a bare `db.sql(...)`), and a handle reached through an
alias the walker cannot see is listed as *skipped* rather than silently
dropped. This says nothing about `order_by` / `group_by` / `having` passed to
`get_all`, which Frappe sanitises - checked by hand on 6 Oct 2026, no
whitelisted endpoint in this app passes caller input to any of them. And a
literal query is not necessarily a correct one: whether its columns exist is
`test_undeclared_attributes.py` and `test_doctype_metadata.py`.

`TheWalkerItself` holds 17 self-tests - every accepted shape and every rejected
one, plus the two scope cases. Third guard in a row to ship with its own
boundary tests, after the two walker bugs those caught.
