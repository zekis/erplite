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

import json
import os
import re

APP_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


class UnknownField(Exception):
    """Raised when a query names a field the DocType does not have."""


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


# ToDo is a Frappe DocType, not one of ours, so its fields are listed here.
TODO_FIELDS = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "status", "priority", "color", "date", "allocated_to", "description",
    "reference_type", "reference_name", "role", "assigned_by",
    "assigned_by_full_name", "sender", "assignment_rule", "_assign",
}

ALIAS = re.compile(r"^\s*(?P<field>[\w.]+)\s+as\s+(?P<alias>[\w]+)\s*$", re.IGNORECASE)


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

    Deliberately empty: Frappe's Document does the work in __init__, and
    make_doc below stands in for that, so a controller under test behaves the
    way Frappe would drive it.
    """


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
