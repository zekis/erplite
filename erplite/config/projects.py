# -*- coding: utf-8 -*-
# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe import _

def get_data():
    return [
        {
            "label": _("Projects"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Project",
                    "label": _("Project"),
                    "description": _("Manage projects and track progress")
                },
                {
                    "type": "doctype",
                    "name": "Activity",
                    "label": _("Activity"),
                    "description": _("Create and manage project activities")
                }
            ]
        },
        {
            "label": _("Time Tracking"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Timesheet Entry",
                    "label": _("Timesheet Entry"),
                    "description": _("Track time spent on projects and tasks")
                },
                {
                    "type": "page",
                    "name": "timesheet-dashboard",
                    "label": _("Timesheet Dashboard"),
                    "description": _("Quick check-in/out and timesheet overview")
                }
            ]
        },
        {
            "label": _("Reports"),
            "items": [
                {
                    "type": "report",
                    "name": "Project Summary",
                    "label": _("Project Summary"),
                    "doctype": "Project",
                    "is_query_report": True
                },
                {
                    "type": "report",
                    "name": "Time Summary",
                    "label": _("Time Summary"),
                    "doctype": "Timesheet Entry",
                    "is_query_report": True
                }
            ]
        }
    ]
