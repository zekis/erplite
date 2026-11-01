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
    form = getattr(frappe.local, 'form_dict', {}) or {}
    commands = [form.get('cmd', '')]
    path = request.path
    for prefix in ('/api/method/', '/api/v1/method/', '/api/v2/method/'):
        if path.startswith(prefix):
            commands.append(path[len(prefix):].split('/')[0])
            break
    # Reject legacy namespaces through both direct RPC and call wrappers. The
    # v2 controller shorthand resolves <doctype>/<method> to its module path.
    if any(command in ('frappe.call', 'frappe.utils.call') for command in commands):
        commands.append(form.get('fn', ''))
    if path.startswith('/api/v2/method/'):
        suffix = path[len('/api/v2/method/'):].split('/')
        if len(suffix) == 2:
            from frappe.modules.utils import load_doctype_module
            commands.append(load_doctype_module(suffix[0]).__name__ + '.' + suffix[1])
    for candidate in commands:
        if not isinstance(candidate, str):
            p.require(False, 'Invalid RPC method')
        parts = candidate.split('.')
        if parts[:2] in (['erplite', 'projects'], ['erplite', 'scheduler']) or parts[:3] == ['erplite', 'www', 'erplite']:
            p.require(p.admin(), 'Use your authorised Workz workspace for this action.')


def enforce_scope(allowed):
    """A False hook result is overridable by Frappe's DocShare fallback."""
    p.require(allowed, 'This record is outside your authorised Workz scope')
    return True


def check_shared_scope(doctype, actor):
    """Fail closed before Frappe ORs shares around query conditions.

    Existing shares can survive assignment/role revocation. Do not silently
    broaden lists, counts or exports in that case. Workz's scoped projections
    remain available; an administrator can remove the conflicting share.
    """
    if mapped(actor) and (actor == 'Administrator' or 'System Manager' in frappe.get_roles(actor)):
        return
    from erplite.workz.guards import time_permission, plan_permission
    permission = {'Project': project_permission, 'Activity': activity_permission,
                  'ToDo': assignment_permission, 'Timesheet Entry': time_permission,
                  'Planner Entry': plan_permission, 'File': file_permission}[doctype]
    # get_all is intentional: checking the ACL itself must not recurse through
    # permission_query_conditions or hide everyone-shares from this check.
    names = frappe.get_all('DocShare', filters={'share_doctype': doctype, 'read': 1},
                           or_filters={'user': actor, 'everyone': 1}, pluck='share_name', limit_page_length=0)
    for name in set(names):
        permission(frappe.get_doc(doctype, name), actor, 'read')


def project_permission(doc, user=None, ptype=None):
    actor = user or frappe.session.user
    if not mapped(actor):
        return enforce_scope(False)
    if actor == 'Administrator' or 'System Manager' in frappe.get_roles(actor):
        return None
    # Ordinary staff get the minimal context projection, not full project
    # documents containing business/financial metadata or other assignments.
    return enforce_scope(bool(doc and actor in (doc.project_lead, doc.timesheet_approver)) and ptype in ('read', 'select', 'print', 'email', 'export', 'report'))


def project_query(user=None):
    actor = user or frappe.session.user
    check_shared_scope('Project', actor)
    return _project_scope(actor)


def _project_scope(actor):
    if not mapped(actor):
        return '1=0'
    if actor == 'Administrator' or 'System Manager' in frappe.get_roles(actor):
        return ''
    escaped = frappe.db.escape(actor)
    return f'(`tabProject`.project_lead={escaped} OR `tabProject`.timesheet_approver={escaped})'


def activity_permission(doc, user=None, ptype=None):
    actor = user or frappe.session.user
    if not mapped(actor):
        return enforce_scope(False)
    if actor == 'Administrator' or 'System Manager' in frappe.get_roles(actor):
        return None
    project = frappe.get_doc('Project', doc.project)
    return enforce_scope(actor in (project.project_lead, project.timesheet_approver) and ptype in ('read', 'select', 'print', 'email', 'export', 'report'))


def activity_query(user=None):
    actor = user or frappe.session.user
    check_shared_scope('Activity', actor)
    query = _project_scope(actor)
    return query if query in ('', '1=0') else '`tabActivity`.project IN (SELECT name FROM `tabProject` WHERE ' + query + ')'


def assignment_permission(doc, user=None, ptype=None):
    old = frappe.db.get_value('ToDo', doc.name, ['reference_type', 'reference_name', 'allocated_to'], as_dict=True) if doc.name else None
    if old and old.reference_type == 'Activity':
        enforce_scope(all(doc.get(key) == old.get(key) for key in ('reference_type', 'reference_name', 'allocated_to')))
    if doc.reference_type != 'Activity':
        return None
    actor = user or frappe.session.user
    if not mapped(actor):
        return enforce_scope(False)
    if actor == 'Administrator' or 'System Manager' in frappe.get_roles(actor):
        return None
    if doc.allocated_to == actor:
        return enforce_scope(ptype in ('read', 'select', 'print', 'email', 'export', 'report'))
    activity = frappe.get_doc('Activity', doc.reference_name)
    project = frappe.get_doc('Project', activity.project)
    return enforce_scope(ptype in ('read', 'select', 'print', 'email', 'export', 'report') and actor in (project.project_lead, project.timesheet_approver))


def assignment_query(user=None):
    actor = user or frappe.session.user
    check_shared_scope('ToDo', actor)
    scope = _project_scope(actor)
    if scope in ('', '1=0'):
        return scope
    value = frappe.db.escape(actor)
    return "(`tabToDo`.reference_type != 'Activity' OR `tabToDo`.allocated_to=" + value + " OR `tabToDo`.reference_name IN (SELECT name FROM `tabActivity` WHERE project IN (SELECT name FROM `tabProject` WHERE " + scope + ')))'


WORK_RECORDS = ('Project', 'Activity', 'ToDo', 'Planner Entry', 'Timesheet Entry')


def file_permission(doc, user=None, ptype=None):
    """File ownership/sharing must not bypass an attached record's scope."""
    old = frappe.db.get_value('File', doc.name, ['attached_to_doctype', 'attached_to_name'], as_dict=True) if doc.name else None
    if old and old.attached_to_doctype in WORK_RECORDS and old.attached_to_name:
        if (doc.attached_to_doctype, doc.attached_to_name) != (old.attached_to_doctype, old.attached_to_name):
            # Check the old parent too: relinking cannot erase its boundary.
            previous = frappe._dict(attached_to_doctype=old.attached_to_doctype,
                                    attached_to_name=old.attached_to_name, name=None)
            file_permission(previous, user=user, ptype=ptype)
    if doc.attached_to_doctype not in WORK_RECORDS or not doc.attached_to_name:
        return None
    from erplite.workz.guards import time_permission, plan_permission
    permission = {'Project': project_permission, 'Activity': activity_permission,
                  'ToDo': assignment_permission, 'Timesheet Entry': time_permission,
                  'Planner Entry': plan_permission}[doc.attached_to_doctype]
    parent = frappe.get_doc(doc.attached_to_doctype, doc.attached_to_name)
    permission(parent, user=user, ptype=ptype)
    # Leave Frappe's existing File policy in force for records within scope.
    return None


def file_query(user=None):
    actor = user or frappe.session.user
    if mapped(actor) and (actor == 'Administrator' or 'System Manager' in frappe.get_roles(actor)):
        return ''
    check_shared_scope('File', actor)
    from erplite.workz.guards import time_query, plan_query
    queries = {'Project': _project_scope(actor), 'Activity': activity_query(actor),
               'ToDo': assignment_query(actor), 'Timesheet Entry': time_query(actor),
               'Planner Entry': plan_query(actor)}
    excluded = ','.join(frappe.db.escape(dt) for dt in WORK_RECORDS)
    clauses = [f"COALESCE(`tabFile`.attached_to_doctype,'') NOT IN ({excluded})"]
    for dt, query in queries.items():
        clauses.append('(`tabFile`.attached_to_doctype=' + frappe.db.escape(dt) +
                       f' AND `tabFile`.attached_to_name IN (SELECT name FROM `tab{dt}` WHERE ' +
                       (query or '1=1') + '))')
    return '(' + ' OR '.join(clauses) + ')'


def deny_realtime():
    # Frappe v15 has no per-message authorization or room revocation. Allowing
    # even an administrator to connect leaves a live channel after demotion.
    # Workz uses scoped HTTP polling; all human sockets fail closed until the
    # server can enforce revocation. Restart realtime on initial rollout.
    p.require(False, 'This workspace uses authenticated polling.')


@frappe.whitelist(allow_guest=True)
def realtime_user_info():
    deny_realtime()


@frappe.whitelist(allow_guest=True)
def realtime_doc(doctype, docname):
    deny_realtime()


@frappe.whitelist(allow_guest=True)
def realtime_doctype(doctype):
    deny_realtime()


def private_attachment(doc, method=None):
    # Public files are served outside Python permission checks. Work records
    # may only attach private blobs, including after an is_private edit.
    if doc.attached_to_doctype in WORK_RECORDS and not doc.is_folder:
        enforce_scope(bool(doc.is_private))


def no_scoped_cache(response, request):
    # Default private downloads can otherwise outlive a revoked permission in
    # a browser/proxy cache. This policy also works without Office installed.
    if request.path.startswith(('/api/', '/private/files/', '/workz', '/erplite')):
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Pragma'] = 'no-cache'
        response.vary.add('Cookie')
        response.vary.add('Authorization')
