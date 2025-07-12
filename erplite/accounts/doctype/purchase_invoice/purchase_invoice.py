# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

class PurchaseInvoice(Document):
    def validate(self):
        """Validate purchase invoice"""
        self.set_supplier_name()
        self.set_default_company()
        self.calculate_totals()
    
    def set_supplier_name(self):
        """Set supplier name from supplier"""
        if self.supplier and not self.supplier_name:
            self.supplier_name = frappe.db.get_value("Supplier", self.supplier, "supplier_name")
    
    @frappe.whitelist()
    def set_default_company(self):
        """Set default company if not specified"""
        if not self.company:
            # Get the first company that is set as default
            default_company = frappe.db.get_value("Company", {"is_default": 1}, "name")
            if default_company:
                self.company = default_company
            else:
                # If no default company, get the first company
                companies = frappe.get_all("Company", limit=1)
                if companies:
                    self.company = companies[0].name
    
    def calculate_totals(self):
        """Calculate invoice totals"""
        self.total = 0
        self.total_tax = 0
        
        for item in self.items:
            item.amount = item.qty * item.rate
            self.total += item.amount
            
            if item.tax_rate:
                item.tax_amount = item.amount * (item.tax_rate / 100)
                self.total_tax += item.tax_amount
        
        self.grand_total = self.total + self.total_tax
        self.rounded_total = round(self.grand_total)
    
    def on_submit(self):
        """Actions on submit"""
        # Update status
        self.status = "Submitted"
        
        if self.is_paid:
            self.status = "Paid"
    
    def on_cancel(self):
        """Actions on cancel"""
        self.status = "Cancelled"

@frappe.whitelist()
def send_to_xero(docname):
    """Send purchase invoice to Xero"""
    from erplite.xero.accounts import create_purchase_invoice
    
    try:
        # Get purchase invoice
        purchase_invoice = frappe.get_doc("Purchase Invoice", docname)
        
        # Check if already sent to Xero
        if purchase_invoice.xero_invoice_id:
            frappe.throw(_("This invoice has already been sent to Xero"))
        
        # Send to Xero
        xero_invoice_id = create_purchase_invoice(purchase_invoice)
        
        if xero_invoice_id:
            # Update status to Submitted when successfully sent to Xero
            frappe.db.set_value("Purchase Invoice", docname, "status", "Submitted")
            frappe.db.commit()
            return True
        
        frappe.throw(_("Failed to send invoice to Xero"))
    except Exception as e:
        frappe.log_error("Purchase Invoice", f"Error sending purchase invoice to Xero: {str(e)}")
        frappe.throw(_("Failed to send invoice to Xero: {0}").format(str(e)))
