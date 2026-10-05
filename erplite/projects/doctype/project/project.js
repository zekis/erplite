// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Project', {
    refresh: function(frm) {
        // Default the timesheet approver to whoever is creating the project.
        if (frm.is_new() && !frm.doc.timesheet_approver) {
            frm.set_value('timesheet_approver', frappe.session.user);
        }
        
        // Add custom buttons
        if (!frm.is_new()) {
            frm.add_custom_button(__('View Activities'), function() {
                frappe.route_options = {"project": frm.doc.name};
                frappe.set_route("List", "Activity");
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
