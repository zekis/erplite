"""Single application boundary; explicit scope before every elevated read/write.

Frappe commits successful POST requests and rolls back uncaught errors. Never
swallow write failures or commit inside this module. All UI mutations POST here.
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_system_timezone, now_datetime
from erplite.workz import policy as p
from erplite.workz.domain import (
    interval,
    instant,
    overlaps,
    clipped_hours,
    decimal,
    projection,
)


def zone():
    return get_system_timezone() or "UTC"


def stored(value):
    return instant(value, zone()).astimezone(ZoneInfo(zone())).replace(tzinfo=None)


def record_times(row, first, last):
    start = (
        instant(row.get("workz_start_utc"), "UTC")
        if row.get("workz_start_utc")
        else instant(row[first], zone())
    )
    end = (
        instant(row.get("workz_end_utc"), "UTC")
        if row.get("workz_end_utc")
        else instant(row[last], zone()) if row.get(last) else start
    )
    return start, end


def public(doc):
    return doc.as_dict() if hasattr(doc, "as_dict") else dict(doc)


def audit(doctype, name, action, employee=None, old=None, new=None, details=None):
    frappe.get_doc(
        dict(
            doctype="Workz Audit",
            actor=p.user(),
            employee=employee,
            reference_type=doctype,
            reference_name=name,
            action=action,
            old_status=old,
            new_status=new,
            recorded_at=now_datetime(),
            details=json.dumps(details or {}, default=str),
        )
    ).insert(ignore_permissions=True)


def bounds(data):
    return interval(data["start"], data["end"], zone())


def rows(doctype, filters=None, fields=None):
    return frappe.get_all(
        doctype, filters=filters or {}, fields=fields or ["*"], limit_page_length=0
    )


def context(data):
    actor = p.user()
    is_admin = p.admin()
    projects = rows(
        "Project",
        fields=[
            "name",
            "project_name",
            "status",
            "project_lead",
            "timesheet_approver",
            "modified",
        ],
    )
    activities = rows(
        "Activity", fields=["name", "activity_name", "project", "status", "modified"]
    )
    assignments = rows(
        "ToDo",
        {"reference_type": "Activity", "status": ["not in", ["Closed", "Cancelled"]]},
        ["name", "reference_name", "allocated_to", "modified"],
    )
    own_activities = {r.reference_name for r in assignments if r.allocated_to == actor}
    own_projects = {r.project for r in activities if r.name in own_activities}
    projects = [
        r
        for r in projects
        if is_admin
        or r.project_lead == actor
        or r.timesheet_approver == actor
        or r.name in own_projects
    ]
    project_names = {r.name for r in projects}
    activities = [r for r in activities if r.project in project_names]
    activity_names = {r.name for r in activities}
    managers = {r.name for r in projects if is_admin or r.project_lead == actor}
    visible_projects = managers | {
        r.name for r in projects if r.timesheet_approver == actor
    }
    visible_assignments = {r.name for r in activities if r.project in visible_projects}
    assignments = [
        r
        for r in assignments
        if r.reference_name in activity_names
        and (r.allocated_to == actor or r.reference_name in visible_assignments)
    ]
    people = (
        {actor}
        | {r.allocated_to for r in assignments}
        | {r.project_lead for r in projects}
        | {r.timesheet_approver for r in projects}
    )
    users = (
        rows("User", {"name": ["not in", ["Guest"]]}, ["name", "full_name", "enabled"])
        if is_admin or managers
        else rows(
            "User",
            {"name": ["in", list(people - {None, ""})]},
            ["name", "full_name", "enabled"],
        )
    )
    return dict(
        user=actor,
        admin=is_admin,
        timezone=zone(),
        currencies=rows("Currency", {"enabled": 1}, ["name", "currency_code"]),
        projects=projects,
        activities=activities,
        assignments=assignments,
        users=users,
        managed_projects=list(managers),
        approval_projects=[
            r.name for r in projects if is_admin or r.timesheet_approver == actor
        ],
        preferences=frappe.defaults.get_user_default("workz_preferences") or "{}",
    )


def check_overlap(employee, start, end, kind, exclude=None, actual=False):
    dt = "Timesheet Entry" if actual else "Planner Entry"
    owner, first, last = (
        ("employee", "check_in_time", "check_out_time")
        if actual
        else ("user", "plan_start", "plan_end")
    )
    table = frappe.qb.DocType(dt)
    candidates = (
        frappe.qb.from_(table)
        .select(table.star)
        .where(table[owner] == employee)
        .for_update()
        .run(as_dict=True)
    )
    for row in candidates:
        if row.name == exclude or row.get("status") == "Cancelled":
            continue
        if not actual and (row.get("kind") == "Availability" or kind == "Availability"):
            continue
        if not row.get(first):
            continue
        a, b = record_times(row, first, last)
        if not row.get(last):
            b = a + timedelta(days=366)
        if overlaps(start, end, a, b):
            frappe.throw(
                "Conflicts with "
                + row.name
                + ". Move or edit the existing entry first."
            )


def save_project(data):
    name = data.get("name")
    p.require(
        p.manages(name) if name else p.admin(),
        "Only an administrator creates projects; project leads edit their projects",
    )
    doc = frappe.get_doc("Project", name) if name else frappe.new_doc("Project")
    if name:
        p.same_version(doc, data.get("modified"))
    for key in ("project_name", "status", "project_lead", "timesheet_approver"):
        if key in data:
            if key in ("project_lead", "timesheet_approver"):
                p.require(
                    p.admin(),
                    "Only administrators change project managers and approvers",
                )
                if data[key]:
                    p.require(
                        frappe.db.get_value("User", data[key], "enabled"),
                        "Choose an enabled user",
                    )
            setattr(doc, key, data[key])
    doc.save(ignore_permissions=True)
    audit("Project", doc.name, "save")
    return public(doc)


def save_activity(data):
    p.require(p.manages(data["project"]))
    doc = (
        frappe.get_doc("Activity", data["name"])
        if data.get("name")
        else frappe.new_doc("Activity")
    )
    if data.get("name"):
        p.require(p.manages(doc.project))
        p.same_version(doc, data.get("modified"))
        p.require(
            doc.project == data["project"],
            "Activities cannot be moved between projects",
        )
    for key in ("project", "activity_name", "status"):
        if key in data:
            setattr(doc, key, data[key])
    doc.save(ignore_permissions=True)
    audit("Activity", doc.name, "save")
    return public(doc)


def assignment(data):
    from frappe.desk.form.assign_to import _add as add

    activity = frappe.get_doc("Activity", data["activity"])
    p.require(p.manages(activity.project))
    employee = data["employee"]
    p.require(
        frappe.db.get_value("User", employee, "enabled"), "Choose an enabled employee"
    )
    p.lock_employee(employee)
    # Locking reads see assignments committed while waiting for the employee
    # lock even under MariaDB REPEATABLE READ (ordinary reads may be older).
    table = frappe.qb.DocType("ToDo")
    existing = (
        frappe.qb.from_(table)
        .select(table.star)
        .where(table.allocated_to == employee)
        .for_update()
        .run(as_dict=True)
    )
    active = [
        r
        for r in existing
        if r.reference_type == "Activity"
        and r.reference_name == activity.name
        and r.status not in ("Closed", "Cancelled")
    ]
    # Canonical Frappe ToDo hooks maintain _assign and preserve old time.
    if data.get("assigned"):
        p.require(
            p.project(activity.project).status != "Archived", "Project is archived"
        )
        if not active:
            add(
                {"doctype": "Activity", "name": activity.name, "assign_to": [employee]},
                ignore_permissions=True,
            )
    else:
        for row in active:
            todo = frappe.get_doc("ToDo", row.name, for_update=True)
            todo.status = "Cancelled"
            todo.save(ignore_permissions=True)
    audit(
        "Activity",
        activity.name,
        "assign" if data.get("assigned") else "unassign",
        employee,
    )
    return {"saved": True}


def save_user(data):
    p.require(p.admin(), "Only administrators manage identities and access")
    name = data.get("name")
    doc = frappe.get_doc("User", name) if name else frappe.new_doc("User")
    if name:
        p.same_version(doc, data.get("modified"))
        p.require(
            name not in ("Administrator", "Guest") and name != p.user(),
            "Use another administrator to change protected accounts",
        )
    if not name:
        doc.email = data["email"]
        doc.send_welcome_email = int(bool(data.get("invite")))
    doc.first_name = data["full_name"]
    doc.enabled = int(bool(data.get("enabled", True)))
    allowed = {"Projects User", "Projects Manager"}
    requested = set(data.get("roles", ["Projects User"]))
    p.require(requested <= allowed, "Only supported project roles may be assigned here")
    # Preserve unrelated integration roles; never accept arbitrary role names.
    kept = [r.role for r in doc.get("roles", []) if r.role not in allowed]
    doc.set("roles", [{"role": r} for r in sorted(set(kept) | requested)])
    doc.save(ignore_permissions=True)
    audit("User", doc.name, "access", doc.name)
    return {"name": doc.name, "modified": doc.modified}


def user_detail(data):
    p.require(p.admin())
    doc = frappe.get_doc("User", data["name"])
    return {
        **{
            k: doc.get(k) for k in ("name", "email", "full_name", "enabled", "modified")
        },
        "roles": [
            r.role for r in doc.roles if r.role in ("Projects User", "Projects Manager")
        ],
    }


def save_plan(data):
    ZoneInfo(data.get("timezone") or zone())
    employee = data.get("user") or p.user()
    p.require(p.staff(employee))
    p.lock_employee(employee)
    doc = (
        frappe.get_doc("Planner Entry", data["name"], for_update=True)
        if data.get("name")
        else frappe.new_doc("Planner Entry")
    )
    if data.get("name"):
        p.require(
            doc.user == employee, "Employee cannot change; create a new allocation"
        )
        p.same_version(doc, data.get("modified"))
        p.require(doc.user == p.user() or p.manages(doc.project))
    kind = data.get("kind", "Work")
    p.require(
        kind in ("Work", "Availability", "Leave", "Holiday"), "Invalid planning kind"
    )
    if kind == "Work":
        p.require(employee == p.user() or p.manages(data.get("project")))
        p.eligible(employee, data["project"], data["activity"])
    else:
        p.require(
            employee == p.user() or p.admin(),
            "Only the employee or administrator changes personal availability",
        )
    start, end = interval(
        data["plan_start"], data["plan_end"], data.get("timezone", zone())
    )
    check_overlap(employee, start, end, kind, doc.name)
    if kind in ("Leave", "Holiday"):
        # Personal calendar intention, never an HR approval. If HRMS is present,
        # link its independently approved Leave Application through leave_request.
        data["project"] = None
        data["activity"] = None
        data["billable"] = 0
    for key in (
        "title",
        "project",
        "activity",
        "kind",
        "timezone",
        "all_day",
        "billable",
        "notes",
    ):
        if key in data:
            setattr(doc, key, data[key])
    doc.user = employee
    doc.owner = employee
    doc.plan_start = stored(start)
    doc.plan_end = stored(end)
    doc.workz_start_utc = start.replace(tzinfo=None)
    doc.workz_end_utc = end.replace(tzinfo=None)
    doc.status = "Planned"
    doc.save(ignore_permissions=True)
    audit("Planner Entry", doc.name, "save", employee)
    return public(doc)


def delete_plan(data):
    initial = frappe.get_doc("Planner Entry", data["name"])
    p.lock_employee(initial.user)
    doc = frappe.get_doc("Planner Entry", data["name"], for_update=True)
    p.require(doc.user == p.user() or p.manages(doc.project))
    p.same_version(doc, data.get("modified"))
    doc.status = "Cancelled"
    doc.save(ignore_permissions=True)
    audit("Planner Entry", doc.name, "cancel", doc.user)
    return {"saved": True}


def plans(data):
    start, end = bounds(data)
    visible = []
    for row in rows("Planner Entry", {"status": ["!=", "Cancelled"]}):
        if not p.can_read_plan(row) or not row.plan_start:
            continue
        if data.get("employee") and row.user != data["employee"]:
            continue
        if data.get("project") and row.project != data["project"]:
            continue
        finish = row.plan_end or (
            instant(row.plan_start, zone())
            + timedelta(hours=float(row.duration_hours or 0))
        )
        a, b = record_times(row, "plan_start", "plan_end")
        if not row.plan_end:
            b = instant(finish, zone())
        if overlaps(a, b, start, end):
            # Coworker private notes and leave details never leak to planners.
            visible.append(
                {
                    k: row.get(k)
                    for k in (
                        "name",
                        "user",
                        "title",
                        "project",
                        "activity",
                        "kind",
                        "plan_start",
                        "plan_end",
                        "duration_hours",
                        "timezone",
                        "all_day",
                        "billable",
                        "modified",
                        "status",
                        "leave_application",
                    )
                }
            )
            visible[-1]["plan_start"] = a.isoformat()
            visible[-1]["plan_end"] = b.isoformat()
            if row.user != p.user() and row.kind != "Work" and not p.admin():
                visible[-1]["title"] = row.kind
                visible[-1]["leave_application"] = None
    return visible


def decision(data):
    initial = frappe.get_doc("Planner Entry", data["name"])
    p.require(initial.user == p.user())
    p.lock_employee(p.user())
    doc = frappe.get_doc("Planner Entry", data["name"], for_update=True)
    key = sha256((doc.name + "\0" + p.user()).encode()).hexdigest()
    old = frappe.db.get_value(
        "Workz Decision",
        {"decision_key": key},
        ["decision", "timesheet"],
        as_dict=True,
        for_update=True,
    )
    if old:
        return dict(old)  # exact once across refresh, retries, moves and cancellation
    p.same_version(doc, data.get("modified"))
    p.require(
        doc.status != "Cancelled" and doc.kind == "Work",
        "This plan is no longer a work suggestion",
    )
    action = data["decision"]
    p.require(action in ("Accepted", "Ignored"), "Choose Accept or Ignore")
    entry = None
    if action == "Accepted":
        entry = save_time(
            dict(
                project=doc.project,
                activity=doc.activity,
                check_in_time=record_times(doc, "plan_start", "plan_end")[
                    0
                ].isoformat(),
                check_out_time=record_times(doc, "plan_start", "plan_end")[
                    1
                ].isoformat(),
                description=doc.title,
                employee=p.user(),
            )
        )
    result = frappe.get_doc(
        dict(
            doctype="Workz Decision",
            decision_key=key,
            plan_id=doc.name,
            employee=p.user(),
            decision=action,
            timesheet=entry["name"] if entry else None,
            plan_snapshot=json.dumps(public(doc), default=str),
        )
    ).insert(ignore_permissions=True)
    audit("Planner Entry", doc.name, action, p.user())
    return {"decision": action, "timesheet": result.timesheet}


def save_time(data):
    employee = data.get("employee") or p.user()
    p.require(employee == p.user() or p.approves(data["project"]))
    p.lock_employee(employee)
    doc = (
        frappe.get_doc("Timesheet Entry", data["name"], for_update=True)
        if data.get("name")
        else frappe.new_doc("Timesheet Entry")
    )
    if data.get("name"):
        p.require(
            doc.employee == employee
            and (employee == p.user() or p.approves(doc.project))
        )
        p.same_version(doc, data.get("modified"))
        p.require(doc.status == "Draft", "Submitted/approved entries are locked")
    p.eligible(employee, data["project"], data["activity"])
    start, end = interval(data["check_in_time"], data["check_out_time"], zone())
    check_overlap(employee, start, end, "Work", doc.name, actual=True)
    if not data.get("name"):
        check_locked_period(employee, start, end)
    for key in ("project", "activity", "description"):
        if key in data:
            setattr(doc, key, data[key])
    doc.employee = employee
    doc.owner = employee
    doc.status = "Draft"
    doc.check_in_time = stored(start)
    doc.check_out_time = stored(end)
    doc.workz_start_utc = start.replace(tzinfo=None)
    doc.workz_end_utc = end.replace(tzinfo=None)
    # The existing ownership guard uses DocType write for delegated creation.
    # Endpoint scope is narrower; the controller still applies its existing rule.
    doc.flags.workz_scoped_booking = True
    doc.save(ignore_permissions=True)
    audit("Timesheet Entry", doc.name, "save", employee)
    return public(doc)


def check_locked_period(employee, start, end):
    from datetime import time

    local = start.astimezone(ZoneInfo(zone()))
    beginning = datetime.combine(
        local.date() - timedelta(days=local.weekday()), time(), ZoneInfo(zone())
    )
    ending = (end - timedelta(microseconds=1)).astimezone(ZoneInfo(zone()))
    stop = datetime.combine(
        ending.date() + timedelta(days=7 - ending.weekday()), time(), ZoneInfo(zone())
    )
    table = frappe.qb.DocType("Timesheet Entry")
    candidates = (
        frappe.qb.from_(table)
        .select(table.star)
        .where(table.employee == employee)
        .for_update()
        .run(as_dict=True)
    )
    # Weeks follow site-local calendar boundaries, but all comparisons use
    # canonical instants. Local clock fields alone cannot resolve DST folds.
    beginning, stop = instant(beginning), instant(stop)
    for row in candidates:
        if row.status not in ("Submitted", "Approved"):
            continue
        a, b = record_times(row, "check_in_time", "check_out_time")
        # Preserve the start-week lock for legacy records without an end, and
        # lock every week touched by completed history (exclusive end).
        if beginning <= a < stop or overlaps(beginning, stop, a, b):
            frappe.throw(
                "This week contains submitted or approved time. Return submitted entries before adding new time; approved history stays locked."
            )


def delete_time(data):
    initial = frappe.get_doc("Timesheet Entry", data["name"])
    p.lock_employee(initial.employee)
    doc = frappe.get_doc("Timesheet Entry", data["name"], for_update=True)
    p.require(doc.employee == p.user() or p.approves(doc.project))
    p.same_version(doc, data.get("modified"))
    p.require(doc.status == "Draft", "Only drafts can be deleted")
    # Decisions retain the accepted identity even if the user deletes the actual.
    p.require(
        not frappe.db.exists("Workz Decision", {"timesheet": doc.name}),
        "Accepted plan entries retain provenance; edit the draft instead",
    )
    audit("Timesheet Entry", doc.name, "delete", doc.employee)
    frappe.delete_doc("Timesheet Entry", doc.name, ignore_permissions=True)
    return {"saved": True}


def transition(data):
    initial = frappe.get_doc("Timesheet Entry", data["name"])
    p.lock_employee(initial.employee)
    doc = frappe.get_doc("Timesheet Entry", data["name"], for_update=True)
    action = data["status"]
    p.require(p.can_read_time(doc))
    p.same_version(doc, data.get("modified"))
    if action == "Submitted":
        p.require(doc.employee == p.user() or p.approves(doc.project))
        p.require(
            doc.status == "Draft" and doc.check_out_time,
            "Only completed drafts can be submitted",
        )
    elif action in ("Approved", "Draft"):
        p.require(
            p.approves(doc.project) and doc.employee != p.user(),
            "Self-approval is not allowed",
        )
        p.require(
            doc.status == "Submitted",
            "Only submitted entries can be approved or returned",
        )
        if action == "Draft":
            p.require(bool(data.get("reason")), "Enter a return reason")
        doc.approved_by = p.user()
        doc.approval_date = now_datetime()
        doc.approval_notes = data.get("reason", "")
    else:
        frappe.throw("Invalid transition")
    doc.status = action
    doc.flags.workz_scoped_booking = True
    doc.save(ignore_permissions=True)
    return public(doc)


def times(data):
    start, end = bounds(data)
    result = []
    for row in rows(
        "Timesheet Entry",
        {"check_in_time": ["<", stored(end)], "check_out_time": [">", stored(start)]},
    ):
        if not p.can_read_time(row) or not row.check_in_time:
            continue
        if data.get("employee") and row.employee != data["employee"]:
            continue
        if data.get("project") and row.project != data["project"]:
            continue
        a, b = record_times(row, "check_in_time", "check_out_time")
        if overlaps(a, b, start, end):
            result.append(
                {
                    **{
                        k: row.get(k)
                        for k in (
                            "name",
                            "employee",
                            "project",
                            "activity",
                            "description",
                            "check_in_time",
                            "check_out_time",
                            "duration_hours",
                            "status",
                            "approved_by",
                            "approval_date",
                            "modified",
                        )
                    },
                    "check_in_time": a.isoformat(),
                    "check_out_time": b.isoformat(),
                    "period_hours": str(clipped_hours(a, b, start, end)),
                }
            )
    return result


def report(data):
    actual = times(data)
    planned = plans(data)
    start, end = bounds(data)
    employees = {}
    totals = {key: Decimal(0) for key in ("actual", "submitted", "approved", "planned")}
    for row in actual:
        record = employees.setdefault(
            row["employee"], {key: Decimal(0) for key in totals}
        )
        duration = decimal(row["period_hours"])
        record["actual"] += duration
        totals["actual"] += duration
        key = {"Submitted": "submitted", "Approved": "approved"}.get(row["status"])
        if key:
            record[key] += duration
            totals[key] += duration
    for row in planned:
        if row.get("kind") != "Work" or not row.get("plan_end"):
            continue
        # Keep dashboard/report scopes identical: project leads only see their
        # own time unless also approvers. Planning has a separate staff scope.
        if row["user"] != p.user() and not p.approves(row.get("project")):
            continue
        duration = clipped_hours(
            instant(row["plan_start"], zone()),
            instant(row["plan_end"], zone()),
            start,
            end,
        )
        employees.setdefault(row["user"], {key: Decimal(0) for key in totals})[
            "planned"
        ] += duration
        totals["planned"] += duration
    return dict(
        entries=actual,
        employees=[
            {"employee": e, **{k: str(v) for k, v in values.items()}}
            for e, values in employees.items()
        ],
        totals={k: str(v) for k, v in totals.items()},
        definition="Hours clipped to the selected half-open period in site timezone. Actual includes Draft, Submitted and Approved completed entries; submitted and approved are separate current states. Planned is work allocation, never actual.",
    )


def suggestions(data):
    decided = {
        r.plan_id for r in rows("Workz Decision", {"employee": p.user()}, ["plan_id"])
    }
    return [
        row
        for row in plans(data)
        if row["user"] == p.user()
        and row.get("kind") == "Work"
        and row.get("activity")
        and row["name"] not in decided
    ]


def save_rate(data):
    kind = data["kind"]
    p.require(kind in ("Pay", "Sell"))
    p.require(p.admin() if kind == "Pay" else p.manages(data.get("project")))
    employee = data["employee"]
    p.lock_employee(employee)
    if kind == "Sell":
        acts = rows("Activity", {"project": data["project"]}, ["name"])
        p.require(
            any(p.assigned(employee, a.name) for a in acts),
            "Assign an activity in this project first",
        )
    value = decimal(data["amount"])
    p.require(
        value.as_tuple().exponent >= -6, "Rates support at most six decimal places"
    )
    p.require(
        frappe.db.exists("Currency", data["currency"]),
        "Create or select an existing currency",
    )
    effective = datetime.fromisoformat(data["effective_from"]).date()
    # Existing dates are immutable. No retroactive rate rewriting of old plans.
    p.require(
        effective >= now_datetime().date(),
        "New rate versions cannot backdate historical periods",
    )
    project = data.get("project") if kind == "Sell" else None
    key = sha256(f"{employee}\0{project}\0{kind}\0{effective}".encode()).hexdigest()
    old = frappe.db.get_value(
        "Workz Rate", {"rate_key": key}, ["amount", "currency"], as_dict=True
    )
    if old:
        p.require(
            decimal(old.amount) == value and old.currency == data["currency"],
            "A different rate already exists on this date; choose a later date",
        )
        return {"saved": True}
    doc = frappe.get_doc(
        dict(
            doctype="Workz Rate",
            employee=employee,
            project=project,
            kind=kind,
            effective_from=effective,
            amount=str(value),
            currency=data["currency"],
            rate_key=key,
        )
    ).insert(ignore_permissions=True)
    audit("Workz Rate", doc.name, "rate", employee)
    return {"saved": True}


def financials(data):
    start, end = bounds(data)
    scoped = [
        row
        for row in plans(data)
        if row.get("kind") == "Work" and p.manages(row.get("project"))
    ]
    rates = rows("Workz Rate")
    details = []
    totals = {}
    missing = []
    by_project = {}
    for row in scoped:
        result = projection(row, rates, start, end, zone())
        details.append({"plan": row["name"], "project": row["project"], **result})
        missing += result["missing"]
        project_bucket = by_project.setdefault(
            row["project"], {"missing": [], "currencies": {}}
        )
        project_bucket["missing"] += result["missing"]
        for currency, amounts in result["currencies"].items():
            bucket = totals.setdefault(
                currency, {"cost": Decimal(0), "revenue": Decimal(0)}
            )
            project_values = project_bucket["currencies"].setdefault(
                currency, {"cost": Decimal(0), "revenue": Decimal(0)}
            )
            for key in bucket:
                bucket[key] += decimal(amounts[key])
                project_values[key] += decimal(amounts[key])
    return {
        "allocations": details,
        "projects": [
            {
                "project": project,
                "currency": currency,
                "cost": str(values["cost"]),
                "revenue": str(values["revenue"]),
                "margin": (
                    str(values["revenue"] - values["cost"])
                    if not group["missing"]
                    else None
                ),
            }
            for project, group in by_project.items()
            for currency, values in group["currencies"].items()
        ],
        "missing": missing,
        "currencies": {
            currency: {
                "cost": str(values["cost"]),
                "revenue": str(values["revenue"]),
                "margin": (
                    str(values["revenue"] - values["cost"]) if not missing else None
                ),
                "margin_percent": (
                    str((values["revenue"] - values["cost"]) / values["revenue"] * 100)
                    if values["revenue"] and not missing
                    else None
                ),
            }
            for currency, values in totals.items()
        },
        "definition": "Projections only, excluding overheads, payroll leave and tax. Missing rates mean incomplete totals. Currencies are never converted or combined.",
    }


def rate_history(data):
    employee = data["employee"]
    project = data.get("project")
    p.require(p.admin() or p.manages(project))
    p.require(p.staff(employee))
    return [
        r
        for r in rows("Workz Rate", {"employee": employee})
        if r.kind == "Pay" or r.project == project or p.admin()
    ]


def preferences(data):
    allowed = {k: data[k] for k in ("view", "show_weekends") if k in data}
    current = json.loads(frappe.defaults.get_user_default("workz_preferences") or "{}")
    current.update(allowed)
    frappe.defaults.set_user_default("workz_preferences", json.dumps(current))
    return allowed


def leave_options(data):
    # Frappe/HRMS remains the authority. No substitute approval workflow.
    if not frappe.db.exists("DocType", "Leave Application"):
        return {
            "available": False,
            "message": "HR leave approvals are not configured. Calendar leave/holiday blocks are intentions, not approvals.",
        }
    employee = frappe.db.get_value("Employee", {"user_id": p.user()}, "name")
    return {
        "available": bool(employee),
        "employee": employee,
        "types": frappe.get_list("Leave Type", pluck="name") if employee else [],
        "applications": (
            frappe.get_list(
                "Leave Application",
                filters={"employee": employee},
                fields=["name", "from_date", "to_date", "status", "docstatus"],
            )
            if employee
            else []
        ),
    }


def leave_request(data):
    options = leave_options({})
    p.require(options["available"], "Link an HR employee before requesting leave")
    doc = frappe.get_doc(
        dict(
            doctype="Leave Application",
            employee=options["employee"],
            leave_type=data["leave_type"],
            from_date=data["from_date"],
            to_date=data["to_date"],
            half_day=int(bool(data.get("half_day"))),
            half_day_date=data.get("half_day_date"),
            description=data.get("description", ""),
        )
    )
    doc.insert()  # Existing leave controller, balance, permissions and workflow.
    return {"name": doc.name, "status": doc.status}


READS = {
    "context": context,
    "plans": plans,
    "times": times,
    "report": report,
    "suggestions": suggestions,
    "financials": financials,
    "rate_history": rate_history,
    "user_detail": user_detail,
    "leave_options": leave_options,
}
WRITES = {
    "save_project": save_project,
    "save_activity": save_activity,
    "assignment": assignment,
    "save_user": save_user,
    "save_plan": save_plan,
    "delete_plan": delete_plan,
    "decision": decision,
    "save_time": save_time,
    "delete_time": delete_time,
    "transition": transition,
    "save_rate": save_rate,
    "preferences": preferences,
    "leave_request": leave_request,
}


@frappe.whitelist()
def run(action, payload=None):
    p.user()
    # Preserve Frappe access as well as our narrower row scopes.
    frappe.has_permission("Project", "read", throw=True)
    data = json.loads(payload) if isinstance(payload, str) else (payload or {})
    if action in WRITES:
        if frappe.request.method != "POST":
            frappe.throw("Use POST for changes", frappe.PermissionError)
        return WRITES[action](data)
    if action in READS:
        return READS[action](data)
    frappe.throw("Unknown Workz action")


def save_currency(data):
    p.require(p.admin())
    code = str(data["code"]).upper()
    p.require(len(code) == 3 and code.isalpha(), "Use a three-letter currency code")
    p.require(not frappe.db.exists("Currency", code), "Currency already exists")
    doc = frappe.get_doc(
        dict(
            doctype="Currency",
            currency_name=code,
            currency_code=code,
            symbol=data["symbol"],
            enabled=1,
            exchange_rate=1,
        )
    ).insert(ignore_permissions=True)
    audit("Currency", doc.name, "create")
    return {"name": doc.name}


def audit_history(data):
    doc = frappe.get_doc("Timesheet Entry", data["name"])
    p.require(p.can_read_time(doc))
    return rows(
        "Workz Audit",
        {"reference_type": "Timesheet Entry", "reference_name": doc.name},
        ["actor", "employee", "action", "old_status", "new_status", "recorded_at"],
    )


WRITES["save_currency"] = save_currency
READS["audit_history"] = audit_history
