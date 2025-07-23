import frappe
from datetime import datetime, timedelta

def get_context(context):
    """Get context for timesheet calendar page"""
    try:
        context.no_cache = 1
        context.show_sidebar = False
        
        # Get current user
        user = frappe.session.user
        
        # Get user's full name
        try:
            user_doc = frappe.get_doc("User", user)
            user_full_name = user_doc.full_name or user_doc.first_name or user
        except:
            user_full_name = user
        
        # Get current week dates
        week_param = frappe.form_dict.get('week')
        if week_param:
            try:
                start_of_week = datetime.strptime(week_param, '%Y-%m-%d').date()
            except:
                today = datetime.now().date()
                start_of_week = today - timedelta(days=today.weekday())  # Monday
        else:
            today = datetime.now().date()
            start_of_week = today - timedelta(days=today.weekday())  # Monday
        week_dates = []
        for i in range(7):
            week_dates.append(start_of_week + timedelta(days=i))
        
        # Get projects with tasks (with error handling)
        try:
            projects = frappe.get_all("Project",
                filters={
                    "status": "Active"
                },
                fields=["name", "project_name", "project_manager"],
                order_by="project_name"
            )
        except:
            projects = []
        
        # Get activities for each project
        for project in projects:
            try:
                project.activities = frappe.get_all("Activity",
                    filters={
                        "project": project.name,
                        "status": ["!=", "Completed"]
                    },
                    fields=["name", "subject", "priority"],
                    order_by="subject"
                )
            except:
                project.activities = []
        
            # Get existing timesheet entries for the week
        try:
            week_timesheets = frappe.get_all("Timesheet Entry",
                filters={
                    "employee": user,
                    "date": ["between", [start_of_week, start_of_week + timedelta(days=6)]]
                },
                fields=["name", "project", "activity", "date", "check_in_time", "check_out_time", 
                        "duration_hours", "status", "location", "description"],
                order_by="date, check_in_time"
            )
            
            # Convert datetime objects to strings for JSON serialization and add friendly names
            for timesheet in week_timesheets:
                if timesheet.get('check_in_time'):
                    timesheet['check_in_time'] = str(timesheet['check_in_time'])
                if timesheet.get('check_out_time'):
                    timesheet['check_out_time'] = str(timesheet['check_out_time'])
                if timesheet.get('date'):
                    timesheet['date'] = str(timesheet['date'])
                
                # Add friendly project and activity names
                if timesheet.get('project'):
                    try:
                        project_doc = frappe.get_doc("Project", timesheet['project'])
                        timesheet['project_name'] = project_doc.project_name
                    except:
                        timesheet['project_name'] = timesheet['project']
                
                if timesheet.get('activity'):
                    try:
                        activity_doc = frappe.get_doc("Activity", timesheet['activity'])
                        timesheet['activity_name'] = activity_doc.subject
                    except:
                        timesheet['activity_name'] = timesheet['activity']
                    
        except:
            week_timesheets = []
        
        # Get project colors (we'll generate consistent colors)
        project_colors = {}
        colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4", "#84CC16", "#F97316"]
        for i, project in enumerate(projects):
            project_colors[project.name] = colors[i % len(colors)]
        
        # Ensure all required context variables are set
        context.week_dates = week_dates
        context.projects = projects
        context.week_timesheets = week_timesheets
        context.project_colors = project_colors
        context.current_week_start = start_of_week.strftime("%Y-%m-%d")
        context.user = user_full_name
        context.full_width = True
        return context
        
    except Exception as e:
        frappe.log_error(f"Error in timesheet calendar context: {str(e)}")
        # Provide fallback data
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        week_dates = []
        for i in range(7):
            week_dates.append(start_of_week + timedelta(days=i))
        
        # Get user's full name for fallback
        try:
            user_doc = frappe.get_doc("User", frappe.session.user)
            user_full_name = user_doc.full_name or user_doc.first_name or frappe.session.user
        except:
            user_full_name = frappe.session.user
            
        context.week_dates = week_dates
        context.projects = []
        context.week_timesheets = []
        context.project_colors = {}
        context.current_week_start = start_of_week.strftime("%Y-%m-%d")
        context.user = user_full_name
        context.full_width = True
        return context
