// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Schedule Row', {
    refresh: function(frm) {
        // Add custom buttons
        frm.add_custom_button(__('Preview Daily Entries'), function() {
            preview_daily_entries(frm);
        });
        
        frm.add_custom_button(__('Extend Entries'), function() {
            extend_entries_dialog(frm);
        });
        
        frm.add_custom_button(__('Copy to Date Range'), function() {
            copy_to_date_range_dialog(frm);
        });
        
        // Format daily entries field
        if (frm.doc.daily_entries) {
            format_daily_entries_display(frm);
        }
    },
    
    project: function(frm) {
        // Clear activity when project changes
        if (frm.doc.project) {
            frm.set_value('activity', '');
        }
    },
    
    daily_entries: function(frm) {
        // Validate JSON format
        if (frm.doc.daily_entries) {
            try {
                JSON.parse(frm.doc.daily_entries);
                frm.dashboard.clear_comment();
            } catch (e) {
                frm.dashboard.add_comment('Invalid JSON format in Daily Entries', 'red');
            }
        }
    }
});

function preview_daily_entries(frm) {
    if (!frm.doc.daily_entries) {
        frappe.msgprint(__('No daily entries to preview'));
        return;
    }
    
    try {
        const entries = JSON.parse(frm.doc.daily_entries);
        let html = '<table class="table table-bordered"><thead><tr><th>Date</th><th>Hours</th><th>Description</th><th>Status</th></tr></thead><tbody>';
        
        // Sort dates
        const sortedDates = Object.keys(entries).sort();
        
        for (const date of sortedDates) {
            const entry = entries[date];
            const hours = typeof entry === 'object' ? entry.hours || 0 : entry;
            const description = typeof entry === 'object' ? entry.description || '' : '';
            const status = typeof entry === 'object' ? entry.status || 'planned' : 'planned';
            
            html += `<tr>
                <td>${frappe.datetime.str_to_user(date)}</td>
                <td>${hours}</td>
                <td>${description}</td>
                <td><span class="indicator ${get_status_color(status)}">${status}</span></td>
            </tr>`;
        }
        
        html += '</tbody></table>';
        
        frappe.msgprint({
            title: __('Daily Entries Preview'),
            message: html,
            wide: true
        });
        
    } catch (e) {
        frappe.msgprint(__('Error parsing daily entries: {0}', [e.message]));
    }
}

function get_status_color(status) {
    const colors = {
        'planned': 'blue',
        'in_progress': 'orange',
        'completed': 'green',
        'cancelled': 'red'
    };
    return colors[status] || 'gray';
}

function extend_entries_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Extend Entries'),
        fields: [
            {
                fieldtype: 'Int',
                fieldname: 'additional_days',
                label: __('Additional Days'),
                reqd: 1,
                default: 7
            },
            {
                fieldtype: 'Float',
                fieldname: 'hours_per_day',
                label: __('Hours per Day'),
                default: 8.0,
                precision: 2
            }
        ],
        primary_action_label: __('Extend'),
        primary_action: function(values) {
            frappe.call({
                method: 'erplite.scheduler.doctype.schedule_row.schedule_row.extend_entries',
                args: {
                    schedule_row: frm.doc.name,
                    additional_days: values.additional_days,
                    hours_per_day: values.hours_per_day
                },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.msgprint(__('Entries extended successfully'));
                        frm.reload_doc();
                    } else {
                        frappe.msgprint(__('Error extending entries'));
                    }
                }
            });
            dialog.hide();
        }
    });
    
    dialog.show();
}

function copy_to_date_range_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Copy to Date Range'),
        fields: [
            {
                fieldtype: 'Date',
                fieldname: 'start_date',
                label: __('Start Date'),
                reqd: 1,
                default: frappe.datetime.add_days(frappe.datetime.get_today(), 1)
            },
            {
                fieldtype: 'Date',
                fieldname: 'end_date',
                label: __('End Date'),
                reqd: 1,
                default: frappe.datetime.add_days(frappe.datetime.get_today(), 7)
            },
            {
                fieldtype: 'Check',
                fieldname: 'overwrite',
                label: __('Overwrite Existing Entries'),
                default: 0
            }
        ],
        primary_action_label: __('Copy'),
        primary_action: function(values) {
            frappe.call({
                method: 'run_doc_method',
                args: {
                    docs: frm.doc,
                    method: 'copy_entries_to_date_range',
                    args: [values.start_date, values.end_date, values.overwrite]
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(__('Entries copied successfully'));
                        frm.reload_doc();
                    } else {
                        frappe.msgprint(__('Error copying entries'));
                    }
                }
            });
            dialog.hide();
        }
    });
    
    dialog.show();
}

function format_daily_entries_display(frm) {
    // Add a formatted display of daily entries
    if (frm.doc.daily_entries && frm.fields_dict.daily_entries) {
        try {
            const entries = JSON.parse(frm.doc.daily_entries);
            const entryCount = Object.keys(entries).length;
            const totalHours = Object.values(entries).reduce((sum, entry) => {
                const hours = typeof entry === 'object' ? entry.hours || 0 : entry;
                return sum + parseFloat(hours);
            }, 0);
            
            const summary = `${entryCount} entries, ${totalHours} total hours`;
            frm.fields_dict.daily_entries.set_description(summary);
            
        } catch (e) {
            frm.fields_dict.daily_entries.set_description('Invalid JSON format');
        }
    }
}

// Custom formatter for list view
frappe.listview_settings['Schedule Row'] = {
    add_fields: ['total_hours', 'start_date', 'end_date', 'project_name', 'activity_name', 'resource_name'],
    
    get_indicator: function(doc) {
        if (doc.total_hours > 0) {
            return [__('Active'), 'green', 'total_hours,>,0'];
        } else {
            return [__('Empty'), 'gray', 'total_hours,=,0'];
        }
    },
    
    formatters: {
        total_hours: function(value) {
            return value ? `${value}h` : '0h';
        },
        
        project_name: function(value, field, doc) {
            if (value) {
                return `<strong>${value}</strong>`;
            }
            return value;
        }
    }
};
