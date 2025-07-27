import frappe
import json
from frappe import _

@frappe.whitelist()
def get_tasks():
    """
    Get all tasks for the current user
    This is a demo API endpoint for the Vue test app
    """
    try:
        # In a real app, you'd query actual DocTypes
        # For demo purposes, we'll return sample data
        sample_tasks = [
            {
                "id": 1,
                "title": "Learn Vue.js with Frappe",
                "priority": "high",
                "completed": False,
                "created_at": "2025-01-25T10:00:00Z",
                "user": frappe.session.user
            },
            {
                "id": 2,
                "title": "Build a task management system",
                "priority": "medium", 
                "completed": True,
                "created_at": "2025-01-24T14:30:00Z",
                "user": frappe.session.user
            },
            {
                "id": 3,
                "title": "Deploy Vue app to production",
                "priority": "low",
                "completed": False,
                "created_at": "2025-01-23T09:15:00Z",
                "user": frappe.session.user
            }
        ]
        
        return {
            "success": True,
            "data": sample_tasks,
            "message": "Tasks retrieved successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_tasks: {str(e)}")
        return {
            "success": False,
            "message": f"Error retrieving tasks: {str(e)}"
        }

@frappe.whitelist()
def create_task(title, priority="medium", description=""):
    """
    Create a new task
    """
    try:
        if not title or not title.strip():
            return {
                "success": False,
                "message": "Task title is required"
            }
        
        # In a real app, you'd create a DocType record
        # For demo purposes, we'll simulate task creation
        new_task = {
            "id": frappe.utils.now_datetime().timestamp(),
            "title": title.strip(),
            "priority": priority,
            "description": description,
            "completed": False,
            "created_at": frappe.utils.now(),
            "user": frappe.session.user
        }
        
        # Log the action
        frappe.logger().info(f"Task created: {title} by {frappe.session.user}")
        
        return {
            "success": True,
            "data": new_task,
            "message": "Task created successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error in create_task: {str(e)}")
        return {
            "success": False,
            "message": f"Error creating task: {str(e)}"
        }

@frappe.whitelist()
def update_task(task_id, **kwargs):
    """
    Update an existing task
    """
    try:
        if not task_id:
            return {
                "success": False,
                "message": "Task ID is required"
            }
        
        # In a real app, you'd update the DocType record
        # For demo purposes, we'll simulate the update
        updated_fields = {}
        
        allowed_fields = ['title', 'priority', 'description', 'completed']
        for field in allowed_fields:
            if field in kwargs:
                updated_fields[field] = kwargs[field]
        
        if not updated_fields:
            return {
                "success": False,
                "message": "No valid fields to update"
            }
        
        # Log the action
        frappe.logger().info(f"Task {task_id} updated by {frappe.session.user}: {updated_fields}")
        
        return {
            "success": True,
            "data": {
                "id": task_id,
                "updated_fields": updated_fields,
                "modified": frappe.utils.now()
            },
            "message": "Task updated successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error in update_task: {str(e)}")
        return {
            "success": False,
            "message": f"Error updating task: {str(e)}"
        }

@frappe.whitelist()
def delete_task(task_id):
    """
    Delete a task
    """
    try:
        if not task_id:
            return {
                "success": False,
                "message": "Task ID is required"
            }
        
        # In a real app, you'd delete the DocType record
        # For demo purposes, we'll simulate the deletion
        
        # Log the action
        frappe.logger().info(f"Task {task_id} deleted by {frappe.session.user}")
        
        return {
            "success": True,
            "data": {"deleted_id": task_id},
            "message": "Task deleted successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error in delete_task: {str(e)}")
        return {
            "success": False,
            "message": f"Error deleting task: {str(e)}"
        }

@frappe.whitelist()
def get_user_stats():
    """
    Get user statistics for the Vue app
    """
    try:
        # In a real app, you'd query actual data
        stats = {
            "total_tasks": 15,
            "completed_tasks": 8,
            "pending_tasks": 7,
            "high_priority_tasks": 3,
            "user": frappe.session.user,
            "last_login": frappe.get_value("User", frappe.session.user, "last_login"),
            "user_roles": frappe.get_roles(frappe.session.user)
        }
        
        return {
            "success": True,
            "data": stats,
            "message": "User stats retrieved successfully"
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_user_stats: {str(e)}")
        return {
            "success": False,
            "message": f"Error retrieving user stats: {str(e)}"
        }

@frappe.whitelist()
def test_connection():
    """
    Test API connection
    """
    return {
        "success": True,
        "message": "API connection successful",
        "timestamp": frappe.utils.now(),
        "user": frappe.session.user,
        "frappe_version": frappe.__version__
    }
