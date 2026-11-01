"""Rollback-only plan privacy checks on the existing disposable local site.

SITE=workz-synthetic-office.local SITES_PATH=/tmp/.../sites PYTHONPATH=$PWD \
    /tmp/.../env/bin/python tests/workz/frappe_plan_detail_smoke.py
"""
import os
from pathlib import Path

import frappe

site = os.environ['SITE']
sites = Path(os.environ['SITES_PATH']).resolve()
assert site.startswith('workz-synthetic') and sites.is_relative_to('/tmp')
os.chdir(sites)
frappe.init(site=site, sites_path=str(sites))
assert frappe.conf.get('db_host', '127.0.0.1') in ('127.0.0.1', 'localhost')
frappe.connect()
frappe.set_user('Administrator')
frappe.local.request = frappe._dict(method='POST')
from erplite.workz.api import run


def denied(fn, error=frappe.PermissionError):
    try:
        fn()
    except error:
        return
    raise AssertionError('Expected denial')


try:
    prefix = 'detail-' + frappe.generate_hash(length=8)
    users = {}
    for role in ('owner', 'lead', 'approver', 'other', 'admin'):
        email = f'{prefix}-{role}@example.invalid'
        frappe.get_doc(dict(doctype='User', email=email, first_name=role,
            enabled=1, send_welcome_email=0,
            roles=[dict(role='System Manager' if role == 'admin' else 'Projects User')]
        )).insert(ignore_permissions=True)
        users[role] = email
    project = run('save_project', dict(project_name=prefix, status='Open',
        project_lead=users['lead'], timesheet_approver=users['approver']))['name']
    activity = run('save_activity', dict(project=project, activity_name=prefix, status='Open'))['name']
    run('assignment', dict(activity=activity, employee=users['owner'], assigned=True))
    frappe.set_user(users['owner'])
    plan = run('save_plan', dict(user=users['owner'], project=project, activity=activity,
        title='Private fixture', kind='Work', timezone='UTC', notes='Private notes',
        plan_start='2037-01-07T09:00:00Z', plan_end='2037-01-07T10:00:00Z'))
    detail = lambda: run('plan_detail', dict(name=plan['name']))
    for role in ('owner', 'admin'):
        frappe.set_user(users[role])
        current = detail()
        assert current['notes_editable'] and current['notes'] == 'Private notes'
    for role in ('lead', 'approver'):
        frappe.set_user(users[role])
        current = detail()
        assert not current['notes_editable'] and 'notes' not in current
    frappe.set_user(users['other'])
    denied(detail)
    frappe.set_user(users['lead'])
    before = detail()
    updated = run('save_plan', {**before, 'title': 'Allocation changed'})
    assert 'notes' not in updated and not updated['notes_editable']
    for value in ('overwrite', '', None):
        denied(lambda: run('save_plan', {**updated, 'notes': value}))
    denied(lambda: run('save_plan', before), frappe.TimestampMismatchError)
    assert frappe.db.get_value('Planner Entry', plan['name'], 'notes') == 'Private notes'
    doc = frappe.get_doc('Planner Entry', plan['name'])
    doc.notes = 'Direct overwrite'
    doc.status = 'Cancelled'
    denied(lambda: doc.save(ignore_permissions=True))
    frappe.set_user(users['admin'])
    run('save_plan', {**detail(), 'notes': 'Admin revision'})
    frappe.set_user(users['owner'])
    assert detail()['notes'] == 'Admin revision'
    run('save_plan', {**detail(), 'notes': 'Owner revision'})
    for role, field in (('lead', 'project_lead'), ('approver', 'timesheet_approver')):
        frappe.db.set_value('Project', project, field, users['other'])
        frappe.set_user(users[role])
        denied(detail)
    frappe.set_user(users['owner'])
    frappe.db.set_value('User', users['owner'], 'enabled', 0)
    denied(detail)
    print('PASS: real Frappe owner/admin, shared redaction, unrelated denial, note guards, omission, stale token and revocation')
finally:
    frappe.db.rollback()
    frappe.destroy()
