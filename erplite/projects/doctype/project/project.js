// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Project', {
    refresh: function(frm) {
        // The project_manager field was removed from the Project DocType, so the default
        // that used to be set here cannot be written: frm.set_value on an undeclared
        // field raises "Field project_manager not found." and aborts refresh. Restore
        // this in one line once the replacement field is chosen (timesheet_approver or
        // project_lead).
        
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
