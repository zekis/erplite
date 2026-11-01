import frappe
from erplite.workz.office import CONTRACT, capabilities, shell_available, office_destination

no_cache = 1


def get_context(context):
    if frappe.session.user == 'Guest':
        from urllib.parse import quote
        frappe.local.flags.redirect_location = '/login?redirect-to=' + quote(frappe.request.path, safe='')
        raise frappe.Redirect
    access = capabilities()
    embedded = frappe.form_dict.get('office') == str(CONTRACT)
    if embedded:
        if frappe.request.path.removeprefix('/workz') not in access['routes'].values():
            frappe.throw('This workspace is not available to you.', frappe.PermissionError)
        if not shell_available():
            frappe.throw('The Office and Workz versions are incompatible.', frappe.PermissionError)
    elif shell_available():
        destination = office_destination(frappe.request.path.removeprefix('/workz'), frappe.request.query_string.decode())
        if destination:
            frappe.local.flags.redirect_location = destination
            raise frappe.Redirect
    context.no_cache = 1
    context.workz_boot = {'user': frappe.session.user, 'csrf_token': frappe.sessions.get_csrf_token(),
                          'office_contract': CONTRACT if embedded else None, 'routes': access['routes']}
