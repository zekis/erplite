# -*- coding: utf-8 -*-
# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, get_datetime, time_diff_in_hours

class TimesheetEntry(Document):
    def validate(self):
        """Validate timesheet entry"""
        self.set_employee_default()
        self.calculate_duration()
        self.validate_times()
        self.check_overlapping_entries()
    
    def set_employee_default(self):
        """Set employee to current user if not set"""
        if not self.employee:
            self.employee = frappe.session.user
    
    def calculate_duration(self):
        """Calculate duration in hours"""
        if self.check_in_time and self.check_out_time:
            self.duration_hours = time_diff_in_hours(self.check_out_time, self.check_in_time)
            self.is_active = 0
        elif self.check_in_time and not self.check_out_time:
            self.is_active = 1
            self.duration_hours = 0
        else:
            self.is_active = 0
            self.duration_hours = 0
    
    def validate_times(self):
        """Validate check-in and check-out times"""
        if self.check_in_time and self.check_out_time:
            if get_datetime(self.check_in_time) >= get_datetime(self.check_out_time):
                frappe.throw(_("Check Out Time must be after Check In Time"))
    
    def check_overlapping_entries(self):
        """Check for overlapping timesheet entries for the same employee"""
        if not self.check_in_time:
            return
        
        # Check for active entries (no check-out time) for the same employee
        active_entries = frappe.get_all("Timesheet Entry", 
            filters={
                "employee": self.employee,
                "is_active": 1,
                "name": ["!=", self.name or ""]
            },
            fields=["name", "check_in_time", "project", "activity"]
        )
        
        if active_entries:
            entry = active_entries[0]
            frappe.throw(_("Employee {0} already has an active timesheet entry: {1} (Project: {2}, Activity: {3}). Please check out first.").format(
                self.employee, entry.name, entry.project, entry.activity
            ))
    
    def before_save(self):
        """Actions before save"""
        # Auto-submit when check-out is completed.
        #
        # This must run before the row is written, not in on_update(). Frappe's
        # Document._save() runs run_before_save_methods(), then db_update(), then
        # run_post_save_methods() -- so an assignment made in on_update() lands on
        # the in-memory document after its row has already been written, and is
        # discarded. That is why a checked-out timesheet stayed "Draft" and
        # approve_timesheet() then refused it with "Only submitted timesheets can
        # be approved".
        if self.check_in_time and self.check_out_time and self.status == "Draft":
            self.status = "Submitted"

@frappe.whitelist()
def check_in(project, activity, location=None):
    """Quick check-in function"""
    try:
        # Check if user already has an active entry
        active_entry = frappe.get_all("Timesheet Entry", 
            filters={
                "employee": frappe.session.user,
                "is_active": 1
            },
            fields=["name", "project", "activity"]
        )
        
        if active_entry:
            entry = active_entry[0]
            frappe.throw(_("You already have an active timesheet entry: {0} (Project: {1}, Activity: {2}). Please check out first.").format(
                entry.name, entry.project, entry.activity
            ))
        
        # Create new timesheet entry
        timesheet = frappe.get_doc({
            "doctype": "Timesheet Entry",
            "employee": frappe.session.user,
            "project": project,
            "activity": activity,
            "location": location,
            "check_in_time": now_datetime(),
            "status": "Draft"
        })
        timesheet.insert()
        
        return {
            "success": True,
            "message": _("Successfully checked in to {0}").format(activity),
            "timesheet_id": timesheet.name
        }
        
    except Exception as e:
        frappe.log_error("Timesheet Check-in", str(e))
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def check_out(timesheet_id, description=None):
    """Quick check-out function"""
    try:
        timesheet = frappe.get_doc("Timesheet Entry", timesheet_id)
        
        # Validate ownership
        if timesheet.employee != frappe.session.user:
            frappe.throw(_("You can only check out your own timesheet entries"))
        
        if not timesheet.is_active:
            frappe.throw(_("This timesheet entry is not active"))
        
        # Update check-out time
        timesheet.check_out_time = now_datetime()
        if description:
            timesheet.description = description
        
        timesheet.save()
        
        return {
            "success": True,
            "message": _("Successfully checked out. Duration: {0} hours").format(timesheet.duration_hours),
            "duration": timesheet.duration_hours
        }
        
    except Exception as e:
        frappe.log_error("Timesheet Check-out", str(e))
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def get_active_timesheet():
    """Get current user's active timesheet"""
    active_entry = frappe.get_all("Timesheet Entry", 
        filters={
            "employee": frappe.session.user,
            "is_active": 1
        },
        fields=["name", "project", "activity", "check_in_time", "location"],
        limit=1
    )
    
    return active_entry[0] if active_entry else None

@frappe.whitelist()
def approve_timesheet(timesheet_id, approval_notes=None):
    """Approve a timesheet entry"""
    try:
        timesheet = frappe.get_doc("Timesheet Entry", timesheet_id)
        
        # Check if user is project manager
        project = frappe.get_doc("Project", timesheet.project)
        if project.project_manager != frappe.session.user and not frappe.has_permission("Timesheet Entry", "write"):
            frappe.throw(_("Only the project manager can approve timesheets for this project"))
        
        if timesheet.status != "Submitted":
            frappe.throw(_("Only submitted timesheets can be approved"))
        
        # Update approval fields
        timesheet.status = "Approved"
        timesheet.approved_by = frappe.session.user
        timesheet.approval_date = now_datetime()
        if approval_notes:
            timesheet.approval_notes = approval_notes
        
        timesheet.save()
        
        return {
            "success": True,
            "message": _("Timesheet approved successfully")
        }
        
    except Exception as e:
        frappe.log_error("Timesheet Approval", str(e))
        return {
            "success": False,
            "message": str(e)
        }

@frappe.whitelist()
def reject_timesheet(timesheet_id, approval_notes=None):
    """Reject a timesheet entry"""
    try:
        timesheet = frappe.get_doc("Timesheet Entry", timesheet_id)
        
        # Check if user is project manager
        project = frappe.get_doc("Project", timesheet.project)
        if project.project_manager != frappe.session.user and not frappe.has_permission("Timesheet Entry", "write"):
            frappe.throw(_("Only the project manager can reject timesheets for this project"))
        
        if timesheet.status != "Submitted":
            frappe.throw(_("Only submitted timesheets can be rejected"))
        
        # Update approval fields
        timesheet.status = "Rejected"
        timesheet.approved_by = frappe.session.user
        timesheet.approval_date = now_datetime()
        if approval_notes:
            timesheet.approval_notes = approval_notes
        
        timesheet.save()
        
        return {
            "success": True,
            "message": _("Timesheet rejected")
        }
        
    except Exception as e:
        frappe.log_error("Timesheet Rejection", str(e))
        return {
            "success": False,
            "message": str(e)
        }
