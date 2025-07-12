# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class XeroAccount(Document):
    def validate(self):
        """Validate Xero account"""
        self.validate_account_code()
    
    def validate_account_code(self):
        """Validate account code is unique within company"""
        if self.company and self.account_code:
            existing = frappe.db.get_value(
                "Xero Account",
                {
                    "account_code": self.account_code,
                    "company": self.company,
                    "name": ("!=", self.name)
                },
                "name"
            )
            
            if existing:
                frappe.throw(f"Account Code {self.account_code} already exists for company {self.company}")
    
    def on_update(self):
        """Actions after account update"""
        self.update_erplite_account()
    
    def update_erplite_account(self):
        """Update or create corresponding ERPLite account"""
        # This method will be implemented in future to map Xero accounts to ERPLite accounts
        pass
