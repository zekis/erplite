# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from erplite.xero.auth import get_access_token, get_tenants

class XeroSettings(Document):
    def validate(self):
        """Validate Xero settings"""
        # Ensure required fields are present
        if self.client_id and not self.client_secret:
            frappe.throw(_("Client Secret is required when Client ID is provided"))
        
        if self.client_secret and not self.client_id:
            frappe.throw(_("Client ID is required when Client Secret is provided"))
    
    def is_connected(self):
        """Check if connected to Xero"""
        return bool(self.access_token and self.tenant_id)
    
    @frappe.whitelist()
    def connect(self):
        """Connect to Xero using client credentials flow"""
        if not self.client_id or not self.client_secret:
            frappe.throw(_("Client ID and Client Secret are required"))
        
        try:
            # Get access token
            access_token = get_access_token()
            
            # Get tenants
            tenants = get_tenants()
            
            if not tenants:
                frappe.throw(_("No Xero organizations found for this app"))
            
            # If multiple tenants, let user choose
            if len(tenants) > 1:
                tenant_options = []
                for tenant in tenants:
                    tenant_options.append({
                        "tenant_id": tenant["tenantId"],
                        "tenant_name": tenant["tenantName"]
                    })
                
                frappe.msgprint(_("Multiple Xero organizations found. Please select one:"))
                return tenant_options
            
            # If only one tenant, use it
            # Reload the document to avoid timestamp mismatch error
            settings = frappe.get_doc("Xero Settings")
            settings.tenant_id = tenants[0]["tenantId"]
            settings.tenant_name = tenants[0]["tenantName"]
            settings.last_sync_date = now_datetime()
            settings.save()
            
            # Reload this document to reflect the changes
            self.reload()
            
            frappe.msgprint(_("Successfully connected to Xero!"))
            return True
        except Exception as e:
            # Just re-raise the exception without logging
            raise
    
    @frappe.whitelist()
    def set_tenant(self, tenant_id, tenant_name):
        """Set the Xero tenant to use"""
        self.tenant_id = tenant_id
        self.tenant_name = tenant_name
        self.last_sync_date = now_datetime()
        self.save()
        
        frappe.msgprint(_("Successfully set Xero organization to {0}").format(tenant_name))
        return True
    
    @frappe.whitelist()
    def disconnect(self):
        """Disconnect from Xero"""
        try:
            self.access_token = None
            self.token_expiry = None
            self.tenant_id = None
            self.tenant_name = None
            self.authorization_status = "Not Authorized"
            self.save()
            
            frappe.msgprint(_("Successfully disconnected from Xero"))
            return True
        except Exception as e:
            # Just re-raise the exception without logging
            raise
