# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime
from . import auth
from . import accounts

@frappe.whitelist()
def get_authorization_url():
    """Get the Xero authorization URL for OAuth2 flow"""
    try:
        return auth.get_authorization_url()
    except Exception as e:
        frappe.log_error("API", f"Error getting Xero authorization URL: {str(e)}")
        frappe.throw(_("Failed to generate Xero authorization URL. Please check the Xero settings."))

@frappe.whitelist()
def handle_callback(code=None, state=None, error=None):
    """Handle the OAuth2 callback from Xero"""
    if error:
        frappe.log_error("API", f"Xero OAuth Error: {error}")
        frappe.throw(_("Xero authorization failed: {0}").format(error))
    
    if not code:
        frappe.throw(_("No authorization code received from Xero"))
    
    # Verify state to prevent CSRF
    stored_state = frappe.cache().get_value("xero_oauth_state")
    if not stored_state or stored_state != state:
        frappe.throw(_("Invalid state parameter. Authorization request may have been tampered with."))
    
    # Exchange code for tokens
    if auth.get_tokens(code):
        frappe.msgprint(_("Successfully connected to Xero"))
        return True
    
    frappe.throw(_("Failed to connect to Xero. Please try again."))

@frappe.whitelist()
def get_connection_status():
    """Get the current Xero connection status"""
    settings = frappe.get_single("Xero Settings")
    
    # Get last sync time
    last_sync = frappe.db.get_value("Xero Sync Log", 
                                    filters={"status": "Success"},
                                    fieldname="creation",
                                    order_by="creation desc")
    
    return {
        "connected": settings.authorization_status == "Authorized",
        "last_sync": last_sync
    }

@frappe.whitelist()
def disconnect():
    """Disconnect from Xero"""
    settings = frappe.get_single("Xero Settings")
    
    settings.access_token = None
    settings.refresh_token = None
    settings.token_expiry = None
    settings.authorization_status = "Not Authorized"
    settings.save()
    
    frappe.db.commit()
    frappe.msgprint(_("Disconnected from Xero"))
    return True

@frappe.whitelist()
def sync_all():
    """Sync all data from Xero"""
    try:
        # Create sync log
        sync_log = frappe.get_doc({
            "doctype": "Xero Sync Log",
            "start_time": now_datetime(),
            "status": "In Progress"
        })
        sync_log.insert()
        frappe.db.commit()
        
        # Sync accounts
        accounts_count = accounts.sync_accounts()
        sync_log.accounts_synced = accounts_count
        
        # Sync invoices
        invoices_count = accounts.sync_invoices()
        sync_log.invoices_synced = invoices_count
        
        # Update sync log
        sync_log.end_time = now_datetime()
        sync_log.status = "Success"
        sync_log.save()
        
        frappe.db.commit()
        
        return {
            "success": True,
            "accounts": accounts_count,
            "invoices": invoices_count
        }
    except Exception as e:
        if sync_log:
            sync_log.end_time = now_datetime()
            sync_log.status = "Failed"
            sync_log.error = str(e)
            sync_log.save()
            frappe.db.commit()
        
        frappe.log_error("API",f"Xero sync error: {str(e)}")
        frappe.throw(_("Failed to sync data from Xero: {0}").format(str(e)))
