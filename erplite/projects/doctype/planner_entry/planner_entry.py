import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, time_diff_in_hours


class PlannerEntry(Document):
    def validate(self):
        """
        Validation and auto-field logic:
        - Ensure plan_start exists
        - Require either plan_end or duration_hours
        - Auto-calculate duration_hours when plan_end is given
        - Ensure positive duration when both start and end are present
        - Default user to owner if missing
        - Default title from linked ToDo if missing
        """
        # Default user to owner if not provided
        if not self.user:
            self.user = self.owner

        # Ensure plan_start is provided
        if not self.plan_start:
            frappe.throw("Planned Start (plan_start) is required")

        # Validate duration/plan_end logic
        has_end = bool(self.plan_end)
        has_duration = self.duration_hours is not None and self.duration_hours != ""

        if not has_end and not has_duration:
            frappe.throw("Provide either Planned End (plan_end) or Duration (Hours)")

        if has_end:
            # Calculate duration_hours from start/end
            try:
                start = get_datetime(self.plan_start)
                end = get_datetime(self.plan_end)
            except Exception:
                frappe.throw("Invalid datetime for plan_start or plan_end")

            # Ensure end is after start
            if end <= start:
                frappe.throw("Planned End must be after Planned Start")

            computed_hours = time_diff_in_hours(end, start)
            # Always sync duration_hours to computed value when plan_end present
            self.duration_hours = round(float(computed_hours), 2)

        # If only duration provided, ensure it's positive
        if not has_end and has_duration:
            try:
                self.duration_hours = round(float(self.duration_hours), 2)
            except Exception:
                frappe.throw("Duration (Hours) must be a number")
            if self.duration_hours <= 0:
                frappe.throw("Duration (Hours) must be greater than 0")

        # Default title from ToDo if not explicitly set
        if not self.title and self.todo:
            try:
                todo_doc = frappe.get_doc("ToDo", self.todo)
                # Fallback to the ToDo name if no description
                self.title = (todo_doc.description or "").strip() or todo_doc.name
            except Exception:
                # If lookup fails, keep title as-is; frontend enforces required
                pass
