// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scheduler Role', {
	refresh: function(frm) {
		// Add custom buttons
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__('View Resources'), function() {
				frappe.call({
					method: 'erplite.scheduler.doctype.scheduler_role.scheduler_role.get_role_resources',
					args: {
						role: frm.doc.name
					},
					callback: function(r) {
						if (r.message && r.message.length > 0) {
							frappe.set_route('List', 'Resource', {
								'roles': ['like', '%' + frm.doc.name + '%']
							});
						} else {
							frappe.msgprint(__('No resources found for this role'));
						}
					}
				});
			});
			
			frm.add_custom_button(__('Role Statistics'), function() {
				frappe.call({
					method: 'erplite.scheduler.doctype.scheduler_role.scheduler_role.get_role_statistics',
					args: {
						role: frm.doc.name
					},
					callback: function(r) {
						if (r.message) {
							let stats = r.message;
							let msg = `
								<h4>Role Statistics for ${stats.role_name} (${stats.role_code})</h4>
								<ul>
									<li><strong>Resources:</strong> ${stats.resource_count}</li>
									<li><strong>Schedule Entries:</strong> ${stats.schedule_count}</li>
									<li><strong>Default Hourly Rate:</strong> ${format_currency(stats.default_hourly_rate)}</li>
								</ul>
							`;
							frappe.msgprint(msg, __('Role Statistics'));
						}
					}
				});
			});
		}
		
		// Set color picker default
		if (frm.doc.__islocal && !frm.doc.color) {
			// Will be set by Python controller
		}
	},
	
	role_name: function(frm) {
		// Auto-generate role code from name
		if (frm.doc.role_name && !frm.doc.role_code) {
			let code = frm.doc.role_name
				.toUpperCase()
				.replace(/[^A-Z0-9]/g, '')
				.substring(0, 5);
			frm.set_value('role_code', code);
		}
	},
	
	role_code: function(frm) {
		// Convert to uppercase
		if (frm.doc.role_code) {
			frm.set_value('role_code', frm.doc.role_code.toUpperCase());
		}
	},
	
	hourly_rate: function(frm) {
		// Validate hourly rate
		if (frm.doc.hourly_rate && frm.doc.hourly_rate < 0) {
			frappe.msgprint(__('Hourly rate cannot be negative'));
			frm.set_value('hourly_rate', 0);
		}
	},
	
	validate: function(frm) {
		// Validate role code format
		if (frm.doc.role_code) {
			if (frm.doc.role_code.length > 10) {
				frappe.msgprint(__('Role Code should not exceed 10 characters'));
				frappe.validated = false;
			}
		}
		
		// Validate hourly rate
		if (frm.doc.hourly_rate && frm.doc.hourly_rate < 0) {
			frappe.msgprint(__('Hourly rate cannot be negative'));
			frappe.validated = false;
		}
	}
});
