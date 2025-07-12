# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class FinanceBook(Document):
    def validate(self):
        """Validate finance book"""
        self.validate_defaults()
    
    def validate_defaults(self):
        """Validate default finance book"""
        if self.is_default:
            # Unset other defaults
            frappe.db.sql("""
                UPDATE `tabFinance Book` SET is_default = 0
                WHERE is_default = 1 AND name != %s
            """, (self.name))
    
    def on_update(self):
        """Actions after finance book update"""
        # Check if this is the only finance book and set as default
        if not frappe.db.get_value("Finance Book", {"is_default": 1}):
            self.db_set("is_default", 1)
    
    @staticmethod
    def get_default_finance_book(company=None):
        """Get default finance book"""
        if company:
            default_finance_book = frappe.get_value("Company", company, "default_finance_book")
            if default_finance_book:
                return default_finance_book
        
        # Get the default finance book
        default_finance_book = frappe.db.get_value("Finance Book", {"is_default": 1})
        
        if not default_finance_book:
            # Get the first finance book
            finance_books = frappe.get_all(
                "Finance Book",
                fields=["name"],
                order_by="creation asc",
                limit=1
            )
            
            if finance_books:
                default_finance_book = finance_books[0].name
        
        return default_finance_book
