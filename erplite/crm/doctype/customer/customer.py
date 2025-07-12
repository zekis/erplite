# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from erplite.xero.accounts import create_customer, get_customers_from_xero, import_customer_from_xero

class Customer(Document):
    def validate(self):
        """Validate customer"""
        self.set_full_name()
    
    def set_full_name(self):
        """Set full name from first and last name"""
        if self.first_name and self.last_name and not self.customer_name:
            self.customer_name = f"{self.first_name} {self.last_name}"

@frappe.whitelist()
def send_to_xero(docname):
    """Send customer to Xero"""
    try:
        # Get customer
        customer = frappe.get_doc("Customer", docname)
        
        # Check if already sent to Xero
        if customer.xero_contact_id:
            frappe.throw(_("This customer has already been sent to Xero"))
        
        # Send to Xero
        xero_contact_id = create_customer(customer)
        
        if xero_contact_id:
            # Update customer with Xero details
            customer.xero_contact_id = xero_contact_id
            customer.xero_sync_date = now_datetime()
            customer.save()
            
            frappe.db.commit()
            return True
        
        frappe.throw(_("Failed to send customer to Xero"))
    except Exception as e:
        frappe.log_error("Customer", f"Error sending customer to Xero: {str(e)}")
        frappe.throw(_("Failed to send customer to Xero: {0}").format(str(e)))

@frappe.whitelist()
def get_xero_customers():
    """Get customers from Xero"""
    try:
        return get_customers_from_xero()
    except Exception as e:
        frappe.log_error("Customer", f"Error getting customers from Xero: {str(e)}")
        frappe.throw(_("Failed to get customers from Xero: {0}").format(str(e)))

@frappe.whitelist()
def import_from_xero(xero_contact_id):
    """Import customer from Xero"""
    try:
        return import_customer_from_xero(xero_contact_id)
    except Exception as e:
        frappe.log_error("Customer", f"Error importing customer from Xero: {str(e)}")
        frappe.throw(_("Failed to import customer from Xero: {0}").format(str(e)))
