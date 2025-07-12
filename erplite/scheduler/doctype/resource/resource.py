# -*- coding: utf-8 -*-
# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class Resource(Document):
    def validate(self):
        """Validate resource"""
        self.validate_capacity()
        self.validate_resource_name()
    
    def validate_capacity(self):
        """Validate capacity value"""
        # Convert to float if it's a string
        if isinstance(self.capacity, str):
            try:
                self.capacity = float(self.capacity)
            except (ValueError, TypeError):
                self.capacity = 8.0
        
        # Ensure it's a number
        if not isinstance(self.capacity, (int, float)):
            self.capacity = 8.0
            
        if self.capacity < 0:
            frappe.throw(_("Capacity cannot be negative"))
        elif self.capacity > 24:
            frappe.throw(_("Capacity cannot exceed 24 hours per day"))
    
    def validate_resource_name(self):
        """Validate resource name is unique"""
        if not self.resource_name:
            frappe.throw(_("Resource Name is required"))
        
        # Check for duplicate resource names
        existing = frappe.db.get_value("Resource", 
            {"resource_name": self.resource_name, "name": ["!=", self.name]}, 
            "name")
        
        if existing:
            frappe.throw(_("Resource with name '{0}' already exists").format(self.resource_name))
    
    def on_update(self):
        """Actions on update"""
        pass
    
    def on_submit(self):
        """Actions on submit"""
        pass
    
    def on_cancel(self):
        """Actions on cancel"""
        pass
    
    def get_available_capacity(self, date):
        """Get available capacity for a specific date"""
        # Get total scheduled hours for this resource on the given date
        scheduled_hours = frappe.db.sql("""
            SELECT COALESCE(SUM(duration), 0) as total_hours
            FROM `tabSchedule Entry`
            WHERE resource = %s AND schedule_date = %s AND docstatus != 2
        """, (self.name, date))[0][0]
        
        return max(0, self.capacity - scheduled_hours)
    
    def is_available(self, date, duration=1.0):
        """Check if resource is available for given duration on date"""
        if self.status != "Active":
            return False
        
        available_capacity = self.get_available_capacity(date)
        return available_capacity >= duration
