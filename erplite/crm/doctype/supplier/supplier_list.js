// Copyright (c) 2023, ERPLite and contributors
// For license information, please see license.txt

frappe.listview_settings['Supplier'] = {
    onload: function(listview) {
        listview.page.add_menu_item(__("Import from Xero"), function() {
            frappe.call({
                method: 'erplite.crm.doctype.supplier.supplier.get_xero_suppliers',
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        // Create a dialog to select a supplier
                        let fields = [];
                        let options = [];
                        
                        r.message.forEach(function(supplier) {
                            options.push({
                                label: supplier.Name,
                                value: supplier.ContactID,
                                description: supplier.EmailAddress || ''
                            });
                        });
                        
                        fields.push({
                            label: __('Select Supplier'),
                            fieldname: 'xero_supplier',
                            fieldtype: 'Autocomplete',
                            options: options,
                            reqd: 1
                        });
                        
                        let d = new frappe.ui.Dialog({
                            title: __('Import Supplier from Xero'),
                            fields: fields,
                            primary_action_label: __('Import'),
                            primary_action: function() {
                                let values = d.get_values();
                                if (values.xero_supplier) {
                                    frappe.call({
                                        method: 'erplite.crm.doctype.supplier.supplier.import_from_xero',
                                        args: {
                                            'xero_contact_id': values.xero_supplier
                                        },
                                        callback: function(r) {
                                            if (r.message) {
                                                frappe.show_alert({
                                                    message: __('Supplier imported successfully'),
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
                        frappe.msgprint(__('No suppliers found in Xero'));
                    }
                }
            });
        });
    }
};
