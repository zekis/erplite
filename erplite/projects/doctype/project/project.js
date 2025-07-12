// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Project', {
    refresh: function(frm) {
        // Set default project manager to current user if not set
        if (frm.is_new() && !frm.doc.project_manager) {
            frm.set_value('project_manager', frappe.session.user);
        }
        
        // Add custom buttons
        if (!frm.is_new()) {
            frm.add_custom_button(__('View Tasks'), function() {
                frappe.route_options = {"project": frm.doc.name};
                frappe.set_route("List", "Task");
            });
            
            frm.add_custom_button(__('View Timesheets'), function() {
                frappe.route_options = {"project": frm.doc.name};
                frappe.set_route("List", "Timesheet Entry");
            });
        }
    },
    
    start_date: function(frm) {
        // Validate dates when start date changes
        if (frm.doc.start_date && frm.doc.end_date) {
            if (frm.doc.start_date > frm.doc.end_date) {
                frappe.msgprint(__('End Date cannot be before Start Date'));
                frm.set_value('start_date', '');
            }
        }
    },
    
    end_date: function(frm) {
        // Validate dates when end date changes
        if (frm.doc.start_date && frm.doc.end_date) {
            if (frm.doc.start_date > frm.doc.end_date) {
                frappe.msgprint(__('End Date cannot be before Start Date'));
                frm.set_value('end_date', '');
            }
        }
    }
});
