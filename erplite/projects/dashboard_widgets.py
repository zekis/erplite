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
        fields=["name", "project", "task", "check_in_time", "location"],
        limit=1
    )
    
    # Get recent timesheets (last 5)
    recent_timesheets = frappe.get_all("Timesheet Entry",
        filters={
            "employee": user
        },
        fields=["name", "project", "task", "date", "duration_hours", "status"],
        order_by="modified desc",
        limit=5
    )
    
    # Get pending approvals if user is a project manager
    pending_approvals = []
    managed_projects = frappe.get_all("Project",
        filters={
            "project_manager": user
        },
        fields=["name"]
    )
    
    if managed_projects:
        project_names = [p.name for p in managed_projects]
        pending_approvals = frappe.get_all("Timesheet Entry",
            filters={
                "project": ["in", project_names],
                "status": "Submitted"
            },
            fields=["name", "employee", "project", "task", "date", "duration_hours"],
            order_by="modified desc",
            limit=10
        )
    
    return {
        "active_timesheet": active_timesheet[0] if active_timesheet else None,
        "recent_timesheets": recent_timesheets,
        "pending_approvals": pending_approvals
    }
