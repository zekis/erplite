// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Timesheet Entry', {
    refresh: function(frm) {
        // Set default employee to current user if not set
        if (frm.is_new() && !frm.doc.employee) {
            frm.set_value('employee', frappe.session.user);
        }
        
        // Add custom buttons based on status
        if (!frm.is_new()) {
            // Check-out button for active entries
            if (frm.doc.is_active && frm.doc.employee === frappe.session.user) {
                frm.add_custom_button(__('Check Out'), function() {
                    let description = '';
                    frappe.prompt({
                        label: 'Work Description',
                        fieldname: 'description',
                        fieldtype: 'Text',
                        default: frm.doc.description || ''
                    }, function(values) {
                        frappe.call({
                            method: 'erplite.projects.doctype.timesheet_entry.timesheet_entry.check_out',
                            args: {
                                timesheet_id: frm.doc.name,
                                description: values.description
                            },
                            callback: function(r) {
                                if (r.message && r.message.success) {
                                    frappe.msgprint(r.message.message);
                                    frm.reload_doc();
                                } else {
                                    frappe.msgprint(r.message.message || 'Check-out failed');
                                }
                            }
                        });
                    }, 'Check Out', 'Check Out');
                }, __('Actions')).addClass('btn-primary');
            }
            
            // Approval buttons for project managers
            if (frm.doc.status === 'Submitted') {
                // Check if current user is project manager
                frappe.db.get_value('Project', frm.doc.project, 'project_manager')
                    .then(r => {
                        if (r.message && r.message.project_manager === frappe.session.user) {
                            frm.add_custom_button(__('Approve'), function() {
                                frappe.prompt({
                                    label: 'Approval Notes',
                                    fieldname: 'approval_notes',
                                    fieldtype: 'Text',
                                    reqd: 0
                                }, function(values) {
                                    frappe.call({
                                        method: 'erplite.projects.doctype.timesheet_entry.timesheet_entry.approve_timesheet',
                                        args: {
                                            timesheet_id: frm.doc.name,
                                            approval_notes: values.approval_notes
                                        },
                                        callback: function(r) {
                                            if (r.message && r.message.success) {
                                                frappe.msgprint(r.message.message);
                                                frm.reload_doc();
                                            } else {
                                                frappe.msgprint(r.message.message || 'Approval failed');
                                            }
                                        }
                                    });
                                }, 'Approve Timesheet', 'Approve');
                            }, __('Actions')).addClass('btn-success');
                            
                            frm.add_custom_button(__('Reject'), function() {
                                frappe.prompt({
                                    label: 'Rejection Reason',
                                    fieldname: 'approval_notes',
                                    fieldtype: 'Text',
                                    reqd: 1
                                }, function(values) {
                                    frappe.call({
                                        method: 'erplite.projects.doctype.timesheet_entry.timesheet_entry.reject_timesheet',
                                        args: {
                                            timesheet_id: frm.doc.name,
                                            approval_notes: values.approval_notes
                                        },
                                        callback: function(r) {
                                            if (r.message && r.message.success) {
                                                frappe.msgprint(r.message.message);
                                                frm.reload_doc();
                                            } else {
                                                frappe.msgprint(r.message.message || 'Rejection failed');
                                            }
                                        }
                                    });
                                }, 'Reject Timesheet', 'Reject');
                            }, __('Actions')).addClass('btn-danger');
                        }
                    });
            }
        }
        
        // Set field properties based on status
        if (frm.doc.status === 'Approved' || frm.doc.status === 'Rejected') {
            frm.set_df_property('check_in_time', 'read_only', 1);
            frm.set_df_property('check_out_time', 'read_only', 1);
            frm.set_df_property('project', 'read_only', 1);
            frm.set_df_property('activity', 'read_only', 1);
            frm.set_df_property('description', 'read_only', 1);
        }
        
        // Show active status indicator
        if (frm.doc.is_active) {
            frm.dashboard.add_indicator(__('Active (Checked In)'), 'green');
        }
    },
    
    project: function(frm) {
        // Filter activities based on selected project
        if (frm.doc.project) {
            frm.set_query('activity', function() {
                return {
                    filters: {
                        'project': frm.doc.project
                    }
                };
            });
            
            // Clear activity if project changes
            if (frm.doc.activity) {
                frappe.db.get_value('Activity', frm.doc.activity, 'project')
                    .then(r => {
                        if (r.message && r.message.project !== frm.doc.project) {
                            frm.set_value('activity', '');
                        }
                    });
            }
        }
    },
    
    activity: function(frm) {
        // Auto-fill location from activity
        if (frm.doc.activity && !frm.doc.location) {
            frappe.db.get_value('Activity', frm.doc.activity, 'location')
                .then(r => {
                    if (r.message && r.message.location) {
                        frm.set_value('location', r.message.location);
                    }
                });
        }
    },
    
    check_in_time: function(frm) {
        // Set date from check_in_time
        if (frm.doc.check_in_time && !frm.doc.date) {
            let check_in_date = frappe.datetime.get_date_obj(frm.doc.check_in_time);
            frm.set_value('date', frappe.datetime.obj_to_str(check_in_date));
        }
    },
    
    check_out_time: function(frm) {
        // Auto-submit when check-out is completed
        if (frm.doc.check_in_time && frm.doc.check_out_time && frm.doc.status === 'Draft') {
            frm.set_value('status', 'Submitted');
        }
    }
});

// Quick Check-In function for dashboard
frappe.provide('frappe.timesheet');

frappe.timesheet.quick_check_in = function() {
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
};
