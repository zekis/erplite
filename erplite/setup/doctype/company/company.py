# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url, now_datetime

class Company(Document):
    def validate(self):
        """Validate company"""
        self.validate_currency()
        
        if not self.abbr and self.name:
            self.abbr = ''.join([c[0].upper() for c in self.name.split()]) or self.name[0].upper()
    
    def validate_currency(self):
        """Validate currency"""
        if not self.default_currency:
            self.default_currency = frappe.db.get_default("currency")
    
    def on_update(self):
        """Actions after company update"""
        pass
    
    def connect_to_xero(self):
        """Connect company to Xero"""
        from erplite.xero.accounts import sync_organization
        
        try:
            # Sync organization details
            org_id = sync_organization(self)
            
            if org_id:
                self.xero_organization_id = org_id
                self.xero_last_sync = now_datetime()
                self.save()
                
                frappe.msgprint(_("Successfully connected to Xero"))
                return True
            
            frappe.throw(_("Failed to connect to Xero"))
        except Exception as e:
            frappe.log_error("Company", f"Xero connection error: {str(e)}")
            frappe.throw(_("Failed to connect to Xero: {0}").format(str(e)))
    
    def sync_with_xero(self):
        """Sync company data with Xero"""
        from erplite.xero.accounts import sync_accounts, sync_invoices
        
        try:
            # Create sync log
            sync_log = frappe.get_doc({
                "doctype": "Xero Sync Log",
                "company": self.name,
                "start_time": now_datetime(),
                "status": "In Progress"
            })
            sync_log.insert()
            frappe.db.commit()
            
            # Sync accounts
            accounts_count = sync_accounts()
            sync_log.accounts_synced = accounts_count
            
            # Sync invoices
            invoices_count = sync_invoices()
            sync_log.invoices_synced = invoices_count
            
            # Update sync log
            sync_log.end_time = now_datetime()
            sync_log.status = "Success"
            sync_log.save()
            
            # Update company's last sync time
            self.xero_last_sync = now_datetime()
            self.save()
            
            frappe.db.commit()
            
            frappe.msgprint(_("Successfully synced with Xero"))
            return True
        except Exception as e:
            if sync_log:
                sync_log.end_time = now_datetime()
                sync_log.status = "Failed"
                sync_log.error = str(e)
                sync_log.save()
                frappe.db.commit()
            
            frappe.log_error("Company", f"Xero sync error: {str(e)}")
            frappe.throw(_("Failed to sync with Xero: {0}").format(str(e)))
