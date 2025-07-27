import frappe

def get_context(context):
    """
    Context for Vue Test App
    This function is called by Frappe to prepare data for the template
    """
    
    # Set page title and meta
    context.title = "Vue.js Test App"
    context.show_sidebar = False
    
    # You can add any server-side data here that the Vue app might need
    context.user_info = {
        "user": frappe.session.user,
        "full_name": frappe.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
        "user_image": frappe.get_value("User", frappe.session.user, "user_image"),
        "roles": frappe.get_roles(frappe.session.user)
    }
    
    # Example: Add some sample data that could be used by the Vue app
    context.api_endpoints = {
        "tasks": "/api/method/erplite.vue_test.api.get_tasks",
        "create_task": "/api/method/erplite.vue_test.api.create_task",
        "update_task": "/api/method/erplite.vue_test.api.update_task",
        "delete_task": "/api/method/erplite.vue_test.api.delete_task"
    }
    
    # Add any configuration that the Vue app might need
    context.app_config = {
        "max_tasks": 100,
        "default_priority": "medium",
        "enable_notifications": True
    }
    
    return context
