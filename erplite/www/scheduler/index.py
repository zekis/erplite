# -*- coding: utf-8 -*-
# Copyright (c) 2025, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from erplite.scheduler.api import get_scheduler_data

def get_context(context):
    """Get context for scheduler page"""
    
    # Check permissions (basic check for now)
    if frappe.session.user == 'Guest':
        frappe.throw(_("Please login to access the scheduler"), frappe.PermissionError)
    
    # Get initial scheduler data
    try:
        scheduler_data = get_scheduler_data()
        
        context.update({
            'current_start_date': scheduler_data.get('date_range', {}).get('start_date'),
            'projects': scheduler_data.get('projects', []),
            'resources': scheduler_data.get('resources', []),
            'schedule_entries': scheduler_data.get('schedule_entries', []),
            'project_colors': scheduler_data.get('project_colors', {})
        })
        
    except Exception as e:
        frappe.log_error(f"Error loading scheduler data: {str(e)}")
        # Set empty defaults if there's an error
        context.update({
            'current_start_date': frappe.utils.today(),
            'projects': [],
            'resources': [],
            'schedule_entries': [],
            'project_colors': {}
        })
    
    # Set page metadata
    context.update({
        'title': _('Scheduler'),
        'page_name': 'scheduler',
        'show_sidebar': False,
        'full_width': True,
        'no_cache': True
    })
    
    return context
