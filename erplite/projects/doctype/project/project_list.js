// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.listview_settings['Project'] = {
    add_fields: ["status", "timesheet_approver", "customer"],
    
    // No get_indicator here on purpose. The one that used to be here tested for
    // "Active", "Completed", "On Hold" and "Cancelled"; Project.status holds
    // 'Opportunity', 'Estimate', 'Open' or 'Archived', so every branch was dead and
    // the function returned undefined for every Project that exists. frappe skips a
    // falsy return (indicator.js:90) and renders the status itself with guess_colour
    // (:98), so the list looked right and this code had no part in it. Removing it
    // changes nothing. To colour Project's statuses deliberately, give project.json a
    // `states` block the way activity.json does: frappe checks that first and it
    // applies in every view, not just the list.
    
    onload: function(listview) {
        // Add filter for the projects this user approves timesheets for
        listview.page.add_menu_item(__("My Projects"), function() {
            frappe.route_options = {"timesheet_approver": frappe.session.user};
            frappe.set_route("List", "Project");
        });
        
        // Add filter for active projects only
        listview.page.add_menu_item(__("Active Projects"), function() {
            frappe.route_options = {"status": "Active"};
            frappe.set_route("List", "Project");
        });
    }
};
