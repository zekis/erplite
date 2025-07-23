# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Activity(Document):
	def validate(self):
		self.validate_dates()
		self.validate_progress()
	
	def validate_dates(self):
		"""Validate due date"""
		if self.due_date:
			from frappe.utils import getdate, today
			if getdate(self.due_date) < getdate(today()):
				frappe.msgprint("Due date is in the past", indicator="orange")
	
	def validate_progress(self):
		"""Validate progress percentage"""
		if self.progress_percent:
			try:
				progress = float(self.progress_percent)
				if progress < 0 or progress > 100:
					frappe.throw("Progress percentage must be between 0 and 100")
			except (ValueError, TypeError):
				frappe.throw("Progress percentage must be a valid number")
	
	def before_save(self):
		"""Actions before saving"""
		# Auto-update status based on progress
		if self.progress_percent:
			try:
				progress = float(self.progress_percent)
				if progress == 100 and self.status != "Completed":
					self.status = "Completed"
				elif progress > 0 and self.status == "Open":
					self.status = "In Progress"
			except (ValueError, TypeError):
				pass  # Skip status update if progress is not a valid number
	
	def on_update(self):
		"""Actions after update"""
		# Update project progress if needed
		if self.project:
			self.update_project_progress()
	
	def update_project_progress(self):
		"""Update project progress based on activities"""
		try:
			# Get all activities for this project
			activities = frappe.get_all("Activity",
				filters={"project": self.project},
				fields=["progress_percent", "estimated_hours"]
			)
			
			if activities:
				# Calculate weighted average progress
				total_weighted_progress = 0
				total_hours = 0
				
				for activity in activities:
					hours = activity.estimated_hours or 1  # Default to 1 if no hours
					progress = activity.progress_percent or 0
					total_weighted_progress += (progress * hours)
					total_hours += hours
				
				if total_hours > 0:
					project_progress = total_weighted_progress / total_hours
					
					# Update project progress (if project has progress field)
					frappe.db.set_value("Project", self.project, "progress_percent", project_progress)
		except Exception as e:
			# Don't fail the activity save if project update fails
			frappe.log_error(f"Failed to update project progress: {str(e)}")

@frappe.whitelist()
def get_project_activities(project):
	"""Get all activities for a project"""
	activities = frappe.get_all("Activity",
		filters={"project": project},
		fields=["name", "subject", "status", "priority", "progress_percent", "due_date", "assigned_to"],
		order_by="creation desc"
	)
	return activities

@frappe.whitelist()
def get_activity_summary(project=None):
	"""Get activity summary statistics"""
	filters = {}
	if project:
		filters["project"] = project
	
	# Get activity counts by status
	status_counts = frappe.db.sql("""
		SELECT status, COUNT(*) as count
		FROM `tabActivity`
		WHERE docstatus < 2 {project_filter}
		GROUP BY status
	""".format(
		project_filter=f"AND project = '{project}'" if project else ""
	), as_dict=True)
	
	# Get overdue activities
	overdue_count = frappe.db.count("Activity", {
		**filters,
		"due_date": ["<", frappe.utils.today()],
		"status": ["not in", ["Completed", "Cancelled"]]
	})
	
	return {
		"status_counts": status_counts,
		"overdue_count": overdue_count
	}

@frappe.whitelist()
def duplicate_activity(activity_name):
	"""Duplicate an activity"""
	original = frappe.get_doc("Activity", activity_name)
	
	# Create new activity
	new_activity = frappe.copy_doc(original)
	new_activity.subject = f"{original.subject} (Copy)"
	new_activity.status = "Open"
	new_activity.progress_percent = 0
	new_activity.due_date = None
	
	new_activity.insert()
	return new_activity.name
