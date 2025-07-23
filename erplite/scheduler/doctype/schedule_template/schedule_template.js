// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Schedule Template', {
	refresh: function(frm) {
		// Add custom buttons
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__('Preview Template'), function() {
				show_template_preview(frm);
			});
		}
		
		// Add button to create default templates
		if (frappe.user.has_role('System Manager')) {
			frm.add_custom_button(__('Create Default Templates'), function() {
				frappe.call({
					method: 'erplite.scheduler.doctype.schedule_template.schedule_template.create_default_templates',
					callback: function(r) {
						if (r.message) {
							frappe.msgprint(r.message);
							frm.reload_doc();
						}
					}
				});
			}, __('Actions'));
		}
		
		// Set color picker default
		if (frm.doc.__islocal && !frm.doc.color) {
			// Will be set by Python controller based on status
		}
	},
	
	template_name: function(frm) {
		// Auto-generate template code from name
		if (frm.doc.template_name && !frm.doc.template_code) {
			let code = frm.doc.template_name
				.toLowerCase()
				.replace(/[^a-z0-9]/g, '')
				.substring(0, 10);
			frm.set_value('template_code', code);
		}
	},
	
	template_code: function(frm) {
		// Convert to lowercase
		if (frm.doc.template_code) {
			frm.set_value('template_code', frm.doc.template_code.toLowerCase());
		}
	},
	
	hours: function(frm) {
		// Validate hours
		if (frm.doc.hours && frm.doc.hours < 0) {
			frappe.msgprint(__('Hours cannot be negative'));
			frm.set_value('hours', 0);
		}
		
		if (frm.doc.hours && frm.doc.hours > 24) {
			frappe.msgprint(__('Hours cannot exceed 24'));
			frm.set_value('hours', 24);
		}
		
		// Auto-calculate end time if start time is set
		if (frm.doc.start_time && frm.doc.hours) {
			auto_calculate_end_time(frm);
		}
	},
	
	start_time: function(frm) {
		// Auto-calculate end time if hours is set
		if (frm.doc.hours && frm.doc.start_time) {
			auto_calculate_end_time(frm);
		}
	},
	
	status: function(frm) {
		// Update color based on status if color is not manually set
		if (frm.doc.status && !frm.doc.__color_manually_set) {
			set_status_color(frm);
		}
	},
	
	color: function(frm) {
		// Mark that color was manually set
		frm.doc.__color_manually_set = true;
	},
	
	sort_order: function(frm) {
		// Validate sort order
		if (frm.doc.sort_order && frm.doc.sort_order < 0) {
			frappe.msgprint(__('Sort order cannot be negative'));
			frm.set_value('sort_order', 1);
		}
	},
	
	validate: function(frm) {
		// Validate template code format
		if (frm.doc.template_code) {
			if (frm.doc.template_code.length > 20) {
				frappe.msgprint(__('Template Code should not exceed 20 characters'));
				frappe.validated = false;
			}
		}
		
		// Validate hours
		if (frm.doc.hours && (frm.doc.hours < 0 || frm.doc.hours > 24)) {
			frappe.msgprint(__('Hours must be between 0 and 24'));
			frappe.validated = false;
		}
		
		// Validate sort order
		if (frm.doc.sort_order && frm.doc.sort_order < 0) {
			frappe.msgprint(__('Sort order cannot be negative'));
			frappe.validated = false;
		}
	}
});

function auto_calculate_end_time(frm) {
	if (!frm.doc.start_time || !frm.doc.hours) return;
	
	// Parse start time
	let start_parts = frm.doc.start_time.split(':');
	let start_hour = parseInt(start_parts[0]);
	let start_minute = parseInt(start_parts[1]);
	
	// Calculate end time
	let total_minutes = (start_hour * 60) + start_minute + (frm.doc.hours * 60);
	let end_hour = Math.floor(total_minutes / 60) % 24;
	let end_minute = total_minutes % 60;
	
	// Format end time
	let end_time = String(end_hour).padStart(2, '0') + ':' + String(end_minute).padStart(2, '0') + ':00';
	
	frm.set_value('end_time', end_time);
}

function set_status_color(frm) {
	const status_colors = {
		'planned': '#3b82f6',    // Blue
		'leave': '#f59e0b',      // Yellow
		'overtime': '#ef4444',   // Red
		'sick': '#ec4899',       // Pink
		'training': '#10b981'    // Green
	};
	
	let color = status_colors[frm.doc.status] || '#6b7280';
	frm.set_value('color', color);
}

function show_template_preview(frm) {
	let preview_html = `
		<div style="padding: 20px; border: 1px solid #ddd; border-radius: 8px; background: ${frm.doc.color || '#f8f9fa'}; color: white; text-align: center; margin: 10px 0;">
			<h3 style="margin: 0; color: white;">${frm.doc.template_name}</h3>
			<p style="margin: 5px 0; color: rgba(255,255,255,0.9);">${frm.doc.hours}h • ${frm.doc.start_time || '09:00'} - ${frm.doc.end_time || '17:00'}</p>
			<p style="margin: 5px 0; font-size: 0.9em; color: rgba(255,255,255,0.8);">${frm.doc.description || 'No description'}</p>
			<span style="background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">${frm.doc.status}</span>
		</div>
	`;
	
	frappe.msgprint({
		title: __('Template Preview'),
		message: preview_html,
		wide: true
	});
}
