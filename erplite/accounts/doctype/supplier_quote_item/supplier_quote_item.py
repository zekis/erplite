# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class SupplierQuoteItem(Document):
	def validate(self):
		self.calculate_amount()
	
	def calculate_amount(self):
		"""Calculate amount based on quantity and rate"""
		if self.qty and self.rate:
			self.amount = self.qty * self.rate
		else:
			self.amount = 0
