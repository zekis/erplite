# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Activity(Document):
	def validate(self):
		# Basic validation for existing fields only
		pass

@frappe.whitelist()
def get_project_activities(project):
	"""Get all activities for a project"""
	activities = frappe.get_all("Activity",
		filters={"project": project},
		fields=["name", "activity_name", "status", "work_type", "estimate", "description"],
		order_by="creation desc"
	)
	return activities

@frappe.whitelist()
def get_activity_summary(project=None):
	"""Get activity summary statistics"""
	filters = {"docstatus": ["<", 2]}
	if project:
		filters["project"] = project

	# Count activities by status. The project name travels as a value, never as SQL
	# text: interpolating it into the query string broke on any name containing an
	# apostrophe, and let a caller append SQL of their own.
	status_counts = frappe.get_all(
		"Activity",
		filters=filters,
		fields=["status", "count(*) as count"],
		group_by="status",
	)
	
	return {
		"status_counts": status_counts
	}

@frappe.whitelist()
def duplicate_activity(activity_name):
	"""Duplicate an activity"""
	original = frappe.get_doc("Activity", activity_name)
	
	# Create new activity
	new_activity = frappe.copy_doc(original)
	new_activity.activity_name = f"{original.activity_name} (Copy)"
	new_activity.status = "Open"
	
	new_activity.insert()
	return new_activity.name
