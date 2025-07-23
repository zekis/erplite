// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Scheduler Log', {
	refresh: function(frm) {
		// Make the form read-only since logs shouldn't be edited
		frm.set_read_only();
		
		// Add custom button to clear old logs
		if (frappe.user.has_role('System Manager')) {
			frm.add_custom_button(__('Clear Old Logs'), function() {
				frappe.confirm(
					__('Are you sure you want to delete logs older than 30 days?'),
					function() {
						frappe.call({
							method: 'erplite.scheduler.doctype.scheduler_log.scheduler_log.clear_old_logs',
							callback: function(r) {
								if (r.message) {
									frappe.msgprint(__('Cleared {0} old log entries', [r.message.deleted_count]));
									frm.reload_doc();
								}
							}
						});
					}
				);
			});
		}
	}
});
