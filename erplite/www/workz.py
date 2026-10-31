import frappe


def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login?redirect-to=/workz'
        raise frappe.Redirect
    context.no_cache = 1
    context.workz_boot = {'user': frappe.session.user, 'csrf_token': frappe.sessions.get_csrf_token()}
