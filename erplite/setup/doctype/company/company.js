// Copyright (c) 2023, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Company', {
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.name) {
            frm.add_custom_button(__('Connect to Xero'), function() {
                frappe.call({
                    method: 'connect_to_xero',
                    doc: frm.doc,
                    callback: function(r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: __('Successfully connected to Xero'),
                                indicator: 'green'
                            });
                            frm.refresh();
                        }
                    }
                });
            }, __('Xero'));
            
            if (frm.doc.xero_organization_id) {
                frm.add_custom_button(__('Sync with Xero'), function() {
                    frappe.call({
                        method: 'sync_with_xero',
                        doc: frm.doc,
                        callback: function(r) {
                            if (r.message) {
                                frappe.show_alert({
                                    message: __('Successfully synced with Xero'),
                                    indicator: 'green'
                                });
                                frm.refresh();
                            }
                        }
                    });
                }, __('Xero'));
            }
        }
    }
});
