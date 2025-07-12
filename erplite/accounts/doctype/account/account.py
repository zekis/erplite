# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

class Account(Document):
    def validate(self):
        """Validate account"""
        self.validate_parent()
        self.validate_root_type()
        self.validate_group_or_ledger()
        self.set_report_type()
        self.validate_frozen()
    
    def validate_parent(self):
        """Validate parent account"""
        if self.parent_account:
            # Parent account should be a group
            is_group = frappe.db.get_value("Account", self.parent_account, "is_group")
            if not cint(is_group):
                frappe.throw(_("Parent account {0} must be a group").format(self.parent_account))
            
            # Parent account should be in the same company
            parent_company = frappe.db.get_value("Account", self.parent_account, "company")
            if parent_company != self.company:
                frappe.throw(_("Parent account {0} does not belong to company {1}").format(
                    self.parent_account, self.company))
    
    def validate_root_type(self):
        """Validate root type"""
        if self.parent_account:
            # Root type should match parent account
            parent_root_type = frappe.db.get_value("Account", self.parent_account, "root_type")
            if parent_root_type != self.root_type:
                frappe.throw(_("Root type must be same as parent account {0}").format(self.parent_account))
    
    def validate_group_or_ledger(self):
        """Validate group or ledger account"""
        if self.is_group:
            # Group account cannot have account type
            if self.account_type:
                frappe.throw(_("Group account cannot have account type"))
        else:
            # Ledger account cannot have child accounts
            if frappe.db.exists("Account", {"parent_account": self.name}):
                frappe.throw(_("Account {0} has existing child accounts. It cannot be set as a ledger account.").format(self.name))
    
    def set_report_type(self):
        """Set report type based on root type"""
        if self.root_type in ["Asset", "Liability", "Equity"]:
            self.report_type = "Balance Sheet"
        elif self.root_type in ["Income", "Expense"]:
            self.report_type = "Profit and Loss"
    
    def validate_frozen(self):
        """Validate frozen account"""
        if self.freeze_account == "Yes":
            if not self.get_doc_before_save():
                return
            
            if self.get_doc_before_save().freeze_account != self.freeze_account:
                frappe.msgprint(_("Account {0} has been frozen. Any changes to this account must be approved by the Accounts Manager.").format(self.name))
    
    def on_update(self):
        """Actions after account update"""
        pass
    
    def on_trash(self):
        """Actions before account deletion"""
        # Check if account has child accounts
        if frappe.db.exists("Account", {"parent_account": self.name}):
            frappe.throw(_("Cannot delete account {0} as it has child accounts").format(self.name))
        
        # Check if account is used in any transactions
        # This would need to be expanded based on the transaction DocTypes that reference accounts
        # For now, we'll just check if it's linked to a Xero Account
        if frappe.db.exists("Xero Account", {"account": self.name}):
            frappe.throw(_("Cannot delete account {0} as it is linked to a Xero Account").format(self.name))
