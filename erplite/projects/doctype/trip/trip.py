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
        """Derive status from the trip's dates, unless this save set it explicitly.

        A pre-save hook, not on_update(): frappe's Document._save() writes the row
        in db_update() before it runs the post-save hooks, so a status assigned in
        on_update() never reached the database. Supplier Quote already derives its
        status in before_save() for the same reason.

        The guard matters because status is not purely derived. trip.js offers
        "Start Trip" and "Complete Trip" buttons, which do
        `frm.set_value('status', ...)` then `frm.save()`, and the Select also lets
        a user pick a status by hand. Deriving unconditionally overwrote that
        choice before the row was written, so both buttons silently did nothing.

        `get_doc_before_save()` is populated for us: `_save()` calls
        `check_if_latest()` (frappe/model/document.py:408), which calls
        `load_doc_before_save()`, before `run_before_save_methods()` at :414. It is
        None on insert -- `load_doc_before_save` returns early when `is_new()` --
        which is the behaviour we want, since a brand-new trip has no prior status
        to respect. Note this is why `has_value_changed()` is the wrong tool here:
        it returns True when there is no prior document (:508-509), so on insert it
        would skip derivation in exactly the case that needs it.

        This still only re-evaluates when the document is saved, so a trip's status
        goes stale between saves. Keeping it current without a save would need a
        scheduled job, which is a separate change.
        """
        previous = self.get_doc_before_save()
        if previous and previous.status != self.status:
            return

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
