# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class SalesInvoiceItem(Document):
    def validate(self):
        """Validate sales invoice item"""
        self.calculate_amount()
        self.calculate_tax_amount()
    
    def calculate_amount(self):
        """Calculate amount based on quantity and rate"""
        self.amount = self.qty * self.rate
    
    def calculate_tax_amount(self):
        """Calculate tax amount based on amount and tax rate"""
        if self.tax_rate:
            self.tax_amount = self.amount * (self.tax_rate / 100)
        else:
            self.tax_amount = 0
