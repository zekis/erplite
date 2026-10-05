// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Activity', {
	refresh: function(frm) {
		// Add custom buttons
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__('Duplicate'), function() {
				frappe.call({
					method: 'erplite.projects.doctype.activity.activity.duplicate_activity',
					args: {
						activity_name: frm.doc.name
					},
					callback: function(r) {
						if (r.message) {
							frappe.set_route('Form', 'Activity', r.message);
						}
					}
				});
			});
			
			frm.add_custom_button(__('View Project'), function() {
				if (frm.doc.project) {
					frappe.set_route('Form', 'Project', frm.doc.project);
				}
			});
		}
		
		// Set color indicators based on status
		frm.set_indicator_formatter('status', function(doc) {
			return {
				'Open': 'blue',
				'In Progress': 'orange',
				'Review': 'yellow',
				'Completed': 'green',
				'Cancelled': 'red'
			}[doc.status];
		});
		
		// Set priority color
		if (frm.doc.priority) {
			let priority_colors = {
				'Low': 'green',
				'Medium': 'blue',
				'High': 'orange',
				'Urgent': 'red'
			};
			frm.set_df_property('priority', 'color', priority_colors[frm.doc.priority]);
		}
	},
	
	project: function(frm) {
		// Filter assigned_to based on project team members if needed
		if (frm.doc.project) {
			// Could add project-specific user filtering here
		}
	},
	
	// An Activity does not track progress. The DocType has no progress_percent
	// field and the owner decided it should not get one (review item
	// rev_0ee5b675ce), so the handler that watched the field, the status handler
	// that drove it, and the validation and list-view formatting for it are all
	// gone rather than left as a record of what was once intended.
	
	due_date: function(frm) {
		// Warn if due date is in the past
		if (frm.doc.due_date) {
			let due_date = frappe.datetime.str_to_obj(frm.doc.due_date);
			let today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
			
			if (due_date < today && frm.doc.status != 'Completed') {
				frappe.msgprint({
					message: __('Due date is in the past'),
					indicator: 'orange'
				});
			}
		}
	},
	
	// The estimated_hours handler never fired: the Activity DocType no longer declares
	// the field, so there is no field for the form to watch, and its frm.set_value
	// would have raised "Field estimated_hours not found." if it had. Removed.
	
	validate: function(frm) {
		// Validate estimated hours
		if (frm.doc.estimated_hours && frm.doc.estimated_hours < 0) {
			frappe.msgprint(__('Estimated hours cannot be negative'));
			frappe.validated = false;
		}
	}
});

// Custom list view formatting
frappe.listview_settings['Activity'] = {
	add_fields: ["status", "priority", "due_date"],
	get_indicator: function(doc) {
		return [__(doc.status), {
			"Open": "blue",
			"In Progress": "orange", 
			"Review": "yellow",
			"Completed": "green",
			"Cancelled": "red"
		}[doc.status], "status,=," + doc.status];
	},
	formatters: {
		due_date: function(value) {
			if (value) {
				let due_date = frappe.datetime.str_to_obj(value);
				let today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
				
				if (due_date < today) {
					return `<span style="color: red;">${frappe.datetime.str_to_user(value)}</span>`;
				}
			}
			return value ? frappe.datetime.str_to_user(value) : '';
		}
	}
};
