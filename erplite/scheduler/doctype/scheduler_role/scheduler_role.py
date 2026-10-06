# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class SchedulerRole(Document):
	def validate(self):
		self.validate_role_code()
		self.set_default_color()
		self.validate_hourly_rate()
	
	def validate_role_code(self):
		"""Validate role code format"""
		if self.role_code:
			# Convert to uppercase
			self.role_code = self.role_code.upper()
			
			# Check for duplicates
			existing = frappe.db.get_value("Scheduler Role", 
				{"role_code": self.role_code, "name": ["!=", self.name]}, 
				"name"
			)
			if existing:
				frappe.throw(f"Role Code '{self.role_code}' already exists")
	
	def set_default_color(self):
		"""Set default color if not provided"""
		if not self.color:
			# Default colors for roles
			default_colors = [
				"#10b981",  # Green
				"#3b82f6",  # Blue
				"#f59e0b",  # Yellow
				"#ef4444",  # Red
				"#8b5cf6",  # Purple
				"#06b6d4",  # Cyan
				"#84cc16",  # Lime
				"#f97316",  # Orange
				"#ec4899",  # Pink
				"#6b7280"   # Gray
			]
			
			# Get existing role count to cycle through colors
			existing_count = frappe.db.count("Scheduler Role")
			color_index = existing_count % len(default_colors)
			self.color = default_colors[color_index]
	
	def validate_hourly_rate(self):
		"""Validate hourly rate"""
		if self.hourly_rate and self.hourly_rate < 0:
			frappe.throw("Hourly rate cannot be negative")
	
	def before_save(self):
		"""Actions before saving"""
		if self.is_active is None:
			self.is_active = 1
	
	def on_update(self):
		"""Actions after update"""
		# Clear cache for role data
		frappe.cache().delete_key("scheduler_roles")
	
	def on_trash(self):
		"""Actions before deletion"""
		# Check if role is used in schedule rows
		schedule_rows_using_role = frappe.get_all("Schedule Row", 
			filters={"role": self.name},
			fields=["name"]
		)
		
		if schedule_rows_using_role:
			frappe.throw(f"Cannot delete role. It is used in {len(schedule_rows_using_role)} schedule entries")

@frappe.whitelist()
def get_active_roles():
	"""Get all active roles"""
	roles = frappe.get_list("Scheduler Role",
		filters={"is_active": 1},
		fields=["name", "role_name", "role_code", "color", "hourly_rate", "description"],
		order_by="role_name"
	)
	return roles

@frappe.whitelist()
def get_role_resources(role):
	"""Get resources for a specific role"""
	resource_roles = frappe.get_all("Resource Role",
		filters={"role": role},
		fields=["parent"]
	)
	
	if not resource_roles:
		return []
	
	resource_names = [rr.parent for rr in resource_roles]
	
	resources = frappe.get_all("Resource",
		filters={"name": ["in", resource_names], "status": "Active"},
		fields=["name", "resource_name", "resource_type", "capacity"],
		order_by="resource_name"
	)
	return resources

@frappe.whitelist()
def get_role_statistics(role):
	"""Get statistics for a specific role"""
	# Get resource count
	resource_count = frappe.db.count("Resource Role", {"role": role})
	
	# Get active schedule entries count
	schedule_count = frappe.db.count("Schedule Row", {"role": role})
	
	# Get average hourly rate (if multiple resources have different rates)
	role_doc = frappe.get_doc("Scheduler Role", role)
	
	return {
		"resource_count": resource_count,
		"schedule_count": schedule_count,
		"default_hourly_rate": role_doc.hourly_rate or 0,
		"role_name": role_doc.role_name,
		"role_code": role_doc.role_code
	}
