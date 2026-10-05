# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from datetime import datetime, date
from typing import Dict, Any, Optional


class ScheduleRow(Document):
    def before_save(self):
        """Update calculated fields before saving"""
        self.update_summary_fields()
        self.last_updated = frappe.utils.now()
    
    def update_summary_fields(self):
        """Update start_date, end_date, and total_hours based on daily_entries"""
        if not self.daily_entries:
            self.start_date = None
            self.end_date = None
            self.total_hours = 0.0
            return
        
        try:
            entries = json.loads(self.daily_entries) if isinstance(self.daily_entries, str) else self.daily_entries
            
            if not entries:
                self.start_date = None
                self.end_date = None
                self.total_hours = 0.0
                return
            
            # Handle optimized format with blocks and individual_days
            if 'blocks' in entries or 'individual_days' in entries:
                # Expand to daily entries for calculation
                daily_entries = self.expand_optimized_entries(entries)
                
                if not daily_entries:
                    self.start_date = None
                    self.end_date = None
                    self.total_hours = 0.0
                    return
                
                # Get date range from daily entries
                dates = [frappe.utils.getdate(date_str) for date_str in daily_entries.keys()]
                self.start_date = min(dates)
                self.end_date = max(dates)
                
                # Calculate total hours from daily entries
                total = 0.0
                for entry in daily_entries.values():
                    if isinstance(entry, dict) and 'hours' in entry:
                        total += float(entry.get('hours', 0))
                    elif isinstance(entry, (int, float)):
                        total += float(entry)
                
                self.total_hours = total
            else:
                # Handle legacy format (direct date keys)
                # Filter out non-date keys
                date_entries = {}
                for key, value in entries.items():
                    # Check if key looks like a date (YYYY-MM-DD format)
                    if isinstance(key, str) and len(key) == 10 and key.count('-') == 2:
                        try:
                            frappe.utils.getdate(key)  # Validate it's a real date
                            date_entries[key] = value
                        except:
                            continue  # Skip invalid date keys
                
                if not date_entries:
                    self.start_date = None
                    self.end_date = None
                    self.total_hours = 0.0
                    return
                
                # Get date range
                dates = [frappe.utils.getdate(date_str) for date_str in date_entries.keys()]
                self.start_date = min(dates)
                self.end_date = max(dates)
                
                # Calculate total hours
                total = 0.0
                for entry in date_entries.values():
                    if isinstance(entry, dict) and 'hours' in entry:
                        total += float(entry.get('hours', 0))
                    elif isinstance(entry, (int, float)):
                        total += float(entry)
                
                self.total_hours = total
            
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            frappe.log_error(f"Error parsing daily_entries for {self.name}: {str(e)}")
            self.total_hours = 0.0
    
    def get_daily_entries_dict(self) -> Dict[str, Any]:
        """Get daily entries as a dictionary"""
        if not self.daily_entries:
            return {}
        
        try:
            if isinstance(self.daily_entries, str):
                return json.loads(self.daily_entries)
            return self.daily_entries
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_daily_entries_dict(self, entries: Dict[str, Any]):
        """Set daily entries from a dictionary and optimize storage"""
        optimized_entries = self.optimize_entries_storage(entries)
        self.daily_entries = json.dumps(optimized_entries, default=str)
        self.update_summary_fields()
    
    def optimize_entries_storage(self, entries: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize storage by consolidating consecutive identical shifts into blocks"""
        if not entries:
            return {}
        
        # If entries is already in optimized format, expand it first
        if 'blocks' in entries or 'individual_days' in entries:
            entries = self.expand_optimized_entries(entries)
        
        # Convert to list of (date, entry) tuples and sort by date
        sorted_entries = sorted(entries.items(), key=lambda x: x[0])
        
        optimized = {
            "blocks": [],
            "individual_days": {}
        }
        
        current_block = None
        
        for date_str, entry in sorted_entries:
            # Normalize entry format
            if isinstance(entry, (int, float)):
                entry = {"hours": float(entry), "start_time": "09:00", "end_time": "17:00", "status": "planned"}
            elif not isinstance(entry, dict):
                continue
            
            # Check if this entry can extend the current block
            if current_block and self.can_extend_block(current_block, date_str, entry):
                current_block["end_date"] = date_str
                current_block["days_count"] = self.count_days_between(current_block["start_date"], date_str) + 1
            else:
                # Finalize current block if it exists
                if current_block:
                    if current_block["days_count"] >= 2:  # Only create blocks for 2+ consecutive days
                        optimized["blocks"].append(current_block)
                    else:
                        # Single day, store as individual
                        optimized["individual_days"][current_block["start_date"]] = {
                            "hours": current_block["hours"],
                            "start_time": current_block["start_time"],
                            "end_time": current_block["end_time"],
                            "description": current_block.get("description", ""),
                            "status": current_block.get("status", "planned")
                        }
                
                # Start new block
                current_block = {
                    "start_date": date_str,
                    "end_date": date_str,
                    "hours": entry.get("hours", 8),
                    "start_time": entry.get("start_time", "09:00"),
                    "end_time": entry.get("end_time", "17:00"),
                    "description": entry.get("description", ""),
                    "status": entry.get("status", "planned"),
                    "days_count": 1
                }
        
        # Finalize the last block
        if current_block:
            if current_block["days_count"] >= 2:
                optimized["blocks"].append(current_block)
            else:
                optimized["individual_days"][current_block["start_date"]] = {
                    "hours": current_block["hours"],
                    "start_time": current_block["start_time"],
                    "end_time": current_block["end_time"],
                    "description": current_block.get("description", ""),
                    "status": current_block.get("status", "planned")
                }
        
        return optimized
    
    def can_extend_block(self, block: Dict[str, Any], date_str: str, entry: Dict[str, Any]) -> bool:
        """Check if an entry can extend the current block"""
        # Check if date is consecutive
        last_date = frappe.utils.getdate(block["end_date"])
        current_date = frappe.utils.getdate(date_str)
        
        if (current_date - last_date).days != 1:
            return False
        
        # Check if shift details match
        return (
            entry.get("hours") == block["hours"] and
            entry.get("start_time") == block["start_time"] and
            entry.get("end_time") == block["end_time"] and
            entry.get("status", "planned") == block.get("status", "planned")
        )
    
    def count_days_between(self, start_date: str, end_date: str) -> int:
        """Count days between two dates (inclusive)"""
        start = frappe.utils.getdate(start_date)
        end = frappe.utils.getdate(end_date)
        return (end - start).days
    
    def add_daily_entry(self, date_str: str, hours: float, description: str = "", status: str = "planned", start_time: str = "09:00", end_time: str = "17:00"):
        """Add or update a daily entry"""
        entries = self.expand_entries_to_daily()
        
        entries[date_str] = {
            "hours": hours,
            "start_time": start_time,
            "end_time": end_time,
            "description": description,
            "status": status,
            "updated": frappe.utils.now()
        }
        
        self.set_daily_entries_dict(entries)
    
    def expand_optimized_entries(self, optimized: Dict[str, Any]) -> Dict[str, Any]:
        """Expand optimized entries structure to daily entries for calculation"""
        daily_entries = {}
        
        # Add individual days
        if "individual_days" in optimized:
            daily_entries.update(optimized["individual_days"])
        
        # Expand blocks to individual days
        if "blocks" in optimized:
            for block in optimized["blocks"]:
                start_date = frappe.utils.getdate(block["start_date"])
                end_date = frappe.utils.getdate(block["end_date"])
                
                current_date = start_date
                while current_date <= end_date:
                    date_str = current_date.strftime("%Y-%m-%d")
                    daily_entries[date_str] = {
                        "hours": block["hours"],
                        "start_time": block["start_time"],
                        "end_time": block["end_time"],
                        "description": block.get("description", ""),
                        "status": block.get("status", "planned")
                    }
                    current_date = frappe.utils.add_days(current_date, 1)
        
        return daily_entries

    def expand_entries_to_daily(self) -> Dict[str, Any]:
        """Expand optimized storage back to daily entries for manipulation"""
        optimized = self.get_daily_entries_dict()
        return self.expand_optimized_entries(optimized)
    
    def remove_daily_entry(self, date_str: str):
        """Remove a daily entry"""
        entries = self.get_daily_entries_dict()
        
        if date_str in entries:
            del entries[date_str]
            self.set_daily_entries_dict(entries)
    
    def get_daily_entry(self, date_str: str) -> Optional[Dict[str, Any]]:
        """Get a specific daily entry"""
        entries = self.get_daily_entries_dict()
        return entries.get(date_str)
    
    def copy_entries_to_date_range(self, start_date: str, end_date: str, overwrite: bool = False):
        """Copy existing entries to a new date range"""
        entries = self.get_daily_entries_dict()
        
        if not entries:
            return
        
        # Get a sample entry to copy
        sample_entry = next(iter(entries.values()))
        if isinstance(sample_entry, dict):
            template = {
                "hours": sample_entry.get("hours", 0),
                "description": sample_entry.get("description", ""),
                "status": "planned"
            }
        else:
            template = {"hours": float(sample_entry), "description": "", "status": "planned"}
        
        # Generate date range
        current_date = frappe.utils.getdate(start_date)
        end_date_obj = frappe.utils.getdate(end_date)
        
        while current_date <= end_date_obj:
            date_str = current_date.strftime("%Y-%m-%d")
            
            if overwrite or date_str not in entries:
                entries[date_str] = template.copy()
                entries[date_str]["updated"] = frappe.utils.now()
            
            current_date = frappe.utils.add_days(current_date, 1)
        
        self.set_daily_entries_dict(entries)
    
    def extend_entries(self, additional_days: int, hours_per_day: float = 0):
        """Extend entries by additional days"""
        entries = self.get_daily_entries_dict()
        
        if not entries:
            # Start from today if no entries exist
            start_date = frappe.utils.today()
        else:
            # Start from the day after the last entry
            last_date = max(frappe.utils.getdate(date_str) for date_str in entries.keys())
            start_date = frappe.utils.add_days(last_date, 1)
        
        # Add entries for additional days
        for i in range(additional_days):
            date_obj = frappe.utils.add_days(start_date, i)
            date_str = date_obj.strftime("%Y-%m-%d")
            
            entries[date_str] = {
                "hours": hours_per_day,
                "description": "",
                "status": "planned",
                "updated": frappe.utils.now()
            }
        
        self.set_daily_entries_dict(entries)
    
    def get_entries_for_date_range(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Get entries within a specific date range"""
        entries = self.get_daily_entries_dict()
        
        start_date_obj = frappe.utils.getdate(start_date)
        end_date_obj = frappe.utils.getdate(end_date)
        
        filtered_entries = {}
        for date_str, entry in entries.items():
            date_obj = frappe.utils.getdate(date_str)
            if start_date_obj <= date_obj <= end_date_obj:
                filtered_entries[date_str] = entry
        
        return filtered_entries


@frappe.whitelist()
def create_schedule_row(
    project: str, activity: str = None, resource: str = None, task: str = None
) -> str:
    """Create a new schedule row.

    `task` is the pre-rename name for `activity` and is still accepted, so a caller written
    before the Task -> Activity rename keeps working. Prefer `activity`.
    """
    doc = frappe.new_doc("Schedule Row")
    doc.project = project
    # This was `doc.task = task`. Schedule Row has no `task` field -- only `activity` -- and
    # get_valid_dict() builds the INSERT from the DocType's declared fields, so an undeclared
    # attribute is dropped without an error. The caller's task was silently discarded and the
    # row was created with no work attached to it.
    activity = activity or task
    if activity:
        doc.activity = activity
    doc.resource = resource
    doc.daily_entries = "{}"
    doc.insert()
    
    return doc.name


@frappe.whitelist()
def update_daily_entries(schedule_row: str, entries: str) -> Dict[str, Any]:
    """Update daily entries for a schedule row"""
    try:
        doc = frappe.get_doc("Schedule Row", schedule_row)
        entries_dict = json.loads(entries) if isinstance(entries, str) else entries
        
        doc.set_daily_entries_dict(entries_dict)
        doc.save()
        
        return {
            "success": True,
            "message": "Daily entries updated successfully",
            "total_hours": doc.total_hours,
            "start_date": doc.start_date,
            "end_date": doc.end_date
        }
    
    except Exception as e:
        frappe.log_error(f"Error updating daily entries: {str(e)}")
        return {
            "success": False,
            "message": f"Error updating daily entries: {str(e)}"
        }


@frappe.whitelist()
def extend_entries(schedule_row: str, additional_days: int, hours_per_day: float = 0) -> Dict[str, Any]:
    """Extend a schedule row's daily entries by a number of days.

    The "Extend" dialog in schedule_row.js has always called
    `erplite...schedule_row.extend_entries` as a dotted module path, but the only
    `extend_entries` was the ScheduleRow method, which `frappe.get_attr` cannot reach
    (`getattr(module, name)`), so the dialog could never have worked -- it raised "Failed to get
    method for command ...". This is the missing module-level wrapper, in the same shape as
    `update_daily_entries` above: load, mutate through the controller, save.

    The method only calls `set_daily_entries_dict`, which mutates in memory, so the `save()`
    here is what actually persists the new days.
    """
    try:
        doc = frappe.get_doc("Schedule Row", schedule_row)
        doc.extend_entries(int(additional_days), float(hours_per_day or 0))
        doc.save()

        return {
            "success": True,
            "message": "Entries extended successfully",
            "total_hours": doc.total_hours,
            "start_date": doc.start_date,
            "end_date": doc.end_date,
        }

    except Exception as e:
        frappe.log_error(f"Error extending entries: {str(e)}")
        return {
            "success": False,
            "message": f"Error extending entries: {str(e)}",
        }


@frappe.whitelist()
def copy_schedule_row(
    source_row: str,
    target_project: str = None,
    target_activity: str = None,
    target_resource: str = None,
    target_task: str = None,
) -> str:
    """Copy a schedule row to create a new one.

    `target_task` is the pre-rename name for `target_activity` and is still accepted.
    """
    try:
        source_doc = frappe.get_doc("Schedule Row", source_row)

        new_doc = frappe.new_doc("Schedule Row")
        new_doc.project = target_project or source_doc.project
        # This was `new_doc.task = target_task or source_doc.task`, which was wrong twice over:
        # `source_doc.task` reads an orphan column left behind by the Task -> Activity rename
        # (a loaded document gets it from SELECT *, so it is a stale value rather than an
        # error), and `new_doc.task` is then dropped by get_valid_dict() on insert because
        # Schedule Row declares only `activity`. The copy silently lost its activity.
        new_doc.activity = target_activity or target_task or source_doc.activity
        new_doc.resource = target_resource or source_doc.resource
        new_doc.daily_entries = source_doc.daily_entries
        new_doc.insert()
        
        return new_doc.name
    
    except Exception as e:
        frappe.log_error(f"Error copying schedule row: {str(e)}")
        frappe.throw(f"Error copying schedule row: {str(e)}")


@frappe.whitelist()
def bulk_update_entries(updates: str) -> Dict[str, Any]:
    """Bulk update multiple schedule rows"""
    try:
        updates_list = json.loads(updates) if isinstance(updates, str) else updates
        results = []
        
        for update in updates_list:
            schedule_row = update.get("schedule_row")
            entries = update.get("entries", {})
            
            if schedule_row:
                doc = frappe.get_doc("Schedule Row", schedule_row)
                doc.set_daily_entries_dict(entries)
                doc.save()
                
                results.append({
                    "schedule_row": schedule_row,
                    "success": True,
                    "total_hours": doc.total_hours
                })
        
        return {
            "success": True,
            "message": f"Updated {len(results)} schedule rows",
            "results": results
        }
    
    except Exception as e:
        frappe.log_error(f"Error in bulk update: {str(e)}")
        return {
            "success": False,
            "message": f"Error in bulk update: {str(e)}"
        }
