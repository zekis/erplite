// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Resource', {
    refresh: function(frm) {
        // Set default values for new resource
        if (frm.is_new()) {
            if (!frm.doc.resource_type) {
                frm.set_value('resource_type', 'Person');
            }
            if (!frm.doc.status) {
                frm.set_value('status', 'Active');
            }
            if (!frm.doc.capacity) {
                frm.set_value('capacity', 8.0);
            }
        }
        
        // Add custom buttons
        if (!frm.is_new()) {
            frm.add_custom_button(__('View Schedule'), function() {
                frappe.route_options = {"resource": frm.doc.name};
                frappe.set_route("List", "Schedule Entry");
            });
            
            frm.add_custom_button(__('Open Scheduler'), function() {
                window.open('/scheduler?resource=' + frm.doc.name, '_blank');
            });
            
            // Add capacity utilization button
            frm.add_custom_button(__('Capacity Report'), function() {
                show_capacity_report(frm);
            });
        }
        
        // Show capacity indicator
        if (!frm.is_new() && frm.doc.capacity) {
            show_capacity_indicator(frm);
        }
    },
    
    resource_type: function(frm) {
        // Update capacity based on resource type
        if (frm.doc.resource_type === 'Equipment') {
            frm.set_value('capacity', 24.0); // Equipment can run 24/7
        } else if (frm.doc.resource_type === 'Person') {
            frm.set_value('capacity', 8.0); // Standard work day
        }
    },
    
    capacity: function(frm) {
        // Validate capacity
        if (frm.doc.capacity < 0) {
            frappe.msgprint(__('Capacity cannot be negative'));
            frm.set_value('capacity', 0);
        } else if (frm.doc.capacity > 24) {
            frappe.msgprint(__('Capacity cannot exceed 24 hours per day'));
            frm.set_value('capacity', 24);
        }
        
        // Update capacity indicator
        if (!frm.is_new()) {
            show_capacity_indicator(frm);
        }
    },
    
    status: function(frm) {
        // Show warning when deactivating resource with active schedules
        if (frm.doc.status === 'Inactive' && !frm.is_new()) {
            frappe.call({
                method: 'frappe.client.get_count',
                args: {
                    doctype: 'Schedule Entry',
                    filters: {
                        resource: frm.doc.name,
                        schedule_date: ['>=', frappe.datetime.get_today()],
                        status: ['!=', 'Cancelled']
                    }
                },
                callback: function(r) {
                    if (r.message > 0) {
                        frappe.msgprint({
                            title: __('Warning'),
                            message: __('This resource has {0} active schedule entries. Consider reassigning them before deactivating.', [r.message]),
                            indicator: 'orange'
                        });
                    }
                }
            });
        }
    }
});

function show_capacity_indicator(frm) {
    // Get today's utilization
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Schedule Entry',
            filters: {
                resource: frm.doc.name,
                schedule_date: frappe.datetime.get_today(),
                docstatus: ['!=', 2]
            },
            fields: ['duration']
        },
        callback: function(r) {
            let total_scheduled = 0;
            if (r.message) {
                total_scheduled = r.message.reduce((sum, entry) => sum + (entry.duration || 0), 0);
            }
            
            let utilization = frm.doc.capacity > 0 ? (total_scheduled / frm.doc.capacity) * 100 : 0;
            let color = utilization > 100 ? 'red' : utilization > 80 ? 'orange' : 'green';
            
            frm.dashboard.add_indicator(__('Today\'s Utilization: {0}% ({1}/{2} hours)', 
                [utilization.toFixed(1), total_scheduled.toFixed(1), frm.doc.capacity]), color);
        }
    });
}

function show_capacity_report(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Capacity Report - {0}', [frm.doc.resource_name]),
        fields: [
            {
                fieldtype: 'Date',
                fieldname: 'from_date',
                label: __('From Date'),
                default: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
                reqd: 1
            },
            {
                fieldtype: 'Date',
                fieldname: 'to_date',
                label: __('To Date'),
                default: frappe.datetime.add_days(frappe.datetime.get_today(), 7),
                reqd: 1
            }
        ],
        primary_action_label: __('Generate Report'),
        primary_action: function(values) {
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Schedule Entry',
                    filters: {
                        resource: frm.doc.name,
                        schedule_date: ['between', [values.from_date, values.to_date]],
                        docstatus: ['!=', 2]
                    },
                    fields: ['schedule_date', 'duration', 'project', 'activity', 'status'],
                    order_by: 'schedule_date'
                },
                callback: function(r) {
                    if (r.message) {
                        show_capacity_chart(frm, r.message, values.from_date, values.to_date);
                    }
                    dialog.hide();
                }
            });
        }
    });
    
    dialog.show();
}

function show_capacity_chart(frm, data, from_date, to_date) {
    // Group data by date
    let daily_data = {};
    data.forEach(entry => {
        if (!daily_data[entry.schedule_date]) {
            daily_data[entry.schedule_date] = 0;
        }
        daily_data[entry.schedule_date] += entry.duration || 0;
    });
    
    // Create chart data
    let dates = [];
    let current_date = new Date(from_date);
    let end_date = new Date(to_date);
    
    while (current_date <= end_date) {
        let date_str = frappe.datetime.obj_to_str(current_date);
        dates.push({
            date: date_str,
            scheduled: daily_data[date_str] || 0,
            capacity: frm.doc.capacity
        });
        current_date.setDate(current_date.getDate() + 1);
    }
    
    // Show in a new dialog with chart
    let chart_dialog = new frappe.ui.Dialog({
        title: __('Capacity Utilization Chart'),
        size: 'large'
    });
    
    let chart_html = `
        <div style="height: 400px;">
            <canvas id="capacity-chart"></canvas>
        </div>
        <div class="mt-3">
            <h5>Summary</h5>
            <p><strong>Average Utilization:</strong> ${(dates.reduce((sum, d) => sum + d.scheduled, 0) / dates.length / frm.doc.capacity * 100).toFixed(1)}%</p>
            <p><strong>Peak Day:</strong> ${Math.max(...dates.map(d => d.scheduled)).toFixed(1)} hours</p>
            <p><strong>Available Capacity:</strong> ${(frm.doc.capacity * dates.length - dates.reduce((sum, d) => sum + d.scheduled, 0)).toFixed(1)} hours</p>
        </div>
    `;
    
    chart_dialog.$body.html(chart_html);
    chart_dialog.show();
    
    // Note: In a real implementation, you would use a charting library like Chart.js here
    frappe.msgprint(__('Chart functionality requires Chart.js library integration'));
}
