// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Schedule Entry', {
    refresh: function(frm) {
        // Set default values for new entry
        if (frm.is_new()) {
            if (!frm.doc.status) {
                frm.set_value('status', 'Planned');
            }
            if (!frm.doc.priority) {
                frm.set_value('priority', 'Medium');
            }
            if (!frm.doc.duration) {
                frm.set_value('duration', 1.0);
            }
            if (!frm.doc.schedule_date) {
                frm.set_value('schedule_date', frappe.datetime.get_today());
            }
        }
        
        // Add custom buttons
        if (!frm.is_new()) {
            frm.add_custom_button(__('Duplicate Entry'), function() {
                duplicate_schedule_entry(frm);
            });
            
            frm.add_custom_button(__('Move to Resource'), function() {
                move_to_resource(frm);
            });
            
            frm.add_custom_button(__('Open Scheduler'), function() {
                let url = '/scheduler';
                if (frm.doc.resource) {
                    url += '?resource=' + frm.doc.resource;
                }
                if (frm.doc.schedule_date) {
                    url += (url.includes('?') ? '&' : '?') + 'date=' + frm.doc.schedule_date;
                }
                window.open(url, '_blank');
            });
        }
        
        // Show resource capacity indicator
        if (frm.doc.resource && frm.doc.schedule_date) {
            show_resource_capacity(frm);
        }
        
        // Show time conflict warnings
        if (frm.doc.resource && frm.doc.start_time && frm.doc.end_time) {
            check_time_conflicts(frm);
        }
    },
    
    project: function(frm) {
        // Filter activities by project
        if (frm.doc.project) {
            frm.set_query('activity', function() {
                return {
                    filters: {
                        project: frm.doc.project
                    }
                };
            });
            
            // Clear activity if it doesn't belong to the new project
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
    
    resource: function(frm) {
        if (frm.doc.resource && frm.doc.schedule_date) {
            show_resource_capacity(frm);
        }
        
        // Check for conflicts if times are set
        if (frm.doc.resource && frm.doc.start_time && frm.doc.end_time) {
            check_time_conflicts(frm);
        }
    },
    
    schedule_date: function(frm) {
        if (frm.doc.resource && frm.doc.schedule_date) {
            show_resource_capacity(frm);
        }
        
        // Check for conflicts if times are set
        if (frm.doc.resource && frm.doc.start_time && frm.doc.end_time) {
            check_time_conflicts(frm);
        }
    },
    
    start_time: function(frm) {
        // Calculate end time if duration is set
        if (frm.doc.start_time && frm.doc.duration && !frm.doc.end_time) {
            calculate_end_time(frm);
        }
        
        // Check for conflicts
        if (frm.doc.resource && frm.doc.start_time && frm.doc.end_time) {
            check_time_conflicts(frm);
        }
    },
    
    end_time: function(frm) {
        // Calculate duration if start time is set
        if (frm.doc.start_time && frm.doc.end_time) {
            calculate_duration_from_times(frm);
        }
        
        // Check for conflicts
        if (frm.doc.resource && frm.doc.start_time && frm.doc.end_time) {
            check_time_conflicts(frm);
        }
    },
    
    duration: function(frm) {
        // Validate duration
        if (frm.doc.duration <= 0) {
            frappe.msgprint(__('Duration must be greater than 0'));
            frm.set_value('duration', 1.0);
        } else if (frm.doc.duration > 24) {
            frappe.msgprint(__('Duration cannot exceed 24 hours'));
            frm.set_value('duration', 24.0);
        }
        
        // Calculate end time if start time is set
        if (frm.doc.start_time && frm.doc.duration) {
            calculate_end_time(frm);
        }
        
        // Update capacity check
        if (frm.doc.resource && frm.doc.schedule_date) {
            show_resource_capacity(frm);
        }
    },
    
    status: function(frm) {
        // Nothing to do here. This used to call
        // erplite.scheduler.doctype.schedule_entry.schedule_entry.update_activity_progress,
        // which has never existed in any commit, so changing the status of a saved entry that
        // had an activity always raised "Failed to get method for command ..." in the user's
        // face. There is nothing to point it at either: Activity's progress_percent field was
        // removed in 8126278 and has no successor, so whether the scheduler should roll
        // progress up to the Activity at all is an open product question (review tray
        // rev_e3d5be99e3), not a rename. Restoring this means adding both the field and the
        // server method.
    }
});

function calculate_end_time(frm) {
    if (!frm.doc.start_time || !frm.doc.duration) return;
    
    let start_time = moment(frm.doc.start_time, 'HH:mm:ss');
    let end_time = start_time.clone().add(frm.doc.duration, 'hours');
    
    // Handle day overflow
    if (end_time.format('YYYY-MM-DD') !== start_time.format('YYYY-MM-DD')) {
        end_time = moment('23:59:59', 'HH:mm:ss');
        // Recalculate duration
        let actual_duration = end_time.diff(start_time, 'hours', true);
        frm.set_value('duration', Math.round(actual_duration * 100) / 100);
    }
    
    frm.set_value('end_time', end_time.format('HH:mm:ss'));
}

function calculate_duration_from_times(frm) {
    if (!frm.doc.start_time || !frm.doc.end_time) return;
    
    let start_time = moment(frm.doc.start_time, 'HH:mm:ss');
    let end_time = moment(frm.doc.end_time, 'HH:mm:ss');
    
    if (end_time.isBefore(start_time)) {
        frappe.msgprint(__('End time must be after start time'));
        frm.set_value('end_time', '');
        return;
    }
    
    let duration = end_time.diff(start_time, 'hours', true);
    frm.set_value('duration', Math.round(duration * 100) / 100);
}

function show_resource_capacity(frm) {
    if (!frm.doc.resource || !frm.doc.schedule_date) return;
    
    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Resource',
            fieldname: ['resource_name', 'capacity'],
            filters: {name: frm.doc.resource}
        },
        callback: function(r) {
            if (r.message) {
                let resource_name = r.message.resource_name;
                let capacity = r.message.capacity;
                
                // Get scheduled hours for this resource on this date
                frappe.call({
                    method: 'frappe.client.get_list',
                    args: {
                        doctype: 'Schedule Entry',
                        filters: {
                            resource: frm.doc.resource,
                            schedule_date: frm.doc.schedule_date,
                            name: ['!=', frm.doc.name || ''],
                            docstatus: ['!=', 2]
                        },
                        fields: ['duration']
                    },
                    callback: function(r2) {
                        let scheduled_hours = 0;
                        if (r2.message) {
                            scheduled_hours = r2.message.reduce((sum, entry) => sum + (entry.duration || 0), 0);
                        }
                        
                        let available = capacity - scheduled_hours;
                        let utilization = capacity > 0 ? (scheduled_hours / capacity) * 100 : 0;
                        let color = utilization > 100 ? 'red' : utilization > 80 ? 'orange' : 'green';
                        
                        frm.dashboard.add_indicator(
                            __('Resource Capacity: {0}/{1} hours ({2}% utilized)', 
                                [scheduled_hours.toFixed(1), capacity, utilization.toFixed(1)]), 
                            color
                        );
                        
                        if (frm.doc.duration > available) {
                            frm.dashboard.add_indicator(
                                __('Warning: Requested {0}h exceeds available {1}h', 
                                    [frm.doc.duration, available.toFixed(1)]), 
                                'red'
                            );
                        }
                    }
                });
            }
        }
    });
}

function check_time_conflicts(frm) {
    if (!frm.doc.resource || !frm.doc.start_time || !frm.doc.end_time || !frm.doc.schedule_date) return;
    
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Schedule Entry',
            filters: {
                resource: frm.doc.resource,
                schedule_date: frm.doc.schedule_date,
                name: ['!=', frm.doc.name || ''],
                docstatus: ['!=', 2],
                start_time: ['is', 'set'],
                end_time: ['is', 'set']
            },
            fields: ['name', 'start_time', 'end_time', 'project', 'activity']
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                let conflicts = [];
                let current_start = moment(frm.doc.start_time, 'HH:mm:ss');
                let current_end = moment(frm.doc.end_time, 'HH:mm:ss');
                
                r.message.forEach(entry => {
                    let entry_start = moment(entry.start_time, 'HH:mm:ss');
                    let entry_end = moment(entry.end_time, 'HH:mm:ss');
                    
                    // Check for overlap
                    if (current_start.isBefore(entry_end) && current_end.isAfter(entry_start)) {
                        conflicts.push(`${entry.name} (${entry.start_time}-${entry.end_time})`);
                    }
                });
                
                if (conflicts.length > 0) {
                    frm.dashboard.add_indicator(
                        __('Time Conflict with: {0}', [conflicts.join(', ')]), 
                        'red'
                    );
                }
            }
        }
    });
}

function duplicate_schedule_entry(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Duplicate Schedule Entry'),
        fields: [
            {
                fieldtype: 'Date',
                fieldname: 'new_date',
                label: __('New Date'),
                default: frm.doc.schedule_date,
                reqd: 1
            },
            {
                fieldtype: 'Link',
                fieldname: 'new_resource',
                label: __('New Resource (optional)'),
                options: 'Resource',
                default: frm.doc.resource
            }
        ],
        primary_action_label: __('Duplicate'),
        primary_action: function(values) {
            frm.call({
                // duplicate_entry is an @frappe.whitelist() method on the ScheduleEntry
                // controller, so it has to be called as a document method: frappe.get_attr
                // resolves a dotted path with getattr(module, name) and cannot see inside the
                // class. Passing the doc routes this through run_doc_method instead, which
                // identifies the record itself -- hence no `name` argument, which
                // duplicate_entry does not accept.
                method: 'duplicate_entry',
                doc: frm.doc,
                args: {
                    new_date: values.new_date,
                    new_resource: values.new_resource
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(__('Entry duplicated successfully'));
                        frappe.set_route('Form', 'Schedule Entry', r.message);
                    }
                }
            });
            dialog.hide();
        }
    });
    
    dialog.show();
}

function move_to_resource(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Move to Resource'),
        fields: [
            {
                fieldtype: 'Link',
                fieldname: 'new_resource',
                label: __('New Resource'),
                options: 'Resource',
                reqd: 1
            },
            {
                fieldtype: 'Date',
                fieldname: 'new_date',
                label: __('New Date (optional)'),
                default: frm.doc.schedule_date
            }
        ],
        primary_action_label: __('Move'),
        primary_action: function(values) {
            frm.call({
                // Same as duplicate_entry above: a whitelisted controller method, so it goes
                // through run_doc_method with the doc rather than a dotted module path, and
                // move_to_resource takes no `name` argument.
                method: 'move_to_resource',
                doc: frm.doc,
                args: {
                    new_resource: values.new_resource,
                    new_date: values.new_date
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint(r.message.message);
                        frm.reload_doc();
                    } else if (r.message) {
                        frappe.msgprint({
                            title: __('Error'),
                            message: r.message.message,
                            indicator: 'red'
                        });
                    }
                }
            });
            dialog.hide();
        }
    });
    
    dialog.show();
}
