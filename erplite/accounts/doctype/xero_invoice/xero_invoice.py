# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class XeroInvoice(Document):
    def validate(self):
        """Validate Xero invoice"""
        self.validate_invoice_number()
        
        if not self.last_sync_date:
            self.last_sync_date = now_datetime()
    
    def validate_invoice_number(self):
        """Validate invoice number is unique within company"""
        if self.company and self.invoice_number:
            existing = frappe.db.get_value(
                "Xero Invoice",
                {
                    "invoice_number": self.invoice_number,
                    "company": self.company,
                    "name": ("!=", self.name)
                },
                "name"
            )
            
            if existing:
                frappe.throw(f"Invoice Number {self.invoice_number} already exists for company {self.company}")
    
    def on_update(self):
        """Actions after invoice update"""
        self.update_erp_invoice()
    
    def update_erp_invoice(self):
        """Update or create corresponding ERPLite invoice"""
        # This method will be implemented in future to map Xero invoices to ERPLite invoices
        pass
    
    def get_items(self):
        """Get invoice items from Xero"""
        from erplite.xero.client import XeroClient
        
        client = XeroClient()
        response = client.get(f"Invoices/{self.xero_invoice_id}")
        
        if "Invoices" in response and len(response["Invoices"]) > 0:
            invoice_data = response["Invoices"][0]
            return invoice_data.get("LineItems", [])
        
        return []
