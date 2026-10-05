# -*- coding: utf-8 -*-
# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

import frappe

@frappe.whitelist()
def has_timesheet_permission():
    """Check if user has permission to access timesheet app"""
    # Allow all logged-in users to access the timesheet system
    # You can customize this logic based on your requirements
    return True

@frappe.whitelist()
def is_timesheet_admin():
    """Check if the current user is a timesheet admin"""
    # Check if user has System Manager role or a custom Timesheet Admin role
    user_roles = frappe.get_roles(frappe.session.user)
    return "System Manager" in user_roles or "Timesheet Admin" in user_roles

@frappe.whitelist()
def get_timesheet_users():
    """Get list of users for timesheet admin to switch between"""
    if not is_timesheet_admin():
        return []
    
    # Get all active users
    users = frappe.get_all("User", 
        fields=["name", "full_name", "email"],
        filters={"enabled": 1, "user_type": "System User"},
        order_by="full_name"
    )
    
    return users

@frappe.whitelist()
def get_timesheet_app_data():
    """Get data for timesheet app dashboard"""
    from erplite.projects.dashboard_widgets import get_timesheet_widget_data
    return get_timesheet_widget_data()

@frappe.whitelist()
def delete_timesheet_entry(entry_id):
    """Delete a timesheet entry"""
    try:
        if entry_id and entry_id != 'null':
            frappe.delete_doc("Timesheet Entry", entry_id)
            frappe.db.commit()
            return {"success": True, "message": "Timesheet entry deleted successfully"}
        else:
            return {"success": False, "message": "Invalid entry ID"}
    except Exception as e:
        frappe.log_error(f"Error deleting timesheet entry: {str(e)}")
        return {"success": False, "message": f"Error deleting timesheet: {str(e)}"}

@frappe.whitelist()
def save_timesheet_entries(entries, target_user=None):
    """Save timesheet entries from calendar interface"""
    try:
        import json
        from datetime import datetime
        
        # Determine which user to save entries for
        if target_user and is_timesheet_admin():
            # Admin creating entries for another user
            employee_user = target_user
        else:
            # Regular user or admin creating entries for themselves
            employee_user = frappe.session.user
        
        # Parse entries if it's a JSON string
        if isinstance(entries, str):
            entries = json.loads(entries)
        
        saved_entries = []
        
        for entry in entries:
            # Parse the entry data
            project = entry.get('project')
            activity = entry.get('activity')
            date = entry.get('date')
            start_time = entry.get('start_time')
            duration = float(entry.get('duration', 0))
            description = entry.get('description', '')
            entry_id = entry.get('id')
            
            # Calculate check-in and check-out times
            start_datetime = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
            end_datetime = start_datetime + frappe.utils.datetime.timedelta(hours=duration)
            
            if entry_id and entry_id != 'null':
                # Update existing entry
                timesheet_doc = frappe.get_doc("Timesheet Entry", entry_id)
                timesheet_doc.project = project
                timesheet_doc.activity = activity
                timesheet_doc.check_in_time = start_datetime
                timesheet_doc.check_out_time = end_datetime
                timesheet_doc.duration_hours = duration
                timesheet_doc.description = description
                timesheet_doc.save()
                saved_entries.append({
                    "temp_id": entry.get('temp_id'),
                    "id": timesheet_doc.name,
                    "project": project,
                    "activity": activity,
                    "date": date,
                    "start_time": start_time,
                    "duration": duration,
                    "description": description
                })
            else:
                # Create new entry for the specified user
                timesheet_doc = frappe.new_doc("Timesheet Entry")
                timesheet_doc.employee = employee_user
                timesheet_doc.project = project
                timesheet_doc.activity = activity
                timesheet_doc.check_in_time = start_datetime
                timesheet_doc.check_out_time = end_datetime
                timesheet_doc.duration_hours = duration
                timesheet_doc.description = description
                timesheet_doc.is_active = 0
                timesheet_doc.status = "Draft"
                timesheet_doc.insert()
                saved_entries.append({
                    "temp_id": entry.get('temp_id'),
                    "id": timesheet_doc.name,
                    "project": project,
                    "activity": activity,
                    "date": date,
                    "start_time": start_time,
                    "duration": duration,
                    "description": description
                })
        
        frappe.db.commit()
        return {"success": True, "message": "Timesheet entries saved successfully", "entries": saved_entries}
        
    except Exception as e:
        frappe.log_error(f"Error saving timesheet entries: {str(e)}")
        return {"success": False, "message": f"Error saving timesheet: {str(e)}"}

@frappe.whitelist()
def get_projects_and_activities(target_user=None):
    """Get all projects and their activities for the timesheet calendar"""
    try:
        # Determine which user's activities to show
        if target_user and is_timesheet_admin():
            # Admin viewing another user's activities
            user_to_filter = target_user
        else:
            # Regular user or admin viewing their own activities
            user_to_filter = frappe.session.user
        
        # Get all projects
        projects = frappe.get_all("Project", 
            fields=["name", "project_name"], 
            filters={"status": ["!=", "Archived"]},
            order_by="project_name"
        )
        
        # Activities assigned to this user, through Frappe's standard
        # assignment mechanism. The _assign field is maintained from ToDo rows
        # that are neither Cancelled nor Closed, so filtering ToDo the same way
        # yields exactly the set of activities that _assign lists.
        assigned_activity_names = frappe.get_all("ToDo",
            filters={
                "reference_type": "Activity",
                "allocated_to": user_to_filter,
                "status": ["not in", ["Cancelled", "Closed"]]
            },
            pluck="reference_name"
        )

        result = {
            project.name: {
                "project_name": project.project_name,
                "activities": []
            }
            for project in projects
        }

        if assigned_activity_names:
            # activity_name is the Activity title field. It is also returned as
            # "subject" because older front-end code still reads that key.
            activities = frappe.get_all("Activity",
                fields=["name", "activity_name", "activity_name as subject", "description", "project"],
                filters={
                    "name": ["in", assigned_activity_names],
                    "project": ["in", list(result)]
                },
                order_by="activity_name"
            )

            for activity in activities:
                result[activity.project]["activities"].append(activity)

        return result
        
    except Exception as e:
        frappe.log_error(f"Error getting projects and activities: {str(e)}")
        return {}

@frappe.whitelist()
def get_week_timesheets(week_start, target_user=None):
    """Get timesheet entries for a specific week"""
    try:
        from datetime import datetime, timedelta
        
        # Determine which user's timesheets to get
        if target_user and is_timesheet_admin():
            # Admin viewing another user's timesheets
            user_to_filter = target_user
        else:
            # Regular user or admin viewing their own timesheets
            user_to_filter = frappe.session.user
        
        # Parse week start date
        start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
        end_date = start_date + timedelta(days=6)
        
        # Get timesheet entries for the week
        entries = frappe.get_all("Timesheet Entry",
            fields=["name", "project", "activity", "check_in_time", "duration_hours", "description"],
            filters={
                "check_in_time": ["between", [start_date, end_date]],
                "employee": user_to_filter
            },
            order_by="check_in_time"
        )
        
        # Format entries for frontend
        formatted_entries = []
        for entry in entries:
            if entry.check_in_time:
                start_time = entry.check_in_time.strftime("%H:%M")
            else:
                start_time = "09:00"  # Default start time
                
            formatted_entries.append({
                "id": entry.name,
                "project": entry.project,
                "activity": entry.activity,
                "date": entry.check_in_time.strftime("%Y-%m-%d") if entry.check_in_time else "",
                "start_time": start_time,
                "duration": entry.duration_hours or 0,
                "description": entry.description or ""
            })
        
        return formatted_entries
        
    except Exception as e:
        frappe.log_error(f"Error getting week timesheets: {str(e)}")
        return []

@frappe.whitelist()
def export_timesheet_data(format='csv', week_start=None):
    """Export timesheet data in CSV or JSON format"""
    try:
        from datetime import datetime, timedelta
        import json
        import csv
        from io import StringIO
        
        # Build filters
        filters = {"employee": frappe.session.user}
        
        if week_start:
            start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
            end_date = start_date + timedelta(days=6)
            filters["check_in_time"] = ["between", [start_date, end_date]]
        
        # Get timesheet entries
        entries = frappe.get_all("Timesheet Entry",
            fields=["name", "project", "activity", "check_in_time", "check_out_time", "duration_hours", "description"],
            filters=filters,
            order_by="check_in_time"
        )
        
        if format == 'csv':
            # Create CSV data
            output = StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Date', 'Project', 'Activity', 'Start Time', 'End Time', 'Duration (Hours)', 'Description'])
            
            # Write data
            for entry in entries:
                start_time = entry.check_in_time.strftime("%H:%M") if entry.check_in_time else ""
                end_time = entry.check_out_time.strftime("%H:%M") if entry.check_out_time else ""
                
                writer.writerow([
                    entry.check_in_time.strftime("%Y-%m-%d") if entry.check_in_time else "",
                    entry.project or "",
                    entry.activity or "",
                    start_time,
                    end_time,
                    entry.duration_hours or 0,
                    entry.description or ""
                ])
            
            return {"success": True, "data": output.getvalue()}
            
        else:  # JSON format
            formatted_entries = []
            for entry in entries:
                formatted_entries.append({
                    "id": entry.name,
                    "date": entry.check_in_time.strftime("%Y-%m-%d") if entry.check_in_time else "",
                    "project": entry.project or "",
                    "activity": entry.activity or "",
                    "start_time": entry.check_in_time.strftime("%H:%M") if entry.check_in_time else "",
                    "end_time": entry.check_out_time.strftime("%H:%M") if entry.check_out_time else "",
                    "duration_hours": entry.duration_hours or 0,
                    "description": entry.description or ""
                })
            
            return {"success": True, "data": json.dumps(formatted_entries, indent=2)}
        
    except Exception as e:
        frappe.log_error(f"Error exporting timesheet data: {str(e)}")
        return {"success": False, "message": f"Error exporting data: {str(e)}"}

@frappe.whitelist()
def save_user_preferences(preferences):
    """Save user preferences for timesheet calendar"""
    try:
        import json
        
        # Parse preferences if it's a JSON string
        if isinstance(preferences, str):
            preferences = json.loads(preferences)
        
        # Save preferences to user settings or a custom doctype
        # For now, we'll use frappe.defaults which stores user-specific settings
        for key, value in preferences.items():
            frappe.defaults.set_user_default(f"timesheet_calendar_{key}", value)
        
        frappe.db.commit()
        return {"success": True, "message": "Preferences saved successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error saving user preferences: {str(e)}")
        return {"success": False, "message": f"Error saving preferences: {str(e)}"}

@frappe.whitelist()
def get_user_preferences():
    """Get user preferences for timesheet calendar"""
    try:
        # Get all timesheet calendar preferences for the current user
        preferences = {}
        
        # Get common preference keys (you can expand this list as needed)
        preference_keys = [
            'default_project',
            'default_activity', 
            'hour_range_start',
            'hour_range_end',
            'auto_save_enabled',
            'show_weekends',
            'time_format'
        ]
        
        for key in preference_keys:
            value = frappe.defaults.get_user_default(f"timesheet_calendar_{key}")
            if value is not None:
                preferences[key] = value
        
        return preferences
        
    except Exception as e:
        frappe.log_error(f"Error getting user preferences: {str(e)}")
        return {}

@frappe.whitelist()
def get_all_projects_and_activities():
    """Get all projects and activities for admin assignment dialog"""
    try:
        if not is_timesheet_admin():
            return {"success": False, "message": "Access denied"}
        
        # Get all projects
        projects = frappe.get_all("Project", 
            fields=["name", "project_name"], 
            filters={"status": ["!=", "Archived"]},
            order_by="project_name"
        )
        
        result = {}
        for project in projects:
            # All activities for this project, not filtered by user.
            # activity_name is the Activity title field. It is also returned as
            # "subject" because older front-end code still reads that key.
            activities = frappe.get_all("Activity",
                fields=["name", "activity_name", "activity_name as subject", "description"],
                filters={"project": project.name},
                order_by="activity_name"
            )

            result[project.name] = {
                "project_name": project.project_name,
                "activities": activities
            }

        # Who each activity is assigned to, from Frappe's standard assignment.
        # One query covering every activity rather than one query per activity.
        activity_names = [
            activity.name
            for project_entry in result.values()
            for activity in project_entry["activities"]
        ]

        assignees = {}
        if activity_names:
            for todo in frappe.get_all("ToDo",
                fields=["reference_name", "allocated_to"],
                filters={
                    "reference_type": "Activity",
                    "reference_name": ["in", activity_names],
                    "status": ["not in", ["Cancelled", "Closed"]],
                    "allocated_to": ["is", "set"]
                }
            ):
                assignees.setdefault(todo.reference_name, []).append(todo.allocated_to)

        for project_entry in result.values():
            for activity in project_entry["activities"]:
                allocated = assignees.get(activity.name, [])
                # An activity can have more than one assignee. assigned_users
                # is the full list; assigned_to keeps the single-value shape
                # the assignment dialog was written against.
                activity["assigned_users"] = allocated
                activity["assigned_to"] = allocated[0] if allocated else None

        return {"success": True, "data": result}
        
    except Exception as e:
        frappe.log_error(f"Error getting all projects and activities: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def assign_activities_to_user(user, activity_assignments):
    """Assign activities to a user"""
    try:
        import json

        from frappe.desk.form.assign_to import add as add_assignment
        from frappe.desk.form.assign_to import remove as remove_assignment
        
        if not is_timesheet_admin():
            return {"success": False, "message": "Access denied"}
        
        # Parse assignments if it's a JSON string
        if isinstance(activity_assignments, str):
            activity_assignments = json.loads(activity_assignments)
        
        updated_count = 0
        
        for assignment in activity_assignments:
            activity_id = assignment.get('activity_id')
            should_assign = assignment.get('assign', False)

            if not activity_id:
                continue

            if not frappe.db.exists("Activity", activity_id):
                continue

            if should_assign:
                # add() is idempotent: when an open ToDo already exists for this
                # user it reports that and leaves it alone rather than raising.
                # It creates the ToDo, keeps _assign in step and notifies them.
                add_assignment({
                    "doctype": "Activity",
                    "name": activity_id,
                    "assign_to": [user]
                })
            else:
                # Cancels this user's open ToDo for the activity, if there is
                # one. A no-op when they are not assigned to it.
                remove_assignment("Activity", activity_id, user)

            updated_count += 1
        
        frappe.db.commit()
        
        return {
            "success": True, 
            "message": f"Successfully updated {updated_count} activity assignments for {user}"
        }
        
    except Exception as e:
        frappe.log_error(f"Error assigning activities to user: {str(e)}")
        return {"success": False, "message": str(e)}
