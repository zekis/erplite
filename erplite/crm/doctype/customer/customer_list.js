// Copyright (c) 2023, ERPLite and contributors
// For license information, please see license.txt

frappe.listview_settings['Customer'] = {
    onload: function(listview) {
        listview.page.add_menu_item(__("Import from Xero"), function() {
            frappe.call({
                method: 'erplite.crm.doctype.customer.customer.get_xero_customers',
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        // Create a dialog to select a customer
                        let fields = [];
                        let options = [];
                        
                        r.message.forEach(function(customer) {
                            options.push({
                                label: customer.Name,
                                value: customer.ContactID,
                                description: customer.EmailAddress || ''
                            });
                        });
                        
                        fields.push({
                            label: __('Select Customer'),
                            fieldname: 'xero_customer',
                            fieldtype: 'Autocomplete',
                            options: options,
                            reqd: 1
                        });
                        
                        let d = new frappe.ui.Dialog({
                            title: __('Import Customer from Xero'),
                            fields: fields,
                            primary_action_label: __('Import'),
                            primary_action: function() {
                                let values = d.get_values();
                                if (values.xero_customer) {
                                    frappe.call({
                                        method: 'erplite.crm.doctype.customer.customer.import_from_xero',
                                        args: {
                                            'xero_contact_id': values.xero_customer
                                        },
                                        callback: function(r) {
                                            if (r.message) {
                                                frappe.show_alert({
                                                    message: __('Customer imported successfully'),
                                                    indicator: 'green'
                                                });
                                                listview.refresh();
                                            }
                                        }
                                    });
                                }
                                d.hide();
                            }
                        });
                        
                        d.show();
                    } else {
                        frappe.msgprint(__('No customers found in Xero'));
                    }
                }
            });
        });
    }
};
