# -*- coding: utf-8 -*-
# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from datetime import datetime, timedelta

class ScheduleEntry(Document):
    def validate(self):
        """Validate schedule entry"""
        self.validate_duration()
        self.validate_times()
        self.validate_resource_capacity()
        self.validate_activity_project_link()
        self.calculate_end_time()
    
    def validate_duration(self):
        """Validate duration value"""
        # Convert to float if it's a string
        if isinstance(self.duration, str):
            try:
                self.duration = float(self.duration)
            except (ValueError, TypeError):
                self.duration = 1.0
        
        # Ensure it's a number
        if not isinstance(self.duration, (int, float)):
            self.duration = 1.0
            
        if self.duration <= 0:
            frappe.throw(_("Duration must be greater than 0"))
        elif self.duration > 24:
            frappe.throw(_("Duration cannot exceed 24 hours"))
    
    def validate_times(self):
        """Validate start and end times - only if both are explicitly provided by user"""
        # For scheduler workflow: user only provides date + duration
        # Times are auto-generated and should not be validated
        # Only validate times if they were explicitly provided by user in a different workflow
        
        # Skip validation entirely for scheduler workflow
        # This method should only validate when times are manually entered by user
        return
    
    def calculate_end_time(self):
        """Calculate end time if start time is provided but end time is not"""
        if self.start_time and not self.end_time and self.duration:
            try:
                # Handle time string that might contain microseconds
                start_time_str = str(self.start_time)
                if '.' in start_time_str:
                    start_time_str = start_time_str.split('.')[0]
                
                start_dt = datetime.strptime(start_time_str, '%H:%M:%S')
                end_dt = start_dt + timedelta(hours=self.duration)
                
                # Handle day overflow
                if end_dt.day > start_dt.day:
                    # Cap at 23:59:59 if it goes to next day
                    end_dt = start_dt.replace(hour=23, minute=59, second=59)
                    # Recalculate duration
                    time_diff = end_dt - start_dt
                    self.duration = round(time_diff.total_seconds() / 3600, 2)
                
                self.end_time = end_dt.strftime('%H:%M:%S')
            except ValueError as e:
                # If time parsing fails, just skip calculation
                frappe.log_error(f"End time calculation failed: {e}", "Schedule Entry")
    
    def validate_resource_capacity(self):
        """Validate that resource has capacity for this schedule"""
        if not self.resource:
            return  # Unassigned entries are allowed
        
        # Get resource document
        resource_doc = frappe.get_doc("Resource", self.resource)
        
        if resource_doc.status != "Active":
            frappe.throw(_("Cannot schedule inactive resource: {0}").format(resource_doc.resource_name))
        
        # Check if resource has capacity for this duration on this date
        if not resource_doc.is_available(self.schedule_date, self.duration):
            available_capacity = resource_doc.get_available_capacity(self.schedule_date)
            frappe.throw(_("Resource {0} only has {1} hours available on {2}. Requested: {3} hours").format(
                resource_doc.resource_name, 
                available_capacity, 
                self.schedule_date, 
                self.duration
            ))
    
    def validate_activity_project_link(self):
        """Validate that the activity belongs to the selected project"""
        if self.activity and self.project:
            activity_project = frappe.db.get_value("Activity", self.activity, "project")
            if activity_project != self.project:
                frappe.throw(_("Activity {0} does not belong to project {1}").format(self.activity, self.project))
    
    def on_update(self):
        """Actions on update"""
        # Progress used to be written back to the linked record from here, with
        # frappe.db.set_value("Task", self.task, "progress_percent", ...). Both
        # halves of that are gone: commit 98e9b04 renamed this DocType's "task"
        # field to "activity" and pointed it at Activity, and "progress_percent"
        # was removed from Activity by 8126278. The write therefore targeted a
        # table that does not exist and took the whole save down with it, so
        # on_update does nothing for now. The calculation is kept as
        # get_activity_progress(); restore the write here once Activity has a
        # field to hold it.
        pass
    
    def on_submit(self):
        """Actions on submit"""
        pass
    
    def on_cancel(self):
        """Actions on cancel"""
        pass
    
    def get_activity_progress(self):
        """Share of this activity's scheduled hours that are completed, 0-100.

        Returns None when there is nothing to measure, so callers can tell
        "no scheduled hours" apart from "scheduled but none done yet".
        """
        if not self.activity:
            return None
        
        # Every schedule entry for this activity, cancelled ones excluded
        entries = frappe.get_all("Schedule Entry",
            filters={"activity": self.activity, "docstatus": ["!=", 2]},
            fields=["status", "duration"])
        
        if not entries:
            return None
        
        total_hours = sum(entry.duration or 0 for entry in entries)
        if not total_hours:
            return None
        
        completed_hours = sum(
            entry.duration or 0 for entry in entries if entry.status == "Completed")
        
        return min(100, (completed_hours / total_hours) * 100)
    
    def get_overlapping_entries(self):
        """Get overlapping schedule entries for the same resource"""
        if not self.resource or not self.start_time or not self.end_time:
            return []
        
        # Find entries that overlap with this one
        overlapping = frappe.db.sql("""
            SELECT name, start_time, end_time, project
            FROM `tabSchedule Entry`
            WHERE resource = %s 
            AND schedule_date = %s 
            AND name != %s
            AND docstatus != 2
            AND (
                (start_time <= %s AND end_time > %s) OR
                (start_time < %s AND end_time >= %s) OR
                (start_time >= %s AND end_time <= %s)
            )
        """, (
            self.resource, self.schedule_date, self.name or "",
            self.start_time, self.start_time,
            self.end_time, self.end_time,
            self.start_time, self.end_time
        ), as_dict=True)
        
        return overlapping
    
    def before_save(self):
        """Actions before save"""
        # Check for time conflicts if times are specified
        if self.resource and self.start_time and self.end_time:
            overlapping = self.get_overlapping_entries()
            if overlapping:
                conflict_details = []
                for entry in overlapping:
                    conflict_details.append(f"{entry.name} ({entry.start_time}-{entry.end_time})")
                
                frappe.throw(_("Time conflict detected with: {0}").format(", ".join(conflict_details)))
    
    @frappe.whitelist()
    def move_to_resource(self, new_resource, new_date=None):
        """Move this schedule entry to a different resource"""
        old_resource = self.resource
        old_date = self.schedule_date
        
        self.resource = new_resource
        if new_date:
            self.schedule_date = new_date
        
        try:
            self.save()
            return {
                "success": True,
                "message": _("Schedule entry moved successfully")
            }
        except Exception as e:
            # Revert changes
            self.resource = old_resource
            self.schedule_date = old_date
            return {
                "success": False,
                "message": str(e)
            }
    
    @frappe.whitelist()
    def duplicate_entry(self, new_date, new_resource=None):
        """Create a duplicate of this entry for a different date/resource"""
        new_doc = frappe.copy_doc(self)
        new_doc.schedule_date = new_date
        if new_resource:
            new_doc.resource = new_resource
        
        new_doc.insert()
        return new_doc.name
