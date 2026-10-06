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


class DoesNotExistError(Exception):
    """frappe.DoesNotExistError, raised by get_doc for a name that is not there."""


class ValidationError(Exception):
    """What frappe.throw raises."""


class TimestampMismatchError(ValidationError):
    """frappe.TimestampMismatchError: the row moved after the document was read.

    A ValidationError subclass, exactly as frappe declares it
    (`frappe/exceptions.py:152`). That inheritance is the point rather than a
    detail: an endpoint whose handler is `except Exception` cannot tell this
    apart from a business-rule failure, so it re-labels a stale-write bug as
    "Failed to send ... to Xero" and rolls the request back.
    """


class PermissionError(Exception):
    """frappe.PermissionError, raised by has_permission(throw=True).

    Deliberately NOT a subclass of ValidationError, because frappe's is not:
    `frappe/exceptions.py:34` declares `class PermissionError(Exception)` with
    `http_status_code = 403`, while `ValidationError` (`:18`) is a separate
    `Exception` subclass carrying 417.

    That distinction is load-bearing rather than cosmetic. Four of the six Xero
    endpoints wrap their body in `except Exception` and re-raise through
    `frappe.throw`, which raises ValidationError. A permission gate placed
    *inside* one of those try blocks would therefore be caught and relabelled
    "Failed to send invoice to Xero" -- reporting a refusal, which sent nothing,
    as a failed send, which may have sent something. If this class inherited
    from ValidationError the tests could not tell the two apart and the gate
    could be moved inside the try without anything going red.
    """


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


def doctype_permissions(module, doctype_dir):
    """role -> {ptype: True} for a DocType, from the `permissions` rows in its JSON.

    Read from the JSON for the same reason as the field list: the gate under test
    enforces the rows this repo ships, so the test must follow them rather than
    restate them. If someone grants a new role write on Sales Invoice, these
    tests move with it instead of going stale.
    """
    path = os.path.join(
        APP_ROOT, "erplite", module, "doctype", doctype_dir, doctype_dir + ".json"
    )
    with open(path, "rb") as handle:
        definition = json.loads(handle.read().decode("utf-8"))

    rows = {}
    for row in definition.get("permissions", []):
        role = row.get("role")
        if not role:
            continue
        granted = {p for p in ("read", "write", "create", "delete", "submit",
                               "cancel", "amend", "report", "export", "share")
                   if row.get(p)}
        entry = rows.setdefault(role, {"granted": set(), "if_owner": False})
        entry["granted"] |= granted
        if row.get("if_owner"):
            entry["if_owner"] = True
    return rows


# ToDo is a Frappe DocType, not one of ours, so its fields are listed here.
TODO_FIELDS = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "status", "priority", "color", "date", "allocated_to", "description",
    "reference_type", "reference_name", "role", "assigned_by",
    "assigned_by_full_name", "sender", "assignment_rule", "_assign",
}

# Likewise ToDo's Select options -- but NOT frappe's. This site's ToDo carries five
# statuses with `Backlog` as the default, measured read-only against
# crew.tierneymorris.com.au on 5 Oct 2026; stock frappe version-15 ships only
# `Open\nClosed\nCancelled` and its controller restates that as
# `status: DF.Literal["Open", "Closed", "Cancelled"]` (frappe/desk/doctype/todo/todo.py:35).
# Trusting frappe's copy here, as this file first did, makes the stand-in reject writes the
# real site accepts -- `status="Backlog"` is what `create_todo` sets and what the kanban's
# backlog column reads. tests/offline/test_select_values.py KNOWN_CORE_SELECTS carries the
# same set, the measured counts behind it, and the migrate risk; keep the two in step.
TODO_SELECT_OPTIONS = {
    "status": {"Backlog", "Planned", "Open", "Closed", "Cancelled"},
    "priority": {"High", "Medium", "Low"},
}

# Two more Frappe DocTypes, listed here for the same reason ToDo is: they are
# not ours, so doctype_fields() has no JSON to read. The todo kanban page reads
# `Has Role` to decide who is a manager and `User` to fill its assignee list.
HAS_ROLE_FIELDS = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "parent", "parentfield", "parenttype", "role",
}

USER_FIELDS = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "email", "first_name", "last_name", "full_name", "username", "user_image",
    "enabled", "user_type", "time_zone",
}

ALIAS = re.compile(r"^\s*(?P<field>[\w.]+)\s+as\s+(?P<alias>[\w]+)\s*$", re.IGNORECASE)


def _order_by_columns(order_by):
    """The column names in an `order_by`, without their direction keywords."""
    columns = []
    for clause in order_by.split(","):
        parts = clause.strip().split()
        if parts:
            columns.append(parts[0])
    return columns


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
    def __init__(self, session_user="pat@company.test", roles=None):
        self.session = _dict(user=session_user)
        self._roles = roles if roles is not None else ["System Manager"]
        self.tables = {}
        self.fields = {
            "Activity": doctype_fields("projects", "activity"),
            "Project": doctype_fields("projects", "project"),
            "ToDo": TODO_FIELDS,
            "Has Role": HAS_ROLE_FIELDS,
            "User": USER_FIELDS,
            "Division": doctype_fields("scheduler", "division"),
            "Timesheet Entry": doctype_fields("projects", "timesheet_entry"),
            "Schedule Entry": doctype_fields("scheduler", "schedule_entry"),
            "Resource": doctype_fields("scheduler", "resource"),
            "Scheduler Role": doctype_fields("scheduler", "scheduler_role"),
            "Schedule Row": doctype_fields("scheduler", "schedule_row"),
            "Schedule Template": doctype_fields("scheduler", "schedule_template"),
        }
        self.select_options = {
            "Activity": doctype_select_options("projects", "activity"),
            "Project": doctype_select_options("projects", "project"),
            "ToDo": dict(TODO_SELECT_OPTIONS),
            "Division": doctype_select_options("scheduler", "division"),
            "Timesheet Entry": doctype_select_options("projects", "timesheet_entry"),
            "Schedule Entry": doctype_select_options("scheduler", "schedule_entry"),
            "Resource": doctype_select_options("scheduler", "resource"),
            "Scheduler Role": doctype_select_options("scheduler", "scheduler_role"),
            "Schedule Row": doctype_select_options("scheduler", "schedule_row"),
            "Schedule Template": doctype_select_options("scheduler", "schedule_template"),
        }
        # doctype -> doctype_permissions(...) rows. Loaded here, from the
        # JSON, rather than left empty for each test to fill: `get_list` asks
        # `has_permission` on every read, and an unloaded DocType is an
        # AssertionError, so leaving these out would make every test that
        # reaches a `get_list` call site fail for the wrong reason. A test that
        # wants different rows still assigns over them.
        self.permissions = {
            "Activity": doctype_permissions("projects", "activity"),
            "Project": doctype_permissions("projects", "project"),
            "Timesheet Entry": doctype_permissions("projects", "timesheet_entry"),
            "Division": doctype_permissions("scheduler", "division"),
            "Schedule Entry": doctype_permissions("scheduler", "schedule_entry"),
            "Resource": doctype_permissions("scheduler", "resource"),
            "Scheduler Role": doctype_permissions("scheduler", "scheduler_role"),
            "Schedule Row": doctype_permissions("scheduler", "schedule_row"),
            "Schedule Template": doctype_permissions("scheduler", "schedule_template"),
            "Scheduler Log": doctype_permissions("scheduler", "scheduler_log"),
        }
        self.permission_checks = []  # every has_permission asked, for assertions
        self.errors = []
        self.messages = []
        self.commits = 0
        # Everything the code asked us to do, so tests can assert on it.
        self.queries = []
        self.assignments_added = []
        self.assignments_removed = []
        self.values_set = []
        self.inserts = []
        self.saves = []
        self.deletes = []
        self._names = {}
        # Real `modified` values differ between two writes; a constant cannot
        # model a stale-document check at all. This advances once per write so
        # ordinary reads/writes behave as before while a second write to the
        # same row becomes visible to the first reader.
        self._clock = 0
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

    def has_permission(self, doctype=None, ptype="read", doc=None, user=None,
                       throw=False, **kwargs):
        """frappe.has_permission, enforcing the permission rows this repo ships.

        Mirrors frappe 15.52.0 in the behaviours these tests rest on, each read
        from the source rather than assumed:

          * `Administrator` is allowed everything, before any row is consulted
            (`frappe/permissions.py:106-108`).
          * A `doc` given as a **name** is loaded and the check is done against
            the document (`permissions.py:125-127`). So a name that does not
            exist raises `DoesNotExistError` -- it is not a refusal, and the
            difference matters: a gate must not turn a typo into "no permission".
          * With `throw=True` a refusal raises `frappe.PermissionError`
            (`frappe/__init__.py:1045-1048`); with `throw=False` it returns
            False and raises nothing.
          * `doctype` may be omitted when `doc` is a document, in which case the
            DocType comes off the doc (`__init__.py:1032-1033`).

        The permission rows come from `self.permissions`, loaded out of the
        DocType JSON by `doctype_permissions`. A DocType with no entry there is
        refused for every non-Administrator rather than allowed, so a test that
        forgot to load its rows fails loudly instead of passing vacuously.

        Blind spots, stated so they are places to look rather than places to
        stop: real frappe also applies User Permissions, document sharing,
        `has_permission` hooks and the submittable docstatus rules in
        `get_doc_permissions`. None of the four DocTypes gated here declares a
        share rule or a hook, and none is submittable, so the role rows and
        `if_owner` are the whole of the real answer for them -- but this is not
        a general-purpose permission engine and should not be used as one.
        """
        if doctype is None and doc is not None and hasattr(doc, "doctype"):
            doctype = doc.doctype

        if user is None:
            user = self.session.user

        if user == "Administrator":
            return True

        rows = self.permissions.get(doctype)
        if rows is None:
            raise AssertionError(
                "has_permission asked about %r, whose permission rows were never "
                "loaded into this FakeFrappe. Load them with "
                "doctype_permissions(module, dir) so the answer comes from the "
                "DocType JSON rather than from this stand-in's silence." % (doctype,)
            )

        # A name resolves to the document, as frappe does, so a missing record
        # raises rather than being refused.
        if doc is not None and isinstance(doc, (str, int)):
            doc = self.get_doc(doctype, doc)

        # frappe's own algorithm, from get_role_permissions
        # (permissions.py:288-305). Ported rather than paraphrased because its
        # no-doc answer is the whole point and this file had it wrong before:
        # it used to let an `if_owner` row grant write at DocType level, so a
        # Projects User passed `has_permission("Timesheet Entry", "write")`.
        # Frappe refuses that. For a right granted only by `if_owner` rows it
        # sets the right to 0 -- except `select` and `read`, which stay 1 so the
        # list view can load and then be filtered by owner, and except `create`,
        # which `if_owner` never restricts ("if_owner does not come with create
        # rights", permissions.py:303-305).
        #
        # Note the three tests are taken across **all** the user's applicable
        # rows, not row by row: a user holding both Projects User (write
        # `if_owner`) and Projects Manager (write outright) has write on
        # everyone's rows, because one applicable row grants it without
        # `if_owner`.
        applicable = [rows[role] for role in self.get_roles(user) if role in rows]
        granted = any(ptype in entry["granted"] for entry in applicable)
        has_if_owner_enabled = any(entry["if_owner"] for entry in applicable)
        without_if_owner = any(
            ptype in entry["granted"] and not entry["if_owner"] for entry in applicable)

        if not granted:
            allowed = False
        elif has_if_owner_enabled and not without_if_owner and ptype != "create":
            if doc is None:
                allowed = ptype in ("select", "read")
            else:
                if not hasattr(doc, "get"):
                    raise AssertionError(
                        "has_permission was given a %r, which cannot answer "
                        "`owner`, on a DocType whose rows are restricted by "
                        "if_owner. Refusing silently would make the check pass "
                        "for the wrong reason." % (type(doc).__name__,))
                allowed = doc.get("owner") == user
        else:
            allowed = True

        self.permission_checks.append(
            _dict(doctype=doctype, ptype=ptype,
                  doc=(doc.get("name") if doc is not None and hasattr(doc, "get") else doc),
                  user=user, allowed=allowed, threw=bool(throw) and not allowed))

        if not allowed and throw:
            raise PermissionError("No permission for %s" % (doctype,))
        return allowed

    def get_roles(self, user=None):
        return list(self._roles)

    def log_error(self, *args, **kwargs):
        self.errors.append((args, kwargs))

    def msgprint(self, *args, **kwargs):
        self.messages.append((args, kwargs))

    def throw(self, message, exc=None, **kwargs):
        """frappe.throw aborts the save; nothing after it runs."""
        raise (exc or ValidationError)(message)

    def _check_select_values(self, doctype, data):
        """Refuse to write a Select value the DocType cannot hold.

        The real database does not enforce this -- the column is varchar -- so
        a status the DocType never declared is written and read back happily.
        That is precisely the bug class this suite exists to catch, so the
        stand-in raises where Frappe would shrug.
        """
        allowed_by_field = self.select_options.get(doctype) or {}
        for field, allowed in allowed_by_field.items():
            value = data.get(field)
            if value in (None, "") or value in allowed:
                continue
            raise ImpossibleValue(
                "writing %s %r with %s=%r, which %s.%s cannot hold. Options: %s"
                % (doctype, data.get("name"), field, value, doctype, field,
                   ", ".join(sorted(allowed))))

    def next_stamp(self):
        """The next `modified` value. Monotonic, and shaped like frappe's."""
        self._clock += 1
        return "2026-10-06 09:%02d:%02d" % (self._clock // 60, self._clock % 60)

    def _find_row(self, doctype, name):
        for row in self.tables.get(doctype, []):
            if row.get("name") == name:
                return row
        return None

    def get_doc(self, doctype, name=None, **kwargs):
        """frappe.get_doc, in its two shapes.

        `get_doc(dict)` builds a new, unsaved document; `get_doc(doctype,
        name)` loads a stored one. The page under test uses both, which is why
        neither could be called before this existed.
        """
        if isinstance(doctype, dict):
            data = dict(doctype)
            doctype = data.pop("doctype")
            self._check_fields(doctype, list(data.keys()), "get_doc({...})")
            return FakeStoredDoc(self, doctype, data, is_new=True)

        row = self._find_row(doctype, name)
        if row is None:
            raise DoesNotExistError("%s %r not found" % (doctype, name))
        # A copy, not the row: Frappe only writes on save(), so a test can tell
        # an aborted save from a completed one.
        return FakeStoredDoc(self, doctype, dict(row), is_new=False)

    def get_cached_doc(self, doctype, name=None, **kwargs):
        """Frappe's cached read. Same answer; the cache is not what is under test."""
        return self.get_doc(doctype, name, **kwargs)

    def delete_doc(self, doctype, name=None, **kwargs):
        row = self._find_row(doctype, name)
        if row is None:
            raise DoesNotExistError("%s %r not found" % (doctype, name))
        self.tables[doctype].remove(row)
        self.deletes.append(_dict(doctype=doctype, name=name))

    def next_name(self, doctype):
        self._names[doctype] = self._names.get(doctype, 0) + 1
        return "%s-%04d" % (doctype.upper().replace(" ", "-"), self._names[doctype])

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
    def get_list(self, doctype, *args, **kwargs):
        """frappe.get_list: get_all, but it consults the DocType's read rows.

        The one difference, read off the installed frappe 15.52.0 rather than
        assumed: there is only one implementation. `get_list`
        (`frappe/__init__.py:1970`) calls `DatabaseQuery(doctype).execute(...)`
        as given, and `get_all` (`:1993`) is that same call with
        `ignore_permissions=True` added (`:2012`) -- its own docstring says it
        "will **not** check for permissions". `execute` starts with `if not
        ignore_permissions: self.check_read_permission(...)`
        (`frappe/model/db_query.py:114-115`), which calls
        `frappe.has_permission(..., throw=True)` in `_set_permission_map`
        (`:516-523`). So the gate is the one flag, and `get_all` is the only
        one of the pair that sets it.

        **A user with no read row therefore gets `frappe.PermissionError`, not
        an empty list.** That is the behaviour to hold on to: the refusal is
        loud, and a caller that wanted "the rows I may see, or none" does not
        get it from `get_list`.

        Blind spots, stated so they are places to look rather than places to
        stop:

          * **No row-level narrowing.** Real `get_list` also applies User
            Permissions and `if_owner`, which cut down the rows that come
            back. This answers the DocType-level question only, so a test must
            not read "which rows a restricted user sees" off this stand-in.
          * **No select-only fallback.** `_set_permission_map` asks for
            `select` instead of `read` when `frappe.only_has_select_perm` is
            true. None of the DocTypes here grants select without read, so the
            distinction never arises; it would have to be added if one did.
          * **No child-table handling.** Real `get_list` on an `istable`
            DocType is refused unless `parent_doctype` is passed, because
            `has_permission` rejects a child DocType as its own parent
            (`frappe/permissions.py:780`). None of the call sites converted
            here reads a child table.
        """
        self.has_permission(doctype, ptype="read", throw=True)
        return self.get_all(doctype, *args, **kwargs)

    def get_all(self, doctype, fields=None, filters=None, order_by=None,
                pluck=None, limit=None, or_filters=None, **kwargs):
        self.queries.append(_dict(
            doctype=doctype, fields=list(fields or []),
            filters=dict(filters or {}), or_filters=dict(or_filters or {}),
            order_by=order_by, pluck=pluck,
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
        self._check_fields(doctype, list((or_filters or {}).keys()), "or_filters")
        if order_by:
            # `order_by` may name more than one column -- the scheduler asks for
            # "schedule_date, start_time". Splitting on whitespace alone made the
            # first column "schedule_date," and rejected a legitimate query, so
            # every clause is split out and checked. Direction keywords (asc/desc)
            # are dropped before the check.
            self._check_fields(doctype, _order_by_columns(order_by), "order_by")
        self._check_select_filters(doctype, filters, "get_all")
        self._check_select_rows(doctype)

        rows = [r for r in self.tables.get(doctype, [])
                if all(_matches(r, k, v) for k, v in (filters or {}).items())]

        if or_filters:
            # Frappe ANDs the two groups and ORs within or_filters: filters go
            # into `conditions` and or_filters into `grouped_or_conditions`,
            # which DatabaseQuery joins with AND
            # (frappe/model/db_query.py build_conditions).
            rows = [r for r in rows
                    if any(_matches(r, k, v) for k, v in or_filters.items())]

        if order_by:
            # Direction matters: `modified desc` is how the callers ask for
            # "the most recent N", and ignoring the keyword silently gave
            # them the oldest N instead. NULLs sort lowest, as in MariaDB.
            #
            # Only the FIRST clause is applied. A multi-column `order_by` is
            # checked in full above but sorted on its leading column only, so a
            # test must not assert on the order within a tie -- real MariaDB
            # would break those ties and this does not.
            parts = order_by.split(",")[0].split()
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
        """frappe.db.exists(doctype, filters), where filters may be a name or a dict.

        This used to compare `row["name"]` only, so the todo kanban page's

            frappe.db.exists("Has Role", {"parent": user, "role": ["in", [...]]})

        compared a name against a dict and answered False for everybody --
        making every user a non-manager and quietly passing any test that did
        not involve a manager. A stand-in that cannot express the question
        gives the wrong answer rather than an error, which is the worst of the
        two, so it matches real Frappe's signature now.
        """
        rows = self._frappe.tables.get(doctype, [])
        if isinstance(name, dict):
            self._frappe._check_fields(doctype, list(name.keys()), "db.exists")
            for row in rows:
                if all(_matches(row, k, v) for k, v in name.items()):
                    return row.get("name")
            return None
        return any(r.get("name") == name for r in rows)

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
        # `update_modified` defaults to True in real frappe, so a set_value
        # moves the row out from under anything already holding it in memory.
        # Modelling this is what lets a test see a stale save, instead of the
        # stand-in silently making every stale save succeed.
        bump = kwargs.get("update_modified", True) and "modified" not in updates
        for row in self._frappe.tables.get(doctype, []):
            if row.get("name") == name:
                for field, val in updates.items():
                    row[field] = val
                if bump:
                    row["modified"] = self._frappe.next_stamp()

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

    def get(self, key, default=None):
        """frappe BaseDocument.get, for the plain-fieldname case.

        Here because `has_permission(doc=...)` asks a document for its `owner`
        the way frappe does. Without it a controller instance answered nothing,
        `hasattr(doc, "get")` was False, and the check silently refused -- a
        permission test that fails for the wrong reason is worse than no test.
        """
        return getattr(self, key, default)

    def is_new(self):
        """frappe BaseDocument.is_new (base_document.py:461-462): `__islocal`.

        `insert()` sets `__islocal` before it runs a single hook and deletes it
        once the row is written (document.py:390 and :430-432); `_save()` on an
        existing document never sets it. So a hook asking `self.is_new()` is
        asking "am I being inserted", and a rule guarded by it cannot reach an
        update. make_doc's `is_new=` argument stands in for that, and defaults
        to True because make_doc builds a document the way frappe builds a
        **new** one -- a test standing for a later save must say
        `is_new=False`.
        """
        return bool(getattr(self, "__islocal", False))

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


class FakeStoredDoc(object):
    """What `get_doc` hands back: a document that can be inserted or saved.

    Deliberately thin. It exists because the ToDo kanban page's endpoints are
    written against get_doc/insert/save rather than db.set_value, so before
    this there was no way to call them at all.

    Two behaviours are copied from Frappe rather than invented, because tests
    turn on them:

      * `insert()` sets `owner` from the session user (Frappe does this in
        BaseDocument.db_insert) and nothing afterwards changes it. That is why
        `owner` is the durable record of who created a document, and why the
        todo page can use it to keep a creator in touch with work they have
        handed on.
      * A save writes nothing until it is called. `get_doc` hands back a copy
        of the row, so a `frappe.throw` part-way through an endpoint leaves the
        stored document untouched -- which is what makes a refused update
        testable rather than merely unobserved.

    What it does NOT copy, so no test may assert on it: `fetch_from`. Frappe
    fills `assigned_by_full_name` from `assigned_by.full_name` on save; this
    does not. Nor does it enforce `reqd`; tests/offline/test_mandatory_fields_
    on_insert.py checks that statically across every get_doc literal instead.
    """

    STAMP = "2026-10-06 09:00:00"

    def __init__(self, frappe, doctype, data, is_new):
        object.__setattr__(self, "_frappe", frappe)
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_is_new", is_new)
        object.__setattr__(self, "doctype", doctype)

    def __getattr__(self, key):
        # Only reached when normal lookup fails, so the real attributes set in
        # __init__ never come through here.
        data = object.__getattribute__(self, "_data")
        if key in data:
            return data[key]
        doctype = object.__getattribute__(self, "doctype")
        known = object.__getattribute__(self, "_frappe").fields.get(doctype) or set()
        if key in known:
            # A declared field that this row has no value for. Frappe's
            # init_valid_columns gives it None rather than leaving it missing.
            return None
        raise AttributeError(
            "%s has no field %r, so Frappe would not have it either" % (doctype, key))

    def __setattr__(self, key, value):
        self._frappe._check_fields(self.doctype, [key], "setting %s.%s" % (self.doctype, key))
        self._data[key] = value

    def as_dict(self):
        return dict(self._data)

    def get_db_value(self, fieldname):
        """Frappe's Document.get_db_value: the stored value, not the in-memory one."""
        row = self._frappe._find_row(self.doctype, self._data.get("name"))
        return (row or {}).get(fieldname)

    def insert(self, **kwargs):
        frappe = self._frappe
        data = self._data
        data.setdefault("name", frappe.next_name(self.doctype))
        data.setdefault("owner", frappe.session.user)
        data.setdefault("creation", self.STAMP)
        data.setdefault("docstatus", 0)
        data.setdefault("idx", 0)
        data["modified"] = self.STAMP
        frappe._check_select_values(self.doctype, data)
        frappe.tables.setdefault(self.doctype, []).append(_dict(data))
        object.__setattr__(self, "_is_new", False)
        frappe.inserts.append(_dict(doctype=self.doctype, name=data["name"]))
        return self

    def save(self, **kwargs):
        if self._is_new:
            return self.insert()
        frappe = self._frappe
        frappe._check_select_values(self.doctype, self._data)
        row = frappe._find_row(self.doctype, self._data.get("name"))
        if row is None:
            raise DoesNotExistError(
                "%s %r vanished before save" % (self.doctype, self._data.get("name")))
        # frappe's check_if_latest (`model/document.py:372` calls it; `807-832`
        # is the body): it reloads the row and compares its `modified` against
        # the value the in-memory document was read with
        # (`_original_modified`, set in set_user_and_timestamp at `:556`).
        # Different means someone wrote in between, and it raises rather than
        # overwriting their write.
        if row.get("modified") != self._data.get("modified"):
            raise TimestampMismatchError(
                "Error: Document has been modified after you have opened it "
                "(%s, %s). Please refresh to get the latest document."
                % (row.get("modified"), self._data.get("modified")))
        self._data["modified"] = frappe.next_stamp()
        row.update(self._data)
        frappe.saves.append(_dict(doctype=self.doctype, name=self._data.get("name")))
        return self


class FakeUtils(object):
    """The handful of frappe.utils helpers the todo page formats dates with.

    Real `formatdate` honours the site's date format and `getdate` accepts
    several shapes. These do the least that lets the page run, and no test
    asserts on the exact wording of a formatted date.
    """

    def getdate(self, value=None):
        if value in (None, ""):
            return datetime.date.today()
        if isinstance(value, datetime.datetime):
            return value.date()
        if isinstance(value, datetime.date):
            return value
        return datetime.datetime.fromisoformat(str(value)[:19]).date()

    def today(self):
        return datetime.date.today().isoformat()

    def formatdate(self, value=None, fmt=None):
        if value in (None, ""):
            return ""
        return self.getdate(value).isoformat()

    def get_system_timezone(self):
        return "Australia/Perth"


def make_doc(controller_class, doctype, module, doctype_dir, data=None,
             is_new=True):
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
    # `__islocal` is not a DocType field, so it is set past __setattr__'s field
    # check, exactly as frappe's `self.set("__islocal", True)` sits outside the
    # valid column list.
    if is_new:
        object.__setattr__(doc, "__islocal", True)
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
