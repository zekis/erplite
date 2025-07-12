# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class ChartofAccounts(Document):
    def validate(self):
        """Validate chart of accounts"""
        self.validate_root_accounts()
        self.validate_default()
    
    def validate_root_accounts(self):
        """Validate root accounts"""
        # Check if all required root types are present
        required_root_types = ["Asset", "Liability", "Equity", "Income", "Expense"]
        root_types = [d.root_type for d in self.root_accounts]
        
        for root_type in required_root_types:
            if root_type not in root_types:
                frappe.throw(_("Root type {0} is required").format(root_type))
    
    def validate_default(self):
        """Validate default chart of accounts"""
        if self.is_active and self.company:
            # Check if another chart is active for the same company
            existing = frappe.db.get_value(
                "Chart of Accounts",
                {
                    "company": self.company,
                    "is_active": 1,
                    "name": ("!=", self.name)
                },
                "name"
            )
            
            if existing:
                frappe.throw(_("Another Chart of Accounts is already active for company {0}").format(self.company))
    
    def on_update(self):
        """Actions after chart of accounts update"""
        pass
    
    @staticmethod
    def get_default_chart(company=None):
        """Get default chart of accounts for a company"""
        if company:
            chart = frappe.db.get_value(
                "Chart of Accounts",
                {
                    "company": company,
                    "is_active": 1
                },
                "name"
            )
            
            if chart:
                return chart
        
        # Get standard chart
        standard_chart = frappe.db.get_value(
            "Chart of Accounts",
            {
                "is_standard": 1,
                "is_active": 1
            },
            "name"
        )
        
        return standard_chart
