"""Real Frappe WSGI/DB security regression; disposable local synthetic sites only.

Run with the parent's isolated Frappe environment, setting SITE and SITES_PATH.
Creates uniquely named synthetic fixtures. Never reads production credentials.
"""
import json
import os
import secrets
from pathlib import Path
from urllib.parse import quote


def run():
    import frappe
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    from frappe.app import application
    from frappe.utils.password import set_encrypted_password
    from erplite.workz.api import run as workz

    site = os.environ['SITE']
    sites_path = os.environ['SITES_PATH']
    assert site == 'office-test.local' or site.startswith('workz-synthetic')
    assert Path(sites_path).resolve().is_relative_to(Path('/tmp'))
    os.chdir(sites_path)
    results = []
    prefix = 'scope-' + secrets.token_hex(4)
    tokens = {}

    def connect():
        frappe.init(site=site, sites_path=sites_path)
        # This suite is never allowed to use the remote rehearsal DB network.
        assert frappe.conf.get('db_host', '127.0.0.1') in ('127.0.0.1', 'localhost')
        frappe.connect()
        frappe.set_user('Administrator')
        frappe.local.request = frappe._dict(method='POST')

    def call(action, **payload):
        return workz(action, payload)

    connect()
    people = {role: f'{prefix}-{role}@example.invalid'
              for role in ('alice', 'bob', 'lead', 'approver', 'admin', 'unmapped')}
    for role, user in people.items():
        doc = frappe.get_doc({'doctype': 'User', 'email': user,
                              'first_name': f'Synthetic {role}', 'enabled': 1,
                              'send_welcome_email': 0,
                              'roles': [{'role': 'System Manager' if role == 'admin' else 'Projects User'}]
                              if role != 'unmapped' else []})
        doc.insert(ignore_permissions=True)
        key, secret = secrets.token_hex(12), secrets.token_hex(20)
        frappe.db.set_value('User', user, 'api_key', key)
        set_encrypted_password('User', user, secret, 'api_secret')
        tokens[role] = f'token {key}:{secret}'
    project = call('save_project', project_name=prefix, status='Open',
                   project_lead=people['lead'], timesheet_approver=people['approver'])['name']
    activity = call('save_activity', project=project, activity_name=prefix, status='Open')['name']
    call('assignment', activity=activity, employee=people['alice'], assigned=True)
    assignment = frappe.db.get_value('ToDo', {'reference_type': 'Activity',
                'reference_name': activity, 'allocated_to': people['alice']}, 'name')
    frappe.set_user(people['alice'])
    plan = call('save_plan', user=people['alice'], project=project, activity=activity,
                kind='Work', title='Synthetic scoped work', timezone='UTC',
                plan_start='2035-01-08T09:00:00Z', plan_end='2035-01-08T10:00:00Z')['name']
    time = call('save_time', employee=people['alice'], project=project, activity=activity,
                description='Synthetic scoped time', check_in_time='2035-01-08T09:00:00Z',
                check_out_time='2035-01-08T10:00:00Z')['name']
    frappe.set_user('Administrator')
    records = {'Project': project, 'Activity': activity, 'ToDo': assignment,
               'Planner Entry': plan, 'Timesheet Entry': time}
    attachments = []
    for dt, name in records.items():
        file = frappe.get_doc({'doctype': 'File', 'file_name': prefix + '-' + dt + '.txt',
                              'content': 'synthetic-private-' + prefix,
                              'is_private': 1, 'attached_to_doctype': dt,
                              'attached_to_name': name}).insert(ignore_permissions=True)
        attachments.append((file.name, file.file_url))
        frappe.get_doc({'doctype': 'DocShare', 'share_doctype': 'File',
                       'share_name': file.name, 'user': people['bob'],
                       'read': 1, 'write': 1, 'share': 1}).insert(ignore_permissions=True)
    # Direct insertion deliberately models old/adversarial ACLs. No permission
    # enforcement should trust a share merely because it already exists.
    shares = []
    for dt, name in records.items():
        for user in (people['bob'], people['unmapped']):
            share = frappe.get_doc({'doctype': 'DocShare', 'share_doctype': dt,
                        'share_name': name, 'user': user, 'read': 1, 'write': 1, 'share': 1})
            share.insert(ignore_permissions=True)
            shares.append(share.name)
    for dt in ('Planner Entry', 'Timesheet Entry'):
        for role in (('lead', 'approver') if dt == 'Planner Entry' else ('approver',)):
            frappe.get_doc({'doctype': 'DocShare', 'share_doctype': dt,
                           'share_name': records[dt], 'user': people[role], 'read': 1}).insert(ignore_permissions=True)
    frappe.db.commit()
    frappe.destroy()

    try:
        client = Client(application, Response, use_cookies=False)
    
        def request(role, path, method='GET', payload=None, expected=(200,)):
            headers = {'Accept': 'application/json'}
            if role:
                headers['Authorization'] = tokens[role]
            response = client.open(path, method=method, json=payload,
                                   base_url='http://' + site, headers=headers)
            status = response.status_code
            # Never print request headers, credentials or complete response payloads.
            assert status in expected, (role, method, path, status,
                                        (response.get_json(silent=True) or {}).get('exc_type'))
            results.append({'actor': role or 'Guest', 'method': method, 'path': path, 'status': status})
            return response
    
        denied = (403,)
        for dt, name in records.items():
            for role in ('bob', 'unmapped', None):
                for root in ('/api/resource/', '/api/v1/resource/', '/api/v2/document/'):
                    request(role, root + quote(dt) + '/' + quote(name), expected=denied)
                request(role, '/api/method/frappe.client.get', 'POST',
                        {'doctype': dt, 'name': name}, expected=denied)
            # Explicit hostile write/share grants must not confer mutation rights.
            request('bob', '/api/resource/' + quote(dt) + '/' + quote(name), 'PUT',
                    {'description': 'forbidden edit'}, expected=denied)
            request('bob', '/api/method/frappe.share.add', 'POST',
                    {'doctype': dt, 'name': name, 'user': people['unmapped'], 'read': 1}, expected=denied)
            request('admin', '/api/resource/' + quote(dt) + '/' + quote(name))
            # Normal list and count paths must never surface a forbidden shared row.
            for path in ('/api/resource/' + quote(dt), '/api/v2/document/' + quote(dt),
                         '/api/v2/doctype/' + quote(dt) + '/count'):
                response = request('bob', path, expected=(200, 403))
                assert name not in response.get_data(as_text=True), (dt, path, 'shared row escaped')
            for method, payload in (
                ('frappe.desk.search.search_link', {'doctype': dt, 'txt': name}),
                ('frappe.desk.reportview.export_query', {'doctype': dt, 'fields': ['name'],
                     'file_format_type': 'CSV', 'filters': [['name', '=', name]]}),
            ):
                response = request('bob', '/api/method/' + method, 'POST', payload, expected=(200, 403))
                assert name not in response.get_data(as_text=True), (dt, method, 'shared row escaped')
            for method in ('frappe.client.get_list', 'frappe.client.get_count'):
                response = request('bob', '/api/method/' + method, 'POST',
                                    {'doctype': dt}, expected=(200, 403))
                if response.status_code == 200:
                    value = (response.get_json() or {}).get('message')
                    assert value in ([], 0), (dt, method, value)
    
        for name, url in attachments:
            request('bob', '/api/resource/File/' + quote(name), expected=denied)
            request('bob', url, expected=denied)
            request('admin', url)
            request('bob', '/api/resource/File/' + quote(name), 'PUT',
                    {'attached_to_doctype': None, 'attached_to_name': None}, expected=denied)
        request('bob', '/api/resource/ToDo/' + assignment, 'PUT',
                {'reference_type': None, 'reference_name': None, 'allocated_to': people['bob']}, expected=denied)
        for dt in ('ToDo', 'Planner Entry', 'Timesheet Entry'):
            request('alice', '/api/resource/' + quote(dt) + '/' + quote(records[dt]))
        for role in ('lead', 'approver'):
            for dt in ('Project', 'Activity', 'ToDo', 'Planner Entry'):
                request(role, '/api/resource/' + quote(dt) + '/' + quote(records[dt]))
        request('approver', '/api/resource/Timesheet%20Entry/' + time)
        request('lead', '/api/resource/Timesheet%20Entry/' + time, expected=denied)
    
        legacy = 'erplite.projects.api.get_timesheet_users'
        for role in ('alice', 'bob', 'approver', None):
            for root in ('/api/method/', '/api/v1/method/', '/api/v2/method/'):
                request(role, root + legacy, expected=denied)
            request(role, '/api/v2/method/Activity/get_activity_summary', expected=denied)
            request(role, '/api/method/frappe.ping', 'POST', {'cmd': legacy}, expected=denied)
            request(role, '/', 'POST', {'cmd': legacy}, expected=denied)
            for wrapper in ('frappe.call', 'frappe.utils.call'):
                request(role, '/api/method/' + wrapper, 'POST', {'fn': legacy}, expected=denied)
        request('admin', '/api/method/' + legacy)
    
        # Exercise the public Workz dispatcher as well as generic record paths.
        endpoint = '/api/method/erplite.workz.api.run'
        period = {'start': '2035-01-01T00:00:00Z', 'end': '2035-02-01T00:00:00Z'}
        for action in ('context', 'plans', 'times', 'report'):
            request('alice', endpoint, 'POST', {'action': action, 'payload': period})
            response = request('bob', endpoint, 'POST', {'action': action, 'payload': period})
            assert time not in response.get_data(as_text=True)
            assert plan not in response.get_data(as_text=True)
        for status, actor in (('Submitted', 'alice'), ('Approved', 'approver')):
            current = request('alice', '/api/resource/Timesheet%20Entry/' + time).get_json()['data']
            request(actor, endpoint, 'POST', {'action': 'transition', 'payload': {
                    'name': time, 'modified': current['modified'], 'status': status}})
            request('alice', '/api/resource/Timesheet%20Entry/' + time, 'PUT',
                    {'description': 'edit locked history'}, expected=denied)
            request('alice', '/api/resource/Timesheet%20Entry/' + time, 'DELETE', expected=denied)
        # Processed is import-only; seed it directly as a synthetic historical row.
        connect()
        frappe.db.set_value('Timesheet Entry', time, 'status', 'Processed')
        frappe.db.commit()
        frappe.destroy()
        request('alice', '/api/resource/Timesheet%20Entry/' + time, 'PUT',
                {'description': 'edit processed history'}, expected=denied)
        request('alice', '/api/resource/Timesheet%20Entry/' + time, 'DELETE', expected=denied)
    
        for role in ('alice', 'bob', 'lead', 'approver', 'unmapped', None):
            for method, payload in (
                ('realtime_user_info', {}),
                ('realtime_doc', {'doctype': 'Timesheet Entry', 'docname': time}),
                ('realtime_doctype', {'doctype': 'Timesheet Entry'}),
            ):
                request(role, '/api/method/erplite.workz.boundary.' + method,
                        'POST', payload, expected=denied)
        request('admin', '/api/method/erplite.workz.boundary.realtime_user_info', expected=denied)
    
        # All-user shares and stale shares after leadership revocation are also
        # adversarial. Restore the role after the assertion for independent tests.
        connect()
        frappe.db.set_value('Project', project, 'project_lead', people['bob'])
        frappe.db.commit()
        frappe.destroy()
        request('bob', '/api/resource/Project/' + project)
        connect()
        frappe.db.set_value('Project', project, 'project_lead', people['lead'])
        for dt, name in records.items():
            frappe.get_doc({'doctype': 'DocShare', 'share_doctype': dt, 'share_name': name,
                            'everyone': 1, 'read': 1, 'write': 1, 'share': 1}).insert(ignore_permissions=True)
        frappe.db.commit()
        frappe.destroy()
        for dt, name in records.items():
            request('bob', '/api/resource/' + quote(dt) + '/' + quote(name), expected=denied)
            response = request('bob', '/api/resource/' + quote(dt), expected=(200, 403))
            assert name not in response.get_data(as_text=True)
    
        print(json.dumps({'suite': 'frappe_scope_security', 'checks': len(results),
                          'result': 'passed', 'site': site}))
        return results
    finally:
        # Everyone shares must not poison unrelated tests on the shared
        # disposable site after this suite exits (including failed assertions).
        connect()
        for dt, name in list(records.items()) + [('File', name) for name, _ in attachments]:
            frappe.db.delete('DocShare', {'share_doctype': dt, 'share_name': name})
        frappe.db.commit()
        frappe.destroy()


if __name__ == '__main__':
    run()
