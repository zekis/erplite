# -*- coding: utf-8 -*-
# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class Task(Document):
    def validate(self):
        """Validate task"""
        self.validate_progress()
        self.update_status_based_on_progress()
    
    def validate_progress(self):
        """Validate progress percentage"""
        # Convert to float if it's a string
        if isinstance(self.progress_percent, str):
            try:
                self.progress_percent = float(self.progress_percent)
            except (ValueError, TypeError):
                self.progress_percent = 0
        
        # Ensure it's a number
        if not isinstance(self.progress_percent, (int, float)):
            self.progress_percent = 0
            
        if self.progress_percent < 0:
            self.progress_percent = 0
        elif self.progress_percent > 100:
            self.progress_percent = 100
    
    def update_status_based_on_progress(self):
        """Update status based on progress percentage"""
        if self.progress_percent == 100 and self.status != "Completed":
            self.status = "Completed"
        elif self.progress_percent > 0 and self.progress_percent < 100 and self.status == "Open":
            self.status = "In Progress"
    
    def on_update(self):
        """Actions on update"""
        pass
    
    def on_submit(self):
        """Actions on submit"""
        pass
    
    def on_cancel(self):
        """Actions on cancel"""
        pass
