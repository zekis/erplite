# -*- coding: utf-8 -*-
"""Declare the todo board's two extra ToDo statuses in code.

`Backlog` and `Planned` are two of the three columns the todo board is built
from, and they are not frappe's. Stock frappe ships ToDo/status as
`Open\\nClosed\\nCancelled` with default `Open`
(frappe/desk/doctype/todo/todo.json at v15.52.0). On
crew.tierneymorris.com.au the field holds five options with `Backlog` as the
default, and until this patch they existed **only as a hand-edited row in
`tabDocField` on that one database** -- nothing in erplite, no fixture, no
Property Setter, no frappe fork.

That is safe against a routine `bench migrate` and not safe against a frappe
upgrade. `sync_all()` is called with no arguments so `force=0`, and for a
DocType the only skip gate that applies is `migration_hash` against the hash of
the JSON on disk (`import_file.py:130-144`; the timestamp gate beside it is
explicitly `and doc["doctype"] != "DocType"`). An unchanged frappe means an
unchanged `todo.json` means an equal hash means the import is skipped -- the 17
ToDos sitting on `Planned` are the evidence for that rather than an inference.
But any frappe version bump changes `todo.json`, the hash differs,
`import_doc` runs, and `delete_old_doc` (258-276) drops the ToDo DocType with
its DocField children -- `ignore_doctypes = [""]` spares nothing -- and
reinserts frappe's three. The 17 Planned ToDos go off-list, `Backlog` stops
being the default, and two of the board's three columns empty. **Nothing errors
and nothing is logged.**

A Property Setter survives that, by design: `meta.py:138` calls
`apply_property_setters` on every meta load, those rows live in their own table,
and importing `todo.json` never touches them.

## What this patch does, and does not, change

It pins **the options the site already has**, read from the live meta, with
`Backlog` and `Planned` guaranteed to be in the list. So on
crew.tierneymorris.com.au today it writes the same five options the field
already holds: no option appears, disappears or moves, and no ToDo changes
status. The behaviour change is only in what happens to a frappe upgrade
afterwards. On a site that has already lost them (or a fresh install) the same
code puts them back.

Two consequences worth knowing:

  * **The authority for ToDo/status moves** from `tabDocField` to the Property
    Setter. A later hand-edit of `tabDocField` would be overridden on every meta
    load. Changing the statuses is now either a change to this app or an edit in
    Customize Form, which replaces these rows (same name, so frappe's
    delete-then-insert upserts them) and marks them as the user's.
  * **Both rows are marked `is_system_generated`**, because the app declares
    them rather than a user having customised them. That also keeps Customize
    Form's "Reset to defaults" from dropping the `default` row:
    `reset_customization` deletes every Property Setter on the DocType filtered
    `is_system_generated: False`, and its two exemptions are
    `property != "options"` and `field_name != "naming_series"`. The `options`
    row is spared by the first whatever it is marked; the `default` row on
    `status` is spared by neither, so unmarked it would be deleted there --
    silently, and this patch runs once.

Re-running is safe. The Property Setter name is
`{doc_type}-{field_name}-{property}`, and `PropertySetter.validate` deletes any
row for the same doc_type/field/property when a new one is inserted, so each
call is an upsert rather than a duplicate.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# What the board needs on top of whatever frappe ships. Order matters only for
# where they appear in the Select; the board's own column order is in
# erplite/public/js/todo/dragdrop/TodoDragDropManager.js.
EXTRA_STATUSES = ("Backlog", "Planned")

# The status a new ToDo gets. The board's first column is Backlog.
DEFAULT_STATUS = "Backlog"

# The live DocField on crew.tierneymorris.com.au, measured read-only 5 Oct 2026,
# recorded so a reviewer can see what this pins without reading the database.
# NOT used by the code below, which reads the live meta instead -- a constant
# here would overwrite any later change with a year-old snapshot.
MEASURED_OPTIONS = "Backlog\nPlanned\nOpen\nClosed\nCancelled"


def execute():
    status = frappe.get_meta("ToDo").get_field("status")

    _declare("options", options_with_extra_statuses(status.options))
    _declare("default", DEFAULT_STATUS)


def options_with_extra_statuses(options):
    """`options` with Backlog and Planned guaranteed to be in it.

    Pure, so it can be tested without a site. Existing options are kept
    verbatim, in their existing order, including a leading blank line if the
    field has one (in frappe that is what makes a Select allow no value).
    """
    lines = (options or "").split("\n")
    if lines == [""]:  # no options at all; do not leave a blank one behind
        lines = []

    present = {line.strip() for line in lines}
    missing = [status for status in EXTRA_STATUSES if status not in present]

    return "\n".join(missing + lines)


def _declare(property_name, value):
    setter = make_property_setter(
        "ToDo",
        "status",
        property_name,
        value,
        # The fieldtype of DocField.options and DocField.default, which is what
        # Customize Form passes and what `cast()` uses to read the value back.
        "Small Text",
        # Explicit rather than relying on `frappe.flags.in_patch`, which frappe
        # checks in PropertySetter.on_update for the same reason: a patch of
        # ours should not abort a migrate over an unrelated validation problem
        # in a core DocType it did not touch.
        validate_fields_for_doctype=False,
    )

    # Not an argument to make_property_setter, so it is set after the insert.
    setter.db_set("is_system_generated", 1, update_modified=False)
