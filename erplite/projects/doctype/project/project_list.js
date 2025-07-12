// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.listview_settings['Project'] = {
    add_fields: ["status", "project_manager", "customer"],
    
    get_indicator: function(doc) {
        if (doc.status === "Active") {
            return [__("Active"), "green", "status,=,Active"];
        } else if (doc.status === "Completed") {
            return [__("Completed"), "blue", "status,=,Completed"];
        } else if (doc.status === "On Hold") {
            return [__("On Hold"), "orange", "status,=,On Hold"];
        } else if (doc.status === "Cancelled") {
            return [__("Cancelled"), "red", "status,=,Cancelled"];
        }
    },
    
    onload: function(listview) {
        // Add filter for projects managed by current user
        listview.page.add_menu_item(__("My Projects"), function() {
            frappe.route_options = {"project_manager": frappe.session.user};
            frappe.set_route("List", "Project");
        });
        
        // Add filter for active projects only
        listview.page.add_menu_item(__("Active Projects"), function() {
            frappe.route_options = {"status": "Active"};
            frappe.set_route("List", "Project");
        });
    }
};
