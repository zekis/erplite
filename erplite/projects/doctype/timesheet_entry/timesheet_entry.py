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
        self.validate_employee_ownership()
        self.calculate_duration()
        self.validate_times()
        self.check_overlapping_entries()
    
    def set_employee_default(self):
        """Set employee to current user if not set"""
        if not self.employee:
            self.employee = frappe.session.user
    
    def validate_employee_ownership(self):
        """On insert, keep `employee` and `owner` naming the same person.

        Two different fields answer "whose timesheet is this", and nothing kept
        them in agreement:

          * **Frappe decides who may read and write from `owner`**, the standard
            column it sets to the creating user (`set_user_and_timestamp`,
            frappe/model/document.py:555-566). The Projects User row on this
            DocType carries `if_owner`, so for that role read and write stop at
            the rows that user created (`get_role_permissions`,
            frappe/permissions.py:288-305).
          * **The app decides whose hours they are from `employee`**, a required
            editable Link to User. `get_week_timesheets`,
            `export_timesheet_data` and the dashboard widgets all filter on it,
            through `frappe.get_all`, which ignores permissions by design.

        That went wrong in both directions. Any Projects User could insert an
        entry with `employee` set to a colleague -- `create` is the one right
        `if_owner` never restricts ("if_owner does not come with create rights",
        permissions.py:303-305) -- and the hours then counted as that
        colleague's everywhere the app looks. And an entry booked *for* you by
        someone else could not be corrected by you, because `owner` was them:
        you saw it in the week view (`get_all` skips permissions) and frappe
        refused the save.

        So, on insert:

          * an `employee` other than the session user needs write on this
            DocType. That invents no policy -- it is the test `approve_timesheet`
            below already applies, and the one Afterz applies in its own
            `update_timesheet_entry` -- and it enforces the permission rows this
            app ships: System Manager and Projects Manager hold write outright,
            Projects User holds it only `if_owner`, which at DocType level
            evaluates to 0 (permissions.py:296-305).
          * when that is allowed, `owner` becomes the employee, so frappe's
            `if_owner` and the app's `employee` name the same person. The
            employee can then correct their own hours. `modified_by` still
            records who entered them, and nothing in this app or in Afterz reads
            `owner` on a Timesheet Entry.

        **Insert only, and that is structural rather than tidy.** Every other
        save must stay exactly as it was, because acting on another person's
        entry is the point of the approval workflow. Afterz's
        `submit_week_entries`, `approve_all_entries`, `reject_entry_with_reason`
        and `unapprove_entry` each `save()` an entry whose `employee` is someone
        else; erplite's own `approve_timesheet` and `reject_timesheet` do too. A
        rule on every save would refuse all six.

        Two edges, stated rather than hidden. Frappe's doctype-level write test
        also answers True to anyone who has even one Timesheet Entry shared with
        them for write (`false_if_not_shared`, permissions.py:159-184) -- a
        deliberate grant by someone who could already do it, but wider than the
        role rows alone. And during `bench migrate` or a patch,
        `set_user_and_timestamp` leaves `owner` unset and `db_insert` fills it
        from the session user afterwards (base_document.py:551-553), so a row
        created by a patch keeps the patch's user as owner.
        """
        if not self.is_new():
            return
        if self.employee == frappe.session.user:
            return
        if not frappe.has_permission(self.doctype, "write"):
            frappe.throw(_(
                "You can only book time against your own name. "
                "Set Employee to yourself, or ask someone who may book time for "
                "others to enter it."
            ))
        self.owner = self.employee

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
        """Actions before save.

        Deliberately does NOT derive `status`, and must stay that way.

        Auto-submitting here looks right -- a pre-save hook is where a derived
        field belongs, because an assignment in on_update() happens after
        db_update() has written the row and is discarded. But `status` is not a
        derived field: it is a workflow state that other apps set explicitly, and
        a hook here runs on *every* save of the document, not only on check-out.

        Afterz (crew.tierneymorris.com.au/afterz, repo zekis/afterz) never calls
        erplite code, but it creates and saves Timesheet Entry rows directly, so
        this hook reaches it. Every one of its five timesheet calls hands this
        hook a Draft row that already has both times:

          * create_timesheet_entry  -- drag an activity onto the calendar and the
            row is inserted Draft with check_in_time AND check_out_time;
          * update_timesheet_entry  -- moving or resizing that block saves it;
          * submit_week_entries     -- filters status == "Draft";
          * reject_entry_with_reason -- sets status = "Draft", then save();
          * unapprove_entry          -- sets status = "Draft", then save().

        So a rule here does not merely submit early. It makes the first two lock
        the entry on creation, leaves the third with nothing to find, and turns
        the last two into no-ops that land back on "Submitted" in the same save --
        a reject that silently re-queues the entry it just rejected.

        erplite's own check-out is the one place that genuinely means "submit
        this now", and it says so itself in check_out() below, before it saves.

        tests/offline/test_afterz_timesheet_workflow.py pins all five paths.
        """
        # Date field has been removed - no longer needed
        pass

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
        
        # Auto-submit: checking out is the explicit "I have finished this entry"
        # action, so it is the one place that may move the entry on by itself.
        #
        # Set before save(), not in an on_update() hook: frappe's Document._save()
        # runs run_before_save_methods(), then db_update(), then
        # run_post_save_methods(), so a status assigned in on_update() lands on the
        # in-memory document after its row has been written and is discarded. That
        # is why a checked-out timesheet stayed "Draft" and approve_timesheet()
        # then refused it with "Only submitted timesheets can be approved".
        #
        # Here rather than in before_save() because before_save() runs on every
        # save by anyone, including Afterz's reject and un-approve -- see the note
        # on before_save() above.
        if timesheet.status == "Draft":
            timesheet.status = "Submitted"
        
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
        
        # Check if user is the project's timesheet approver
        project = frappe.get_doc("Project", timesheet.project)
        if project.timesheet_approver != frappe.session.user and not frappe.has_permission("Timesheet Entry", "write"):
            frappe.throw(_("Only the timesheet approver can approve timesheets for this project"))
        
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
        
        # Check if user is the project's timesheet approver
        project = frappe.get_doc("Project", timesheet.project)
        if project.timesheet_approver != frappe.session.user and not frappe.has_permission("Timesheet Entry", "write"):
            frappe.throw(_("Only the timesheet approver can reject timesheets for this project"))
        
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
