# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from erplite.xero.accounts import create_supplier, get_suppliers_from_xero, import_supplier_from_xero

class Supplier(Document):
    def validate(self):
        """Validate supplier"""
        self.set_full_name()
    
    def set_full_name(self):
        """Set full name from supplier name"""
        if self.supplier_name:
            self.full_name = self.supplier_name

@frappe.whitelist()
def send_to_xero(docname):
    """Send supplier to Xero"""
    try:
        # Get supplier
        supplier = frappe.get_doc("Supplier", docname)
        
        # Check if already sent to Xero
        if supplier.xero_contact_id:
            frappe.throw(_("This supplier has already been sent to Xero"))
        
        # Send to Xero
        xero_contact_id = create_supplier(supplier)
        
        if xero_contact_id:
            # Update supplier with Xero details
            supplier.xero_contact_id = xero_contact_id
            supplier.xero_sync_date = now_datetime()
            supplier.save()
            
            frappe.db.commit()
            return True
        
        frappe.throw(_("Failed to send supplier to Xero"))
    except Exception as e:
        frappe.log_error("Supplier", f"Error sending supplier to Xero: {str(e)}")
        frappe.throw(_("Failed to send supplier to Xero: {0}").format(str(e)))

@frappe.whitelist()
def get_xero_suppliers():
    """Get suppliers from Xero"""
    try:
        return get_suppliers_from_xero()
    except Exception as e:
        frappe.log_error("Supplier", f"Error getting suppliers from Xero: {str(e)}")
        frappe.throw(_("Failed to get suppliers from Xero: {0}").format(str(e)))

@frappe.whitelist()
def import_from_xero(xero_contact_id):
    """Import supplier from Xero"""
    try:
        return import_supplier_from_xero(xero_contact_id)
    except Exception as e:
        frappe.log_error("Supplier", f"Error importing supplier from Xero: {str(e)}")
        frappe.throw(_("Failed to import supplier from Xero: {0}").format(str(e)))
