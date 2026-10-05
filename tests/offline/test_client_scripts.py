# -*- coding: utf-8 -*-
"""Guard: no client form script sets a field its own DocType does not declare.

The Python guards in test_undeclared_attributes.py cover the server side. This is the same bug
class on the browser side, and it is NOT silent -- which is what makes it worth its own test.

Frappe's `frm.set_value` (frappe/public/js/frappe/form/form.js, version-15) ends its inner `_set`
with:

    } else {
        frappe.msgprint(__("Field {0} not found.", [f]));
        throw "frm.set_value";
    }

`fieldobj` comes from `me.fields_dict[f]`, which is built from the DocType's CURRENT field list, so
a field that has been removed from the JSON is simply absent. The user gets a modal error dialog
and the handler aborts at that point.

Note the asymmetry in that function, because it decides whether a call is dangerous:

    if (typeof field == "string")      -> _set(field, value)            // NO guard
    else if ($.isPlainObject(field))   -> if (me.get_field(f)) ...      // guarded, silently skips

So `frm.set_value('gone', x)` throws, while `frm.set_value({gone: x})` quietly does nothing. Only
the string form is checked here; the object form cannot fail this way.

Three live instances of this were found and removed on 5 Oct 2026, all on ordinary actions:

  * Project, `refresh`        -> "Field project_manager not found." when opening a NEW Project
                                 (restored on `timesheet_approver` once the owner chose it,
                                  review tray rev_e73092bfb5; the guard below covers it)
  * Activity, `status`        -> "Field progress_percent not found." when setting status Completed
  * Timesheet Entry, check_in -> "Field date not found." on every check-in time entered

Each guard was reachable because the condition protecting it tested the same missing field:
`!frm.doc.date` on an undeclared field is `!undefined`, i.e. always true. A fourth
(`estimated_hours` on Activity) was unreachable for the mirror-image reason -- `if (frm.doc.x && ...)`
on an undeclared field is always false -- and was removed too, since an unreachable call to a
throwing path is still not something to leave lying about.

WHAT THIS GUARD DELIBERATELY DOES NOT COVER, so the next reader knows where to look:

  * `frm.doc.<field>` READS of removed fields. There are still 13 in activity.js and one
    `add_fields` in project_list.js. They are inert -- `undefined` is falsy, so the branches
    guarded by them never run -- and whether Activity should have `priority`, `due_date`,
    `estimated_hours` and `progress_percent` at all is a product question, not a rename. Asserting
    on them would make this file red today, and a red test is worth nothing.
  * `frappe.model.set_value(cdt, cdn, field, value)` in child-table handlers. `cdt` is a runtime
    variable, so the DocType cannot be known statically. All three in the app were checked by hand
    on 5 Oct and target declared fields.
  * JS outside `*/doctype/<x>/`: public/js/*, www/*, and the Vue app under frontend/src. None of
    them uses `frm.set_value` at all (they go through the REST API instead, which is the separate
    Scheduler.vue question). Checked on 5 Oct; this is the blind spot to re-check first if this
    class reappears.
  * The built bundles under erplite/public/frontend/assets. They are minified build output, not
    source; changing source does not change them until someone rebuilds.
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODULE_ROOT = os.path.join(APP_ROOT, "erplite")
sys.path.insert(0, HERE)

from test_undeclared_attributes import _app_doctypes  # noqa: E402

# Frappe's standard columns: on every table, never in the DocType JSON.
STD_FIELDS = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "parent", "parentfield", "parenttype", "_assign", "_comments", "_user_tags", "_liked_by",
    "amended_from", "naming_series",
}

SET_VALUE = re.compile(r"""\bfrm\.set_value\(\s*['"](\w+)['"]""")


def _client_scripts():
    """[(path, DocType, declared fieldnames)] for every form/list script in the app.

    A client script's DocType is given by where it lives: erplite/<module>/doctype/<x>/<x>.js is
    the script for the DocType defined by <x>.json beside it. That is what makes this check exact
    rather than a grep -- no name matching, no guessing.
    """
    doctypes = _app_doctypes()
    paths = doctypes.pop("__paths__", {})
    by_dir = {os.path.abspath(p): n for n, p in paths.items()}

    out = []
    for dirpath, _dirs, files in os.walk(MODULE_ROOT):
        doctype = by_dir.get(os.path.abspath(dirpath))
        if not doctype:
            continue
        declared = doctypes.get(doctype, set()) | STD_FIELDS
        for fn in sorted(files):
            if fn.endswith(".js"):
                out.append((os.path.join(dirpath, fn), doctype, declared))
    return out


class ClientScriptFieldsTest(unittest.TestCase):
    def test_client_scripts_exist_to_be_checked(self):
        """If the walk finds nothing the real test below would pass vacuously."""
        scripts = _client_scripts()
        self.assertGreater(
            len(scripts), 20,
            "expected the app's doctype client scripts to be found; got %d" % len(scripts),
        )

    def test_no_client_script_sets_a_field_its_doctype_does_not_declare(self):
        """frm.set_value('<removed field>', ...) shows the user an error and aborts the handler."""
        offenders = []
        for path, doctype, declared in _client_scripts():
            with open(path, encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    for m in SET_VALUE.finditer(line):
                        field = m.group(1)
                        if field not in declared:
                            offenders.append(
                                "%s:%d  frm.set_value('%s', ...) but %s does not declare '%s'"
                                % (
                                    os.path.relpath(path, APP_ROOT),
                                    lineno,
                                    field,
                                    doctype,
                                    field,
                                )
                            )

        self.assertEqual(
            [], offenders,
            "client scripts set fields their DocType does not declare. Frappe's frm.set_value "
            "raises 'Field <x> not found.' and aborts the handler for an unknown fieldname, so "
            "each of these is a modal error dialog on a real user action -- not dead code.\n  "
            + "\n  ".join(offenders),
        )

    def test_no_client_script_names_the_removed_project_manager(self):
        """The regression net for the four client-side query sites.

        The structural check above keys a script to the DocType of the folder it
        lives in, which is exactly right for `frm.set_value` and no use at all
        for a script that queries a *different* DocType by name --
        `frappe.db.get_value('Project', ...)` in timesheet_entry.js,
        `frappe.db.get_list('Project', {filters})` in timesheet_entry_list.js,
        and `add_fields` / `route_options` in project_list.js. All four named
        `project_manager`, removed from Project by 8126278, and all four moved
        to `timesheet_approver` (review tray rev_e73092bfb5).

        Those four cannot be checked structurally without parsing JS, so this
        pins the one field instead. It is narrow on purpose: it cannot report a
        pre-existing violation it was not written for, and it fails the moment
        the removed field comes back anywhere in a client script.
        """
        offenders = []
        for path, _doctype, _declared in _client_scripts():
            with open(path, encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    if "project_manager" in line:
                        offenders.append(
                            "%s:%d  %s"
                            % (os.path.relpath(path, APP_ROOT), lineno, line.strip())
                        )
        self.assertEqual(
            [], offenders,
            "`project_manager` is not a field on Project. A client script that "
            "filters or fetches it reads an orphaned column -- `bench migrate` "
            "drops no columns -- so it matches stale values nothing maintains, "
            "or nothing at all. Use `timesheet_approver`.\n  "
            + "\n  ".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
