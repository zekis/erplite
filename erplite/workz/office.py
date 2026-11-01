"""Versioned, same-origin Office embedding. This grants no data permissions."""
import frappe
from erplite.workz import policy

CONTRACT = 1
ROUTES = {
    'projects': '/projects', 'planning': '/planning', 'timesheets': '/timesheet',
    'approvals': '/timesheet/approvals', 'reports': '/timesheet/reports',
}


def capabilities():
    policy.user()
    from erplite.workz.api import context
    ctx = context({})
    routes = dict(ROUTES)
    if not ctx['admin'] and not ctx['approval_projects']:
        routes.pop('approvals')
    return {'version': CONTRACT, 'routes': routes, 'user': ctx['user']}


def shell_available():
    try:
        from tm_office.integration import CONTRACT as shell_contract
    except ImportError:
        return False
    return shell_contract == CONTRACT


def office_destination(path, query=''):
    section = next((key for key, value in ROUTES.items() if path == value), None)
    if path in ('/', '', '/todos', '/timesheet/assignments'):
        section = 'projects' if path != '/' else 'office'
    if not section:
        return None
    from urllib.parse import parse_qsl, urlencode
    allowed = {'date', 'view', 'employee', 'project'}
    params = urlencode([(k, v) for k, v in parse_qsl(query) if k in allowed])
    return '/virtual-office#/' + section + ('?' + params if params else '')
