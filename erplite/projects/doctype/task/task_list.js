// Copyright (c) 2025, ERPLite and contributors
// For license information, please see license.txt

frappe.listview_settings['Task'] = {
    add_fields: ["status", "priority", "assigned_to", "progress_percent"],
    
    get_indicator: function(doc) {
        if (doc.status === "Completed") {
            return [__("Completed"), "green", "status,=,Completed"];
        } else if (doc.status === "In Progress") {
            return [__("In Progress"), "orange", "status,=,In Progress"];
        } else if (doc.status === "Review") {
            return [__("Review"), "blue", "status,=,Review"];
        } else if (doc.status === "Open") {
            if (doc.priority === "High" || doc.priority === "Urgent") {
                return [__("Open"), "red", "status,=,Open"];
            } else {
                return [__("Open"), "gray", "status,=,Open"];
            }
        } else if (doc.status === "Cancelled") {
            return [__("Cancelled"), "darkgray", "status,=,Cancelled"];
        }
    },
    
    onload: function(listview) {
        // Add filter for tasks assigned to current user
        listview.page.add_menu_item(__("My Tasks"), function() {
            frappe.route_options = {"assigned_to": frappe.session.user};
            frappe.set_route("List", "Task");
        });
        
        // Add filter for open tasks only
        listview.page.add_menu_item(__("Open Tasks"), function() {
            frappe.route_options = {"status": "Open"};
            frappe.set_route("List", "Task");
        });
        
        // Add filter for high priority tasks
        listview.page.add_menu_item(__("High Priority"), function() {
            frappe.route_options = {"priority": ["in", ["High", "Urgent"]]};
            frappe.set_route("List", "Task");
        });
    },
    
    formatters: {
        progress_percent: function(value) {
            if (value) {
                return value + "%";
            }
            return "0%";
        }
    }
};
