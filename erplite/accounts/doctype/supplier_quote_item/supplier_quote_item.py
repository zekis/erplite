# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

from frappe.model.document import Document

# No document hooks here. Frappe never runs a child DocType's controller
# methods: Document._validate() calls only its own _validate_* helpers on
# get_all_children(), and run_method("validate") is called on the parent
# (frappe/model/document.py). A validate() on this class looked like it was
# computing the line amount, and never ran.
# Supplier Quote.calculate_totals() derives amount from qty and rate.


class SupplierQuoteItem(Document):
	pass
