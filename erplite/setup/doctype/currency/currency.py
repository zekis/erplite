# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

class Currency(Document):
    def validate(self):
        """Validate currency"""
        self.validate_base_currency()
        
        if not self.last_update:
            self.last_update = now_datetime()
    
    def validate_base_currency(self):
        """Validate base currency"""
        if self.is_base_currency:
            # Unset other base currencies
            frappe.db.sql("""
                UPDATE `tabCurrency` SET is_base_currency = 0
                WHERE is_base_currency = 1 AND name != %s
            """, (self.name))
            
            # Base currency should have exchange rate 1
            self.exchange_rate = 1
    
    def on_update(self):
        """Actions after currency update"""
        # Check if this is the only currency and set as base
        if not frappe.db.get_value("Currency", {"is_base_currency": 1}):
            self.db_set("is_base_currency", 1)
            self.db_set("exchange_rate", 1)
    
    @staticmethod
    def get_base_currency():
        """Get base currency"""
        base_currency = frappe.db.get_value("Currency", {"is_base_currency": 1})
        
        if not base_currency:
            # Get the first currency
            currencies = frappe.get_all(
                "Currency",
                filters={"enabled": 1},
                fields=["name"],
                order_by="creation asc",
                limit=1
            )
            
            if currencies:
                base_currency = currencies[0].name
                
                # Set as base currency
                frappe.db.set_value("Currency", base_currency, "is_base_currency", 1)
                frappe.db.set_value("Currency", base_currency, "exchange_rate", 1)
        
        return base_currency
    
    @staticmethod
    def get_exchange_rate(from_currency, to_currency):
        """Get exchange rate between currencies"""
        if from_currency == to_currency:
            return 1
        
        from_rate = frappe.db.get_value("Currency", from_currency, "exchange_rate") or 1
        to_rate = frappe.db.get_value("Currency", to_currency, "exchange_rate") or 1
        
        return to_rate / from_rate
