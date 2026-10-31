
__version__ = "0.0.1"


def check_app_permission():
	import frappe
	if frappe.session.user == "Administrator":
		return True

	return frappe.session.user != "Guest" and bool(set(frappe.get_roles()) & {"System Manager", "Projects Manager", "Projects User"})