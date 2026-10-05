# -*- coding: utf-8 -*-
# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

import frappe
from frappe import _

@frappe.whitelist()
def get_timesheet_widget_data():
    """Get data for timesheet dashboard widget"""
    user = frappe.session.user
    
    # Get active timesheet
    active_timesheet = frappe.get_all("Timesheet Entry", 
        filters={
            "employee": user,
            "is_active": 1
        },
        fields=["name", "project", "activity", "check_in_time", "location"],
        limit=1
    )
    
    # Get recent timesheets (last 5)
    recent_timesheets = frappe.get_all("Timesheet Entry",
        filters={
            "employee": user
        },
        fields=["name", "project", "activity", "check_in_time as date", "duration_hours", "status"],
        order_by="modified desc",
        limit=5
    )
    
    # Pending approvals: the submitted entries on the projects this user is
    # the timesheet approver for. This block used to filter Project on
    # `project_manager`, removed from the DocType by 8126278; the replacement
    # field is `timesheet_approver` (review tray rev_e73092bfb5), which is
    # also the field Afterz already reads to decide who sees approvals.
    pending_approvals = []
    approving_projects = frappe.get_all("Project",
        filters={
            "timesheet_approver": user
        },
        fields=["name"]
    )

    if approving_projects:
        project_names = [p.name for p in approving_projects]
        pending_approvals = frappe.get_all("Timesheet Entry",
            filters={
                "project": ["in", project_names],
                "status": "Submitted"
            },
            fields=["name", "employee", "project", "activity", "check_in_time as date", "duration_hours"],
            order_by="modified desc",
            limit=10
        )
    
    return {
        "active_timesheet": active_timesheet[0] if active_timesheet else None,
        "recent_timesheets": recent_timesheets,
        "pending_approvals": pending_approvals
    }
