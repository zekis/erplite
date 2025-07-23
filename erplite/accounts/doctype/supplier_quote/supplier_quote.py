# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate

class SupplierQuote(Document):
	def validate(self):
		self.set_supplier_name()
		self.calculate_totals()
		self.set_created_by()
		self.validate_dates()
	
	def set_supplier_name(self):
		"""Set supplier name from supplier link"""
		if self.supplier:
			supplier_doc = frappe.get_doc("Supplier", self.supplier)
			self.supplier_name = supplier_doc.supplier_name
	
	def calculate_totals(self):
		"""Calculate totals from items"""
		self.total = 0
		self.total_tax = 0
		
		for item in self.items:
			if item.amount:
				self.total += flt(item.amount)
		
		self.grand_total = self.total + self.total_tax
	
	def set_created_by(self):
		"""Set created by to current user"""
		if not self.created_by:
			self.created_by = frappe.session.user
	
	def validate_dates(self):
		"""Validate quote dates"""
		if self.valid_until and self.quote_date:
			if self.valid_until < self.quote_date:
				frappe.throw("Valid Until date cannot be before Quote Date")
	
	def before_save(self):
		"""Update status based on dates"""
		if self.valid_until and self.valid_until < nowdate() and self.status not in ["Accepted", "Rejected"]:
			self.status = "Expired"
	
	def on_update(self):
		"""Update related documents if needed"""
		pass
	
	def get_items_for_comparison(self):
		"""Get items formatted for quote comparison"""
		items = []
		for item in self.items:
			items.append({
				"item_name": item.item_name,
				"description": item.description,
				"qty": item.qty,
				"rate": item.rate,
				"amount": item.amount,
				"delivery_date": item.delivery_date,
				"lead_time_days": item.lead_time_days,
				"supplier_part_number": item.supplier_part_number,
				"brand": item.brand,
				"warranty_period": item.warranty_period
			})
		return items

@frappe.whitelist()
def get_supplier_quotes_for_comparison(item_name=None, project=None):
	"""Get supplier quotes for comparison"""
	filters = {"status": ["not in", ["Draft", "Rejected", "Expired"]]}
	
	if project:
		filters["project"] = project
	
	quotes = frappe.get_all("Supplier Quote", 
		filters=filters,
		fields=["name", "supplier", "supplier_name", "quote_date", "valid_until", "grand_total", "status"]
	)
	
	# If item_name is specified, filter quotes that contain this item
	if item_name:
		filtered_quotes = []
		for quote in quotes:
			quote_items = frappe.get_all("Supplier Quote Item",
				filters={"parent": quote.name, "item_name": ["like", f"%{item_name}%"]},
				fields=["item_name", "rate", "amount"]
			)
			if quote_items:
				quote["items"] = quote_items
				filtered_quotes.append(quote)
		return filtered_quotes
	
	return quotes

@frappe.whitelist()
def create_purchase_order_from_quote(quote_name):
	"""Create Purchase Order from Supplier Quote"""
	quote = frappe.get_doc("Supplier Quote", quote_name)
	
	# Create Purchase Order (this would need the Purchase Order doctype to exist)
	po_doc = frappe.new_doc("Purchase Order")
	po_doc.supplier = quote.supplier
	po_doc.supplier_name = quote.supplier_name
	po_doc.company = quote.company
	po_doc.currency = quote.currency
	po_doc.project = quote.project
	
	# Add items
	for item in quote.items:
		po_doc.append("items", {
			"item_name": item.item_name,
			"description": item.description,
			"qty": item.qty,
			"rate": item.rate,
			"amount": item.amount,
			"delivery_date": item.delivery_date
		})
	
	po_doc.save()
	
	# Update quote status
	quote.status = "Accepted"
	quote.save()
	
	return po_doc.name
