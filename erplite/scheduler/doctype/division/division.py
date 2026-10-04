# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Division(Document):
	def validate(self):
		self.validate_division_code()
		self.set_default_color()
	
	def validate_division_code(self):
		"""Validate division code format"""
		if self.division_code:
			# Convert to uppercase
			self.division_code = self.division_code.upper()
			
			# Check for duplicates
			existing = frappe.db.get_value("Division", 
				{"division_code": self.division_code, "name": ["!=", self.name]}, 
				"name"
			)
			if existing:
				frappe.throw(f"Division Code '{self.division_code}' already exists")
	
	def set_default_color(self):
		"""Set default color if not provided"""
		if not self.color:
			# Default colors for divisions
			default_colors = [
				"#3b82f6",  # Blue
				"#10b981",  # Green
				"#f59e0b",  # Yellow
				"#ef4444",  # Red
				"#8b5cf6",  # Purple
				"#06b6d4",  # Cyan
				"#84cc16",  # Lime
				"#f97316"   # Orange
			]
			
			# Get existing division count to cycle through colors
			existing_count = frappe.db.count("Division")
			color_index = existing_count % len(default_colors)
			self.color = default_colors[color_index]
	
	def before_save(self):
		"""Actions before saving"""
		if self.is_active is None:
			self.is_active = 1
	
	def on_update(self):
		"""Actions after update"""
		# Clear cache for division data
		frappe.cache().delete_key("scheduler_divisions")
	
	def on_trash(self):
		"""Actions before deletion"""
		# Check if division is used in projects
		projects_using_division = frappe.get_all("Project", 
			filters={"division": self.name},
			fields=["name", "project_name"]
		)
		
		if projects_using_division:
			project_names = [p.project_name for p in projects_using_division]
			frappe.throw(f"Cannot delete division. It is used in projects: {', '.join(project_names)}")

@frappe.whitelist()
def get_active_divisions():
	"""Get all active divisions"""
	divisions = frappe.get_all("Division",
		filters={"is_active": 1},
		fields=["name", "division_name", "division_code", "color", "description"],
		order_by="division_name"
	)
	return divisions

@frappe.whitelist()
def get_division_projects(division):
	"""Get projects for a specific division"""
	projects = frappe.get_all("Project",
		filters={"division": division, "status": ["in", ["Open"]]},
		fields=["name", "project_name", "status"],
		order_by="project_name"
	)
	return projects
