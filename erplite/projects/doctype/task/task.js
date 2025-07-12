// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Task', {
    refresh: function(frm) {
        // Set default assigned_to to current user if not set
        if (frm.is_new() && !frm.doc.assigned_to) {
            frm.set_value('assigned_to', frappe.session.user);
        }
        
        // Add custom buttons
        if (!frm.is_new()) {
            frm.add_custom_button(__('View Timesheets'), function() {
                frappe.route_options = {"task": frm.doc.name};
                frappe.set_route("List", "Timesheet Entry");
            });
            
            frm.add_custom_button(__('Quick Check-In'), function() {
                frappe.new_doc("Timesheet Entry", {
                    project: frm.doc.project,
                    task: frm.doc.name
                });
            });
        }
    },
    
    progress_percent: function(frm) {
        // Auto-update status based on progress
        if (frm.doc.progress_percent == 100) {
            frm.set_value('status', 'Completed');
        } else if (frm.doc.progress_percent > 0 && frm.doc.status == 'Open') {
            frm.set_value('status', 'In Progress');
        }
    },
    
    project: function(frm) {
        // Clear task selection when project changes
        if (frm.doc.project) {
            // Get project manager for reference
            frappe.db.get_value('Project', frm.doc.project, 'project_manager')
                .then(r => {
                    if (r.message && r.message.project_manager) {
                        frm.set_df_property('assigned_to', 'description', 
                            'Project Manager: ' + r.message.project_manager);
                    }
                });
        }
    }
});
