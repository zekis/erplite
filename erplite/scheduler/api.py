# -*- coding: utf-8 -*-
# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from datetime import datetime, timedelta
import json

@frappe.whitelist()
def get_scheduler_data(start_date=None, end_date=None, resource=None, project=None):
    """Get all data needed for the scheduler interface"""
    
    # Set default date range (30 days from today)
    if not start_date:
        start_date = frappe.utils.today()
    if not end_date:
        end_date = frappe.utils.add_days(start_date, 30)
    
    # Get projects and activities
    projects_data = get_projects_and_activities()
    
    # Get resources
    resources_data = get_resources()
    
    # Get roles
    roles_data = get_roles()
    
    # Get schedule entries
    schedule_entries = get_schedule_entries(start_date, end_date, resource, project)
    
    # Get project colors (reuse from timesheet-calendar if available)
    project_colors = get_project_colors()
    
    return {
        "projects": projects_data,
        "resources": resources_data,
        "roles": roles_data,
        "schedule_entries": schedule_entries,
        "project_colors": project_colors,
        "date_range": {
            "start_date": start_date,
            "end_date": end_date
        }
    }

@frappe.whitelist()
def get_projects_and_activities():
    """Get all projects with their activities"""
    
    projects = frappe.get_all("Project",
        fields=["name", "project_name", "status", "project_lead", "division"],
        filters={"status": ["!=", "Cancelled"]},
        order_by="project_name"
    )
    
    # Get division details for each project
    for project in projects:
        if project.division:
            division_data = frappe.db.get_value("Division", project.division, 
                ["division_name", "color"], as_dict=True)
            if division_data:
                project['division_name'] = division_data.division_name
                project['division_color'] = division_data.color
        
        # Get activities for each project
        activities = frappe.get_all("Activity",
            fields=["name", "activity_name", "status"],
            filters={"project": project.name, "status": ["!=", "Cancelled"]},
            order_by="activity_name"
        )
        for activity in activities:
            # Compatibility alias: the built scheduler bundle under
            # erplite/public/frontend/assets/ still reads `subject`. Remove this
            # once the frontend has been rebuilt from frontend/src.
            activity['subject'] = activity.activity_name
        project['activities'] = activities
    
    return projects

@frappe.whitelist()
def get_resources(resource_type=None, status="Active"):
    """Get all resources"""
    
    filters = {"status": status}
    if resource_type:
        filters["resource_type"] = resource_type
    
    resources = frappe.get_all("Resource",
        filters=filters,
        fields=["name", "resource_name", "resource_type", "status", "capacity"],
        order_by="resource_name"
    )
    
    # Add current utilization for each resource
    for resource in resources:
        today = frappe.utils.today()
        resource['today_utilization'] = float(get_resource_utilization(resource.name, today))
        resource['available_capacity'] = float(max(0, resource.capacity - resource['today_utilization']))
        
        # Ensure all numeric fields are JSON serializable
        if resource.get('capacity'):
            resource['capacity'] = float(resource['capacity'])
    
    return resources

@frappe.whitelist()
def get_roles(status="Active"):
    """Get all scheduler roles"""
    
    filters = {"is_active": 1}
    if status == "Active":
        filters["is_active"] = 1
    elif status == "Inactive":
        filters["is_active"] = 0
    
    roles = frappe.get_all("Scheduler Role",
        filters=filters,
        fields=["name", "role_name", "role_code", "description", "is_active", "color", "hourly_rate"],
        order_by="role_name"
    )
    
    # Ensure all numeric fields are JSON serializable
    for role in roles:
        if role.get('hourly_rate'):
            role['hourly_rate'] = float(role['hourly_rate'])
        if role.get('is_active'):
            role['is_active'] = int(role['is_active'])
    
    return roles

@frappe.whitelist()
def get_schedule_entries(start_date, end_date, resource=None, project=None):
    """Get schedule entries within date range"""
    
    filters = {
        "schedule_date": ["between", [start_date, end_date]],
        "docstatus": ["!=", 2]  # Exclude cancelled entries
    }
    
    if resource:
        filters["resource"] = resource
    if project:
        filters["project"] = project
    
    entries = frappe.get_all("Schedule Entry",
        filters=filters,
        fields=[
            "name", "project", "activity", "resource", "schedule_date", 
            "duration", "status", "priority", "start_time", "end_time", 
            "description"
        ],
        order_by="schedule_date, start_time"
    )
    
    # Enrich entries with additional data and ensure JSON serializable
    for entry in entries:
        # Get project and activity names
        if entry.project:
            entry['project_name'] = frappe.db.get_value("Project", entry.project, "project_name")
        if entry.activity:
            entry['activity_name'] = frappe.db.get_value("Activity", entry.activity, "activity_name")
        if entry.resource:
            entry['resource_name'] = frappe.db.get_value("Resource", entry.resource, "resource_name")
        
        # Ensure all fields are JSON serializable
        if entry.get('schedule_date'):
            entry['schedule_date'] = str(entry['schedule_date'])
        if entry.get('start_time'):
            entry['start_time'] = str(entry['start_time'])
        if entry.get('end_time'):
            entry['end_time'] = str(entry['end_time'])
        if entry.get('duration'):
            entry['duration'] = float(entry['duration'])
    
    return entries

@frappe.whitelist()
def create_schedule_entry(data):
    """Create a new schedule entry"""
    
    try:
        # Parse data if it's a string
        if isinstance(data, str):
            data = json.loads(data)
        
        # Create new document
        doc = frappe.new_doc("Schedule Entry")
        
        # Set fields
        doc.project = data.get("project")
        doc.activity = data.get("activity")
        doc.resource = data.get("resource")
        
        # Parse date properly to handle any timestamp issues
        schedule_date = data.get("schedule_date")
        if schedule_date:
            # Convert to proper date format if it contains timestamp data
            if isinstance(schedule_date, str):
                # Extract just the date part if it contains time/timestamp
                schedule_date = schedule_date.split('T')[0].split(' ')[0]
            doc.schedule_date = schedule_date
        
        doc.duration = float(data.get("duration", 1.0))
        doc.status = data.get("status", "Planned")
        doc.priority = data.get("priority", "Medium")
        
        # Only set start_time and end_time if they are explicitly provided
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        if start_time:
            doc.start_time = start_time
        if end_time:
            doc.end_time = end_time
            
        doc.description = data.get("description", "")
        
        # Save document
        doc.insert()
        
        return {
            "success": True,
            "message": _("Schedule entry created successfully"),
            "name": doc.name,
            "data": doc.as_dict()
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating schedule entry: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def update_schedule_entry(name, data):
    """Update an existing schedule entry"""
    
    try:
        # Parse data if it's a string
        if isinstance(data, str):
            data = json.loads(data)
        
        # Get existing document
        doc = frappe.get_doc("Schedule Entry", name)
        
        # Update fields
        if "project" in data:
            doc.project = data["project"]
        if "activity" in data:
            doc.activity = data["activity"]
        if "resource" in data:
            doc.resource = data["resource"]
        if "schedule_date" in data:
            doc.schedule_date = data["schedule_date"]
        if "duration" in data:
            doc.duration = data["duration"]
        if "status" in data:
            doc.status = data["status"]
        if "priority" in data:
            doc.priority = data["priority"]
        if "start_time" in data:
            doc.start_time = data["start_time"]
        if "end_time" in data:
            doc.end_time = data["end_time"]
        if "description" in data:
            doc.description = data["description"]
        
        # Save document
        doc.save()
        
        return {
            "success": True,
            "message": _("Schedule entry updated successfully"),
            "data": doc.as_dict()
        }
        
    except Exception as e:
        frappe.log_error(f"Error updating schedule entry: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def delete_schedule_entry(name):
    """Delete a schedule entry"""
    
    try:
        frappe.delete_doc("Schedule Entry", name)
        
        return {
            "success": True,
            "message": _("Schedule entry deleted successfully")
        }
        
    except Exception as e:
        frappe.log_error(f"Error deleting schedule entry: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def move_schedule_entry(name, new_resource=None, new_date=None):
    """Move a schedule entry to a different resource or date"""
    
    try:
        doc = frappe.get_doc("Schedule Entry", name)
        
        if new_resource:
            doc.resource = new_resource
        if new_date:
            doc.schedule_date = new_date
        
        doc.save()
        
        return {
            "success": True,
            "message": _("Schedule entry moved successfully"),
            "data": doc.as_dict()
        }
        
    except Exception as e:
        frappe.log_error(f"Error moving schedule entry: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def bulk_create_entries(entries_data):
    """Create multiple schedule entries at once"""
    
    try:
        # Parse data if it's a string
        if isinstance(entries_data, str):
            entries_data = json.loads(entries_data)
        
        created_entries = []
        errors = []
        
        for entry_data in entries_data:
            try:
                result = create_schedule_entry(entry_data)
                if result["success"]:
                    created_entries.append(result["name"])
                else:
                    errors.append(result["message"])
            except Exception as e:
                errors.append(str(e))
        
        return {
            "success": len(errors) == 0,
            "created_count": len(created_entries),
            "error_count": len(errors),
            "created_entries": created_entries,
            "errors": errors,
            "message": _("Created {0} entries, {1} errors").format(len(created_entries), len(errors))
        }
        
    except Exception as e:
        frappe.log_error(f"Error in bulk create: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

def get_resource_utilization(resource, date):
    """Get total scheduled hours for a resource on a specific date"""
    
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(duration), 0) as total_hours
        FROM `tabSchedule Entry`
        WHERE resource = %s AND schedule_date = %s AND docstatus != 2
    """, (resource, date))
    
    return result[0][0] if result else 0

def get_project_colors():
    """Get project colors from Division doctype"""
    
    # Always use division-based colors, don't fallback to timesheet-calendar
    projects = frappe.db.sql("""
        SELECT 
            p.name,
            p.project_name,
            p.division,
            d.color as division_color
        FROM `tabProject` p
        LEFT JOIN `tabDivision` d ON p.division = d.name
        WHERE p.status != 'Cancelled'
    """, as_dict=True)
    
    colors = {}
    color_palette = [
        "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
        "#06b6d4", "#84cc16", "#f97316", "#ec4899", "#6366f1"
    ]
    
    for i, project in enumerate(projects):
        if project.division_color:
            # Use division color if available
            colors[project.name] = project.division_color
        else:
            # Fallback to color palette
            colors[project.name] = color_palette[i % len(color_palette)]
    
    return colors

@frappe.whitelist()
def create_bulk_schedule_entries(entries=None, entries_data=None):
    """Alias for `bulk_create_entries`, kept because the built Vue scheduler calls this name.

    `erplite/public/frontend/assets/VueScheduler-*.js` -- the bundle that is actually deployed --
    calls `erplite.scheduler.api.create_bulk_schedule_entries` and passes its payload as
    `entries`. Neither the name nor the argument existed: the function is `bulk_create_entries`
    and its parameter is `entries_data`, so the call failed in `frappe.handler.execute_cmd` with
    "Failed to get method for command ...". Renaming the call in the Vue source alone would not
    have fixed the deployed bundle, and correcting only the method name would have moved the
    failure to a missing-argument TypeError, so this accepts either argument name and delegates.
    """
    return bulk_create_entries(entries_data if entries_data is not None else entries)


@frappe.whitelist()
def get_resource_capacity_report(resource, start_date, end_date):
    """Get detailed capacity report for a resource"""
    
    # Get resource details
    resource_doc = frappe.get_doc("Resource", resource)
    
    # Get schedule entries for the period
    entries = frappe.get_all("Schedule Entry",
        filters={
            "resource": resource,
            "schedule_date": ["between", [start_date, end_date]],
            "docstatus": ["!=", 2]
        },
        fields=["schedule_date", "duration", "project", "activity", "status"],
        order_by="schedule_date"
    )
    
    # Group by date
    daily_data = {}
    current_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    
    # Initialize all dates
    while current_date <= end_date_obj:
        date_str = current_date.strftime("%Y-%m-%d")
        daily_data[date_str] = {
            "date": date_str,
            "scheduled_hours": 0,
            "capacity": resource_doc.capacity,
            "utilization": 0,
            "entries": []
        }
        current_date += timedelta(days=1)
    
    # Fill in actual data
    for entry in entries:
        date_str = entry.schedule_date
        if date_str in daily_data:
            daily_data[date_str]["scheduled_hours"] += entry.duration
            daily_data[date_str]["entries"].append(entry)
    
    # Calculate utilization
    for date_data in daily_data.values():
        if date_data["capacity"] > 0:
            date_data["utilization"] = (date_data["scheduled_hours"] / date_data["capacity"]) * 100
    
    return {
        "resource": resource_doc.as_dict(),
        "daily_data": list(daily_data.values()),
        "summary": {
            "total_capacity": resource_doc.capacity * len(daily_data),
            "total_scheduled": sum(d["scheduled_hours"] for d in daily_data.values()),
            "average_utilization": sum(d["utilization"] for d in daily_data.values()) / len(daily_data)
        }
    }

@frappe.whitelist()
def get_unassigned_entries(start_date=None, end_date=None, project=None):
    """Get schedule entries without assigned resources"""
    
    if not start_date:
        start_date = frappe.utils.today()
    if not end_date:
        end_date = frappe.utils.add_days(start_date, 30)
    
    filters = {
        "resource": ["is", "not set"],
        "schedule_date": ["between", [start_date, end_date]],
        "docstatus": ["!=", 2]
    }
    
    if project:
        filters["project"] = project
    
    entries = frappe.get_all("Schedule Entry",
        filters=filters,
        fields=[
            "name", "project", "activity", "schedule_date", "duration", 
            "status", "priority", "description"
        ],
        order_by="schedule_date, priority desc"
    )
    
    # Enrich with project and activity names
    for entry in entries:
        if entry.project:
            entry['project_name'] = frappe.db.get_value("Project", entry.project, "project_name")
        if entry.activity:
            entry['activity_name'] = frappe.db.get_value("Activity", entry.activity, "activity_name")
    
    return entries


# Schedule Row API Functions

@frappe.whitelist()
def get_schedule_rows(start_date=None, end_date=None, project=None):
    """Get schedule rows with their daily entries for the date range"""
    
    if not start_date:
        start_date = frappe.utils.today()
    if not end_date:
        end_date = frappe.utils.add_days(start_date, 30)
    
    filters = {}
    if project:
        filters["project"] = project
    
    # Get all schedule rows
    schedule_rows = frappe.get_all("Schedule Row",
        filters=filters,
        fields=[
            "name", "project", "activity", "resource", "role", "project_name", 
            "activity_name", "resource_name", "role_name", "daily_entries", "total_hours"
        ],
        order_by="project, activity, resource"
    )
    
    # Filter daily entries to the requested date range
    for row in schedule_rows:
        if row.daily_entries:
            try:
                all_entries = json.loads(row.daily_entries)
                
                # Handle optimized format with blocks and individual_days
                if 'blocks' in all_entries or 'individual_days' in all_entries:
                    # For optimized format, we need to expand and filter
                    filtered_optimized = {"blocks": [], "individual_days": {}}
                    
                    start_date_obj = frappe.utils.getdate(start_date)
                    end_date_obj = frappe.utils.getdate(end_date)
                    
                    # Filter blocks that overlap with date range
                    if 'blocks' in all_entries:
                        for block in all_entries['blocks']:
                            block_start = frappe.utils.getdate(block['start_date'])
                            block_end = frappe.utils.getdate(block['end_date'])
                            
                            # Check if block overlaps with requested range
                            if block_start <= end_date_obj and block_end >= start_date_obj:
                                filtered_optimized['blocks'].append(block)
                    
                    # Filter individual days
                    if 'individual_days' in all_entries:
                        for date_str, entry in all_entries['individual_days'].items():
                            try:
                                entry_date = frappe.utils.getdate(date_str)
                                if start_date_obj <= entry_date <= end_date_obj:
                                    filtered_optimized['individual_days'][date_str] = entry
                            except:
                                continue  # Skip invalid date keys
                    
                    row.daily_entries = json.dumps(filtered_optimized)
                else:
                    # Handle legacy format (direct date keys)
                    filtered_entries = {}
                    start_date_obj = frappe.utils.getdate(start_date)
                    end_date_obj = frappe.utils.getdate(end_date)
                    
                    for date_str, entry in all_entries.items():
                        # Only process keys that look like dates
                        if isinstance(date_str, str) and len(date_str) == 10 and date_str.count('-') == 2:
                            try:
                                entry_date = frappe.utils.getdate(date_str)
                                if start_date_obj <= entry_date <= end_date_obj:
                                    filtered_entries[date_str] = entry
                            except:
                                continue  # Skip invalid date keys
                    
                    row.daily_entries = json.dumps(filtered_entries)
                
            except (json.JSONDecodeError, ValueError):
                row.daily_entries = "{}"
    
    return schedule_rows


@frappe.whitelist()
def create_schedule_row_entry(project, activity=None, resource=None, role=None):
    """Create a new schedule row"""
    
    try:
        # Check if row already exists
        existing = frappe.db.exists("Schedule Row", {
            "project": project,
            "activity": activity or "",
            "resource": resource or "",
            "role": role or ""
        })
        
        if existing:
            return {
                "success": False,
                "message": "Schedule row already exists",
                "name": existing
            }
        
        # Create new schedule row
        doc = frappe.new_doc("Schedule Row")
        doc.project = project
        if activity:
            doc.activity = activity
        if resource:
            doc.resource = resource
        if role:
            doc.role = role
        doc.daily_entries = "{}"
        doc.insert()
        
        return {
            "success": True,
            "message": "Schedule row created successfully",
            "name": doc.name,
            "data": doc.as_dict()
        }
        
    except Exception as e:
        frappe.log_error(f"Error creating schedule row: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def update_schedule_row_entries(schedule_row, entries_json):
    """Update daily entries for a schedule row with automatic optimization"""
    
    try:
        # Validate JSON
        entries = json.loads(entries_json) if isinstance(entries_json, str) else entries_json
        
        # Get and update document
        doc = frappe.get_doc("Schedule Row", schedule_row)
        doc.set_daily_entries_dict(entries)
        doc.save()
        
        # Get the optimized structure for frontend
        optimized_entries = doc.get_daily_entries_dict()
        
        return {
            "success": True,
            "message": "Daily entries updated successfully",
            "total_hours": doc.total_hours,
            "start_date": doc.start_date,
            "end_date": doc.end_date,
            "optimized_entries": optimized_entries,
            "blocks_count": len(optimized_entries.get("blocks", [])),
            "individual_days_count": len(optimized_entries.get("individual_days", {}))
        }
        
    except Exception as e:
        frappe.log_error(f"Error updating schedule row entries: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def get_schedule_row_expanded(schedule_row):
    """Get schedule row with entries expanded to daily format for editing"""
    
    try:
        doc = frappe.get_doc("Schedule Row", schedule_row)
        expanded_entries = doc.expand_entries_to_daily()
        
        return {
            "success": True,
            "schedule_row": doc.as_dict(),
            "daily_entries": expanded_entries,
            "optimized_entries": doc.get_daily_entries_dict()
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting expanded schedule row: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def add_time_block(schedule_row, start_date, end_date, hours=8, start_time="09:00", end_time="17:00", description="", status="planned"):
    """Add a time block for consecutive days with identical shifts"""
    
    try:
        doc = frappe.get_doc("Schedule Row", schedule_row)
        
        # Get current entries in daily format
        daily_entries = doc.expand_entries_to_daily()
        
        # Add entries for the date range
        current_date = frappe.utils.getdate(start_date)
        end_date_obj = frappe.utils.getdate(end_date)
        
        while current_date <= end_date_obj:
            date_str = current_date.strftime("%Y-%m-%d")
            daily_entries[date_str] = {
                "hours": float(hours),
                "start_time": start_time,
                "end_time": end_time,
                "description": description,
                "status": status
            }
            current_date = frappe.utils.add_days(current_date, 1)
        
        # Save with optimization
        doc.set_daily_entries_dict(daily_entries)
        doc.save()
        
        optimized_entries = doc.get_daily_entries_dict()
        
        return {
            "success": True,
            "message": f"Time block added from {start_date} to {end_date}",
            "total_hours": doc.total_hours,
            "optimized_entries": optimized_entries,
            "blocks_count": len(optimized_entries.get("blocks", [])),
            "individual_days_count": len(optimized_entries.get("individual_days", {}))
        }
        
    except Exception as e:
        frappe.log_error(f"Error adding time block: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def copy_schedule_row_entries(source_row, target_row, date_offset_days=0):
    """Copy entries from one schedule row to another"""
    
    try:
        source_doc = frappe.get_doc("Schedule Row", source_row)
        target_doc = frappe.get_doc("Schedule Row", target_row)
        
        source_entries = source_doc.get_daily_entries_dict()
        target_entries = target_doc.get_daily_entries_dict()
        
        # Copy entries with optional date offset
        for date_str, entry in source_entries.items():
            if date_offset_days != 0:
                # Adjust date
                original_date = frappe.utils.getdate(date_str)
                new_date = frappe.utils.add_days(original_date, date_offset_days)
                new_date_str = new_date.strftime("%Y-%m-%d")
            else:
                new_date_str = date_str
            
            # Copy entry
            target_entries[new_date_str] = entry.copy() if isinstance(entry, dict) else entry
        
        target_doc.set_daily_entries_dict(target_entries)
        target_doc.save()
        
        return {
            "success": True,
            "message": "Entries copied successfully",
            "total_hours": target_doc.total_hours
        }
        
    except Exception as e:
        frappe.log_error(f"Error copying schedule row entries: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def bulk_update_schedule_rows(updates_json):
    """Bulk update multiple schedule rows"""
    
    try:
        updates = json.loads(updates_json) if isinstance(updates_json, str) else updates_json
        results = []
        
        for update in updates:
            schedule_row = update.get("schedule_row")
            entries = update.get("entries", {})
            
            if schedule_row:
                try:
                    doc = frappe.get_doc("Schedule Row", schedule_row)
                    doc.set_daily_entries_dict(entries)
                    doc.save()
                    
                    results.append({
                        "schedule_row": schedule_row,
                        "success": True,
                        "total_hours": doc.total_hours
                    })
                    
                except Exception as e:
                    results.append({
                        "schedule_row": schedule_row,
                        "success": False,
                        "error": str(e)
                    })
        
        return {
            "success": True,
            "message": f"Updated {len([r for r in results if r['success']])} of {len(results)} schedule rows",
            "results": results
        }
        
    except Exception as e:
        frappe.log_error(f"Error in bulk update: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def update_schedule_row_resource(schedule_row, resource=None):
    """Update the resource assignment for a schedule row"""
    
    try:
        doc = frappe.get_doc("Schedule Row", schedule_row)
        doc.resource = resource
        doc.save()
        
        return {
            "success": True,
            "message": "Schedule row resource updated successfully",
            "resource": resource,
            "resource_name": doc.resource_name if resource else None
        }
        
    except Exception as e:
        frappe.log_error(f"Error updating schedule row resource: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def update_schedule_row_role(schedule_row, role=None):
    """Update the role assignment for a schedule row"""
    
    try:
        doc = frappe.get_doc("Schedule Row", schedule_row)
        doc.role = role
        doc.save()
        
        return {
            "success": True,
            "message": "Schedule row role updated successfully",
            "role": role,
            "role_name": doc.role_name if role else None
        }
        
    except Exception as e:
        frappe.log_error(f"Error updating schedule row role: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def delete_schedule_row(schedule_row):
    """Delete a schedule row"""
    
    try:
        frappe.delete_doc("Schedule Row", schedule_row)
        
        return {
            "success": True,
            "message": "Schedule row deleted successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error deleting schedule row: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def schedule_log(message, level="Info"):
    """Log messages for scheduler operations"""
    
    # create a schedule log doc
    log_doc = frappe.new_doc("Scheduler Log")

    log_doc.message = message
    log_doc.level = level
    log_doc.timestamp = frappe.utils.now()
    log_doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {
        "success": True,
        "message": _("Log created successfully"),
        "log_name": log_doc.name
    }
