import frappe

def get_context(context):
    """Get context for timesheet dashboard page"""
    context.no_cache = 1
    context.show_sidebar = False
    
    # Get current user
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
    
    # Get recent timesheets (last 10)
    recent_timesheets = frappe.get_all("Timesheet Entry",
        filters={
            "employee": user
        },
        fields=["name", "project", "task", "date", "duration_hours", "status", "check_in_time"],
        order_by="modified desc",
        limit=10
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
            limit=20
        )
    
    # Get projects for quick check-in
    projects = frappe.get_all("Project",
        filters={
            "status": "Active"
        },
        fields=["name", "project_name"],
        order_by="project_name"
    )
    
    context.update({
        "active_timesheet": active_timesheet[0] if active_timesheet else None,
        "recent_timesheets": recent_timesheets,
        "pending_approvals": pending_approvals,
        "projects": projects,
        "is_project_manager": len(managed_projects) > 0
    })
    
    return context
