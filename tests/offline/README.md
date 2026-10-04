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
