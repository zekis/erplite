#!/usr/bin/env python3

import frappe

def remove_projects_workspace():
    """Remove the Projects & Timesheets workspace from database"""
    try:
        # Connect to the database
        frappe.init(site='your_site_name')  # Replace with your actual site name
        frappe.connect()
        
        # Delete the workspace if it exists
        if frappe.db.exists("Workspace", "Projects & Timesheets"):
            frappe.delete_doc("Workspace", "Projects & Timesheets", force=True)
            print("✅ Removed 'Projects & Timesheets' workspace from database")
        else:
            print("ℹ️  Workspace 'Projects & Timesheets' not found in database")
        
        # Commit the changes
        frappe.db.commit()
        
        # Clear cache
        frappe.clear_cache()
        print("✅ Cache cleared")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        frappe.destroy()

if __name__ == "__main__":
    remove_projects_workspace()
