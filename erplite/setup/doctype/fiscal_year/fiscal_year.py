# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, add_days, add_years, cstr

class FiscalYear(Document):
    def validate(self):
        """Validate fiscal year"""
        self.validate_dates()
        self.validate_overlap()
        self.validate_defaults()
    
    def validate_dates(self):
        """Validate start and end dates"""
        if self.start_date and self.end_date:
            if getdate(self.start_date) >= getdate(self.end_date):
                frappe.throw(_("Start Date should be before End Date"))
    
    def validate_overlap(self):
        """Validate fiscal year overlap"""
        existing_fiscal_years = frappe.db.sql("""
            SELECT name FROM `tabFiscal Year`
            WHERE (
                (%(start_date)s BETWEEN start_date AND end_date)
                OR (%(end_date)s BETWEEN start_date AND end_date)
                OR (start_date BETWEEN %(start_date)s AND %(end_date)s)
            ) AND name != %(name)s
            """, {
                "start_date": self.start_date,
                "end_date": self.end_date,
                "name": self.name or "No Name"
            }, as_dict=True)
        
        if existing_fiscal_years:
            fiscal_years = ", ".join([d.name for d in existing_fiscal_years])
            frappe.throw(_("Fiscal Year overlaps with {0}").format(fiscal_years))
    
    def validate_defaults(self):
        """Validate default fiscal year"""
        if self.is_default:
            # Unset other defaults
            frappe.db.sql("""
                UPDATE `tabFiscal Year` SET is_default = 0
                WHERE is_default = 1 AND name != %s
            """, (self.name))
    
    def on_update(self):
        """Actions after fiscal year update"""
        # Check if this is the only fiscal year and set as default
        if not frappe.db.get_value("Fiscal Year", {"is_default": 1}):
            self.db_set("is_default", 1)
    
    @staticmethod
    def get_default():
        """Get default fiscal year"""
        default_fiscal_year = frappe.db.get_value("Fiscal Year", {"is_default": 1})
        
        if not default_fiscal_year:
            # Get the latest fiscal year
            default_fiscal_year = frappe.db.get_value(
                "Fiscal Year", 
                filters={"disabled": 0},
                fieldname="name",
                order_by="end_date desc"
            )
        
        return default_fiscal_year
