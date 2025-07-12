// Copyright (c) 2023, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sales Invoice', {
    setup: function(frm) {
        // Set default company when creating a new sales invoice
        if (frm.doc.__islocal) {
            frm.call('set_default_company').then(() => {
                frm.refresh_field('company');
            });
        }
    },
    
    refresh: function(frm) {
        // Add custom buttons
        // Show "Send to Xero" button regardless of docstatus, as long as it hasn't been sent to Xero yet
        if (!frm.doc.xero_invoice_id) {
            frm.add_custom_button(__('Send to Xero'), function() {
                frappe.call({
                    method: 'erplite.accounts.doctype.sales_invoice.sales_invoice.send_to_xero',
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
