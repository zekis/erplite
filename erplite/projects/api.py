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
            task = entry.get('task')
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
                timesheet_doc.task = task
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
                    "task": task,
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
                timesheet_doc.task = task
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
                    "task": task,
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
