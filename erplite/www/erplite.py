import frappe
from frappe import _
import json
from datetime import datetime, date


def serialize_for_json(obj):
	"""Recursively convert datetime objects to strings for JSON serialization"""
	if isinstance(obj, (datetime, date)):
		return obj.isoformat() if obj else None
	elif isinstance(obj, dict):
		return {key: serialize_for_json(value) for key, value in obj.items()}
	elif isinstance(obj, list):
		return [serialize_for_json(item) for item in obj]
	else:
		return obj


def get_context(context):
	"""Get context for the ERPLite Vue app"""
	
	# Check if user is logged in
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to access ERPLite"), frappe.PermissionError)
	
	# Set basic context
	context.no_cache = 1
	context.show_sidebar = False
	
	# Add boot data for Vue app
	boot = frappe._dict()
	
	# Add user info
	boot.user = frappe.session.user
	user_doc = frappe.get_doc("User", frappe.session.user)
	boot.user_info = serialize_for_json(user_doc.as_dict())
	
	# Add site config
	boot.site_name = frappe.local.site
	boot.csrf_token = frappe.sessions.get_csrf_token()
	
	# Add system settings
	boot.system_settings = serialize_for_json(frappe.get_single("System Settings").as_dict())
	
	# Add ERPLite specific settings
	boot.erplite_settings = {
		"app_name": "ERPLite",
		"version": "1.0.0"
	}
	
	# Serialize the entire boot object
	context.boot = serialize_for_json(boot)
	
	return context


@frappe.whitelist(allow_guest=False)
def get_context_for_dev():
	"""Get context for development mode"""
	
	# This endpoint is called by the Vue frontend in development mode
	# to get the boot data and CSRF token
	
	boot = frappe._dict()
	
	# Add user info
	boot.user = frappe.session.user
	user_doc = frappe.get_doc("User", frappe.session.user)
	boot.user_info = serialize_for_json(user_doc.as_dict())
	
	# Add site config
	boot.site_name = frappe.local.site
	boot.csrf_token = frappe.sessions.get_csrf_token()
	
	# Add system settings
	boot.system_settings = serialize_for_json(frappe.get_single("System Settings").as_dict())
	
	# Add ERPLite specific settings
	boot.erplite_settings = {
		"app_name": "ERPLite",
		"version": "1.0.0"
	}
	
	return serialize_for_json(boot)
