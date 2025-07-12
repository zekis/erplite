// Copyright (c) 2023, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Xero Settings', {
    refresh: function(frm) {
        // Set authorization status based on token presence
        if (frm.doc.access_token && frm.doc.tenant_id) {
            frm.set_value('authorization_status', 'Authorized');
        } else {
            frm.set_value('authorization_status', 'Not Authorized');
        }
        
        // Connect button
        frm.add_custom_button(__('Connect to Xero'), function() {
            frappe.call({
                method: 'connect',
                doc: frm.doc,
                callback: function(r) {
                    if (r.message && Array.isArray(r.message)) {
                        // Multiple tenants found, show selection dialog
                        let d = new frappe.ui.Dialog({
                            title: __('Select Xero Organization'),
                            fields: [
                                {
                                    label: __('Xero Organization'),
                                    fieldname: 'tenant',
                                    fieldtype: 'Select',
                                    options: r.message.map(t => `${t.tenant_name}|${t.tenant_id}`).join('\n'),
                                    reqd: 1
                                }
                            ],
                            primary_action_label: __('Select'),
                            primary_action: function() {
                                let values = d.get_values();
                                let selected = values.tenant.split('|');
                                let tenant_name = selected[0];
                                let tenant_id = selected[1];
                                
                                frappe.call({
                                    method: 'set_tenant',
                                    doc: frm.doc,
                                    args: {
                                        'tenant_id': tenant_id,
                                        'tenant_name': tenant_name
                                    },
                                    callback: function(r) {
                                        if (r.message) {
                                            frm.refresh();
                                        }
                                    }
                                });
                                
                                d.hide();
                            }
                        });
                        d.show();
                    } else if (r.message) {
                        // Successfully connected
                        frm.refresh();
                    }
                }
            });
        }).addClass('btn-primary');
        
        // Disconnect button (only show if connected)
        if (frm.doc.authorization_status === 'Authorized') {
            frm.add_custom_button(__('Disconnect from Xero'), function() {
                frappe.confirm(
                    __('Are you sure you want to disconnect from Xero?'),
                    function() {
                        frappe.call({
                            method: 'disconnect',
                            doc: frm.doc,
                            callback: function(r) {
                                if (r.message) {
                                    frm.refresh();
                                }
                            }
                        });
                    }
                );
            }).addClass('btn-danger');
        }
    },
    
    
});
