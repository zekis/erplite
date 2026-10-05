# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate, add_days

class PaymentEntry(Document):
    def validate(self):
        """Validate payment entry"""
        self.validate_party()
        self.validate_accounts()
        self.validate_reference()
        self.set_missing_values()
        self.set_status()
    
    def validate_party(self):
        """Validate party details"""
        # Check if party type and party are consistent
        if self.party_type and self.party:
            # Set party name
            if self.party_type == "Customer":
                # In a real implementation, this would fetch from Customer DocType
                self.party_name = self.party
            elif self.party_type == "Supplier":
                # In a real implementation, this would fetch from Supplier DocType
                self.party_name = self.party
    
    def validate_accounts(self):
        """Validate accounts"""
        # Validate paid from account
        if self.paid_from:
            account_details = frappe.db.get_value("Account", self.paid_from, 
                ["account_type", "currency"], as_dict=1)
            if account_details:
                self.paid_from_account_type = account_details.account_type
                self.paid_from_account_currency = account_details.currency
        
        # Validate paid to account
        if self.paid_to:
            account_details = frappe.db.get_value("Account", self.paid_to, 
                ["account_type", "currency"], as_dict=1)
            if account_details:
                self.paid_to_account_type = account_details.account_type
                self.paid_to_account_currency = account_details.currency
        
        # Validate account types based on payment type
        if self.payment_type == "Receive":
            if self.paid_from_account_type not in ["Receivable"]:
                frappe.throw(_("Paid From account must be a Receivable account for Payment Type 'Receive'"))
            if self.paid_to_account_type not in ["Bank", "Cash"]:
                frappe.throw(_("Paid To account must be a Bank or Cash account for Payment Type 'Receive'"))
        
        elif self.payment_type == "Pay":
            if self.paid_from_account_type not in ["Bank", "Cash"]:
                frappe.throw(_("Paid From account must be a Bank or Cash account for Payment Type 'Pay'"))
            if self.paid_to_account_type not in ["Payable"]:
                frappe.throw(_("Paid To account must be a Payable account for Payment Type 'Pay'"))
    
    def validate_reference(self):
        """Validate reference document"""
        if self.reference_type and self.reference_name:
            # Get reference document
            if self.reference_type == "Sales Invoice":
                ref_doc = frappe.get_doc("Sales Invoice", self.reference_name)
                self.reference_date = ref_doc.posting_date
                self.reference_amount = ref_doc.grand_total
                
                # Validate party
                if self.party_type != "Customer" or self.party != ref_doc.customer:
                    frappe.throw(_("Party Type and Party must match the Customer in Sales Invoice"))
                
                # Validate payment type
                if self.payment_type != "Receive":
                    frappe.throw(_("Payment Type must be 'Receive' for Sales Invoice"))
            
            elif self.reference_type == "Purchase Invoice":
                ref_doc = frappe.get_doc("Purchase Invoice", self.reference_name)
                self.reference_date = ref_doc.posting_date
                self.reference_amount = ref_doc.grand_total
                
                # Validate party
                if self.party_type != "Supplier" or self.party != ref_doc.supplier:
                    frappe.throw(_("Party Type and Party must match the Supplier in Purchase Invoice"))
                
                # Validate payment type
                if self.payment_type != "Pay":
                    frappe.throw(_("Payment Type must be 'Pay' for Purchase Invoice"))
    
    def set_missing_values(self):
        """Set missing values"""
        # Set received amount equal to paid amount if not specified
        if not self.received_amount and self.paid_amount:
            self.received_amount = self.paid_amount
        
        # Set paid amount equal to received amount if not specified
        if not self.paid_amount and self.received_amount:
            self.paid_amount = self.received_amount
    
    def set_status(self):
        """Set payment status"""
        if self.docstatus == 0:
            self.payment_status = "Draft"
        elif self.docstatus == 1:
            self.payment_status = "Submitted"
        elif self.docstatus == 2:
            self.payment_status = "Cancelled"
    
    def on_submit(self):
        """Actions on submit"""
        self.update_reference_document()
        
        # Update status
        self.payment_status = "Submitted"
        self.db_update()
    
    def on_cancel(self):
        """Actions on cancel"""
        self.update_reference_document(cancel=True)
        
        # Update status
        self.payment_status = "Cancelled"
        self.db_update()
    
    def update_reference_document(self, cancel=False):
        """Update reference document payment status"""
        if self.reference_type and self.reference_name:
            if self.reference_type == "Sales Invoice":
                # Update Sales Invoice
                invoice = frappe.get_doc("Sales Invoice", self.reference_name)
                invoice.is_paid = not cancel
                invoice.save()
            
            elif self.reference_type == "Purchase Invoice":
                # Update Purchase Invoice
                invoice = frappe.get_doc("Purchase Invoice", self.reference_name)
                invoice.is_paid = not cancel
                invoice.save()
