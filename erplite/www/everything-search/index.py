import frappe
from frappe import _

def get_context(context):
    """Get context for everything search page"""
    
    # Get current user
    current_user = frappe.session.user
    
    # Security: Throw error if guest user tries to access
    if current_user == "Guest":
        frappe.throw(_("Please login to access the Everything Search application"), frappe.PermissionError)
    
    # Set page configuration
    context.no_cache = 1
    context.show_sidebar = False
    context.full_width = True
    
    # Get user's full name
    try:
        user_doc = frappe.get_doc("User", current_user)
        user_full_name = user_doc.full_name or user_doc.first_name or current_user
    except:
        user_full_name = current_user
    
    context.update({
        "current_user": current_user,
        "user_full_name": user_full_name
    })
    
    return context
