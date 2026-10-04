# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, get_datetime
from datetime import datetime, timedelta


class Trip(Document):
    def validate(self):
        self.calculate_duration()
        self.validate_dates()

    def calculate_duration(self):
        """Calculate trip duration in days"""
        if self.departure_datetime and self.arrival_datetime:
            departure = get_datetime(self.departure_datetime)
            arrival = get_datetime(self.arrival_datetime)
            duration = arrival - departure
            self.duration_days = duration.total_seconds() / (24 * 3600)  # Convert to days

    def validate_dates(self):
        """Validate that arrival date is after departure date"""
        if self.departure_datetime and self.arrival_datetime:
            departure = get_datetime(self.departure_datetime)
            arrival = get_datetime(self.arrival_datetime)
            
            if arrival <= departure:
                frappe.throw("Arrival date and time must be after departure date and time")

    def before_save(self):
        """Update status based on dates.

        A pre-save hook, not on_update(): frappe's Document._save() writes the row
        in db_update() before it runs the post-save hooks, so a status assigned in
        on_update() never reached the database. Supplier Quote already derives its
        status in before_save() for the same reason.

        This still only re-evaluates when the document is saved, so a trip's status
        goes stale between saves. Keeping it current without a save would need a
        scheduled job, which is a separate change.
        """
        if self.departure_datetime and self.arrival_datetime:
            now = datetime.now()
            departure = get_datetime(self.departure_datetime)
            arrival = get_datetime(self.arrival_datetime)
            
            if now < departure:
                if self.status != "Cancelled":
                    self.status = "Planned"
            elif departure <= now <= arrival:
                if self.status != "Cancelled":
                    self.status = "In Progress"
            elif now > arrival:
                if self.status != "Cancelled":
                    self.status = "Completed"
