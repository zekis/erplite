# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

class SalesInvoice(Document):
    def validate(self):
        """Validate sales invoice"""
        self.set_customer_name()
        self.set_default_company()
        self.calculate_totals()
    
    def set_customer_name(self):
        """Set customer name from customer"""
        if self.customer and not self.customer_name:
            self.customer_name = frappe.db.get_value("Customer", self.customer, "customer_name")
    
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
    """Send sales invoice to Xero"""
    from erplite.xero.accounts import create_sales_invoice
    
    try:
        # Get sales invoice
        sales_invoice = frappe.get_doc("Sales Invoice", docname)
        
        # Check if already sent to Xero
        if sales_invoice.xero_invoice_id:
            frappe.throw(_("This invoice has already been sent to Xero"))
        
        # Send to Xero
        xero_invoice_id = create_sales_invoice(sales_invoice)
        
        if xero_invoice_id:
            # The invoice is already updated in the database by create_sales_invoice
            # No need to save the document again, just commit the transaction
            frappe.db.commit()
            return True
        
        frappe.throw(_("Failed to send invoice to Xero"))
    except frappe.ValidationError as e:
        # Everything on this path that calls frappe.throw has already written a
        # message for the user, and some of them are deliberate stops rather than
        # failures -- "already sent to Xero", or "Xero already has this invoice".
        # Re-labelling a stop as "Failed to send" is exactly what makes someone
        # retry a send that must not be retried, so the message goes through
        # unchanged. It is still logged: the Error Log is where a send whose
        # outcome is unknown gets traced from.
        frappe.log_error("Sales Invoice", f"Send to Xero stopped: {str(e)}")
        raise
    except Exception as e:
        frappe.log_error("Sales Invoice", f"Error sending sales invoice to Xero: {str(e)}")
        frappe.throw(_("Failed to send invoice to Xero: {0}").format(str(e)))
