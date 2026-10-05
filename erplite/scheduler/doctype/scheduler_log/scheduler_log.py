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
	"""Clear scheduler logs older than `days` days, and report how many went.

	`days` comes from the caller and is checked rather than coerced. This
	function carries no type annotations, so frappe's argument validation does
	nothing with it (`frappe/utils/typing_validations.py`
	`transform_parameter_types` returns early when `__annotations__` is empty),
	and over a JSON request body the value arrives as a real int rather than a
	string (`frappe/app.py` `make_form_dict` runs `json.loads`). A negative
	`days` would put the cutoff in the future and so delete every row, which is
	not what any caller can mean by "older than", so it is refused.

	Non-numeric is refused too, rather than passed through `cint()`: `cint()`
	turns anything it cannot read into 0, and 0 here means "delete everything
	before today", which is the worst available reading of a typo.
	"""

	try:
		days = int(days)
	except (TypeError, ValueError):
		frappe.throw(frappe._("days must be a whole number"))

	if days < 0:
		frappe.throw(frappe._("days must be zero or more"))

	cutoff_date = frappe.utils.add_days(frappe.utils.today(), -days)

	# Count before deleting. A DELETE cannot report its own row count here:
	# `frappe.db.sql` returns `()` whenever the cursor has no description
	# (`frappe/database/database.py`, `if not self._cursor.description`), which
	# is the case for a DELETE. Reading `[0][0]` off that result is why this
	# endpoint used to tell the caller it had cleared 0 entries however many it
	# had actually removed.
	rows = frappe.db.sql("""
		SELECT COUNT(*) FROM `tabScheduler Log`
		WHERE DATE(timestamp) < %s
	""", (cutoff_date,))
	deleted_count = rows[0][0] if rows else 0

	frappe.db.sql("""
		DELETE FROM `tabScheduler Log`
		WHERE DATE(timestamp) < %s
	""", (cutoff_date,))

	frappe.db.commit()

	return {
		"deleted_count": deleted_count
	}
