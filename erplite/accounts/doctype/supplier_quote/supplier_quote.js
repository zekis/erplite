// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Supplier Quote', {
	refresh: function(frm) {
		// Add custom buttons
		if (frm.doc.status === "Received" || frm.doc.status === "Under Review") {
			frm.add_custom_button(__('Accept Quote'), function() {
				frm.set_value('status', 'Accepted');
				frm.save();
			}, __('Actions'));
			
			frm.add_custom_button(__('Reject Quote'), function() {
				frm.set_value('status', 'Rejected');
				frm.save();
			}, __('Actions'));
		}
		
		if (frm.doc.status === "Accepted") {
			frm.add_custom_button(__('Create Purchase Order'), function() {
				frappe.call({
					method: 'erplite.accounts.doctype.supplier_quote.supplier_quote.create_purchase_order_from_quote',
					args: {
						quote_name: frm.doc.name
					},
					callback: function(r) {
						if (r.message) {
							frappe.msgprint(__('Purchase Order {0} created successfully', [r.message]));
							frm.reload_doc();
						}
					}
				});
			}, __('Create'));
		}
		
		// Add quote comparison button
		frm.add_custom_button(__('Compare Quotes'), function() {
			show_quote_comparison_dialog(frm);
		}, __('Tools'));
	},
	
	supplier: function(frm) {
		if (frm.doc.supplier) {
			frappe.db.get_value('Supplier', frm.doc.supplier, 'supplier_name', function(r) {
				if (r && r.supplier_name) {
					frm.set_value('supplier_name', r.supplier_name);
				}
			});
		}
	},
	
	quote_date: function(frm) {
		// Auto-set valid until date (30 days from quote date)
		if (frm.doc.quote_date && !frm.doc.valid_until) {
			let valid_until = frappe.datetime.add_days(frm.doc.quote_date, 30);
			frm.set_value('valid_until', valid_until);
		}
	},
	
	items_add: function(frm, cdt, cdn) {
		// Set default values for new items
		let row = locals[cdt][cdn];
		if (!row.qty) {
			frappe.model.set_value(cdt, cdn, 'qty', 1);
		}
	}
});

frappe.ui.form.on('Supplier Quote Item', {
	qty: function(frm, cdt, cdn) {
		calculate_item_amount(frm, cdt, cdn);
		calculate_totals(frm);
	},
	
	rate: function(frm, cdt, cdn) {
		calculate_item_amount(frm, cdt, cdn);
		calculate_totals(frm);
	},
	
	items_remove: function(frm) {
		calculate_totals(frm);
	}
});

function calculate_item_amount(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	if (row.qty && row.rate) {
		row.amount = row.qty * row.rate;
	} else {
		row.amount = 0;
	}
	refresh_field('amount', cdn, 'items');
}

function calculate_totals(frm) {
	let total = 0;
	
	frm.doc.items.forEach(function(item) {
		if (item.amount) {
			total += item.amount;
		}
	});
	
	frm.set_value('total', total);
	frm.set_value('grand_total', total + (frm.doc.total_tax || 0));
}

function show_quote_comparison_dialog(frm) {
	let d = new frappe.ui.Dialog({
		title: __('Compare Supplier Quotes'),
		fields: [
			{
				fieldtype: 'Data',
				fieldname: 'item_name',
				label: __('Item Name (optional)'),
				description: __('Filter quotes by item name')
			},
			{
				fieldtype: 'Link',
				fieldname: 'project',
				label: __('Project (optional)'),
				options: 'Project',
				description: __('Filter quotes by project')
			}
		],
		primary_action: function() {
			let values = d.get_values();
			
			frappe.call({
				method: 'erplite.accounts.doctype.supplier_quote.supplier_quote.get_supplier_quotes_for_comparison',
				args: {
					item_name: values.item_name,
					project: values.project
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						show_quote_comparison_results(r.message);
					} else {
						frappe.msgprint(__('No quotes found for comparison'));
					}
				}
			});
			
			d.hide();
		},
		primary_action_label: __('Compare')
	});
	
	d.show();
}

function show_quote_comparison_results(quotes) {
	let html = '<table class="table table-bordered">';
	html += '<thead><tr>';
	html += '<th>Supplier</th>';
	html += '<th>Quote Date</th>';
	html += '<th>Valid Until</th>';
	html += '<th>Grand Total</th>';
	html += '<th>Status</th>';
	html += '<th>Action</th>';
	html += '</tr></thead><tbody>';
	
	quotes.forEach(function(quote) {
		html += '<tr>';
		html += '<td>' + quote.supplier_name + '</td>';
		html += '<td>' + frappe.datetime.str_to_user(quote.quote_date) + '</td>';
		html += '<td>' + (quote.valid_until ? frappe.datetime.str_to_user(quote.valid_until) : '-') + '</td>';
		html += '<td>' + format_currency(quote.grand_total) + '</td>';
		html += '<td><span class="indicator ' + get_status_color(quote.status) + '">' + quote.status + '</span></td>';
		html += '<td><a href="/app/supplier-quote/' + quote.name + '" target="_blank">View</a></td>';
		html += '</tr>';
	});
	
	html += '</tbody></table>';
	
	let d = new frappe.ui.Dialog({
		title: __('Quote Comparison Results'),
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'comparison_table',
				options: html
			}
		]
	});
	
	d.show();
}

function get_status_color(status) {
	const status_colors = {
		'Draft': 'gray',
		'Received': 'blue',
		'Under Review': 'orange',
		'Accepted': 'green',
		'Rejected': 'red',
		'Expired': 'gray'
	};
	return status_colors[status] || 'gray';
}
