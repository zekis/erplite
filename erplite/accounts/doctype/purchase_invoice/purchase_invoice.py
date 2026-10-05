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
    
    # Whitelisted means any logged-in user can call this by name, so the Desk
    # button is not the gate -- and until this line there was no gate at all.
    # Nothing below checks either: frappe.get_doc does no permission
    # check (frappe/__init__.py:1308 delegates to model/document.py, where
    # check_permission is called only from insert, save, submit/cancel and
    # delete -- loading a document is not one of them), and the result is
    # recorded with frappe.db.set_value, which checks no permission and runs
    # no validate. So a Projects User -- no read and no write on
    # Purchase Invoice -- could push a real invoice into the real Xero ledger.
    #
    # This sits OUTSIDE the try on purpose. frappe.PermissionError is a plain
    # Exception (frappe/exceptions.py:34), not a ValidationError, so inside the
    # try the `except Exception` below would catch a refusal and re-raise it as
    # "Failed to send invoice to Xero: {0}" -- turning a 403 refusal into a 417
    # validation failure and telling the user a send failed when nothing was
    # sent. That is the same mislabelling the comment in that handler warns
    # about.
    frappe.has_permission("Purchase Invoice", "write", doc=docname, throw=True)

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
    except frappe.ValidationError as e:
        # Everything on this path that calls frappe.throw has already written a
        # message for the user, and some of them are deliberate stops rather than
        # failures -- "already sent to Xero", or "Xero already has this invoice".
        # Re-labelling a stop as "Failed to send" is exactly what makes someone
        # retry a send that must not be retried, so the message goes through
        # unchanged. It is still logged: the Error Log is where a send whose
        # outcome is unknown gets traced from.
        frappe.log_error("Purchase Invoice", f"Send to Xero stopped: {str(e)}")
        raise
    except Exception as e:
        frappe.log_error("Purchase Invoice", f"Error sending purchase invoice to Xero: {str(e)}")
        frappe.throw(_("Failed to send invoice to Xero: {0}").format(str(e)))
