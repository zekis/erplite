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
	
	progress_percent: function(frm) {
		// Auto-update status based on progress
		if (frm.doc.progress_percent == 100 && frm.doc.status != 'Completed') {
			frm.set_value('status', 'Completed');
		} else if (frm.doc.progress_percent > 0 && frm.doc.status == 'Open') {
			frm.set_value('status', 'In Progress');
		}
		
		// Show progress bar
		if (frm.doc.progress_percent) {
			frm.dashboard.add_progress(__('Progress'), frm.doc.progress_percent, __('% Complete'));
		}
	},
	
	// The status handler used to drive progress_percent, which the Activity DocType no
	// longer declares. frm.set_value on it raised "Field progress_percent not found."
	// whenever status was set to Completed, so the handler is removed. Whether an
	// Activity should track progress at all is a product question; the rest of this
	// file's progress logic is left in place as a record of what was intended.
	
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
		// Validate progress percentage
		if (frm.doc.progress_percent && (frm.doc.progress_percent < 0 || frm.doc.progress_percent > 100)) {
			frappe.msgprint(__('Progress percentage must be between 0 and 100'));
			frappe.validated = false;
		}
		
		// Validate estimated hours
		if (frm.doc.estimated_hours && frm.doc.estimated_hours < 0) {
			frappe.msgprint(__('Estimated hours cannot be negative'));
			frappe.validated = false;
		}
	}
});

// Custom list view formatting
frappe.listview_settings['Activity'] = {
	add_fields: ["status", "priority", "progress_percent", "due_date"],
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
		progress_percent: function(value) {
			if (value) {
				return `<div class="progress" style="height: 12px; margin: 0;">
					<div class="progress-bar" style="width: ${value}%; background-color: #5e64ff;"></div>
				</div> ${value}%`;
			}
			return '';
		},
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
