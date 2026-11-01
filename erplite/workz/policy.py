"""Scope policy. Project leadership is not global administration."""

import frappe


def user():
    value = frappe.session.user
    readers = (getattr(frappe, "conf", {}) or {}).get("office_agent_file_readers", {})
    if (not value or value == "Guest" or value in readers.values()
            or not frappe.db.get_value("User", value, "enabled")
            or not {"System Manager", "Projects Manager", "Projects User"}.intersection(frappe.get_roles(value))):
        frappe.throw("Sign in to Workz", frappe.PermissionError)
    return value


def admin():
    return user() == "Administrator" or "System Manager" in frappe.get_roles(user())


def require(condition, message="You do not have access to this action"):
    if not condition:
        frappe.throw(message, frappe.PermissionError)


def project(name):
    return frappe.get_doc("Project", name)


def manages(name):
    return bool(name) and (admin() or project(name).project_lead == user())


def approves(name):
    return bool(name) and (admin() or project(name).timesheet_approver == user())


def assigned(employee, activity):
    return bool(
        frappe.db.get_value(
            "ToDo",
            {
                "reference_type": "Activity",
                "reference_name": activity,
                "allocated_to": employee,
                "status": ["not in", ["Closed", "Cancelled"]],
            },
            "name",
            for_update=True,
        )
    )


def eligible(employee, project_name, activity):
    require(
        bool(frappe.db.get_value("User", employee, "enabled", for_update=True)),
        "Employee is disabled or missing",
    )
    p = frappe.get_doc("Project", project_name, for_update=True)
    require(p.status != "Archived", "Project is archived")
    a = frappe.get_doc("Activity", activity, for_update=True)
    require(a.project == project_name, "Activity does not belong to this project")
    require(a.status not in ("Closed", "Cancelled", "Complete"), "Activity is closed")
    require(
        assigned(employee, activity),
        "Assign the employee to this activity before booking",
    )


def can_read_time(doc):
    return admin() or doc.employee == user() or approves(doc.project)


def can_read_plan(doc):
    return (
        admin()
        or doc.user == user()
        or (doc.kind == "Work" and (manages(doc.project) or approves(doc.project)))
        or (doc.kind != "Work" and staff(doc.user))
    )


def can_edit_plan_notes(doc):
    return doc.user == user() or admin()


def staff(employee):
    if admin() or employee == user():
        return True
    names = frappe.get_all("Project", filters={"project_lead": user()}, pluck="name")
    if not names:
        return False
    activities = frappe.get_all(
        "Activity", filters={"project": ["in", names]}, pluck="name"
    )
    return bool(
        activities
        and frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Activity",
                "reference_name": ["in", activities],
                "allocated_to": employee,
                "status": ["not in", ["Closed", "Cancelled"]],
            },
        )
    )


def lock_employee(employee):
    # All Workz writes for an employee serialize on a pre-existing User row.
    # Parameterized SQL; the parent row also covers the empty-calendar race.
    frappe.db.sql("SELECT name FROM `tabUser` WHERE name=%s FOR UPDATE", (employee,))


def same_version(doc, expected):
    if not expected or str(doc.modified) != str(expected):
        frappe.throw(
            "This record changed. Refresh and try again.", frappe.TimestampMismatchError
        )
