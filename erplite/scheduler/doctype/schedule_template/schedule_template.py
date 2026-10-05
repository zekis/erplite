# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import time_diff_in_hours

class ScheduleTemplate(Document):
	def validate(self):
		self.validate_template_code()
		self.validate_time_configuration()
		self.set_default_color()
		self.validate_sort_order()
	
	def validate_template_code(self):
		"""Validate template code format"""
		if self.template_code:
			# Convert to lowercase for consistency
			self.template_code = self.template_code.lower()
			
			# Check for duplicates
			existing = frappe.db.get_value("Schedule Template", 
				{"template_code": self.template_code, "name": ["!=", self.name]}, 
				"name"
			)
			if existing:
				frappe.throw(f"Template Code '{self.template_code}' already exists")
	
	def validate_time_configuration(self):
		"""Validate time configuration"""
		if self.hours and self.hours < 0:
			frappe.throw("Hours cannot be negative")
		
		if self.hours and self.hours > 24:
			frappe.throw("Hours cannot exceed 24")
		
		# Validate time range if both start and end times are provided
		if self.start_time and self.end_time:
			# Calculate hours between start and end time
			calculated_hours = time_diff_in_hours(self.end_time, self.start_time)
			
			# Allow some tolerance for rounding
			if abs(calculated_hours - self.hours) > 0.5:
				frappe.msgprint(
					f"Note: Time range ({self.start_time} to {self.end_time}) "
					f"suggests {calculated_hours:.1f} hours, but template is set to {self.hours} hours"
				)
	
	def set_default_color(self):
		"""Set default color based on status"""
		if not self.color:
			status_colors = {
				"planned": "#3b82f6",    # Blue
				"leave": "#f59e0b",      # Yellow
				"overtime": "#ef4444",   # Red
				"sick": "#ec4899",       # Pink
				"training": "#10b981"    # Green
			}
			
			self.color = status_colors.get(self.status, "#6b7280")  # Default gray
	
	def validate_sort_order(self):
		"""Validate sort order"""
		if self.sort_order and self.sort_order < 0:
			frappe.throw("Sort order cannot be negative")
	
	def before_save(self):
		"""Actions before saving"""
		if self.is_active is None:
			self.is_active = 1
		
		if not self.sort_order:
			# Auto-assign sort order
			max_sort_order = frappe.db.sql(
				"SELECT COALESCE(MAX(sort_order), 0) FROM `tabSchedule Template`"
			)[0][0]
			self.sort_order = max_sort_order + 1
	
	def on_update(self):
		"""Actions after update"""
		# Clear cache for template data
		frappe.cache().delete_key("scheduler_templates")
	
	def on_trash(self):
		"""Actions before deletion"""
		# Check if template is used in schedule entries (if we track this)
		# For now, just allow deletion since templates are configuration
		pass
	
	def get_template_config(self):
		"""Get template configuration for frontend"""
		return {
			"name": self.template_name,
			"code": self.template_code,
			"hours": self.hours,
			"start_time": str(self.start_time) if self.start_time else "09:00",
			"end_time": str(self.end_time) if self.end_time else "17:00",
			"description": self.description or "",
			"status": self.status,
			"color": self.color,
			"sort_order": self.sort_order
		}

@frappe.whitelist()
def get_active_templates():
	"""Get all active schedule templates"""
	templates = frappe.get_list("Schedule Template",
		filters={"is_active": 1},
		fields=[
			"name", "template_name", "template_code", "hours", 
			"start_time", "end_time", "status", "color", 
			"description", "sort_order"
		],
		order_by="sort_order ASC, template_name ASC"
	)
	
	# Format for frontend use
	formatted_templates = []
	for template in templates:
		formatted_templates.append({
			"name": template.template_name,
			"code": template.template_code,
			"hours": template.hours,
			"start_time": str(template.start_time) if template.start_time else "09:00",
			"end_time": str(template.end_time) if template.end_time else "17:00",
			"description": template.description or "",
			"status": template.status,
			"color": template.color,
			"sort_order": template.sort_order
		})
	
	return formatted_templates

@frappe.whitelist()
def get_template_by_code(template_code):
	"""Get template configuration by code"""
	template = frappe.get_doc("Schedule Template", {"template_code": template_code})
	if template and template.is_active:
		return template.get_template_config()
	return None

@frappe.whitelist()
def create_default_templates():
	"""Create default schedule templates"""
	default_templates = [
		{
			"template_name": "8 Hour Shift",
			"template_code": "8h",
			"hours": 8.0,
			"start_time": "09:00:00",
			"end_time": "17:00:00",
			"status": "planned",
			"description": "Standard 8-hour work day",
			"sort_order": 1
		},
		{
			"template_name": "12 Hour Shift",
			"template_code": "12h",
			"hours": 12.0,
			"start_time": "07:00:00",
			"end_time": "19:00:00",
			"status": "planned",
			"description": "Extended 12-hour shift",
			"sort_order": 2
		},
		{
			"template_name": "Leave",
			"template_code": "leave",
			"hours": 8.0,
			"start_time": "00:00:00",
			"end_time": "23:59:00",
			"status": "leave",
			"description": "Time off / Leave",
			"sort_order": 3
		},
		{
			"template_name": "Half Day",
			"template_code": "4h",
			"hours": 4.0,
			"start_time": "09:00:00",
			"end_time": "13:00:00",
			"status": "planned",
			"description": "Half day shift",
			"sort_order": 4
		}
	]
	
	created_count = 0
	for template_data in default_templates:
		# Check if template already exists
		existing = frappe.db.exists("Schedule Template", {"template_code": template_data["template_code"]})
		if not existing:
			template = frappe.new_doc("Schedule Template")
			template.update(template_data)
			template.insert()
			created_count += 1
	
	return f"Created {created_count} default templates"
