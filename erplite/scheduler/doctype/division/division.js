// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Division', {
	refresh: function(frm) {
		// Add custom buttons
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__('View Projects'), function() {
				frappe.set_route('List', 'Project', {
					'division': frm.doc.name
				});
			});
		}
		
		// Set color picker default
		if (frm.doc.__islocal && !frm.doc.color) {
			// Will be set by Python controller
		}
	},
	
	division_name: function(frm) {
		// Auto-generate division code from name
		if (frm.doc.division_name && !frm.doc.division_code) {
			let code = frm.doc.division_name
				.toUpperCase()
				.replace(/[^A-Z0-9]/g, '')
				.substring(0, 5);
			frm.set_value('division_code', code);
		}
	},
	
	division_code: function(frm) {
		// Convert to uppercase
		if (frm.doc.division_code) {
			frm.set_value('division_code', frm.doc.division_code.toUpperCase());
		}
	},
	
	validate: function(frm) {
		// Validate division code format
		if (frm.doc.division_code) {
			if (frm.doc.division_code.length > 10) {
				frappe.msgprint(__('Division Code should not exceed 10 characters'));
				frappe.validated = false;
			}
		}
	}
});
