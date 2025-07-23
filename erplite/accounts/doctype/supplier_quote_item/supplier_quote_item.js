// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.ui.form.on('Supplier Quote Item', {
	qty: function(frm, cdt, cdn) {
		calculate_amount(frm, cdt, cdn);
	},
	
	rate: function(frm, cdt, cdn) {
		calculate_amount(frm, cdt, cdn);
	}
});

function calculate_amount(frm, cdt, cdn) {
	var row = locals[cdt][cdn];
	if (row.qty && row.rate) {
		row.amount = row.qty * row.rate;
	} else {
		row.amount = 0;
	}
	refresh_field('amount', cdn, 'items');
}
