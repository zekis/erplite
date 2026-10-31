"""Document-level guards also cover REST/legacy clients, not just the Workz UI."""

import frappe
from erplite.workz import policy as p
from erplite.workz.domain import interval


def is_admin(actor):
    return actor == "Administrator" or "System Manager" in frappe.get_roles(actor)


def time_permission(doc, user=None, ptype=None):
    actor = user or p.user()
    if ptype in ("read", "write", "delete", "submit", "cancel"):
        return (
            is_admin(actor)
            or doc.employee == actor
            or (
                bool(doc.project) and p.project(doc.project).timesheet_approver == actor
            )
        )
    return None


def plan_permission(doc, user=None, ptype=None):
    actor = user or p.user()
    own = is_admin(actor) or doc.user == actor
    project = p.project(doc.project) if doc.kind == "Work" and doc.project else None
    if ptype == "read":
        # Personal staff availability is only exposed through the redacted API.
        return own or bool(
            project and actor in (project.project_lead, project.timesheet_approver)
        )
    if ptype in ("write", "delete"):
        return own or bool(project and project.project_lead == actor)
    return None


def time_query(user=None):
    subject = user or p.user()
    if is_admin(subject):
        return ""
    actor = frappe.db.escape(subject)
    return (
        "( `tabTimesheet Entry`.employee = "
        + actor
        + " OR `tabTimesheet Entry`.project IN (SELECT name FROM `tabProject` WHERE timesheet_approver = "
        + actor
        + "))"
    )


def plan_query(user=None):
    subject = user or p.user()
    if is_admin(subject):
        return ""
    actor = frappe.db.escape(subject)
    return (
        "( `tabPlanner Entry`.user = "
        + actor
        + " OR (`tabPlanner Entry`.kind = 'Work' AND `tabPlanner Entry`.project IN (SELECT name FROM `tabProject` WHERE project_lead = "
        + actor
        + " OR timesheet_approver = "
        + actor
        + ")))"
    )


def preserve_setup(doc, method=None):
    p.require(False, "Archive projects or close activities to preserve history")


def validate_time(doc, method=None):
    from erplite.workz.api import check_overlap, check_locked_period, zone, audit

    if frappe.flags.workz_history_import:
        p.require(p.admin())
        return
    old = doc.get_doc_before_save()
    p.require(doc.employee == p.user() or p.approves(doc.project))
    p.lock_employee(doc.employee)
    if old:
        current = frappe.db.get_value(
            "Timesheet Entry", doc.name, "modified", for_update=True
        )
        p.require(
            str(current) == str(old.modified),
            "This timesheet changed. Refresh and try again.",
        )
        p.require(old.employee == doc.employee, "Employee cannot be changed")
        p.require(old.employee == p.user() or p.approves(old.project))
    booking = (
        "project",
        "activity",
        "check_in_time",
        "check_out_time",
        "workz_start_utc",
        "workz_end_utc",
    )
    changed = not old or any(not same_value(doc, old, k) for k in booking)
    if old and old.status in ("Submitted", "Approved"):
        p.require(
            not changed and old.description == doc.description,
            "Submitted/approved actual history is locked",
        )
    if changed:
        p.eligible(doc.employee, doc.project, doc.activity)
        if doc.check_out_time:
            start, end = effective_interval(doc, "check_in_time", "check_out_time", old)
            check_overlap(doc.employee, start, end, "Work", doc.name, actual=True)
            check_locked_period(doc.employee, start, end)
    if old and doc.status == old.status:
        p.require(
            all(
                same_value(doc, old, k)
                for k in ("approved_by", "approval_date", "approval_notes")
            ),
            "Approval metadata is immutable outside a transition",
        )
    previous = old.status if old else None
    if doc.status != previous:
        if not old:
            p.require(doc.status == "Draft", "New timesheets start as drafts")
        elif doc.status == "Submitted":
            p.require(
                previous in ("Draft", "Rejected") and doc.check_out_time,
                "Only completed drafts can be submitted",
            )
        elif doc.status in ("Approved", "Rejected", "Draft"):
            p.require(
                previous == "Submitted"
                and p.approves(doc.project)
                and doc.employee != p.user(),
                "Only the scoped approver can decide submitted time; no self-approval",
            )
        else:
            p.require(False, "Invalid timesheet transition")
        if doc.status in ("Approved", "Rejected"):
            from frappe.utils import now_datetime

            doc.approved_by = p.user()
            doc.approval_date = now_datetime()
        elif not old:
            doc.approved_by = None
            doc.approval_date = None
            doc.approval_notes = None
        audit(
            "Timesheet Entry",
            doc.name,
            "status",
            doc.employee,
            previous,
            doc.status,
            {"reason": doc.approval_notes},
        )


def delete_time(doc, method=None):
    p.require(doc.employee == p.user() or p.approves(doc.project))
    p.require(doc.status == "Draft", "Submitted/approved history cannot be deleted")
    p.require(
        not frappe.db.exists("Workz Decision", {"timesheet": doc.name}),
        "Accepted suggestion provenance cannot be deleted",
    )


def validate_plan(doc, method=None):
    from erplite.workz.api import check_overlap, zone

    if frappe.flags.workz_history_import:
        p.require(p.admin())
        return
    old = doc.get_doc_before_save()
    p.require(
        doc.user == p.user()
        or (doc.kind == "Work" and p.manages(doc.project))
        or p.admin()
    )
    p.lock_employee(doc.user)
    if old:
        p.require(old.user == doc.user, "Employee cannot change")
        p.require(old.user == p.user() or p.manages(old.project) or p.admin())
    if doc.status == "Cancelled":
        return
    if doc.kind == "Work":
        p.eligible(doc.user, doc.project, doc.activity)
    start, end = effective_interval(doc, "plan_start", "plan_end", old)
    if doc.all_day:
        from zoneinfo import ZoneInfo

        z = ZoneInfo(doc.timezone or zone())
        p.require(
            all(
                not any(
                    (
                        d.astimezone(z).hour,
                        d.astimezone(z).minute,
                        d.astimezone(z).second,
                    )
                )
                for d in (start, end)
            ),
            "All-day entries must begin and end at midnight",
        )
    check_overlap(doc.user, start, end, doc.kind, doc.name)


def delete_plan(doc, method=None):
    p.require(False, "Cancel plans instead of deleting their occurrence identity")


def validate_setup(doc, method=None):
    if frappe.flags.workz_history_import:
        p.require(p.admin())
        return
    old = doc.get_doc_before_save()
    if doc.doctype == "Project":
        p.require(p.admin() or (old and old.project_lead == p.user()))
        if old and any(
            doc.get(k) != old.get(k) for k in ("project_lead", "timesheet_approver")
        ):
            p.require(p.admin(), "Only administrators change leads and approvers")
    elif doc.doctype == "Activity":
        p.require(p.manages(doc.project))
        if old:
            p.require(
                doc.project == old.project, "Activities cannot move between projects"
            )
    elif doc.doctype == "ToDo" and doc.reference_type == "Activity":
        activity = frappe.get_doc("Activity", doc.reference_name)
        p.require(
            p.manages(activity.project),
            "Only the project lead manages activity assignments",
        )
        if old and (
            old.reference_name != doc.reference_name
            or old.allocated_to != doc.allocated_to
        ):
            p.require(False, "Cancel the old assignment and create a new one")
        p.lock_employee(doc.allocated_to)


def immutable(doc, method=None):
    if method == "on_trash" or doc.get_doc_before_save():
        p.require(False, "History records are append-only")


def effective_interval(doc, first, last, old=None):
    """Keep legacy site-local fields and UTC shadow fields in agreement."""
    from erplite.workz.api import zone, stored
    from erplite.workz.domain import hours
    from frappe.utils import get_datetime

    shadows = ("workz_start_utc", "workz_end_utc")
    legacy_edit = (
        old
        and any(not same_value(doc, old, k) for k in (first, last))
        and all(same_value(doc, old, k) for k in shadows)
    )
    if legacy_edit or not any(doc.get(k) for k in shadows):
        start, end = interval(doc.get(first), doc.get(last), zone())
        doc.workz_start_utc = start.replace(tzinfo=None)
        doc.workz_end_utc = end.replace(tzinfo=None)
    else:
        p.require(all(doc.get(k) for k in shadows), "Both UTC endpoints are required")
        start, end = interval(doc.workz_start_utc, doc.workz_end_utc, "UTC")
        p.require(
            stored(start) == get_datetime(doc.get(first))
            and stored(end) == get_datetime(doc.get(last)),
            "Local timestamps and UTC instants disagree",
        )
    doc.duration_hours = float(hours(start, end))
    return start, end


def same_value(doc, old, key):
    from frappe.utils import get_datetime

    a, b = doc.get(key), old.get(key)
    if (
        a
        and b
        and key
        in (
            "check_in_time",
            "check_out_time",
            "plan_start",
            "plan_end",
            "workz_start_utc",
            "workz_end_utc",
            "approval_date",
        )
    ):
        return get_datetime(a) == get_datetime(b)
    return a == b
