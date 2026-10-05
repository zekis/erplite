// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.listview_settings['Timesheet Entry'] = {
    add_fields: ["status", "is_active", "employee", "duration_hours"],
    
    get_indicator: function(doc) {
        if (doc.is_active) {
            return [__("Active"), "green", "is_active,=,1"];
        } else if (doc.status === "Approved") {
            return [__("Approved"), "blue", "status,=,Approved"];
        } else if (doc.status === "Submitted") {
            return [__("Pending Approval"), "orange", "status,=,Submitted"];
        } else if (doc.status === "Rejected") {
            return [__("Rejected"), "red", "status,=,Rejected"];
        } else {
            return [__("Draft"), "gray", "status,=,Draft"];
        }
    },
    
    onload: function(listview) {
        // Add Quick Check-In button
        listview.page.add_menu_item(__("Quick Check-In"), function() {
            quick_check_in_dialog();
        });
        
        // Add filter for current user's timesheets
        listview.page.add_menu_item(__("My Timesheets"), function() {
            frappe.route_options = {"employee": frappe.session.user};
            frappe.set_route("List", "Timesheet Entry");
        });
        
        // Add filter for pending approvals (if user is a timesheet approver)
        frappe.db.get_list('Project', {
            filters: {'timesheet_approver': frappe.session.user},
            fields: ['name']
        }).then(function(projects) {
            if (projects.length > 0) {
                listview.page.add_menu_item(__("Pending Approvals"), function() {
                    let project_names = projects.map(p => p.name);
                    frappe.route_options = {
                        "project": ["in", project_names],
                        "status": "Submitted"
                    };
                    frappe.set_route("List", "Timesheet Entry");
                });
            }
        });
    },
    
    formatters: {
        duration_hours: function(value) {
            if (value) {
                return value.toFixed(2) + " hrs";
            }
            return "";
        }
    }
};

// Quick Check-In function for list view
function quick_check_in_dialog() {
    // First check if user has an active timesheet
    frappe.call({
        method: 'erplite.projects.doctype.timesheet_entry.timesheet_entry.get_active_timesheet',
        callback: function(r) {
            if (r.message) {
                // User has active timesheet, show check-out option
                frappe.msgprint({
                    title: __('Active Timesheet Found'),
                    message: __('You have an active timesheet for Project: {0}, Activity: {1}. Would you like to check out?', 
                        [r.message.project, r.message.activity]),
                    primary_action: {
                        label: __('Check Out'),
                        action: function() {
                            frappe.set_route('Form', 'Timesheet Entry', r.message.name);
                        }
                    }
                });
            } else {
                // No active timesheet, show check-in dialog
                let d = new frappe.ui.Dialog({
                    title: __('Quick Check-In'),
                    fields: [
                        {
                            label: __('Project'),
                            fieldname: 'project',
                            fieldtype: 'Link',
                            options: 'Project',
                            reqd: 1
                        },
                        {
                            label: __('Activity'),
                            fieldname: 'activity',
                            fieldtype: 'Link',
                            options: 'Activity',
                            reqd: 1
                        },
                        {
                            label: __('Location'),
                            fieldname: 'location',
                            fieldtype: 'Data'
                        }
                    ],
                    primary_action_label: __('Check In'),
                    primary_action: function() {
                        let values = d.get_values();
                        frappe.call({
                            method: 'erplite.projects.doctype.timesheet_entry.timesheet_entry.check_in',
                            args: values,
                            callback: function(r) {
                                if (r.message && r.message.success) {
                                    frappe.msgprint(r.message.message);
                                    d.hide();
                                    // Refresh the list
                                    frappe.set_route('List', 'Timesheet Entry');
                                } else {
                                    frappe.msgprint(r.message.message || 'Check-in failed');
                                }
                            }
                        });
                    }
                });
                
                // Set up activity filtering
                d.fields_dict.project.df.onchange = function() {
                    let project = d.get_value('project');
                    d.set_query('activity', function() {
                        return {
                            filters: {
                                'project': project
                            }
                        };
                    });
                    d.set_value('activity', '');
                };
                
                d.show();
            }
        }
    });
}
