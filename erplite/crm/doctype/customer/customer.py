# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from erplite.xero.accounts import create_customer, get_customers_from_xero, import_customer_from_xero

class Customer(Document):
    def validate(self):
        """Validate customer"""
        self.set_full_name()
    
    def set_full_name(self):
        """Set full name from first and last name"""
        # Check if fields exist before accessing them (defensive programming)
        first_name = getattr(self, 'first_name', None)
        last_name = getattr(self, 'last_name', None)
        
        if first_name and last_name and not self.customer_name:
            self.customer_name = f"{first_name} {last_name}"

@frappe.whitelist()
def send_to_xero(docname):
    """Send customer to Xero"""
    # Whitelisted means any logged-in user can call this by name, so the Desk
    # button is not the gate -- and until this line there was no gate at all.
    # frappe.get_doc does no permission check
    # (frappe/__init__.py:1308; check_permission runs only from insert, save,
    # submit/cancel and delete), and the save() below -- which does check --
    # happens only AFTER the contact has been created in Xero. So a refused
    # user used to leave a real Xero contact behind with its id unstored,
    # which also defeated the xero_contact_id guard above and duplicated the
    # contact on the next attempt. Checking here sends nothing instead.
    #
    # This sits OUTSIDE the try on purpose. frappe.PermissionError is a plain
    # Exception (frappe/exceptions.py:34), not a ValidationError, so inside the
    # try the `except Exception` below would catch a refusal and re-raise it as
    # "Failed to send customer to Xero: {0}" -- turning a 403 refusal into a 417
    # validation failure and telling the user a send failed when nothing was
    # sent. That is the same mislabelling the comment in that handler warns
    # about.
    frappe.has_permission("Customer", "write", doc=docname, throw=True)

    try:
        # Get customer
        customer = frappe.get_doc("Customer", docname)
        
        # Check if already sent to Xero
        if customer.xero_contact_id:
            frappe.throw(_("This customer has already been sent to Xero"))
        
        # Send to Xero
        xero_contact_id = create_customer(customer)
        
        if xero_contact_id:
            # The customer is already updated in the database by create_customer
            # (erplite/xero/accounts.py:511 sets xero_contact_id and
            # xero_sync_date with frappe.db.set_value before returning the id).
            # No need to save the document again, just commit the transaction.
            #
            # Saving it again is not merely redundant, it cannot succeed, and
            # that is the bug this removes. `customer` was loaded BEFORE that
            # set_value; set_value updates `modified` by default
            # (frappe/database/database.py:926-948), so frappe's own
            # check_if_latest (model/document.py:372, body at 807-832) compares
            # the row's new `modified` against the stale `_original_modified`
            # the document was read with (:556), finds them different and
            # raises TimestampMismatchError. That is a ValidationError
            # (frappe/exceptions.py:152), so the `except Exception` below
            # caught it, re-labelled it "Failed to send customer to Xero" and
            # rolled the request back -- discarding the recorded id while the
            # contact stayed in Xero. The `if customer.xero_contact_id` guard
            # above then saw nothing, and the next attempt created a SECOND
            # contact.
            #
            # sales_invoice.py already does this for the invoice path.
            
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
    # Same gate as send_to_xero, with "create" rather than "write" because this
    # endpoint inserts a new Customer: that is the permission the operation
    # actually needs. On Customer every role granted write is also granted
    # create (System Manager, Accounts Manager, Accounts User), so this refuses
    # and permits exactly the same people -- it is the precise spelling of the
    # owner's rule, not a different rule. Outside the try for the reason given
    # in send_to_xero.
    frappe.has_permission("Customer", "create", throw=True)

    try:
        return import_customer_from_xero(xero_contact_id)
    except Exception as e:
        frappe.log_error("Customer", f"Error importing customer from Xero: {str(e)}")
        frappe.throw(_("Failed to import customer from Xero: {0}").format(str(e)))
