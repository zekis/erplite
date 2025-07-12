# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, add_days, date_diff

class HolidayList(Document):
    def validate(self):
        """Validate holiday list"""
        self.validate_dates()
        self.validate_holidays()
        self.validate_defaults()
    
    def validate_dates(self):
        """Validate from and to dates"""
        if self.from_date and self.to_date:
            if getdate(self.from_date) > getdate(self.to_date):
                frappe.throw(_("From Date cannot be after To Date"))
    
    def validate_holidays(self):
        """Validate holidays are within date range"""
        if self.holidays:
            for holiday in self.holidays:
                if getdate(holiday.holiday_date) < getdate(self.from_date) or getdate(holiday.holiday_date) > getdate(self.to_date):
                    frappe.throw(_("Holiday {0} is not within the date range of the holiday list").format(holiday.description))
    
    def validate_defaults(self):
        """Validate default holiday list"""
        if self.is_default:
            # Unset other defaults
            frappe.db.sql("""
                UPDATE `tabHoliday List` SET is_default = 0
                WHERE is_default = 1 AND name != %s
            """, (self.name))
    
    def on_update(self):
        """Actions after holiday list update"""
        # Check if this is the only holiday list and set as default
        if not frappe.db.get_value("Holiday List", {"is_default": 1}):
            self.db_set("is_default", 1)
    
    @staticmethod
    def get_default_holiday_list(company=None):
        """Get default holiday list"""
        if company:
            default_holiday_list = frappe.get_value("Company", company, "default_holiday_list")
            if default_holiday_list:
                return default_holiday_list
        
        # Get the default holiday list
        default_holiday_list = frappe.db.get_value("Holiday List", {"is_default": 1})
        
        if not default_holiday_list:
            # Get the latest holiday list
            holiday_lists = frappe.get_all(
                "Holiday List",
                fields=["name"],
                order_by="creation desc",
                limit=1
            )
            
            if holiday_lists:
                default_holiday_list = holiday_lists[0].name
        
        return default_holiday_list
    
    def get_holidays(self):
        """Get holidays as a list of dates"""
        return [getdate(holiday.holiday_date) for holiday in self.holidays]
    
    def is_holiday(self, date):
        """Check if date is a holiday"""
        return getdate(date) in self.get_holidays()
