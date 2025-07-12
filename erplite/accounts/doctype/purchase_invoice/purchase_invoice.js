// Copyright (c) 2023, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Purchase Invoice', {
    setup: function(frm) {
        // Set default company when creating a new purchase invoice
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
                    method: 'erplite.accounts.doctype.purchase_invoice.purchase_invoice.send_to_xero',
                    args: {
                        'docname': frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.show_alert({
                                message: __('Successfully sent to Xero'),
                                indicator: 'green'
                            });
                            // Reload the form to show updated status and comments
                            frm.reload_doc();
                        }
                    }
                });
            }, __('Xero'));
        }
    },

    calculate_totals: function(frm) {
        let total = 0;
        let total_tax = 0;
        
        // Calculate totals from all line items
        frm.doc.items.forEach(function(item) {
            if (item.amount) {
                total += flt(item.amount);
            }
            if (item.tax_amount) {
                total_tax += flt(item.tax_amount);
            }
        });
        
        // Update totals
        frm.set_value('total', total);
        frm.set_value('total_tax', total_tax);
        frm.set_value('grand_total', total + total_tax);
        frm.set_value('rounded_total', Math.round(total + total_tax));
    }
});

frappe.ui.form.on('Purchase Invoice Item', {
    qty: function(frm, cdt, cdn) {
        calculate_line_total(frm, cdt, cdn);
    },
    
    rate: function(frm, cdt, cdn) {
        calculate_line_total(frm, cdt, cdn);
    },
    
    tax_rate: function(frm, cdt, cdn) {
        calculate_line_total(frm, cdt, cdn);
    },

    items_remove: function(frm) {
        frm.trigger('calculate_totals');
    }
});

function calculate_line_total(frm, cdt, cdn) {
    let item = locals[cdt][cdn];
    
    // Calculate amount (qty * rate)
    let amount = flt(item.qty) * flt(item.rate);
    frappe.model.set_value(cdt, cdn, 'amount', amount);
    
    // Calculate tax amount (amount * tax_rate / 100)
    let tax_amount = 0;
    if (item.tax_rate) {
        tax_amount = amount * flt(item.tax_rate) / 100;
    }
    frappe.model.set_value(cdt, cdn, 'tax_amount', tax_amount);
    
    // Trigger total calculation
    frm.trigger('calculate_totals');
}
