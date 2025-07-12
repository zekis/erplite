// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Trip', {
    refresh: function(frm) {
        // Add custom buttons or functionality here
        if (frm.doc.status === "Planned") {
            frm.add_custom_button(__('Start Trip'), function() {
                frm.set_value('status', 'In Progress');
                frm.save();
            });
        }
        
        if (frm.doc.status === "In Progress") {
            frm.add_custom_button(__('Complete Trip'), function() {
                frm.set_value('status', 'Completed');
                frm.save();
            });
        }
        
        // Add button to view related purchase invoices
        frm.add_custom_button(__('View Purchase Invoices'), function() {
            frappe.route_options = {
                "trip": frm.doc.name
            };
            frappe.set_route("List", "Purchase Invoice");
        });
    },
    
    departure_datetime: function(frm) {
        calculate_duration(frm);
    },
    
    arrival_datetime: function(frm) {
        calculate_duration(frm);
    }
});

function calculate_duration(frm) {
    if (frm.doc.departure_datetime && frm.doc.arrival_datetime) {
        let departure = new Date(frm.doc.departure_datetime);
        let arrival = new Date(frm.doc.arrival_datetime);
        
        if (arrival > departure) {
            let duration = (arrival - departure) / (1000 * 60 * 60 * 24); // Convert to days
            frm.set_value('duration_days', duration);
        }
    }
}
