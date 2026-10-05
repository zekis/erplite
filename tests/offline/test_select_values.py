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

## What "a write" and "a filter" mean here, and why the list is longer than it was

The first version of this pass read `frappe.get_doc({...})` and `filters={...}` and nothing
else. Fault injection against real source (`tests/faultinject`, target `select_values`) found
fourteen other ways to write or filter a Select value that frappe accepts and this pass did
not see -- **most of frappe's filter API, including the list-of-lists form documented in
`get_all`'s own docstring beside the dict form.** Each is now read, through the shapes frappe
itself funnels them into rather than a list of special cases:

Writes: a `get_doc({...})` dict and **every nested dict in it that names its own doctype** (a
child row's Select aborts the parent's save too), `get_doc(doctype=..., field=...)`,
`frappe.new_doc("X").update({...})`, and `db.set_value` -- whose `field` argument may be a
**dict of field to value** (`_get_update_dict`, database.py:769-773; four live Xero writes in
this app use that form).

Filters: `filters` and `or_filters`, given by keyword **or positionally**, on `get_all`,
`get_list`, `db.get_all`, `db.get_list`, `db.get_value`, `db.get_values`, `frappe.get_value`,
`db.exists`, `db.count`, `frappe.get_last_doc`, and `db.set_value`'s `dn` (which may be
filters, database.py:948). In every form `get_filter` accepts: a dict, a list of dicts, a
three-element list, and a four-element list -- which **names its own DocType**, so its value is
compared against that DocType's options and not the queried one's. Operators `=`, `!=`, `in`
and `not in`; `like`, `between` and the rest are not options comparisons.

A write is judged the way `_validate_selects` judges it (base_document.py:892-920), which is
narrower than "in options" and reporting anything narrower would flag correct code: it exempts
`naming_series` by name, skips a falsy value, and strips the value before comparing. A filter
is **not** stripped, because frappe compares the string it is given.

## Scope, and what this pass cannot see

Not covered, and each is a real way past this guard:

  * `doc.status = "..."` attribute assignment. The DocType of a controller's `self` is knowable
    from its folder, but of an arbitrary local it is not, and guessing is what produced the
    false positives above. The write sites in this app all go through `get_doc`. `.update()` is
    read only where the DocType is in the same expression (`new_doc("X").update({...})`),
    which is the same boundary drawn in the same place.
  * `from frappe import get_all` and then a bare `get_all(...)`. Every call site in this app
    is written `frappe.`-qualified; `test_every_query_call_is_frappe_qualified` below asserts
    that, so this becomes a failing test rather than a silent gap the day someone writes one.
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
# WHERE THOSE TWO EXTRA OPTIONS LIVE: as of `erplite.patches.declare_todo_status_options`,
# in a Property Setter this app declares (see DECIDED below).
#
# Before that patch they existed only as a hand-edited row in `tabDocField` on the live
# database. There was no Property Setter on ToDo (the only ones on the site were two on
# `Project.naming_series`), erplite declared them nowhere (`fixtures = ["Workspace"]`, an
# empty patches.txt, no todo.json, no make_property_setter), and there is no frappe fork to
# hold them. That is what made the upgrade below silent, and it is the state the patch ends.
#
# CORRECTION, 5 Oct 2026 (Ellis). The paragraph above used to end "which a `bench migrate`
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
#     all five.
#
# DECIDED, 5 Oct 2026 (the owner, on review tray item rev_a007dfc7a8): "Declare them in code.
# Backlog and Planned must stay supported." Built as `erplite.patches.declare_todo_status_options`
# -- erplite's first patch, so `patches.txt` is no longer empty, which matters to the auto-deploy
# rollback design and Alex has been told. The patch pins the options the site already has rather
# than a constant, so it changed nothing on the day it landed. `tests/offline/
# test_todo_status_property_setter.py` holds it, and compares its statuses against the mirror
# below so these two hand-kept records cannot drift apart.
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

# Where a filters argument sits when it is not given by name, read from each function's own
# signature in frappe 15.52.0 rather than assumed:
#
#   * `frappe.get_all` / `frappe.get_list` hand their arguments to
#     `DatabaseQuery.execute(fields, filters, or_filters, ...)` (model/db_query.py:315-319), so
#     the first positional after the DocType is **fields**, and filters is the one after that.
#     Getting this wrong in either direction is silent: an index too low reads the field list as
#     filters, an index too high reads nothing.
#   * `frappe.db.get_all` / `frappe.db.get_list` are pass-throughs to those two
#     (database/database.py:761-766), so they share the layout.
#   * `frappe.db.get_value` / `frappe.db.get_values` take `(doctype, filters, fieldname)`
#     (database.py:469-473, :548-552), and `frappe.get_value` is the documented alias for the
#     first (__init__.py:2068).
#   * `frappe.db.exists(dt, dn)` takes a name **or** filters as `dn` (database.py:1234), and
#     `frappe.db.count(dt, filters)` (:1269).
#   * `frappe.get_last_doc(doctype, filters)` passes them straight to `get_all`
#     (__init__.py:1338-1340).
FILTER_ARG = {
    "frappe.get_all": 2,
    "frappe.get_list": 2,
    "frappe.db.get_all": 2,
    "frappe.db.get_list": 2,
    "frappe.db.get_value": 1,
    "frappe.db.get_values": 1,
    "frappe.get_value": 1,
    "frappe.db.exists": 1,
    "frappe.db.count": 1,
    "frappe.get_last_doc": 1,
}

# `or_filters` is a separate argument of the same kind, next along in `execute`. It is read
# exactly like `filters` because frappe reads it exactly like `filters` -- the same
# `build_filter_conditions` over the same `get_filter` (db_query.py:973-982). The app has one
# live `or_filters`, in the ToDo kanban.
OR_FILTER_ARG = {
    "frappe.get_all": 3,
    "frappe.get_list": 3,
    "frappe.db.get_all": 3,
    "frappe.db.get_list": 3,
}

QUERY_CALLS = set(FILTER_ARG) | {"frappe.db.set_value"}

# Fields `_validate_selects` never checks, so neither does this. `naming_series` is exempted by
# name (base_document.py:897) because its value is a series pattern, not an option.
WRITE_EXEMPT_FIELDS = {"naming_series"}


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


def _argument(node, index, name):
    """A call's argument, given positionally or by keyword, or None.

    Reading only positions misses `field="status"`; reading only keywords misses
    `get_all("ToDo", fields, filters)`. Both forms are ordinary frappe and both appear in this
    app, so every argument this pass reads is read through here.
    """
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    if index is not None and len(node.args) > index:
        return node.args[index]
    return None


def _conditions(node, doctype):
    """[(doctype, field, operator, operand_node, lineno)] for one filters argument.

    Every filter frappe accepts funnels through `get_filter` (utils/data.py:1940-1975), and
    this follows it rather than the dict form alone:

      * a dict is {fieldname: value} or {fieldname: [operator, value]};
      * a list holds dicts or lists, since `build_filter_conditions` wraps a bare dict in a
        list and iterates (db_query.py:978-982);
      * a three-element list is [fieldname, operator, value], and frappe fills in the query's
        DocType (data.py:1960);
      * a four-element list is [doctype, fieldname, operator, value] and **names its own
        DocType**, which need not be the one queried -- so taking the query's would compare a
        value against the wrong field's options.

    A flat list of three strings is not a filter: `build_filter_conditions` iterates it and
    hands `get_filter` a string, which throws "Filter must be a tuple or list (in a list)"
    (data.py:1958). So it is not a form this pass needs to read.
    """
    out = []

    def from_dict(dict_node):
        for key, value in zip(dict_node.keys, dict_node.values):
            field = _const_str(key)
            if not field:
                continue
            if isinstance(value, (ast.List, ast.Tuple)) and len(value.elts) == 2:
                operator = _const_str(value.elts[0])
                if operator:
                    out.append((doctype, field, operator.lower(), value.elts[1], key.lineno))
                    continue
            out.append((doctype, field, "=", value, key.lineno))

    if isinstance(node, ast.Dict):
        from_dict(node)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for element in node.elts:
            if isinstance(element, ast.Dict):
                from_dict(element)
            elif isinstance(element, (ast.List, ast.Tuple)) and len(element.elts) == 3:
                field, operator = _const_str(element.elts[0]), _const_str(element.elts[1])
                if field and operator:
                    out.append((doctype, field, operator.lower(), element.elts[2],
                                element.lineno))
            elif isinstance(element, (ast.List, ast.Tuple)) and len(element.elts) >= 4:
                own = _const_str(element.elts[0])
                field, operator = _const_str(element.elts[1]), _const_str(element.elts[2])
                if own and field and operator:
                    out.append((own, field, operator.lower(), element.elts[3], element.lineno))
    return out


def _doc_dicts(node):
    """Every dict literal at or under `node` that names its own DocType.

    A child table is a list of dicts inside the parent's dict, each carrying its own
    `doctype`, and `insert()` validates them all -- so a child row's Select aborts the parent's
    save exactly like the parent's own.
    """
    for inner in ast.walk(node):
        if isinstance(inner, ast.Dict) and _dict_value(inner, "doctype"):
            yield inner


def violations():
    """[(rel_path, line, doctype, field, value, how, allowed)] over the whole app."""
    selects = _selects()
    found = []

    def check(rel, line, doctype, field, value, how):
        allowed = selects.get(doctype, {}).get(field)
        if allowed is None or value in allowed:
            return
        found.append((rel, line, doctype, field, value, how, allowed))

    def check_write(rel, line, doctype, field, value_node, how):
        """A write, judged the way `_validate_selects` judges it.

        base_document.py:892-920 is the authority, and it is narrower than "the value is in
        options" in three ways this pass has to copy or it reports correct code:

          * `naming_series` is skipped by name (:897);
          * a falsy value is skipped (:897), so an unset Select is not a violation -- and a
            filter on an empty value is a real query for unset rows, so that is skipped too;
          * the value is **stripped** before the comparison (:907), so trailing space is not a
            violation on a write. A filter is not stripped -- frappe compares the string it is
            given -- which is why only this half strips.
        """
        value = _const_str(value_node)
        if value is None or field in WRITE_EXEMPT_FIELDS or not value.strip():
            return
        check(rel, line, doctype, field, value.strip(), how)

    def check_filters(rel, doctype, node, how):
        for own, field, operator, operand, line in _conditions(node, doctype):
            if operator in ("in", "not in") and isinstance(operand, (ast.List, ast.Tuple)):
                for element in operand.elts:
                    literal = _const_str(element)
                    if literal:
                        check(rel, line, own, field, literal, "%s %s" % (how, operator))
            elif operator in ("=", "==", "!="):
                literal = _const_str(operand)
                if literal:
                    check(rel, line, own, field, literal, "%s %s" % (how, operator))

    def check_doc_fields(rel, dict_node):
        doctype = _dict_value(dict_node, "doctype")
        for key, value in zip(dict_node.keys, dict_node.values):
            field = _const_str(key)
            if field and field != "doctype":
                check_write(rel, key.lineno, doctype, field, value, "get_doc field")

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

            if name == "frappe.get_doc" and node.args and isinstance(node.args[0], ast.Dict):
                for dict_node in _doc_dicts(node.args[0]):
                    check_doc_fields(rel, dict_node)
                continue

            # get_doc(doctype="ToDo", status="...") -- documented, if discouraged, in frappe's
            # own overloads (__init__.py:1294-1297).
            if name == "frappe.get_doc" and not node.args and node.keywords:
                doctype = None
                for keyword in node.keywords:
                    if keyword.arg == "doctype":
                        doctype = _const_str(keyword.value)
                if doctype:
                    for keyword in node.keywords:
                        if keyword.arg and keyword.arg != "doctype":
                            check_write(rel, node.lineno, doctype, keyword.arg,
                                        keyword.value, "get_doc keyword")
                continue

            # `frappe.new_doc("ToDo").update({...})` and the same on a get_doc dict. The
            # DocType is in the expression, so nothing is guessed. A bare local's `.update`
            # stays out of reach, which is the same boundary as attribute assignment.
            if (isinstance(node.func, ast.Attribute) and node.func.attr == "update"
                    and node.args and isinstance(node.args[0], ast.Dict)
                    and isinstance(node.func.value, ast.Call)):
                receiver = node.func.value
                receiver_name = _dotted(receiver.func)
                doctype = None
                if receiver_name == "frappe.new_doc" and receiver.args:
                    doctype = _const_str(receiver.args[0])
                elif (receiver_name == "frappe.get_doc" and receiver.args
                        and isinstance(receiver.args[0], ast.Dict)):
                    doctype = _dict_value(receiver.args[0], "doctype")
                if doctype:
                    for key, value in zip(node.args[0].keys, node.args[0].values):
                        field = _const_str(key)
                        if field and field != "doctype":
                            check_write(rel, key.lineno, doctype, field, value,
                                        "update() field")
                continue

            if name not in QUERY_CALLS:
                continue
            doctype = _const_str(node.args[0]) if node.args else None
            if not doctype:
                continue

            filters = _argument(node, FILTER_ARG.get(name), "filters")
            if filters is not None:
                check_filters(rel, doctype, filters, "filter")
            or_filters = _argument(node, OR_FILTER_ARG.get(name), "or_filters")
            if or_filters is not None:
                check_filters(rel, doctype, or_filters, "or_filter")

            if name == "frappe.db.set_value":
                # `field` may be a dict of field -> value: `_get_update_dict` is
                # `fieldname if isinstance(fieldname, dict) else {fieldname: value}`
                # (database.py:769-773), and four live Xero writes in this app use that form.
                field_node = _argument(node, 2, "field")
                if isinstance(field_node, ast.Dict):
                    for key, value in zip(field_node.keys, field_node.values):
                        field = _const_str(key)
                        if field:
                            check_write(rel, key.lineno, doctype, field, value, "set_value")
                else:
                    field = _const_str(field_node)
                    value_node = _argument(node, 3, "val")
                    if field and value_node is not None:
                        check_write(rel, node.lineno, doctype, field, value_node, "set_value")
                # `dn` is "Document name for updating single record or filters for updating
                # many records" (database.py:948), so a dict there is a filter.
                name_node = _argument(node, 1, "dn")
                if isinstance(name_node, ast.Dict):
                    check_filters(rel, doctype, name_node, "set_value filter")

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


class TheReachOfThisPassIsPinned(unittest.TestCase):
    """What the pass can and cannot see, planted in real source and asserted.

    Every case here was green before it was written: fault injection against real app source
    (`tests/faultinject`, target `select_values`) found fourteen ways frappe writes or filters
    a Select value that this pass did not read, three of them in frappe's own docstrings, and
    three edits real frappe accepts that it reported. A detector's own fixtures only ever
    answer "do you find what I thought of?", so these are kept as the record of what it was
    once blind to -- a form that stops being read fails here, not silently.
    """

    def plant(self, body):
        """`body` in a module inside the app tree; what the pass then reports."""
        planted = os.path.join(MODULE_ROOT, "_select_reach_probe.py")
        with open(planted, "w", encoding="utf-8") as handle:
            handle.write("import frappe\n\n\ndef probe():\n    %s\n" % body)
        try:
            return [v for v in violations() if v[0].endswith("_select_reach_probe.py")]
        finally:
            os.remove(planted)

    # -- filters, in every form frappe's get_filter accepts --------------
    def test_every_filter_form_frappe_accepts_is_read(self):
        impossible = "'Retired'"  # Project holds Opportunity/Estimate/Open/Archived
        for label, body in (
            ("dict", "frappe.get_all('Project', filters={'status': %s})" % impossible),
            ("dict with operator",
             "frappe.get_all('Project', filters={'status': ['!=', %s]})" % impossible),
            ("list of three",
             "frappe.get_all('Project', filters=[['status', '=', %s]])" % impossible),
            ("list of four, naming its own doctype",
             "frappe.get_all('Project', filters=[['Project', 'status', '=', %s]])" % impossible),
            ("dict inside a list",
             "frappe.get_all('Project', filters=[{'status': %s}])" % impossible),
            ("in", "frappe.get_all('Project', filters={'status': ['in', ['Open', %s]]})"
             % impossible),
            ("or_filters", "frappe.get_all('Project', or_filters={'status': %s})" % impossible),
            ("filters positional, after fields",
             "frappe.get_all('Project', ['name'], {'status': %s})" % impossible),
            ("or_filters positional",
             "frappe.get_all('Project', ['name'], None, {'status': %s})" % impossible),
        ):
            with self.subTest(label):
                self.assertEqual(1, len(self.plant(body)), label)

    def test_every_query_entry_point_is_read(self):
        for call, body in (
            ("frappe.get_list", "frappe.get_list('Project', filters={'status': 'Retired'})"),
            ("frappe.db.get_all", "frappe.db.get_all('Project', filters={'status': 'Retired'})"),
            ("frappe.db.get_value", "frappe.db.get_value('Project', {'status': 'Retired'}, 'name')"),
            ("frappe.db.get_values", "frappe.db.get_values('Project', {'status': 'Retired'}, 'name')"),
            ("frappe.get_value", "frappe.get_value('Project', {'status': 'Retired'}, 'name')"),
            ("frappe.db.exists", "frappe.db.exists('Project', {'status': 'Retired'})"),
            ("frappe.db.count", "frappe.db.count('Project', {'status': 'Retired'})"),
            ("frappe.get_last_doc", "frappe.get_last_doc('Project', filters={'status': 'Retired'})"),
        ):
            with self.subTest(call):
                self.assertEqual(1, len(self.plant(body)), call)

    def test_a_four_element_filter_is_judged_against_its_own_doctype(self):
        """The DocType in the element wins, or the value meets the wrong options.

        'Retired' is impossible for both, so the proof is in which options are reported.
        """
        found = self.plant(
            "frappe.get_all('ToDo', filters=[['Project', 'status', '=', 'Retired']])")
        self.assertEqual(1, len(found))
        self.assertEqual("Project", found[0][2])
        self.assertEqual({"Opportunity", "Estimate", "Open", "Archived"}, found[0][6])
        # And a value valid for the named DocType but not the queried one is not a violation.
        self.assertEqual(
            [], self.plant(
                "frappe.get_all('ToDo', filters=[['Project', 'status', '=', 'Archived']])"))

    # -- writes ----------------------------------------------------------
    def test_every_write_form_is_read(self):
        for label, body in (
            ("get_doc dict", "frappe.get_doc({'doctype': 'ToDo', 'status': 'Done'})"),
            ("get_doc keywords", "frappe.get_doc(doctype='ToDo', status='Done')"),
            ("new_doc().update()", "frappe.new_doc('ToDo').update({'status': 'Done'})"),
            ("get_doc({}).update()",
             "frappe.get_doc({'doctype': 'ToDo'}).update({'status': 'Done'})"),
            ("set_value positional", "frappe.db.set_value('ToDo', 't', 'status', 'Done')"),
            ("set_value keywords", "frappe.db.set_value('ToDo', 't', field='status', val='Done')"),
            ("set_value dict of values", "frappe.db.set_value('ToDo', 't', {'status': 'Done'})"),
            ("set_value dn as filters",
             "frappe.db.set_value('ToDo', {'status': 'Done'}, 'description', 'x')"),
        ):
            with self.subTest(label):
                self.assertEqual(1, len(self.plant(body)), label)

    def test_a_child_row_in_a_get_doc_dict_is_read(self):
        """`insert()` validates the children too, so a child Select aborts the parent's save."""
        found = self.plant(
            "frappe.get_doc({'doctype': 'Project', 'rows': "
            "[{'doctype': 'ToDo', 'status': 'Done'}]})")
        self.assertEqual(1, len(found))
        self.assertEqual("ToDo", found[0][2])

    # -- the three edits real frappe accepts, which this once reported ---
    def test_a_write_is_judged_as_validate_selects_judges_it(self):
        """base_document.py:892-920 is the authority; anything narrower flags correct code."""
        for label, body in (
            ("naming_series is exempt by name",
             "frappe.get_doc({'doctype': 'Sales Invoice', 'naming_series': 'SINV-.YYYY.-'})"),
            ("a falsy value is skipped",
             "frappe.get_doc({'doctype': 'ToDo', 'status': ''})"),
            ("the value is stripped before comparing",
             "frappe.get_doc({'doctype': 'ToDo', 'status': 'Open '})"),
        ):
            with self.subTest(label):
                self.assertEqual([], self.plant(body), label)

    def test_a_filter_is_not_stripped_because_frappe_does_not_strip_one(self):
        """The asymmetry is real: `_validate_selects` strips a write, nothing strips a filter.

        `Engine._apply_filter` screens the filter name and passes the value through, so
        ' Open' reaches the WHERE clause with its space and matches nothing.
        """
        self.assertEqual(1, len(self.plant(
            "frappe.get_all('ToDo', filters={'status': 'Open '})")))

    def test_an_operator_that_is_not_an_options_comparison_is_left_alone(self):
        for body in (
            "frappe.get_all('ToDo', filters={'status': ['like', '%pen%']})",
            "frappe.get_all('ToDo', filters={'status': ['is', 'set']})",
            "frappe.get_all('ToDo', filters={'date': ['between', ['2026-01-01', '2026-02-01']]})",
        ):
            with self.subTest(body):
                self.assertEqual([], self.plant(body))

    # -- what it still cannot see, named rather than implied -------------
    def test_what_this_cannot_see_is_still_invisible(self):
        """Each of these is a real regression this pass deliberately does not report.

        They need the type of a local, or a value that does not exist until runtime. Guessing
        either is what produced this file's original false positives, and silent over-reach is
        the one failure a sweep cannot report -- a false positive at least argues with you.
        This test exists so the list is a measurement and not a claim.
        """
        for label, body in (
            ("attribute assignment on a local",
             "doc = frappe.new_doc('ToDo')\n    doc.status = 'Done'"),
            ("the value in a variable", "bad = 'Done'\n    "
             "frappe.get_doc({'doctype': 'ToDo', 'status': bad})"),
            ("the value from an f-string",
             "frappe.get_doc({'doctype': 'ToDo', 'status': f'Do{chr(110)}e'})"),
            ("the filters dict built elsewhere",
             "where = {'status': 'Done'}\n    frappe.get_all('ToDo', filters=where)"),
            ("a doctype that is not a literal",
             "frappe.get_all(some_doctype, filters={'status': 'Done'})"),
        ):
            with self.subTest(label):
                self.assertEqual([], self.plant(body), label)

    def test_every_query_call_is_frappe_qualified(self):
        """The tripwire for the one import style this pass cannot follow.

        `from frappe import get_all` then a bare `get_all(...)` is ordinary Python and
        `_dotted` would read it as `get_all`, which is in no table here. No call site in this
        app is written that way. That is a measurement, and a measurement that is not a test is
        just a sentence -- so this fails the day one is written, naming the file.
        """
        bare = set()
        for path, rel in _python_files():
            with open(path, encoding="utf-8", errors="replace") as handle:
                try:
                    tree = ast.parse(handle.read())
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if (isinstance(node, ast.ImportFrom) and node.module == "frappe"
                        and any(a.name in ("get_all", "get_list", "get_doc", "new_doc",
                                           "get_value", "get_last_doc")
                                for a in node.names)):
                    bare.add("%s:%d" % (rel, node.lineno))
        self.assertEqual(
            set(), bare,
            "a query or write call imported from frappe by name, which this pass reads only "
            "as `frappe.<name>`: %r. Either qualify the call or teach _dotted the alias."
            % (sorted(bare),))


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
