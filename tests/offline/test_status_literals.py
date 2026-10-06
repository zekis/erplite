# -*- coding: utf-8 -*-
"""Whole-app guard: a client script never names a value its Select field cannot hold.

This is the browser-side half of `test_select_values.py`. That file asks the question of
Python -- is this literal one of the values the field is allowed to take -- for writes and
for query filters. The same mistake is just as available in a client script, and there it has
no server to abort it: nothing in frappe compares a string in a `.js` file to a DocType's
`options`, so a stale status name is valid JavaScript that quietly decides the wrong thing
forever.

Both halves are decidable offline, for the same reason: a `Select` field carries its whole
permitted set in its own `options`, and a client script's DocType is given by where the file
lives (`erplite/<module>/doctype/<x>/<x>*.js` belongs to `<x>.json` beside it). So this is an
exact check, not a grep -- no name matching and no guessing, which is the lesson
`test_select_values.py` records from its own first version.

## WHY THIS IS WORTH A TEST: the consequence depends on the shape, and the shapes look alike

The seven live instances found when this file was written (6 Oct 2026) covered three shapes
with three completely different outcomes. Reading the frappe source for each is the only way
to tell them apart, so each is recorded here next to the line it came from.

**1. A colour map read through `set_indicator_formatter` prints the word "undefined".**
`frm.set_indicator_formatter(fieldname, get_color)` installs a formatter on the docfield
(`frappe/public/js/frappe/form/form.js:1855`), and that formatter interpolates the callback's
return value straight into a class attribute with no fallback at all (form.js:1889):

    <a class="indicator ${get_color(doc || {})}" ...>

A map that misses returns `undefined`, so the element is rendered with
`class="indicator undefined"` -- not a colour frappe's stylesheet defines, so the indicator
loses its colour, and nothing is thrown or logged. The formatter is reached from
`frappe.format` wherever that docfield is rendered, because `df.formatter` takes precedence
over the fieldtype's standard formatter (`frappe/public/js/frappe/form/formatters.js:429`):

    var formatter = df.formatter || frappe.form.get_formatter(fieldtype);

Note that `set_indicator_formatter` mutates `frappe.meta.docfield_map`, which is shared, so
opening one form arms this for every later render of that field in the session.

**2. The same miss inside `listview_settings.get_indicator` is harmless -- or fatal -- and
which one depends on where the `undefined` sits.** `frappe.get_indicator` guards the call
(`frappe/public/js/frappe/model/indicator.js:88-91`):

    if (settings.get_indicator) {
        var indicator = settings.get_indicator(doc);
        if (indicator) return indicator;
    }

So a `get_indicator` that falls off the end and returns `undefined` is skipped, and the next
block down (indicator.js:98) renders the status text with `frappe.utils.guess_colour`. The
custom indicator simply has no effect. **But an `undefined` in the returned array survives
that guard**, because a non-empty array is truthy: `return [__(doc.status), MAP[doc.status],
...]` passes `if (indicator)` and `list_view.js:1115` interpolates element 1 into
`class="indicator-pill ${indicator[1]} ..."`, giving the same "undefined" class as shape 1.
Returning nothing is safe; returning a tuple with a hole in it is not.

**3. `!=` against a value the field cannot hold is always true.** This is the direction
`test_select_values.py` calls out as the dangerous one, and it reads as if it excludes
something:

    if (due_date < today && frm.doc.status != 'Completed')   // Activity has no 'Completed'

The option is `Complete`; `Completed` is a different string, so the condition never excludes
anything and the warning it guards fires for finished work too. One letter, no error.

## WHAT IS MEASURED, as of 6 Oct 2026

The sweep found **24** sites across the app's client scripts -- 20 comparisons and 4 lookups
keyed by a field -- and **7 of them named a value the field cannot hold**: the three Activity
shapes described above, and all four branches of `project_list.js`, which tested for "Active",
"Completed", "On Hold" and "Cancelled" on a field whose options are 'Opportunity', 'Estimate',
'Open' and 'Archived'. Not one of them had ever been reported, because not one of them raises.

The change that added this file fixed the two Activity literals and removed the two indicators
that were provably dead (see the comments left in their place for the proof in each case), which
leaves **19** sites: 16 comparisons and 3 lookups. 18 of the 19 are judged against the `options`
of the field named, on the DocType that owns the file; the one skipped is the `priority` map
covered under the exclusions below. Those counts are asserted as floors so that a site cannot
leave the sweep's reach without a word being said.

## WHAT THIS GUARD DELIBERATELY DOES NOT COVER, so the next reader knows where to look

  * **A field the DocType does not declare at all.** `priority_colors[frm.doc.priority]` in
    `activity.js` keys a map by a field Activity has not had for some time. That is the
    territory of `test_client_scripts.py`, whose docstring records the decision: Activity's
    `priority`, `due_date`, `estimated_hours` and `progress_percent` reads are inert
    (`undefined` is falsy, so the branches never run) and whether the DocType should have
    those fields is a product question, not a rename. Asserting on them would make this file
    red over something nobody has decided, so the sweep skips a field that is not a declared
    `Select` and says which of the two reasons applied.
  * **A literal that is a valid option but reached in the wrong order.** `timesheet_entry_list.js`
    names `Approved`, `Submitted` and `Rejected`, all three real, and sends everything else to
    an `else` labelled "Draft" with the filter `status,=,Draft`. `Scheduled` and `Processed`
    are real statuses that therefore read as "Draft" in the list. Every literal is legal, so
    this rule is silent on it by construction; it is a product question about what those two
    states should say, and it is in the owner's tray rather than guessed at here.
  * **Values held by rows written before an `options` change.** `_validate_selects` throws on
    save, so no new row can hold an unlisted value, but a row stored before the field's
    options were edited still can. A comparison to such a value is not dead for that row.
    This is why the dead-code removals in this change are described as no-ops *for every value
    the field can hold*, which is the strongest claim the JSON supports.
  * **Non-Select fields compared to literals.** A `Link` or `Data` field has no declared set,
    so there is nothing to check it against. Keying by field name across DocTypes instead
    would reintroduce exactly the false positives `test_select_values.py` removed.
  * **The built bundles under `erplite/public/frontend/assets`** and the Vue app under
    `frontend/src`: build output is not source, and the Vue app goes through the REST API
    rather than `frm`. Neither is walked here.
"""

import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
MODULE_ROOT = os.path.join(APP_ROOT, "erplite")
sys.path.insert(0, HERE)

# The floor: what a sweep of the tree found on 6 Oct 2026. Asserted so that a site cannot
# stop being judged in silence -- the failure this suite keeps meeting is a check that still
# passes after it has stopped looking at anything.
EXPECTED_SITES = {"compare": 17, "map": 3}
EXPECTED_TOTAL = 20

# doc.<field> or frm.doc.<field> tested against a string literal, either direction of
# equality. An empty literal is allowed through: `status != ''` is a presence test, not a
# claim about which values exist.
COMPARE = re.compile(r"""(?:frm\.)?doc\.(\w+)\s*(?:===?|!==?)\s*['"]([^'"]*)['"]""")

# A lookup keyed by the field's value: either an object literal written in place and indexed
# immediately, `{...}[doc.status]`, or a named one, `let m = {...}; ... m[frm.doc.status]`.
INDEX = re.compile(r"""\[\s*(?:frm\.)?doc\.(\w+)\s*\]""")
OBJ_ASSIGN = re.compile(r"""(?:let|const|var)\s+(\w+)\s*=\s*\{""")
OBJ_KEY = re.compile(r"""['"]([^'"]+)['"]\s*:""")
VAR_BEFORE = re.compile(r"""([A-Za-z_$][\w$]*)$""")


def _doctypes_by_folder():
    """{folder: (DocType, {select field: [options]}, {all declared fieldnames})}

    Read from the DocType JSONs themselves rather than from a list kept here, so that editing
    a field's options cannot leave this file asserting against a set nobody has any more.
    """
    out = {}
    for dirpath, _dirs, files in os.walk(MODULE_ROOT):
        for fn in files:
            if not fn.endswith(".json"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8") as fh:
                    doc = json.load(fh)
            except (ValueError, OSError):
                continue
            if not isinstance(doc, dict) or doc.get("doctype") != "DocType":
                continue
            name = doc.get("name")
            if not name:
                continue
            selects, declared = {}, set()
            for field in doc.get("fields") or []:
                if not isinstance(field, dict):
                    continue
                fieldname = field.get("fieldname")
                if not fieldname:
                    continue
                declared.add(fieldname)
                options = field.get("options")
                if field.get("fieldtype") == "Select" and options:
                    selects[fieldname] = str(options).split("\n")
            out[os.path.abspath(dirpath)] = (name, selects, declared)
    return out


def _object_literal_ending_at(text, close):
    """The source of the object literal whose closing brace is at index `close`."""
    depth = 0
    for i in range(close, -1, -1):
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            depth -= 1
            if depth == 0:
                return text[i:close + 1]
    return None


def _object_literal_assigned_to(text, var, before):
    """The source of the literal assigned to `var` most recently before index `before`."""
    found = None
    for match in OBJ_ASSIGN.finditer(text[:before]):
        if match.group(1) != var:
            continue
        depth = 0
        for i in range(match.end() - 1, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    found = text[match.end() - 1:i + 1]
                    break
    return found


def _sites():
    """[(shape, relpath, line, DocType, field, [literals], selects, declared)] for the app."""
    folders = _doctypes_by_folder()
    sites = []
    for dirpath, _dirs, files in os.walk(MODULE_ROOT):
        entry = folders.get(os.path.abspath(dirpath))
        if not entry:
            continue
        doctype, selects, declared = entry
        for fn in sorted(files):
            if not fn.endswith(".js"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, APP_ROOT)
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()

            for match in COMPARE.finditer(text):
                literal = match.group(2)
                if literal == "":
                    continue
                sites.append((
                    "compare", rel, text[:match.start()].count("\n") + 1,
                    doctype, match.group(1), [literal], selects, declared))

            for match in INDEX.finditer(text):
                head = text[:match.start()].rstrip()
                if head.endswith("}"):
                    source = _object_literal_ending_at(text, len(head) - 1)
                else:
                    var = VAR_BEFORE.search(head)
                    source = (_object_literal_assigned_to(text, var.group(1), match.start())
                              if var else None)
                if source is None:
                    continue
                sites.append((
                    "map", rel, text[:match.start()].count("\n") + 1,
                    doctype, match.group(1), OBJ_KEY.findall(source), selects, declared))
    return sites


SITES = _sites()


class TheSweepStillReachesTheClientScripts(unittest.TestCase):
    """Floors, so that the guard below cannot pass by having stopped looking."""

    def test_the_sweep_found_the_sites_measured(self):
        self.assertGreaterEqual(
            len(SITES), EXPECTED_TOTAL,
            "found %d sites where a client script names a value of a doc field, fewer than "
            "the %d measured on 6 Oct 2026. If a site was deliberately removed, lower the "
            "floor in the same change and say why." % (len(SITES), EXPECTED_TOTAL))

    def test_both_shapes_are_still_found(self):
        counted = {shape: 0 for shape in EXPECTED_SITES}
        for site in SITES:
            counted[site[0]] = counted.get(site[0], 0) + 1
        short = ["%s: %d, was %d" % (s, counted[s], EXPECTED_SITES[s])
                 for s in sorted(EXPECTED_SITES) if counted[s] < EXPECTED_SITES[s]]
        self.assertEqual(
            [], short,
            "a whole shape has gone quiet, which usually means its pattern stopped matching "
            "rather than that the code went away:\n  " + "\n  ".join(short))

    def test_a_select_field_is_actually_being_judged(self):
        """Both floors can be met while every site is skipped as a non-Select."""
        judged = [s for s in SITES if s[4] in s[6]]
        self.assertGreaterEqual(
            len(judged), 19,
            "only %d of %d sites name a declared Select field, so the rule below is nearly "
            "vacuous; 19 of 20 did on 6 Oct 2026" % (len(judged), len(SITES)))


class AClientScriptNamesOnlyValuesItsFieldCanHold(unittest.TestCase):
    def test_no_client_script_names_an_impossible_select_value(self):
        offenders = []
        for shape, rel, line, doctype, field, literals, selects, declared in SITES:
            options = selects.get(field)
            if options is None:
                continue  # not a declared Select -- see the docstring's exclusions
            bad = [lit for lit in literals if lit not in options]
            if not bad:
                continue
            offenders.append(
                "%s:%d  %s.%s %s %s, but its options are %s"
                % (rel, line, doctype, field,
                   "is compared to" if shape == "compare" else "is used to key",
                   ", ".join(repr(b) for b in sorted(bad)),
                   ", ".join(repr(o) for o in options)))
        self.assertEqual(
            [], sorted(offenders),
            "a client script names a value its Select field cannot hold. Depending on the "
            "shape this prints the word 'undefined' into a class attribute, has no effect at "
            "all, or inverts a condition -- none of them raise. Check the spelling against "
            "the DocType's options, and see this file's docstring for which shape does "
            "what:\n  " + "\n  ".join(sorted(offenders)))


if __name__ == "__main__":
    unittest.main()
