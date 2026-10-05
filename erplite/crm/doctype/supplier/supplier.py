# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
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
    # "Failed to send supplier to Xero: {0}" -- turning a 403 refusal into a 417
    # validation failure and telling the user a send failed when nothing was
    # sent. That is the same mislabelling the comment in that handler warns
    # about.
    frappe.has_permission("Supplier", "write", doc=docname, throw=True)

    try:
        # Get supplier
        supplier = frappe.get_doc("Supplier", docname)
        
        # Check if already sent to Xero
        if supplier.xero_contact_id:
            frappe.throw(_("This supplier has already been sent to Xero"))
        
        # Send to Xero
        xero_contact_id = create_supplier(supplier)
        
        if xero_contact_id:
            # The supplier is already updated in the database by create_supplier
            # (erplite/xero/accounts.py:591 sets xero_contact_id and
            # xero_sync_date with frappe.db.set_value before returning the id).
            # No need to save the document again, just commit the transaction.
            #
            # Saving it again is not merely redundant, it cannot succeed, and
            # that is the bug this removes. `supplier` was loaded BEFORE that
            # set_value; set_value updates `modified` by default
            # (frappe/database/database.py:926-948), so frappe's own
            # check_if_latest (model/document.py:372, body at 807-832) compares
            # the row's new `modified` against the stale `_original_modified`
            # the document was read with (:556), finds them different and
            # raises TimestampMismatchError. That is a ValidationError
            # (frappe/exceptions.py:152), so the `except Exception` below
            # caught it, re-labelled it "Failed to send supplier to Xero" and
            # rolled the request back -- discarding the recorded id while the
            # contact stayed in Xero. The `if supplier.xero_contact_id` guard
            # above then saw nothing, and the next attempt created a SECOND
            # contact.
            #
            # sales_invoice.py already does this for the invoice path.
            
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
    # Same gate as send_to_xero, with "create" rather than "write" because this
    # endpoint inserts a new Supplier: that is the permission the operation
    # actually needs. On Supplier every role granted write is also granted
    # create (System Manager, Accounts Manager, Accounts User), so this refuses
    # and permits exactly the same people -- it is the precise spelling of the
    # owner's rule, not a different rule. Outside the try for the reason given
    # in send_to_xero.
    frappe.has_permission("Supplier", "create", throw=True)

    try:
        return import_supplier_from_xero(xero_contact_id)
    except Exception as e:
        frappe.log_error("Supplier", f"Error importing supplier from Xero: {str(e)}")
        frappe.throw(_("Failed to import supplier from Xero: {0}").format(str(e)))
