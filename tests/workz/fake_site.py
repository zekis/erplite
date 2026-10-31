"""Synthetic transactional site for application tests. No network or live fixtures.

This models doc hooks and constraints, not Frappe itself. MariaDB/Frappe staging
checks remain separate from this fast suite.
"""

import copy
import json
import sys
import threading
import types
from datetime import datetime
from pathlib import Path


class Row(dict):
    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value


class Rejected(Exception):
    pass


class Stale(Exception):
    pass


class Site:
    def __init__(self):
        self.data = {}
        self.serial = 0
        self.lock = threading.RLock()
        self.actor = "Administrator"
        self.defaults = {}
        self.now = datetime(2030, 1, 1)
        f = types.ModuleType("frappe")
        self.f = f
        f.session = Row(user=self.actor)
        f.flags = Row()
        f.request = Row(method="POST")
        f.PermissionError = Rejected
        f.TimestampMismatchError = Stale

        def throw(message, exc=Rejected):
            raise exc(message)

        f.throw = throw
        f.whitelist = lambda *a, **k: lambda fn: fn
        f.get_roles = lambda user=None: (
            ["System Manager"]
            if (user or self.actor) == "Administrator"
            else ["Projects User"]
        )
        f.has_permission = lambda *a, **k: True
        f.get_doc = self.get_doc
        f.new_doc = lambda dt: Doc(self, {"doctype": dt})
        f.get_all = self.get_all
        f.get_list = self.get_all
        f.delete_doc = lambda dt, name, **k: self.data[dt].pop(name)

        def meta(dt):
            slug = dt.lower().replace(" ", "_")
            path = Path("erplite/projects/doctype") / slug / (slug + ".json")
            return Row(
                fields=(
                    [Row(r) for r in json.loads(path.read_text())["fields"]]
                    if path.exists()
                    else []
                )
            )

        f.get_meta = meta
        self.savepoint = None

        def savepoint(name):
            self.savepoint = copy.deepcopy(self.data)

        def rollback(**k):
            self.data = copy.deepcopy(self.savepoint)

        f.defaults = Row(
            get_user_default=lambda k: self.defaults.get((self.actor, k)),
            set_user_default=lambda k, v: self.defaults.__setitem__((self.actor, k), v),
        )
        f.db = Row(
            exists=lambda dt, filters: self.get_all(dt, filters=filters, pluck="name")[
                :1
            ],
            get_value=self.get_value,
            savepoint=savepoint,
            rollback=rollback,
            sql=lambda *a, **k: [],
            escape=lambda v: "'" + v.replace("'", "''") + "'",
        )

        class Column:
            def __init__(self, key):
                self.key = key

            def __eq__(self, value):
                return (self.key, value)

        class Table:
            def __init__(self, name):
                self.name = name
                self.star = "*"

            def __getitem__(self, k):
                return Column(k)

            def __getattr__(self, k):
                return Column(k)

        class Query:
            def __init__(q, table):
                q.table = table
                q.filters = {}

            def select(q, *args):
                return q

            def where(q, pair):
                q.filters = dict([pair])
                return q

            def for_update(q):
                return q

            def run(q, **k):
                return self.get_all(q.table.name, filters=q.filters)

        f.qb = Row(DocType=Table, from_=Query)
        utils = types.ModuleType("frappe.utils")
        utils.get_system_timezone = lambda: "UTC"
        utils.get_datetime = lambda value: datetime.fromisoformat(str(value))
        utils.now_datetime = lambda: self.now
        assign = types.ModuleType("frappe.desk.form.assign_to")

        def add(args, **kwargs):
            for employee in args["assign_to"]:
                filt = dict(
                    reference_type=args["doctype"],
                    reference_name=args["name"],
                    allocated_to=employee,
                    status="Open",
                )
                if not self.get_all("ToDo", filt):
                    Doc(self, dict(doctype="ToDo", **filt)).save()

        def remove(dt, name, employee, **kwargs):
            for row in self.get_all(
                "ToDo",
                dict(reference_type=dt, reference_name=name, allocated_to=employee),
            ):
                doc = self.get_doc("ToDo", row.name)
                doc.status = "Cancelled"
                doc.save()

        assign._add = add
        assign._remove = remove
        files = types.ModuleType("frappe.utils.file_manager")
        files.save_file = lambda *a, **k: None
        sys.modules["frappe.utils.file_manager"] = files
        sys.modules.update(
            {"frappe": f, "frappe.utils": utils, "frappe.desk.form.assign_to": assign}
        )
        for mod in [
            "erplite.workz.api",
            "erplite.workz.policy",
            "erplite.workz.guards",
        ]:
            sys.modules.pop(mod, None)
        from erplite.workz import api

        # Reload: package attributes may outlive sys.modules entries in tests.
        import importlib

        self.api = importlib.import_module("erplite.workz.api")
        self.api.p = importlib.import_module("erplite.workz.policy")
        self.guards = importlib.import_module("erplite.workz.guards")
        self.guards.p = self.api.p

    def as_user(self, user):
        self.actor = user
        self.f.session.user = user
        return self

    def seed(self, dt, name, **fields):
        row = Row(doctype=dt, name=name, modified="0", owner=self.actor, **fields)
        self.data.setdefault(dt, {})[name] = row
        return row

    def get_doc(self, dt, name=None, **kwargs):
        return Doc(self, dt if isinstance(dt, dict) else self.data[dt][name])

    def get_all(self, dt, filters=None, fields=None, pluck=None, **kwargs):
        rows = list(self.data.get(dt, {}).values())
        if isinstance(filters, str):
            filters = {"name": filters}

        def matches(r):
            for k, v in (filters or {}).items():
                val = r.get(k)
                if isinstance(v, (list, tuple)):
                    op, x = v
                    if op == "in" and val not in x:
                        return False
                    if op == "not in" and val in x:
                        return False
                    if op == "!=" and val == x:
                        return False
                    if op == "<" and (val is None or str(val) >= str(x)):
                        return False
                    if op == ">" and (val is None or str(val) <= str(x)):
                        return False
                elif val != v:
                    return False
            return True

        rows = [copy.deepcopy(r) for r in rows if matches(r)]
        if pluck:
            return [r.get(pluck) for r in rows]
        return (
            rows
            if not fields or fields == ["*"]
            else [Row({k: r.get(k) for k in fields}) for r in rows]
        )

    def get_value(self, dt, filters, field="name", as_dict=False, **kwargs):
        rows = self.get_all(dt, filters)
        if not rows:
            return None
        if isinstance(field, list):
            return (
                Row({k: rows[0].get(k) for k in field})
                if as_dict
                else tuple(rows[0].get(k) for k in field)
            )
        return rows[0].get(field)

    def call(self, action, payload=None):
        with self.lock:
            old = copy.deepcopy(self.data)
            try:
                return self.api.run(action, payload or {})
            except Exception:
                self.data = old
                raise


class Doc(Row):
    def __init__(self, site, fields):
        super().__init__()
        object.__setattr__(self, "site", site)
        self.update(copy.deepcopy(fields))
        self.flags = Row()
        dt = self["doctype"].lower().replace(" ", "_")
        path = Path("erplite/projects/doctype") / dt / (dt + ".json")
        if path.exists():
            for f in json.loads(path.read_text())["fields"]:
                self.setdefault(f["fieldname"], f.get("default"))
        if self.doctype == "User":
            self.setdefault("roles", [])

    def get_doc_before_save(self):
        return copy.deepcopy(self.site.data.get(self.doctype, {}).get(self.name))

    def as_dict(self):
        return {k: v for k, v in self.items() if k != "flags"}

    def set(self, k, v):
        self[k] = v

    def save(self, **kwargs):
        s = self.site
        old = self.get_doc_before_save()
        if old and str(old.modified) != str(self.modified):
            raise Stale("Concurrent modification")
        if not self.name:
            self.name = (
                self.email
                if self.doctype == "User"
                else (
                    self.currency_name
                    if self.doctype == "Currency"
                    else f"{self.doctype}-{s.serial+1}"
                )
            )
        if self.doctype == "User":
            self.full_name = self.first_name
            self.roles = [Row(r) for r in self.roles]
        if self.doctype == "Timesheet Entry":
            if self.check_out_time:
                self.duration_hours = (
                    self.check_out_time - self.check_in_time
                ).total_seconds() / 3600
            s.guards.validate_time(self)
        if self.doctype == "Planner Entry":
            self.duration_hours = (
                self.plan_end - self.plan_start
            ).total_seconds() / 3600
            s.guards.validate_plan(self)
        if self.doctype in ("Project", "Activity", "ToDo"):
            s.guards.validate_setup(self)
        unique = {
            "Workz Decision": "decision_key",
            "Workz Rate": "rate_key",
            "Workz Import Map": "source_key",
        }.get(self.doctype)
        if unique and any(
            r.get(unique) == self.get(unique) and r.name != self.name
            for r in s.data.get(self.doctype, {}).values()
        ):
            raise Rejected("Duplicate unique key")
        s.serial += 1
        self.modified = str(s.serial)
        s.data.setdefault(self.doctype, {})[self.name] = Row(self.as_dict())
        return self

    insert = save
