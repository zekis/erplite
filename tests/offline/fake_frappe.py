# -*- coding: utf-8 -*-
"""A small in-memory stand-in for the parts of `frappe` that
erplite.projects.api uses, so its queries can be tested without a bench.

The important behaviour here is deliberately *stricter* than real Frappe.
`frappe.get_all` in Frappe 15 does not validate field names: an unknown field
in `fields` comes back as None, an unknown field in `filters` matches nothing,
and an unknown `order_by` is ignored. Nothing raises and nothing is logged,
which is what let the Activity `subject` / `assigned_to` bug sit unnoticed.

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
            column = order_by.split()[0]
            rows = sorted(rows, key=lambda r: (r.get(column) is None, r.get(column)))

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

    def get_value(self, doctype, name, fieldname, **kwargs):
        many = isinstance(fieldname, (list, tuple))
        names = list(fieldname) if many else [fieldname]
        self._frappe._check_fields(doctype, names, "get_value")
        for row in self._frappe.tables.get(doctype, []):
            if row.get("name") == name:
                if not many:
                    return row.get(fieldname)
                values = [row.get(f) for f in names]
                return _dict(zip(names, values)) if kwargs.get("as_dict") else values
        return None

    def set_value(self, doctype, name, fieldname, value, **kwargs):
        self._frappe.values_set.append((doctype, name, fieldname, value))
        for row in self._frappe.tables.get(doctype, []):
            if row.get("name") == name:
                row[fieldname] = value

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
