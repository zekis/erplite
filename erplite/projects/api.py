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
def save_timesheet_entries(entries):
    """Save timesheet entries from calendar interface"""
    try:
        import json
        from datetime import datetime
        
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
                timesheet_doc.date = date
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
                # Create new entry
                timesheet_doc = frappe.new_doc("Timesheet Entry")
                timesheet_doc.employee = frappe.session.user
                timesheet_doc.project = project
                timesheet_doc.activity = activity
                timesheet_doc.date = date
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
def get_projects_and_activities():
    """Get all projects and their activities for the timesheet calendar"""
    try:
        # Get all projects
        projects = frappe.get_all("Project", 
            fields=["name", "project_name"], 
            filters={"status": ["!=", "Cancelled"]},
            order_by="project_name"
        )
        
        result = {}
        for project in projects:
            # Get activities for this project
            activities = frappe.get_all("Activity", 
                fields=["name", "activity_name", "description"],
                filters={"project": project.name},
                order_by="activity_name"
            )
            
            result[project.name] = {
                "project_name": project.project_name,
                "activities": activities
            }
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Error getting projects and activities: {str(e)}")
        return {}

@frappe.whitelist()
def get_week_timesheets(week_start):
    """Get timesheet entries for a specific week"""
    try:
        from datetime import datetime, timedelta
        
        # Parse week start date
        start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
        end_date = start_date + timedelta(days=6)
        
        # Get timesheet entries for the week
        entries = frappe.get_all("Timesheet Entry",
            fields=["name", "project", "activity", "date", "check_in_time", "duration_hours", "description"],
            filters={
                "date": ["between", [start_date, end_date]],
                "employee": frappe.session.user
            },
            order_by="date, check_in_time"
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
                "date": entry.date.strftime("%Y-%m-%d"),
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
            filters["date"] = ["between", [start_date, end_date]]
        
        # Get timesheet entries
        entries = frappe.get_all("Timesheet Entry",
            fields=["name", "project", "activity", "date", "check_in_time", "check_out_time", "duration_hours", "description"],
            filters=filters,
            order_by="date, check_in_time"
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
                    entry.date.strftime("%Y-%m-%d") if entry.date else "",
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
                    "date": entry.date.strftime("%Y-%m-%d") if entry.date else "",
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
