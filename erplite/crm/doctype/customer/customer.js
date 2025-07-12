// Copyright (c) 2023, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Customer', {
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.name && !frm.doc.xero_contact_id) {
            frm.add_custom_button(__('Send to Xero'), function() {
                frappe.call({
                    method: 'erplite.crm.doctype.customer.customer.send_to_xero',
                    args: {
                        'docname': frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: __('Successfully sent to Xero'),
                                indicator: 'green'
                            });
                            frm.refresh();
                        }
                    }
                });
            }, __('Xero'));
        }
    }
});
