# -*- coding: utf-8 -*-
"""A small in-memory stand-in for the parts of `frappe` that
erplite.projects.api uses, so its queries can be tested without a bench.

The important behaviour here is deliberately *stricter* than real Frappe.
`frappe.get_all` in Frappe 15 does not check field names against the DocType at
all. Checked in frappe/frappe version-15: `DatabaseQuery.sanitize_fields`
(frappe/model/db_query.py) only screens for SQL injection -- commas, parens and
blacklisted keywords and functions -- and `Engine._apply_filter`
(frappe/database/query.py) only rejects special characters in a filter name.
Neither compares the name to the DocType's fields.

So the name goes straight into the SQL, and what happens next depends on the
database rather than on Frappe:

- If the column still exists -- and `bench migrate` creates columns but never
  drops them, so a field removed from a DocType JSON usually leaves its column
  behind -- the query succeeds and returns whatever stale value is in that
  orphaned column. In `filters` it matches nothing, because nothing maintains
  the column.
- If the column was never created on this site, MariaDB raises
  "Unknown column 'x' in 'field list'" and the whole request fails.

Either way nothing warns you, and which of the two you get depends on the
site's migration history, not on the code. That is what let the Activity
`subject` / `assigned_to` bug sit unnoticed.

This stand-in raises UnknownField instead. That turns the silent bug into a
test failure, so a query against a column that is no longer a DocType field
cannot be reintroduced without a test going red.
"""

import datetime
import json
import os
import re

APP_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


class UnknownField(Exception):
    """Raised when a query names a field the DocType does not have."""


class ImpossibleValue(Exception):
    """Raised when a Select field holds or is compared to a value it cannot take.

    The field-name checks above answer "does this field exist". This answers
    "can this field ever hold this". Real Frappe splits the two apart and
    enforces them in different places, which is why both need standing in for:

      * A WRITE of an unlisted value is rejected, by `_validate_selects`
        (frappe-version-15/frappe/model/base_document.py:892-920), reached from
        `_validate()` (document.py:627) on both the insert path (:310) and the
        save path (:417). It ends in `frappe.throw`, so the save aborts.
      * A FILTER on an unlisted value is not checked at all. It is valid SQL
        against a value no row holds, so `==` matches nothing and `!=` matches
        everything -- a filter that reads as if it excludes something and
        excludes nothing.

    This stand-in rejects both, because the second one is what bit the tests in
    this folder. `test_projects_api` and `test_scheduler_api` both built a
    fixture Project with `status="Cancelled"` to prove that
    `filters={"status": ["!=", "Cancelled"]}` left it out. Both passed. But
    `Project.status` is a Select whose options are Opportunity, Estimate, Open
    and Archived -- there is no Cancelled -- so the fixture described a row the
    real database cannot contain, and the filter it was demonstrating excludes
    nothing on the real site. A green test about an impossible world.

    Checking names and not values is what let that stand for several sweeps.
    """


class ValidationError(Exception):
    """What frappe.throw raises."""


class _dict(dict):
    """dict with attribute access, like frappe._dict."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


def doctype_fields(module, doctype_dir):
    """Read a DocType's real field list out of its JSON in this repo.

    Reading the JSON rather than hard-coding a list means these tests follow
    the DocType: if a field is added or removed, they move with it.
    """
    path = os.path.join(
        APP_ROOT, "erplite", module, "doctype", doctype_dir, doctype_dir + ".json"
    )
    with open(path, "rb") as handle:
        definition = json.loads(handle.read().decode("utf-8"))

    fields = {f["fieldname"] for f in definition.get("fields", []) if f.get("fieldname")}
    # Frappe's standard columns, present on every DocType's table.
    fields.update({
        "name", "owner", "creation", "modified", "modified_by", "docstatus",
        "idx", "_assign", "_comments", "_user_tags", "_liked_by",
    })
    return fields


def doctype_select_options(module, doctype_dir):
    """fieldname -> set(options) for a DocType's Select fields, from its JSON."""
    path = os.path.join(
        APP_ROOT, "erplite", module, "doctype", doctype_dir, doctype_dir + ".json"
    )
    with open(path, "rb") as handle:
        definition = json.loads(handle.read().decode("utf-8"))

    options = {}
    for field in definition.get("fields", []):
        if field.get("fieldtype") != "Select":
            continue
        name, raw = field.get("fieldname"), field.get("options")
        if not name or not raw:
            continue
        allowed = {o.strip() for o in raw.split("\n") if o.strip()}
        if allowed:
            options[name] = allowed
    return options


# ToDo is a Frappe DocType, not one of ours, so its fields are listed here.
TODO_FIELDS = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "status", "priority", "color", "date", "allocated_to", "description",
    "reference_type", "reference_name", "role", "assigned_by",
    "assigned_by_full_name", "sender", "assignment_rule", "_assign",
}

# Likewise ToDo's Select options, read from frappe version-15's
# frappe/desk/doctype/todo/todo.json. Its controller states the same set a
# second time as `status: DF.Literal["Open", "Closed", "Cancelled"]`
# (frappe/desk/doctype/todo/todo.py:35).
TODO_SELECT_OPTIONS = {
    "status": {"Open", "Closed", "Cancelled"},
    "priority": {"High", "Medium", "Low"},
}

ALIAS = re.compile(r"^\s*(?P<field>[\w.]+)\s+as\s+(?P<alias>[\w]+)\s*$", re.IGNORECASE)


def _as_datetime(value):
    """A datetime for a datetime, a date or an ISO-ish string. Used by `between`."""
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    return datetime.datetime.fromisoformat(str(value))


def _matches(row, key, condition):
    value = row.get(key)

    if not isinstance(condition, (list, tuple)):
        return value == condition

    operator, operand = condition[0], condition[1] if len(condition) > 1 else None
    operator = operator.lower()

    if operator == "=":
        return value == operand
    if operator in ("!=", "not ="):
        return value != operand
    if operator == "in":
        return value in operand
    if operator == "not in":
        return value not in operand
    if operator == "is":
        if operand == "set":
            return value not in (None, "")
        if operand == "not set":
            return value in (None, "")
    if operator == "like":
        return operand.replace("%", "") in (value or "")
    if operator == "between":
        # Afterz's submit_week_entries filters check_in_time with
        # ["between", ["<date> 00:00:00", "<date> 23:59:59"]], so the two sides
        # are a datetime column and two strings. Compare as datetimes, because
        # string order and datetime order disagree the moment a format differs.
        low, high = operand
        if value is None:
            return False
        value, low, high = (_as_datetime(v) for v in (value, low, high))
        # frappe's `between` is inclusive on both ends (frappe/database/query.py).
        return low <= value <= high
    raise NotImplementedError("fake get_all does not implement operator %r" % (operator,))


class FakeFrappe(object):
    def __init__(self, session_user="zeke@tierneymorris.com.au", roles=None):
        self.session = _dict(user=session_user)
        self._roles = roles if roles is not None else ["System Manager"]
        self.tables = {}
        self.fields = {
            "Activity": doctype_fields("projects", "activity"),
            "Project": doctype_fields("projects", "project"),
            "ToDo": TODO_FIELDS,
            "Division": doctype_fields("scheduler", "division"),
            "Timesheet Entry": doctype_fields("projects", "timesheet_entry"),
            "Schedule Entry": doctype_fields("scheduler", "schedule_entry"),
            "Resource": doctype_fields("scheduler", "resource"),
        }
        self.select_options = {
            "Activity": doctype_select_options("projects", "activity"),
            "Project": doctype_select_options("projects", "project"),
            "ToDo": dict(TODO_SELECT_OPTIONS),
            "Division": doctype_select_options("scheduler", "division"),
            "Timesheet Entry": doctype_select_options("projects", "timesheet_entry"),
            "Schedule Entry": doctype_select_options("scheduler", "schedule_entry"),
            "Resource": doctype_select_options("scheduler", "resource"),
        }
        self.errors = []
        self.messages = []
        self.commits = 0
        # Everything the code asked us to do, so tests can assert on it.
        self.queries = []
        self.assignments_added = []
        self.assignments_removed = []
        self.values_set = []
        self.db = _FakeDb(self)

    # -- decorators and odds and ends the module touches at import time --
    def whitelist(self, *args, **kwargs):
        def decorator(fn):
            return fn
        if args and callable(args[0]):
            return args[0]
        return decorator

    def _(self, message, *args, **kwargs):
        """frappe._ is gettext; the stand-in passes the string through."""
        return message

    def get_roles(self, user=None):
        return list(self._roles)

    def log_error(self, *args, **kwargs):
        self.errors.append((args, kwargs))

    def msgprint(self, *args, **kwargs):
        self.messages.append((args, kwargs))

    def throw(self, message, exc=None, **kwargs):
        """frappe.throw aborts the save; nothing after it runs."""
        raise (exc or ValidationError)(message)

    def parse_json(self, value):
        if isinstance(value, str):
            return json.loads(value)
        return value

    def _check_fields(self, doctype, names, where):
        known = self.fields.get(doctype)
        if known is None:
            raise UnknownField("fake frappe knows nothing about doctype %r" % (doctype,))
        for name in names:
            if name not in known:
                raise UnknownField(
                    "%s has no field %r (used in %s). Fields: %s"
                    % (doctype, name, where, ", ".join(sorted(known)))
                )

    def _check_select_rows(self, doctype):
        """Refuse to serve a fixture row holding a Select value its DocType forbids.

        Checked when rows are read rather than when they are put in `tables`,
        because the tests assign to `frappe.tables[...]` directly and there is
        no single place a fixture passes through on the way in.
        """
        allowed_by_field = self.select_options.get(doctype)
        if not allowed_by_field:
            return
        for row in self.tables.get(doctype, []):
            for field, allowed in allowed_by_field.items():
                value = row.get(field)
                if value in (None, "") or value in allowed:
                    continue
                raise ImpossibleValue(
                    "fixture %s %r has %s=%r, which %s.%s cannot hold. Options: %s"
                    % (doctype, row.get("name"), field, value, doctype, field,
                       ", ".join(sorted(allowed))))

    def _check_select_filters(self, doctype, filters, where):
        """Refuse a filter comparing a Select field to a value no row can hold."""
        allowed_by_field = self.select_options.get(doctype)
        if not allowed_by_field or not filters:
            return
        for field, condition in filters.items():
            allowed = allowed_by_field.get(field)
            if not allowed:
                continue
            if isinstance(condition, (list, tuple)) and len(condition) == 2:
                operator, operand = str(condition[0]).lower(), condition[1]
                if operator in ("in", "not in") and isinstance(operand, (list, tuple, set)):
                    candidates = list(operand)
                elif operator in ("=", "==", "!=", "not ="):
                    candidates = [operand]
                else:
                    continue
            elif isinstance(condition, (list, tuple)):
                continue
            else:
                candidates = [condition]
            for value in candidates:
                if not isinstance(value, str) or value in allowed:
                    continue
                raise ImpossibleValue(
                    "%s filters %s.%s against %r, which it cannot hold, so the filter "
                    "matches the wrong set in silence (== matches nothing, != matches "
                    "everything). Options: %s"
                    % (where, doctype, field, value, ", ".join(sorted(allowed))))

    # -- the query API under test --
    def get_all(self, doctype, fields=None, filters=None, order_by=None,
                pluck=None, limit=None, **kwargs):
        self.queries.append(_dict(
            doctype=doctype, fields=list(fields or []),
            filters=dict(filters or {}), order_by=order_by, pluck=pluck,
        ))

        requested = []          # (column, output_key)
        for entry in (fields or []):
            match = ALIAS.match(entry)
            if match:
                requested.append((match.group("field"), match.group("alias")))
            else:
                requested.append((entry, entry))

        if pluck:
            requested.append((pluck, pluck))

        self._check_fields(doctype, [c for c, _ in requested], "fields")
        self._check_fields(doctype, list((filters or {}).keys()), "filters")
        if order_by:
            self._check_fields(doctype, [order_by.split()[0]], "order_by")
        self._check_select_filters(doctype, filters, "get_all")
        self._check_select_rows(doctype)

        rows = [r for r in self.tables.get(doctype, [])
                if all(_matches(r, k, v) for k, v in (filters or {}).items())]

        if order_by:
            # Direction matters: `modified desc` is how the callers ask for
            # "the most recent N", and ignoring the keyword silently gave
            # them the oldest N instead. NULLs sort lowest, as in MariaDB.
            parts = order_by.split()
            column = parts[0]
            descending = len(parts) > 1 and parts[1].lower() == "desc"
            rows = sorted(
                rows,
                key=lambda r: (r.get(column) is not None, r.get(column)),
                reverse=descending,
            )

        if limit:
            rows = rows[:limit]

        if pluck:
            return [r.get(pluck) for r in rows]

        return [_dict((out, r.get(col)) for col, out in requested) for r in rows]


class _FakeDb(object):
    def __init__(self, frappe):
        self._frappe = frappe

    def exists(self, doctype, name):
        return any(r.get("name") == name for r in self._frappe.tables.get(doctype, []))

    def get_value(self, doctype, name=None, fieldname="name", **kwargs):
        # Real frappe's signature is get_value(doctype, filters=None,
        # fieldname="name", ...), and `filters` may be a dict as well as a
        # name. This stand-in used to require `fieldname` and match only on
        # row["name"], so erplite's own
        #     frappe.db.get_value("Customer", {"xero_contact_id": cid})
        # raised TypeError here -- a stand-in fault that surfaced through the
        # app's broad `except Exception` as "Error importing customer from
        # Xero: ... missing 1 required positional argument", reading exactly
        # like a bug in the app. Matching real frappe is what makes the
        # duplicate-contact check testable at all.
        many = isinstance(fieldname, (list, tuple))
        names = list(fieldname) if many else [fieldname]
        self._frappe._check_fields(doctype, names, "get_value")
        if isinstance(name, dict):
            self._frappe._check_fields(doctype, list(name), "get_value filters")
            self._frappe._check_select_filters(doctype, name, "get_value")
        self._frappe._check_select_rows(doctype)
        for row in self._frappe.tables.get(doctype, []):
            if (all(row.get(k) == v for k, v in name.items())
                    if isinstance(name, dict) else row.get("name") == name):
                if not many:
                    return row.get(fieldname)
                values = [row.get(f) for f in names]
                return _dict(zip(names, values)) if kwargs.get("as_dict") else values
        return None

    def set_value(self, doctype, name, fieldname, value=None, **kwargs):
        # Reads were checked and writes were not, so a set_value naming a
        # removed field or a removed DocType went through without a murmur.
        # Real Frappe puts the name straight into the UPDATE, so the write
        # either lands in an orphaned column or the statement fails.
        #
        # `fieldname` may be a dict of several fields, which is real Frappe's
        # documented signature -- frappe/database/database.py: "Property /
        # field name or dictionary of values to be updated", with `val=None`.
        # erplite/xero/accounts.py calls it that way for all four xero_* fields
        # at once, so a stand-in that only took one field made that call look
        # like a TypeError from the app rather than a gap here.
        if isinstance(fieldname, dict):
            updates = dict(fieldname)
        else:
            updates = {fieldname: value}
        self._frappe._check_fields(doctype, list(updates), "set_value")
        # A write of an unlisted Select value is rejected by real Frappe
        # (_validate_selects), so the stand-in rejects it too.
        self._frappe._check_select_filters(doctype, updates, "set_value")
        for field, val in updates.items():
            self._frappe.values_set.append((doctype, name, field, val))
        for row in self._frappe.tables.get(doctype, []):
            if row.get("name") == name:
                for field, val in updates.items():
                    row[field] = val

    def commit(self):
        self._frappe.commits += 1


class FakeAssignTo(object):
    """Stands in for frappe.desk.form.assign_to."""

    def __init__(self, frappe):
        self._frappe = frappe

    def add(self, args=None, **kwargs):
        self._frappe.assignments_added.append(dict(args or {}))
        for user in self._frappe.parse_json(args.get("assign_to")):
            self._frappe.tables.setdefault("ToDo", []).append(_dict(
                name="todo-%d" % (len(self._frappe.tables.get("ToDo", [])) + 1,),
                reference_type=args["doctype"], reference_name=args["name"],
                allocated_to=user, status="Open",
            ))
        return []

    def remove(self, doctype, name, assign_to, **kwargs):
        self._frappe.assignments_removed.append((doctype, name, assign_to))
        for row in self._frappe.tables.get("ToDo", []):
            if (row.get("reference_type") == doctype
                    and row.get("reference_name") == name
                    and row.get("allocated_to") == assign_to):
                row["status"] = "Cancelled"
        return []


class FakeDocumentBase(object):
    """The base erplite's DocType controllers inherit from.

    Almost empty: Frappe's Document does the work in __init__, and make_doc
    below stands in for that, so a controller under test behaves the way Frappe
    would drive it.

    The two methods here are the ones a pre-save hook can legitimately call to
    see the document as it was before this save. They are ported from
    frappe-version-15/frappe/model/document.py rather than invented, because
    their edge cases are the whole point:

      * `_doc_before_save` is loaded by `check_if_latest()` (document.py:408),
        which `_save()` calls BEFORE `run_before_save_methods()` (:414). So a
        `before_save` hook can read it.
      * `load_doc_before_save` returns early when `is_new()` (:1161-1164), so on
        an insert it stays None.
      * `has_value_changed` returns **True** when there is no previous document
        (:508-509). On an insert that means "everything changed", which is the
        opposite of what a hook guarding against an explicit edit wants.

    A test drives the ordering itself; see test_trip_status.py.
    """

    _doc_before_save = None

    def get_doc_before_save(self):
        """frappe Document.get_doc_before_save (document.py:503-504)."""
        return getattr(self, "_doc_before_save", None)

    def has_value_changed(self, fieldname):
        """frappe Document.has_value_changed (document.py:506-524).

        Note the first branch: no previous document means True.
        """
        previous = self.get_doc_before_save()
        if not previous:
            return True
        return getattr(previous, fieldname, None) != getattr(self, fieldname, None)


def make_doc(controller_class, doctype, module, doctype_dir, data=None):
    """Build a controller instance the way Frappe builds a new document.

    Which attributes a Document has is the whole point of this helper, so it
    is worth being precise about what Frappe actually does:

      * BaseDocument.__init__ sets only the keys in the dict it is handed.
      * Document.__init__ then calls init_valid_columns(), which fills in
        default_fields plus whatever get_valid_columns() returns.
      * get_valid_columns() returns self.meta.get_valid_columns() - the
        DocType's own field list. It only reads the real table columns for
        DOCTYPES_FOR_DOCTYPE (DocType, DocField and friends), which no app
        DocType is.
      * Neither BaseDocument nor Document defines __getattr__.

    So a field that was removed from the DocType JSON has no attribute on a
    document built in memory, and self.<that field> raises AttributeError,
    even though bench migrate left the column in the table. A document loaded
    from the database is the other case: load_from_db does SELECT *, so it
    picks the orphaned column's stale value up as an attribute.

    Every new record goes through the in-memory case, which is why a leftover
    reference breaks creation outright rather than merely reading nonsense.
    """
    valid = doctype_fields(module, doctype_dir)
    doc = controller_class.__new__(controller_class)
    doc.doctype = doctype
    for field in valid:
        object.__setattr__(doc, field, None)
    # init_valid_columns gives these two a value rather than leaving them None.
    doc.docstatus = 0
    doc.idx = 0
    for key, value in (data or {}).items():
        if key not in valid:
            raise AttributeError(
                "%s has no field %r, so Frappe would not set it either" % (doctype, key))
        setattr(doc, key, value)
    return doc
