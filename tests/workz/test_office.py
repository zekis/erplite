"""Synthetic contract, legacy boundary and direct-record policy tests."""
import importlib
import unittest
from fake_site import Site, Rejected, Row


class Office(unittest.TestCase):
    def setUp(self):
        self.s = Site()
        for user in ('Administrator', 'alice', 'bob', 'approver', 'lead'):
            self.s.seed('User', user, enabled=1, full_name=user)
        self.s.seed('Project','P',project_name='P',status='Open',project_lead='lead',timesheet_approver='approver')
        self.s.seed('Activity','A',activity_name='A',project='P',status='Open')
        self.s.call('assignment',dict(activity='A',employee='alice',assigned=True))
        import erplite.workz.office, erplite.workz.boundary
        self.office = importlib.reload(erplite.workz.office)
        self.boundary = importlib.reload(erplite.workz.boundary)

    def test_contract_only_exposes_approval_view_to_scoped_approver(self):
        self.s.as_user('alice')
        self.assertEqual(self.office.capabilities()['version'], 2)
        self.assertNotIn('approvals',self.office.capabilities()['routes'])
        self.s.as_user('approver')
        self.assertIn('approvals',self.office.capabilities()['routes'])
        self.s.as_user('Administrator')
        self.assertIn('approvals',self.office.capabilities()['routes'])

    def test_bookmarks_preserve_supported_context(self):
        self.assertEqual(self.office.office_destination('/planning','date=2030-01-01&project=P&office=1&evil=x'),
                         '/virtual-office#/planning?date=2030-01-01&project=P')
        self.assertEqual(self.office.office_destination('/timesheet/approvals'),'/virtual-office#/approvals')
        self.assertIsNone(self.office.office_destination('/settings'))

    def test_legacy_rpc_cannot_bypass_scoped_workz(self):
        for user in ('alice','bob','approver','Guest'):
            self.s.as_user(user)
            self.s.f.local = Row(request=Row(path='/api/method/erplite.projects.api.get_all_users'),form_dict={})
            with self.assertRaises(Rejected): self.boundary.before_request()
        self.s.as_user('Administrator')
        self.boundary.before_request()
        self.s.as_user('alice')
        self.s.f.local.request.path='/api/method/erplite.workz.api.run'
        self.boundary.before_request()

    def test_generic_get_list_and_search_are_not_full_staff_context(self):
        project=self.s.get_doc('Project','P')
        activity=self.s.get_doc('Activity','A')
        for user in ('alice','bob','Guest'):
            with self.assertRaises(Rejected): self.boundary.project_permission(project,user,'read')
            with self.assertRaises(Rejected): self.boundary.activity_permission(activity,user,'read')
        self.assertTrue(self.boundary.project_permission(project,'approver','read'))
        self.assertIn('project_lead',self.boundary.project_query('alice'))
        self.assertEqual(self.boundary.project_query('Guest'),'1=0')
        self.assertIsNone(self.boundary.project_permission(project,'Administrator','read'))

    def test_agent_reader_cannot_acquire_human_workz_authority(self):
        self.s.f.conf={'office_agent_file_readers':{'virtual-agent':'alice'}}
        self.s.as_user('alice')
        with self.assertRaises(Rejected):self.office.capabilities()

    def test_legacy_aliases_and_call_wrappers(self):
        self.s.as_user('alice')
        method = 'erplite.projects.api.get_all_users'
        for path, form in [
            ('/api/v1/method/' + method, {}),
            ('/api/v2/method/' + method, {}),
            ('/', {'cmd': method}),
            ('/api/method/frappe.ping', {'cmd': method}),
            ('/api/method/' + method + '/ignored', {}),
            ('/api/method/frappe.utils.call', {'fn': method}),
            ('/api/v2/method/frappe.call', {'fn': method}),
        ]:
            with self.subTest(path=path):
                self.s.f.local = Row(request=Row(path=path), form_dict=form)
                with self.assertRaises(Rejected): self.boundary.before_request()

    def test_scope_denial_cannot_reach_share_fallback(self):
        project = self.s.get_doc('Project', 'P')
        # Faithful minimal control flow of Frappe's permission fallback. A
        # false-return-only guard would grant this read via the hostile share.
        reached_share = []
        def check():
            allowed = self.boundary.project_permission(project, 'alice', 'read')
            if not allowed:
                reached_share.append(True)
                return True
            return allowed
        with self.assertRaises(Rejected): check()
        self.assertEqual(reached_share, [])
        for right in ('write', 'share', 'print', 'email', 'select'):
            with self.assertRaises(Rejected):
                self.boundary.project_permission(project, 'alice', right)
        with self.assertRaises(Rejected):
            self.boundary.project_permission(project, 'lead', 'share')
        self.assertTrue(self.boundary.project_permission(project, 'lead', 'read'))

    def test_conflicting_read_share_stops_list_scope_or_bypass(self):
        self.s.seed('DocShare', 'hostile', share_doctype='Project',
                    share_name='P', user='alice', read=1)
        with self.assertRaises(Rejected): self.boundary.project_query('alice')
        self.assertIn('project_lead', self.boundary.project_query('lead'))
        self.assertEqual(self.boundary.project_query('Administrator'), '')

    def test_scoped_staff_cannot_join_unscoped_realtime(self):
        for user in ('alice', 'bob', 'lead', 'approver', 'Guest', 'Administrator'):
            self.s.as_user(user)
            with self.assertRaises(Rejected): self.boundary.deny_realtime()

    def test_old_security_contract_cannot_embed(self):
        import sys
        import types
        from unittest.mock import patch
        old = types.ModuleType('tm_office.integration')
        old.CONTRACT = 1
        with patch.dict(sys.modules, {'tm_office.integration': old}):
            self.assertFalse(self.office.shell_available())
            old.CONTRACT = 2
            self.assertTrue(self.office.shell_available())
