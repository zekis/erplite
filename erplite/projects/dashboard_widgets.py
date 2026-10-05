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
    
    # Pending approvals: switched off until the gating field is chosen.
    #
    # This block used to find the projects the user manages with
    # filters={"project_manager": user}. `project_manager` was removed from
    # the Project DocType and has no single successor -- Project now carries
    # both `timesheet_approver` and `project_lead` -- so that filter cannot
    # simply be renamed; which field should gate timesheet approval is a
    # business decision.
    #
    # It is not left in place because it is worse than useless. The column
    # survives in `tabProject` (bench migrate drops no columns) and nothing
    # maintains it, so the filter matches either nothing at all or, on a
    # site old enough to have set it while it was a real field, whichever
    # stale rows still hold the user's name -- granting approval visibility
    # off a value no longer under anyone's control. On a site where the
    # column was never created it fails outright instead.
    #
    # Returning nothing keeps the behaviour this endpoint already has in
    # practice, without reading a dead column. Restoring the feature means
    # putting the chosen field in the filter below.
    pending_approvals = []
    
    return {
        "active_timesheet": active_timesheet[0] if active_timesheet else None,
        "recent_timesheets": recent_timesheets,
        "pending_approvals": pending_approvals
    }
