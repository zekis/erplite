import frappe
from frappe import _
import json
from datetime import datetime, timedelta

# Who may see and change a todo.
#
# Frappe already answers this for ToDo, and its answer is the one the owner
# asked for. frappe/desk/doctype/todo/todo.py has_permission returns
#
#     doc.allocated_to == user or doc.assigned_by == user or doc.owner == user
#
# and get_permission_query_conditions builds the same three-way OR in SQL. So
# whoever a todo is with, whoever created it and whoever last handed it on may
# each read and write it. That applies to anyone without a role granting ToDo
# outright; ToDo's only non-automatic role is System Manager.
#
# This page used to apply a narrower rule of its own -- allocated_to only --
# which is why handing a todo over locked its creator out of it. The helpers
# below restate frappe's rule rather than invent one, so the page and the
# framework agree.
#
# One asymmetry is worth stating because it is easy to get backwards:
# `frappe.get_all` sets ignore_permissions=True (frappe/__init__.py), so
# frappe's query conditions never run for the lists this page builds and the
# filters here are the only thing deciding what a non-manager sees. Saves and
# deletes go through Document, so frappe's has_permission does apply to those.
MANAGER_ROLES = ["System Manager", "Administrator"]


def _is_manager(user):
    """True if `user` holds a role that grants ToDo outright."""
    return bool(frappe.db.exists("Has Role", {
        "parent": user,
        "role": ["in", MANAGER_ROLES]
    }))


def _can_manage_todo(todo, user, user_is_manager):
    """Frappe's own ToDo rule: it is yours if it is with you, by you, or from you."""
    return bool(
        user_is_manager
        or todo.allocated_to == user
        or todo.assigned_by == user
        or todo.owner == user
    )


def get_context(context):
    """Get context data for the todo kanban page"""
    
    # Get current user
    current_user = frappe.session.user
    
    # Security: Throw error if guest user tries to access
    if current_user == "Guest":
        frappe.throw(_("Please login to access the Todo Kanban application"), frappe.PermissionError)
    
    # Check if user is a manager (has System Manager role or custom manager role)
    is_manager = _is_manager(current_user)
    
    # Everyone gets the whole list. Anyone may assign a todo to anyone, so
    # everyone needs somebody to assign it to; a non-manager used to get a
    # dropdown containing only themselves, which left create_todo honouring a
    # choice the page could not offer.
    users = frappe.get_all("User",
        filters={"enabled": 1, "user_type": "System User"},
        fields=["name", "full_name", "user_image"],
        order_by="full_name"
    )
    
    # Get todos based on user permissions
    # `owner` is read as well as `assigned_by`, because both decide who may see
    # and change the todo, and both are sent to the page below.
    todo_fields = [
        "name", "description", "status", "priority", "date",
        "allocated_to", "color", "reference_type", "reference_name",
        "assigned_by", "owner", "creation", "modified"
    ]
    if is_manager:
        # Managers can see all todos
        todos = frappe.get_all("ToDo",
            filters={"status": ["!=", "Cancelled"]},  # Don't show cancelled by default
            fields=todo_fields,
            order_by="creation desc"
        )
    else:
        # Everyone else sees the todos that are theirs by frappe's rule: with
        # them, created by them, or handed on by them. Without the last two a
        # user lost sight of work the moment they gave it to somebody else,
        # which is the opposite of keeping track of it.
        todos = frappe.get_all("ToDo",
            filters={"status": ["!=", "Cancelled"]},
            or_filters={
                "allocated_to": current_user,
                "assigned_by": current_user,
                "owner": current_user
            },
            fields=todo_fields,
            order_by="creation desc"
        )
    
    # Process todos for frontend
    processed_todos = []
    for todo in todos:
        # Determine column based on status and date
        column = get_todo_column(todo)
        
        # Get user info for assigned user
        user_info = None
        if todo.allocated_to:
            user_doc = frappe.get_cached_doc("User", todo.allocated_to)
            user_info = {
                "name": user_doc.name,
                "full_name": user_doc.full_name,
                "user_image": user_doc.user_image,
                "initials": get_user_initials(user_doc.full_name or user_doc.name)
            }
        
        # Format due date
        due_date_info = None
        if todo.date:
            due_date = frappe.utils.getdate(todo.date)
            today = frappe.utils.getdate(frappe.utils.today())
            days_diff = (due_date - today).days
            
            due_date_info = {
                "date": str(todo.date),  # Convert to string for JSON serialization
                "formatted": frappe.utils.formatdate(todo.date, "MMM dd"),
                "is_overdue": days_diff < 0,
                "days_diff": days_diff,
                "relative": get_relative_date(days_diff)
            }
        
        processed_todo = {
            "name": todo.name,
            "description": todo.description,
            "status": todo.status,
            "priority": todo.priority,
            "color": todo.color,
            "column": column,
            "user": user_info,
            # The three fields the page decides its own permissions from. They
            # were not sent before, so `todo.allocated_to` was undefined on
            # every card and TodoDataManager.canEditTodo compared undefined
            # with the current user -- always false, which hid the edit,
            # delete, assign, date and drag controls from every non-manager.
            "allocated_to": todo.allocated_to,
            "assigned_by": todo.assigned_by,
            "owner": todo.owner,
            "due_date": due_date_info,
            "reference": {
                "type": todo.reference_type,
                "name": todo.reference_name
            } if todo.reference_type else None,
            "created": frappe.utils.formatdate(todo.creation, "MMM dd, YYYY"),
            "modified": frappe.utils.formatdate(todo.modified, "MMM dd, YYYY")
        }
        
        processed_todos.append(processed_todo)
    
    # Group todos by column
    todos_by_column = {
        "backlog": [],
        "todo": [],
        "progress": []
    }
    
    for todo in processed_todos:
        column = todo["column"]
        if column in todos_by_column:
            todos_by_column[column].append(todo)
    
    context.update({
        "current_user": current_user,
        "is_manager": is_manager,
        "users": users,
        "todos": processed_todos,
        "todos_by_column": todos_by_column,
        "total_todos": len(processed_todos),
        "no_container": True,  # Make page full width
        "full_width": True
    })
    
    return context

def get_guest_context(context):
    """Get sample context data for guest users"""
    from datetime import datetime, timedelta
    
    # Sample users
    sample_users = [
        {"name": "guest", "full_name": "Guest User"},
        {"name": "john.doe", "full_name": "John Doe"},
        {"name": "jane.smith", "full_name": "Jane Smith"}
    ]
    
    # Sample todos with different priorities and dates
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    
    sample_todos = [
        {
            "name": "sample-todo-1",
            "description": "Review quarterly sales report and prepare presentation for board meeting",
            "status": "Open",
            "priority": "High",
            "color": "#ef4444",
            "column": "progress",
            "user": {
                "name": "john.doe",
                "full_name": "John Doe",
                "initials": "JD"
            },
            "due_date": {
                "date": str(today),
                "formatted": "Today",
                "is_overdue": False,
                "days_diff": 0,
                "relative": "Today"
            },
            "reference": None,
            "created": "Jan 15, 2025",
            "modified": "Jan 22, 2025"
        },
        {
            "name": "sample-todo-2", 
            "description": "Update customer database with new contact information",
            "status": "Open",
            "priority": "Medium",
            "color": "#3b82f6",
            "column": "todo",
            "user": {
                "name": "jane.smith",
                "full_name": "Jane Smith", 
                "initials": "JS"
            },
            "due_date": {
                "date": str(tomorrow),
                "formatted": "Tomorrow",
                "is_overdue": False,
                "days_diff": 1,
                "relative": "Tomorrow"
            },
            "reference": None,
            "created": "Jan 20, 2025",
            "modified": "Jan 21, 2025"
        },
        {
            "name": "sample-todo-3",
            "description": "Research new project management tools for team collaboration",
            "status": "Open", 
            "priority": "Low",
            "color": "#10b981",
            "column": "backlog",
            "user": {
                "name": "guest",
                "full_name": "Guest User",
                "initials": "GU"
            },
            "due_date": None,
            "reference": None,
            "created": "Jan 18, 2025",
            "modified": "Jan 19, 2025"
        },
        {
            "name": "sample-todo-4",
            "description": "Fix critical bug in user authentication system",
            "status": "Open",
            "priority": "High", 
            "color": "#ef4444",
            "column": "progress",
            "user": {
                "name": "john.doe",
                "full_name": "John Doe",
                "initials": "JD"
            },
            "due_date": {
                "date": str(yesterday),
                "formatted": "Yesterday", 
                "is_overdue": True,
                "days_diff": -1,
                "relative": "Yesterday"
            },
            "reference": {
                "type": "Issue",
                "name": "ISS-2025-001"
            },
            "created": "Jan 19, 2025",
            "modified": "Jan 22, 2025"
        },
        {
            "name": "sample-todo-5",
            "description": "Plan team building event for Q1",
            "status": "Open",
            "priority": "Medium",
            "color": "#f59e0b", 
            "column": "todo",
            "user": {
                "name": "jane.smith",
                "full_name": "Jane Smith",
                "initials": "JS"
            },
            "due_date": {
                "date": str(today + timedelta(days=7)),
                "formatted": "Next Week",
                "is_overdue": False,
                "days_diff": 7,
                "relative": "In 7 days"
            },
            "reference": None,
            "created": "Jan 16, 2025", 
            "modified": "Jan 20, 2025"
        }
    ]
    
    # Group todos by column
    todos_by_column = {
        "backlog": [],
        "todo": [],
        "progress": []
    }
    
    for todo in sample_todos:
        column = todo["column"]
        if column in todos_by_column:
            todos_by_column[column].append(todo)
    
    context.update({
        "current_user": "Guest",
        "is_manager": True,  # Allow guest to test all features
        "users": sample_users,
        "todos": sample_todos,
        "todos_by_column": todos_by_column,
        "total_todos": len(sample_todos),
        "no_container": True,
        "full_width": True
    })
    
    return context

def get_todo_column(todo):
    """Determine which column a todo belongs to based on status"""
    # Only show Open, Backlog, and Planned todos on the kanban board
    if todo.status not in ["Open", "Backlog", "Planned"]:
        return None  # Closed/Cancelled todos don't appear on board
    
    # Map status to columns
    status_to_column = {
        "Backlog": "backlog",
        "Planned": "todo", 
        "Open": "progress"
    }
    
    return status_to_column.get(todo.status, "backlog")

def get_user_initials(full_name):
    """Get user initials from full name"""
    if not full_name:
        return "?"
    
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    else:
        return parts[0][0:2].upper()

def get_relative_date(days_diff):
    """Get relative date string"""
    if days_diff == 0:
        return "Today"
    elif days_diff == 1:
        return "Tomorrow"
    elif days_diff == -1:
        return "Yesterday"
    elif days_diff > 1:
        return f"In {days_diff} days"
    else:
        return f"{abs(days_diff)} days ago"

@frappe.whitelist()
def get_todos():
    """API endpoint to get todos"""
    context = {}
    get_context(context)
    return {
        "todos": context["todos"],
        "todos_by_column": context["todos_by_column"],
        "is_manager": context["is_manager"]
    }

@frappe.whitelist()
def update_todo_status(todo_name, new_status, new_column=None):
    """Update todo status and column"""
    try:
        todo = frappe.get_doc("ToDo", todo_name)
        
        # Check permissions
        current_user = frappe.session.user
        
        if not _can_manage_todo(todo, current_user, _is_manager(current_user)):
            frappe.throw(_("You don't have permission to update this todo"))
        
        # Update status
        todo.status = new_status
        
        # If moving to progress column, set priority to High
        if new_column == "progress":
            todo.priority = "High"
        
        todo.save()
        frappe.db.commit()
        
        return {"success": True, "message": "Todo updated successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error updating todo status: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def create_todo(description, priority="Medium", allocated_to=None, date=None, color=None):
    """Create a new todo"""
    try:
        current_user = frappe.session.user
        
        # Anyone may assign a todo to anyone. This used to overwrite a
        # non-manager's choice with themselves and still return success: True,
        # so the assignee they picked in the New Todo dialog was discarded and
        # nobody was told. An unset assignee still means "mine", which is what
        # the quick-add buttons rely on.
        if not allocated_to:
            allocated_to = current_user
        
        todo = frappe.get_doc({
            "doctype": "ToDo",
            "description": description,
            "status": "Backlog",  # New todos start in backlog
            "priority": priority,
            "allocated_to": allocated_to,
            "date": date,
            "color": color,
            "assigned_by": current_user
        })
        
        todo.insert()
        frappe.db.commit()
        
        return {"success": True, "todo_name": todo.name, "message": "Todo created successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error creating todo: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def update_todo(todo_name, description=None, priority=None, allocated_to=None, date=None, color=None):
    """Update todo details"""
    try:
        todo = frappe.get_doc("ToDo", todo_name)
        
        # Check permissions
        current_user = frappe.session.user
        
        if not _can_manage_todo(todo, current_user, _is_manager(current_user)):
            frappe.throw(_("You don't have permission to update this todo"))
        
        # Update fields if provided
        if description is not None:
            todo.description = description
        if priority is not None:
            todo.priority = priority
        if allocated_to is not None and allocated_to != todo.allocated_to:
            # Handing it on. Record who did so, so that person keeps both
            # sight of it and the right to update it afterwards; the creator
            # keeps theirs through `owner`, which never changes.
            # `assigned_by_full_name` follows on its own -- frappe's todo.json
            # fetches it from assigned_by.full_name.
            todo.allocated_to = allocated_to
            todo.assigned_by = current_user
        if date is not None:
            todo.date = date
        if color is not None:
            todo.color = color
        
        todo.save()
        frappe.db.commit()
        
        return {"success": True, "message": "Todo updated successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error updating todo: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def delete_todo(todo_name):
    """Delete a todo"""
    try:
        todo = frappe.get_doc("ToDo", todo_name)
        
        # Check permissions. Deliberately narrower than updating: the ask was
        # that whoever created or assigned a todo keep track of it, not that
        # they be able to destroy it once it is somebody else's. They can still
        # set it to Cancelled through update_todo. Widening this to
        # _can_manage_todo is a one-line change if that is what is wanted.
        current_user = frappe.session.user
        
        if not _is_manager(current_user) and todo.allocated_to != current_user:
            frappe.throw(_("You don't have permission to delete this todo"))
        
        frappe.delete_doc("ToDo", todo_name)
        frappe.db.commit()
        
        return {"success": True, "message": "Todo deleted successfully"}
        
    except Exception as e:
        frappe.log_error(f"Error deleting todo: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def get_daily_metrics():
    """Get daily metrics for the todo dashboard"""
    try:
        # Get current user and permissions
        current_user = frappe.session.user
        is_manager = frappe.db.exists("Has Role", {
            "parent": current_user,
            "role": ["in", ["System Manager", "Administrator"]]
        })
        
        # Get today's date in server timezone
        today = frappe.utils.getdate(frappe.utils.today())
        
        # Base filters based on user permissions
        base_filters = {}
        if not is_manager:
            base_filters["allocated_to"] = current_user
        
        # Calculate metrics
        metrics = {
            "created": 0,
            "completed": 0, 
            "cancelled": 0,
            "active": 0
        }
        
        # Created today - todos created today
        created_filters = base_filters.copy()
        created_filters["creation"] = [">=", today]
        metrics["created"] = frappe.db.count("ToDo", filters=created_filters)
        
        # Completed - todos with Closed status that were modified today (assuming they were closed today)
        completed_filters = base_filters.copy()
        completed_filters["status"] = "Closed"
        completed_filters["modified"] = [">=", today]
        metrics["completed"] = frappe.db.count("ToDo", filters=completed_filters)
        
        # Cancelled - todos with Cancelled status that were modified today (assuming they were cancelled today)
        cancelled_filters = base_filters.copy()
        cancelled_filters["status"] = "Cancelled"
        cancelled_filters["modified"] = [">=", today]
        metrics["cancelled"] = frappe.db.count("ToDo", filters=cancelled_filters)
        
        # Active - todos with Open, Planned, or Backlog status
        active_filters = base_filters.copy()
        active_filters["status"] = ["in", ["Open", "Planned", "Backlog"]]
        metrics["active"] = frappe.db.count("ToDo", filters=active_filters)
        
        # Additional debug info
        debug_info = {
            "today": str(today),
            "user": current_user,
            "is_manager": is_manager,
            "timezone": frappe.utils.get_system_timezone()
        }
        
        return {
            "success": True,
            "metrics": metrics,
            "debug": debug_info
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting daily metrics: {str(e)}")
        return {
            "success": False, 
            "message": str(e),
            "metrics": {
                "created": 0,
                "completed": 0,
                "cancelled": 0, 
                "active": 0
            }
        }
