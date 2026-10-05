# -*- coding: utf-8 -*-
"""Whole-app guard: a Select field is never given, or compared to, a value it cannot hold.

The other field sweeps in this folder ask whether a name exists -- does this DocType declare
this field, does this string name a real method. This one asks a narrower question about a
field that does exist: **is this one of the values the field is allowed to take?**

A `Select` field carries its whole permitted set in its own `options`, so this is decidable
offline from the DocType JSON. It is worth deciding, because the two ways of getting it wrong
have opposite and equally quiet symptoms:

  * **Writing** an unlisted value aborts the save. `Document._validate()` runs
    `_validate_selects()` (frappe-version-15/frappe/model/document.py:627, reached from
    `insert()` at :310 and from `_save()` at :417), and `_validate_selects`
    (base_document.py:892-920) ends in `frappe.throw` for any value not in `options`. Note the
    ordering: the controller's own `validate`/`before_save` hooks run *first*
    (`run_before_save_methods`, document.py:309 and :414), so a hook cannot see this coming and
    nothing a controller does can rescue it. If the caller wraps the save in `except Exception`
    -- which the whitelisted endpoints here do -- the abort is reported to the browser as a
    generic failure with HTTP 200, and `frappe.log_error(message)` records it without a stack.
    An endpoint that does this **cannot create a record for any input**.

  * **Filtering** on an unlisted value is valid SQL that quietly matches the wrong set.
    `frappe.get_all` does not compare filter values to `options` at all -- `Engine._apply_filter`
    only screens the filter *name* for special characters -- so the value goes into the WHERE
    clause and the database answers honestly about a value no row can hold. `== <impossible>`
    matches nothing; `!= <impossible>` matches everything, which is the dangerous direction,
    because the filter reads as if it excludes something and excludes nothing at all.

So the same mistake either kills a feature outright or widens a result set in silence, and
neither shows up as an error anywhere.

## Why the DocType is resolved from the call, not from the field name

A first version of this rule collected options by field *name* across every DocType and
flagged any literal that matched no DocType's options for that name. It reported two false
positives in `erplite/projects/api.py`: `{"reference_type": "Activity"}` on a ToDo query. That
is correct code -- `ToDo.reference_type` is a **Link to DocType** and will happily hold
"Activity" -- but `reference_type` is *also* a Select on Payment Entry, whose options are
payment kinds. Keying by name conflated two unrelated fields that happen to share one.

So this pass resolves the DocType from the call itself: the `"doctype"` key of a
`frappe.get_doc({...})` dict, or the first positional argument of a query. A call whose DocType
is not a literal is skipped rather than guessed at.

## Scope, and what this pass cannot see

Covered: `frappe.get_doc({...})` field literals, and `filters={...}` on `get_all`, `get_list`,
`db.count`, `db.get_value`, `db.get_all`, `db.get_list`, `db.exists` and `db.set_value`, for
`=`, `!=`, `in` and `not in`.

Not covered, and each is a real way past this guard:

  * `doc.status = "..."` attribute assignment. The DocType of a controller's `self` is knowable
    from its folder, but of an arbitrary local it is not, and guessing is what produced the
    false positives above. The write sites in this app all go through `get_doc`.
  * A value held in a variable, built by format string, or arriving from a request. The todo
    kanban's `update_todo_status(todo_name, new_status)` takes the status straight from the
    browser, so no static pass can see what it will be. Its caller
    (`erplite/public/js/todo/dragdrop/TodoDragDropManager.js:745-751`) maps the three kanban
    columns to "Backlog", "Planned" and "Open", all three of which the live site's ToDo does
    hold, and that mapping is in JavaScript, out of this pass's reach. KNOWN_CORE_SELECTS
    below is the record of it, and of why frappe's own JSON is not the authority on it.
  * Frappe's own DocTypes, except the handful mirrored in KNOWN_CORE_SELECTS. These tests run
    without a bench, so there is no frappe source to read; an unmirrored core DocType is
    skipped silently. Extending the mirror is how coverage grows.
"""

import ast
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
APP = "erplite"
MODULE_ROOT = os.path.join(APP_ROOT, APP)

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "public"}

# Select options for the Frappe DocTypes this app writes to or filters on.
#
# Mirrored by hand because these tests run with no bench and no frappe checkout.
#
# READ THIS BEFORE "FIXING" CODE THIS GUARD FLAGS. A core DocType's options are not whatever
# frappe ships. The live site can extend them, and then frappe's JSON is the wrong answer and
# the app code the guard flags is the right one. That happened here, to ToDo, and it got as
# far as a pull request before the owner caught it. Widen the mirror; do not narrow the app.
#
# ToDo/status is the worked example. Stock frappe version-15 ships
# `Open\nClosed\nCancelled` (frappe/desk/doctype/todo/todo.json) and restates it as
# `status: DF.Literal["Open", "Closed", "Cancelled"]` in frappe/desk/doctype/todo/todo.py:35.
# Both agree, both are wrong for crew.tierneymorris.com.au, which carries five options with
# `Backlog` as the default. Measured read-only on the live site, 5 Oct 2026:
#
#   * `DocType/ToDo` field `status` (DocField 549ll9q8br):
#     `Backlog\nPlanned\nOpen\nClosed\nCancelled`, default `Backlog`. The DocType is
#     `custom: 0`, module Desk, last modified 2025-10-12.
#   * 1727 ToDos: Closed 1454, Cancelled 145, Open 111, Planned 17, Backlog 0. Those five
#     account for every row, so nothing holds an off-list value.
#   * `Planned` has 17 real rows. The kanban's backlog column is real too
#     (erplite/www/todo/index.py:299-305, erplite/public/js/todo/utils/TodoUtils.js:128-137).
#
# WHERE THOSE TWO EXTRA OPTIONS LIVE: they exist only in `tabDocField` on the live database.
# There is no Property Setter on ToDo (the only ones on this site are two on
# `Project.naming_series`), erplite declares them nowhere (`fixtures = ["Workspace"]`, empty
# patches.txt, no todo.json, no make_property_setter), and there is no frappe fork to hold
# them.
#
# CORRECTION, 6 Oct 2026 (Ellis). The paragraph above used to end "which a `bench migrate`
# would reset to frappe's three". That was the wrong trigger and it is worth being exact
# about, because the wrong trigger makes a routine deploy look dangerous and a frappe upgrade
# look safe. It is the other way round. Traced read-only through frappe's own source at the
# installed tag v15.52.0:
#
#   * A routine `bench migrate` does NOT touch ToDo. `migrate.py:120` calls
#     `frappe.model.sync.sync_all()` with no arguments, so `force=0`. In
#     `import_file.py:130-144` the only skip gate that applies to a DocType is
#     `stored_hash == calculated_hash` (`migration_hash` against the hash of the JSON on
#     disk); the timestamp gate beside it is explicitly `and doc["doctype"] != "DocType"`,
#     so a newer DB timestamp does NOT save a DocType. An unchanged frappe means an
#     unchanged todo.json means an equal hash, so the import is skipped.
#   * The 17 `Planned` rows are themselves the evidence of that, not an inference. If the
#     hash gate were not holding, ToDo would be reimported on EVERY migrate, the five
#     options would already be gone, and no ToDo could be sitting on `Planned`. They have
#     survived many migrates.
#   * A FRAPPE UPGRADE is the trigger, and it is silent. Any frappe version bump changes
#     `todo.json`, so the hash differs and `import_doc` runs (`import_file.py:145`). That
#     calls `delete_old_doc` (258-276), which deletes the ToDo DocType and its DocField
#     children -- `ignore_doctypes = [""]` spares nothing and `ignore_values` has no DocType
#     entry -- and reinserts from the JSON. ToDo/status goes back to `Open\nClosed\nCancelled`
#     with default `Open`: the 17 Planned rows go off-list, `Backlog` stops being the default,
#     and two of the kanban's three columns empty. Nothing errors and nothing is logged.
#   * A Property Setter would survive, which is the point of them. `meta.py:138` calls
#     `apply_property_setters` (360-387) on every meta load, and for
#     `doctype_or_field == "DocField"` it sets the property over the standard field. Those
#     rows live in their own table and importing `todo.json` never touches them, and
#     `_validate_selects` reads `self.meta.get_select_fields()`, so validation would accept
#     all five. Whether erplite should declare one is a decision for the owner and is filed
#     with him, not assumed here -- it would also give erplite its first patch, and
#     patches.txt being empty is load-bearing for the auto-deploy rollback design.
#
# A mirror can also go stale against a frappe upgrade. It fails safe in the same direction:
# if frappe ADDS an option, this guard reports a violation that is no longer real, and someone
# reads this comment and widens it. It cannot invent a violation out of nothing.
KNOWN_CORE_SELECTS = {
    # NOT frappe's three -- the live site's five. See the comment above before narrowing this.
    "ToDo": {
        "status": {"Backlog", "Planned", "Open", "Closed", "Cancelled"},
        "priority": {"High", "Medium", "Low"},
    },
}

QUERY_CALLS = {
    "frappe.get_all",
    "frappe.get_list",
    "frappe.db.count",
    "frappe.db.get_value",
    "frappe.db.get_all",
    "frappe.db.get_list",
    "frappe.db.exists",
    "frappe.db.set_value",
}

# Calls whose second positional argument is the filters, when `filters=` is not given by name.
POSITIONAL_FILTERS = {"frappe.db.get_value", "frappe.db.exists", "frappe.db.count"}


def _app_selects():
    """doctype -> fieldname -> set(options), from this app's own DocType JSONs."""
    found = {}
    for dirpath, dirnames, filenames in os.walk(MODULE_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            # A DocType's JSON is named after the folder it sits in.
            if not name.endswith(".json") or name[:-5] != os.path.basename(dirpath):
                continue
            with open(os.path.join(dirpath, name), encoding="utf-8") as handle:
                definition = json.load(handle)
            doctype = definition.get("name")
            if not doctype:
                continue
            for field in definition.get("fields", []):
                if field.get("fieldtype") != "Select":
                    continue
                fieldname, options = field.get("fieldname"), field.get("options")
                if not fieldname or not options:
                    continue
                allowed = {o.strip() for o in options.split("\n") if o.strip()}
                if allowed:
                    found.setdefault(doctype, {})[fieldname] = allowed
    return found


def _selects():
    found = _app_selects()
    for doctype, fields in KNOWN_CORE_SELECTS.items():
        found.setdefault(doctype, {}).update(fields)
    return found


def _python_files():
    for dirpath, dirnames, filenames in os.walk(MODULE_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                full = os.path.join(dirpath, name)
                yield full, os.path.relpath(full, APP_ROOT).replace(os.sep, "/")


def _const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _dict_value(node, key):
    """The literal string at `key` in a dict literal, or None."""
    for k, v in zip(node.keys, node.values):
        if _const_str(k) == key:
            return _const_str(v)
    return None


def violations():
    """[(rel_path, line, doctype, field, value, how, allowed)] over the whole app."""
    selects = _selects()
    found = []

    def check(rel, line, doctype, field, value, how):
        allowed = selects.get(doctype, {}).get(field)
        if allowed is None or value in allowed:
            return
        found.append((rel, line, doctype, field, value, how, allowed))

    def check_filters(rel, doctype, node):
        for key, value in zip(node.keys, node.values):
            field = _const_str(key)
            if not field:
                continue
            literal = _const_str(value)
            if literal is not None:
                check(rel, key.lineno, doctype, field, literal, "filter ==")
                continue
            # The [operator, operand] form.
            if not isinstance(value, (ast.List, ast.Tuple)) or len(value.elts) != 2:
                continue
            operator = (_const_str(value.elts[0]) or "").lower()
            operand = value.elts[1]
            if operator in ("in", "not in") and isinstance(operand, (ast.List, ast.Tuple)):
                for element in operand.elts:
                    literal = _const_str(element)
                    if literal is not None:
                        check(rel, key.lineno, doctype, field, literal,
                              "filter %s" % operator)
            elif operator in ("=", "==", "!="):
                literal = _const_str(operand)
                if literal is not None:
                    check(rel, key.lineno, doctype, field, literal,
                          "filter %s" % operator)

    for path, rel in _python_files():
        with open(path, encoding="utf-8", errors="replace") as handle:
            source = handle.read()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _dotted(node.func)
            keywords = {k.arg: k.value for k in node.keywords if k.arg}

            if name == "frappe.get_doc" and node.args and isinstance(node.args[0], ast.Dict):
                literal = node.args[0]
                doctype = _dict_value(literal, "doctype")
                if not doctype:
                    continue
                for key, value in zip(literal.keys, literal.values):
                    field, written = _const_str(key), _const_str(value)
                    if field and written is not None:
                        check(rel, key.lineno, doctype, field, written, "get_doc field")
                continue

            if name not in QUERY_CALLS:
                continue
            doctype = _const_str(node.args[0]) if node.args else None
            if not doctype:
                continue

            filters = keywords.get("filters")
            if filters is None and name in POSITIONAL_FILTERS and len(node.args) > 1:
                filters = node.args[1]
            if isinstance(filters, ast.Dict):
                check_filters(rel, doctype, filters)

            if name == "frappe.db.set_value" and len(node.args) >= 4:
                field, written = _const_str(node.args[2]), _const_str(node.args[3])
                if field and written is not None:
                    check(rel, node.lineno, doctype, field, written, "set_value")

    return found


# Findings this guard stands by, that the owner has not yet ruled on, and that nobody should
# quietly "fix" to get a green run.
#
# A sweep like this finds two kinds of thing: a bug, and a question. Narrowing app code to
# match the guard is how a question gets mistaken for a bug -- it is what happened to ToDo
# above. So a finding the owner has not decided lives here, by exact site, with the reason and
# what is known. It does not fail the run. It is still asserted to exist, so if someone
# changes the code the run fails and points them at this entry to remove.
#
# Each key is "<path>:<line>  <DocType>.<field> = <value>".
AWAITING_OWNER_DECISION = {
    "erplite/scheduler/doctype/division/division.py:82  Project.status = 'Active'": """
    `get_division_projects` filters Project.status on ["Open", "Active"]. Project declares
    Opportunity, Estimate, Open, Archived (erplite/projects/doctype/project/project.json),
    so "Active" matches nothing and the filter is really ["Open"].

    Measured read-only on the live site, 5 Oct 2026: 19 Projects, 12 Open and 7 Archived,
    0 with status "Active", 0 Opportunity or Estimate. 6 Division records, so this is a live
    code path, not dead.

    Today's behaviour is therefore IDENTICAL whether "Active" stays or goes, which is exactly
    why this is not being changed here. Dropping it is a no-op cleanup whose only failure mode
    is the ToDo one -- if the live DocType carries "Active" as an unused option, removing it
    silently breaks the first project ever set to it. Unlike ToDo, the live Project data agrees
    with the repo's JSON and nothing suggests an extension; but the one-line change buys
    nothing today, so it is the owner's call and not worth the risk inside a larger PR.
    """,
}


def _finding_key(rel, line, doctype, field, value):
    return "%s:%d  %s.%s = %r" % (rel, line, doctype, field, value)


class SelectOptionsAreRespected(unittest.TestCase):
    def test_no_select_field_is_given_a_value_it_cannot_hold(self):
        found = [
            v for v in violations()
            if _finding_key(v[0], v[1], v[2], v[3], v[4]) not in AWAITING_OWNER_DECISION
        ]
        if found:
            lines = [
                "%s:%d  [%s]  %s.%s = %r\n        allowed: %s"
                % (rel, line, how, doctype, field, value, ", ".join(sorted(allowed)))
                for rel, line, doctype, field, value, how, allowed in sorted(found)
            ]
            self.fail(
                "%d Select value(s) outside the field's own options.\n"
                "A write aborts the save; a filter matches the wrong set in silence.\n\n%s"
                % (len(found), "\n".join(lines))
            )

    def test_every_awaiting_owner_finding_is_still_there(self):
        """The waiver list cannot outlive what it waives.

        If one of these is fixed or its line moves, this fails and names the stale entry,
        so the list cannot quietly become a place where findings go to be forgotten.
        """
        live = {_finding_key(v[0], v[1], v[2], v[3], v[4]) for v in violations()}
        stale = sorted(set(AWAITING_OWNER_DECISION) - live)
        self.assertEqual(
            [], stale,
            "AWAITING_OWNER_DECISION entries that no longer match a real finding -- the code "
            "changed or the line moved, so remove or re-anchor them: %r" % (stale,))

    def test_the_pass_can_see_this_apps_doctypes(self):
        """Guard the guard: if the JSON walk breaks, every check above passes vacuously."""
        selects = _app_selects()
        self.assertGreater(
            len(selects), 20,
            "only %d DocTypes with Select fields were found; the JSON walk is broken, which "
            "would make the whole-app check pass by seeing nothing" % len(selects))
        self.assertIn("Project", selects)
        self.assertIn("status", selects["Project"])

    def test_the_pass_can_see_a_violation_planted_in_this_apps_own_source(self):
        """Guard the guard, the other half: prove the AST walk reaches a real call site.

        A whole-app rule that reports nothing is indistinguishable from one that looks at
        nothing. This plants a call with a bad Select value in a temporary module inside the
        app tree and requires the pass to find it.
        """
        planted = os.path.join(MODULE_ROOT, "_select_guard_probe.py")
        source = (
            "import frappe\n"
            "\n"
            "def probe():\n"
            "    frappe.get_all('Project', filters={'status': ['!=', 'NotAStatus']})\n"
            "    return frappe.get_doc({'doctype': 'ToDo', 'status': 'NotAStatus'})\n"
        )
        with open(planted, "w", encoding="utf-8") as handle:
            handle.write(source)
        try:
            found = [v for v in violations() if v[0].endswith("_select_guard_probe.py")]
        finally:
            os.remove(planted)
        self.assertEqual(
            2, len(found),
            "the pass found %d of the 2 planted violations: %r" % (len(found), found))
        self.assertEqual({"Project", "ToDo"}, {v[2] for v in found})


class ToDoStatusMirrorIsStated(unittest.TestCase):
    """The mirror of a Frappe DocType is the one fact here that is not read from this repo.

    These assertions do not test the app. They state, in a place that runs, what the mirror
    claims, so that a frappe upgrade that changes ToDo's statuses turns into a failing test
    with this file's comment next to it rather than a silently wrong whole-app rule.
    """

    def test_the_mirror_is_the_live_sites_statuses_not_frappes(self):
        self.assertEqual({"Backlog", "Planned", "Open", "Closed", "Cancelled"},
                         KNOWN_CORE_SELECTS["ToDo"]["status"])

    def test_the_mirror_extends_stock_frappe_rather_than_contradicting_it(self):
        """Every status frappe ships is still a status here; this site only adds."""
        self.assertLess({"Open", "Closed", "Cancelled"},
                        KNOWN_CORE_SELECTS["ToDo"]["status"])

    def test_every_kanban_column_is_reachable(self):
        """The board's three columns all fill, which is why the app code is right as it is.

        `erplite/www/todo/index.py:get_todo_column` and its browser twin
        `erplite/public/js/todo/utils/TodoUtils.js:128-137` map status to column as
        Backlog -> backlog, Planned -> todo, Open -> progress. On stock frappe two of those
        three would be dead and this test would fail, which is the point of it.
        """
        status_to_column = {"Backlog": "backlog", "Planned": "todo", "Open": "progress"}
        reachable = {
            column for status, column in status_to_column.items()
            if status in KNOWN_CORE_SELECTS["ToDo"]["status"]
        }
        self.assertEqual({"backlog", "todo", "progress"}, reachable)


class StandInRejectsImpossibleSelectValues(unittest.TestCase):
    """The stand-in's half of this surface.

    The whole-app pass above reads source and cannot run anything. These tests
    cover the other direction: `fake_frappe` now refuses to serve a fixture row
    holding a Select value its DocType forbids, and refuses a filter comparing a
    Select field to such a value.

    That strictness is the thing that would have caught this surface years
    earlier. `test_projects_api` and `test_scheduler_api` each built a fixture
    Project with `status="Cancelled"` to show that `["!=", "Cancelled"]` left it
    out, and both passed -- because the stand-in checked field *names* and not
    field *values*, so an impossible row went in without complaint and the
    filter excluded it exactly as the test expected. On the real site
    Project.status has no Cancelled option, so no such row exists and that
    filter excludes nothing. The tests were green about a world that cannot
    happen.
    """

    def setUp(self):
        from fake_frappe import FakeFrappe, ImpossibleValue, _dict
        self.ImpossibleValue = ImpossibleValue
        self._dict = _dict
        self.frappe = FakeFrappe()

    def test_the_stand_in_knows_projects_real_statuses(self):
        self.assertEqual({"Opportunity", "Estimate", "Open", "Archived"},
                         self.frappe.select_options["Project"]["status"])

    def test_select_rows_refuses_an_impossible_fixture(self):
        self.frappe.tables["Project"] = [
            self._dict(name="p1", project_name="Fine", status="Open"),
            self._dict(name="p2", project_name="Shelved", status="Cancelled"),
        ]
        with self.assertRaises(self.ImpossibleValue) as caught:
            self.frappe.get_all("Project", fields=["name"])
        self.assertIn("Cancelled", str(caught.exception))
        self.assertIn("p2", str(caught.exception))

    def test_select_rows_allows_every_real_option_and_an_empty_value(self):
        self.frappe.tables["Project"] = [
            self._dict(name="p%d" % i, project_name="x", status=status)
            for i, status in enumerate(
                ["Opportunity", "Estimate", "Open", "Archived", None, ""])
        ]
        self.assertEqual(6, len(self.frappe.get_all("Project", fields=["name"])))

    def test_select_filters_refuses_an_impossible_filter(self):
        self.frappe.tables["Project"] = [
            self._dict(name="p1", project_name="Fine", status="Open")]
        for condition in (["!=", "Cancelled"], ["in", ["Open", "Active"]], "Cancelled"):
            with self.assertRaises(self.ImpossibleValue, msg=repr(condition)):
                self.frappe.get_all("Project", fields=["name"],
                                    filters={"status": condition})

    def test_select_filters_allow_the_real_statuses(self):
        self.frappe.tables["Project"] = [
            self._dict(name="p1", project_name="Fine", status="Open"),
            self._dict(name="p2", project_name="Gone", status="Archived"),
        ]
        kept = self.frappe.get_all("Project", fields=["name"],
                                   filters={"status": ["!=", "Archived"]})
        self.assertEqual(["p1"], [r["name"] for r in kept])

    def test_a_write_of_an_impossible_select_value_is_refused(self):
        """Real Frappe aborts the save; the stand-in raises rather than writing."""
        self.frappe.tables["ToDo"] = [self._dict(name="t1", status="Open")]
        with self.assertRaises(self.ImpossibleValue):
            self.frappe.db.set_value("ToDo", "t1", "status", "Done")
        self.assertEqual("Open", self.frappe.tables["ToDo"][0]["status"])
        # "Backlog" is NOT impossible on this site, so it must be accepted.
        self.frappe.db.set_value("ToDo", "t1", "status", "Backlog")
        self.assertEqual("Backlog", self.frappe.tables["ToDo"][0]["status"])

    def test_a_reverted_fixture_is_caught_by_the_stand_in(self):
        """The two suites that carried an impossible Project fixture now cannot.

        This reads their source rather than their fixtures, so it fails if
        either file reintroduces the value, whichever test happens to use it.
        """
        for name in ("test_projects_api.py", "test_scheduler_api.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                source = handle.read()
            self.assertNotIn(
                'project_name="Shelved", status="Cancelled"', source,
                "%s builds a Project with a status Project.status cannot hold" % name)


if __name__ == "__main__":
    unittest.main()
