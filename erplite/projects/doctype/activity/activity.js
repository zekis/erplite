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
			// Every value Activity.status can hold, with the colours activity.json already
			// gives them in its `states` block. Keep the two in step: this formatter has no
			// fallback -- frappe's form.js:1889 interpolates the return value straight into
			// a class attribute -- so a status missing from this map renders as
			// class="indicator undefined" rather than failing in any visible way.
			return {
				'Estimate': 'yellow',
				'Open': 'green',
				'Complete': 'blue',
				'Closed': 'orange',
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
			
			if (due_date < today && frm.doc.status != 'Complete') {
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
	// No get_indicator here on purpose. activity.json declares a `states` block for
	// all five statuses, and frappe checks that before listview_settings.get_indicator
	// (indicator.js:82 runs ahead of :88), so a custom indicator never ran for any
	// value this field can hold. The one that used to be here keyed its colours on
	// 'In Progress', 'Review' and 'Completed', none of which Activity.status has, so
	// had the `states` block ever been dropped it would have returned an array with an
	// undefined colour in it -- which passes frappe's `if (indicator)` guard, because
	// a non-empty array is truthy, and prints class="indicator-pill undefined".
	// Colours for this field belong in the `states` block.
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
