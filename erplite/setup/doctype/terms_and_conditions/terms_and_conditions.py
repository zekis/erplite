# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class TermsandConditions(Document):
    def validate(self):
        """Validate terms and conditions"""
        if self.disabled:
            self.validate_disabled()
    
    def validate_disabled(self):
        """Validate if disabled terms is set as default in any company"""
        companies = frappe.get_all(
            "Company",
            filters={"default_terms": self.name},
            fields=["name"]
        )
        
        if companies:
            company_list = ", ".join([company.name for company in companies])
            frappe.throw(
                f"Cannot disable Terms and Conditions as it is set as default in the following companies: {company_list}"
            )
    
    @staticmethod
    def get_default_terms(company=None):
        """Get default terms and conditions"""
        if company:
            default_terms = frappe.get_value("Company", company, "default_terms")
            if default_terms:
                return frappe.get_doc("Terms and Conditions", default_terms)
        
        # Get the first non-disabled terms
        terms_list = frappe.get_all(
            "Terms and Conditions",
            filters={"disabled": 0},
            fields=["name"],
            order_by="creation asc",
            limit=1
        )
        
        if terms_list:
            return frappe.get_doc("Terms and Conditions", terms_list[0].name)
        
        return None
