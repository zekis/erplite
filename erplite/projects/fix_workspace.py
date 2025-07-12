# Run this with: bench execute erplite.projects.fix_workspace.remove_workspace

import frappe

def remove_workspace():
    """Remove the problematic workspace"""
    try:
        if frappe.db.exists("Workspace", "Projects & Timesheets"):
            frappe.delete_doc("Workspace", "Projects & Timesheets", force=True)
            frappe.db.commit()
            print("✅ Removed 'Projects & Timesheets' workspace")
        else:
            print("ℹ️  Workspace not found")
        
        frappe.clear_cache()
        print("✅ Cache cleared")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
