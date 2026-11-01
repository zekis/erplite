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
            self.assertFalse(self.boundary.project_permission(project,user,'read'))
            self.assertFalse(self.boundary.activity_permission(activity,user,'read'))
        self.assertTrue(self.boundary.project_permission(project,'approver','read'))
        self.assertIn('project_lead',self.boundary.project_query('alice'))
        self.assertEqual(self.boundary.project_query('Guest'),'1=0')
        self.assertIsNone(self.boundary.project_permission(project,'Administrator','read'))

    def test_agent_reader_cannot_acquire_human_workz_authority(self):
        self.s.f.conf={'office_agent_file_readers':{'virtual-agent':'alice'}}
        self.s.as_user('alice')
        with self.assertRaises(Rejected):self.office.capabilities()
