# -*- coding: utf-8 -*-
# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class SchedulerLog(Document):
	def before_insert(self):
		# Set timestamp if not provided
		if not self.timestamp:
			self.timestamp = frappe.utils.now()

@frappe.whitelist()
def clear_old_logs(days=30):
	"""Clear scheduler logs older than specified days"""
	
	cutoff_date = frappe.utils.add_days(frappe.utils.today(), -days)
	
	# Delete old logs
	deleted_count = frappe.db.sql("""
		DELETE FROM `tabScheduler Log`
		WHERE DATE(timestamp) < %s
	""", (cutoff_date,))
	
	frappe.db.commit()
	
	return {
		"deleted_count": deleted_count[0][0] if deleted_count else 0
	}
