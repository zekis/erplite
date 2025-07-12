# -*- coding: utf-8 -*-
# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class Project(Document):
    def validate(self):
        """Validate project"""
        self.set_default_company()
        self.validate_dates()
    
    def set_default_company(self):
        """Set default company if not specified"""
        if not self.company:
            # Get the first company that is set as default
            default_company = frappe.db.get_value("Company", {"is_default": 1}, "name")
            if default_company:
                self.company = default_company
            else:
                # If no default company, get the first company
                companies = frappe.get_all("Company", limit=1)
                if companies:
                    self.company = companies[0].name
    
    def validate_dates(self):
        """Validate start and end dates"""
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                frappe.throw(_("End Date cannot be before Start Date"))
    
    def on_update(self):
        """Actions on update"""
        pass
    
    def on_submit(self):
        """Actions on submit"""
        pass
    
    def on_cancel(self):
        """Actions on cancel"""
        pass
