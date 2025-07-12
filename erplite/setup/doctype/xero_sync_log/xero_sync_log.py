# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class XeroSyncLog(Document):
    def validate(self):
        """Validate sync log"""
        if not self.user:
            self.user = frappe.session.user
        
        if not self.start_time:
            self.start_time = now_datetime()
    
    def on_update(self):
        """Update company's last sync time"""
        if self.status == "Success" and self.company:
            frappe.db.set_value("Company", self.company, "xero_last_sync", self.end_time)
    
    @staticmethod
    def clear_old_logs(days=30):
        """Clear old sync logs"""
        from frappe.utils import add_days
        
        date_limit = add_days(now_datetime(), -days)
        
        # Find old logs
        old_logs = frappe.get_all(
            "Xero Sync Log",
            filters={"creation": ["<", date_limit]},
            fields=["name"]
        )
        
        # Delete old logs
        for log in old_logs:
            frappe.delete_doc("Xero Sync Log", log.name)
        
        return len(old_logs)
