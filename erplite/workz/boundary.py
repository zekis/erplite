"""Legacy API isolation while the scoped Workz API serves human work views."""
import frappe
from erplite.workz import policy as p


def mapped(actor):
    readers = (getattr(frappe, 'conf', {}) or {}).get('office_agent_file_readers', {})
    return bool(actor and actor != 'Guest' and actor not in readers.values()
                and frappe.db.get_value('User', actor, 'enabled')
                and {'System Manager','Projects User','Projects Manager'}.intersection(frappe.get_roles(actor)))


def before_request():
    request = getattr(frappe.local, 'request', None)
    if not request:
        return
    command = (getattr(frappe.local, 'form_dict', {}) or {}).get('cmd', '')
    path = request.path
    for prefix in ('/api/method/', '/api/v1/method/', '/api/v2/method/'):
        if path.startswith(prefix):
            command = path[len(prefix):]
            break
    # Old RPCs include elevated SQL/get_all reads. Do not expose those to staff
    # simply because a newer browser uses the scoped Workz endpoints.
    parts = command.split('.')
    if parts[:2] in (['erplite','projects'], ['erplite','scheduler']) or parts[:3] == ['erplite','www','erplite']:
        p.require(p.admin(), 'Use your authorised Workz workspace for this action.')


def project_permission(doc, user=None, ptype=None):
    actor = user or frappe.session.user
    if not mapped(actor):
        return False
    if actor == 'Administrator' or 'System Manager' in frappe.get_roles(actor):
        return None
    # Ordinary staff get the minimal context projection, not full project
    # documents containing business/financial metadata or other assignments.
    return bool(doc and actor in (doc.project_lead, doc.timesheet_approver)) and ptype == 'read'


def project_query(user=None):
    actor = user or frappe.session.user
    if not mapped(actor):
        return '1=0'
    if actor == 'Administrator' or 'System Manager' in frappe.get_roles(actor):
        return ''
    escaped = frappe.db.escape(actor)
    return f'(`tabProject`.project_lead={escaped} OR `tabProject`.timesheet_approver={escaped})'


def activity_permission(doc, user=None, ptype=None):
    actor = user or frappe.session.user
    if not mapped(actor):
        return False
    if actor == 'Administrator' or 'System Manager' in frappe.get_roles(actor):
        return None
    project = frappe.get_doc('Project', doc.project)
    return actor in (project.project_lead, project.timesheet_approver) and ptype == 'read'


def activity_query(user=None):
    query = project_query(user)
    return query if query in ('', '1=0') else '`tabActivity`.project IN (SELECT name FROM `tabProject` WHERE ' + query + ')'


def assignment_permission(doc, user=None, ptype=None):
    if doc.reference_type != 'Activity':
        return None
    actor = user or frappe.session.user
    if not mapped(actor):
        return False
    if actor == 'Administrator' or 'System Manager' in frappe.get_roles(actor):
        return None
    if doc.allocated_to == actor:
        return ptype == 'read'
    activity = frappe.get_doc('Activity', doc.reference_name)
    project = frappe.get_doc('Project', activity.project)
    return ptype == 'read' and actor in (project.project_lead, project.timesheet_approver)


def assignment_query(user=None):
    actor = user or frappe.session.user
    scope = project_query(actor)
    if scope in ('', '1=0'):
        return scope
    value = frappe.db.escape(actor)
    return "(`tabToDo`.reference_type != 'Activity' OR `tabToDo`.allocated_to=" + value + " OR `tabToDo`.reference_name IN (SELECT name FROM `tabActivity` WHERE project IN (SELECT name FROM `tabProject` WHERE " + scope + ')))'
