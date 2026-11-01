"""Native editor boundary and private-note regression tests."""
import unittest
from unittest.mock import patch

from fake_site import Rejected, Stale
import test_application


class PlanDetail(unittest.TestCase):
    setUp = test_application.Application.setUp
    plan = test_application.Application.plan

    def detail(self, plan):
        return self.s.call('plan_detail', {'name': plan['name']})

    def test_projection_owner_admin_and_redacted_shared_readers(self):
        self.s.as_user('alice')
        plan = self.plan(notes='Private')
        expected = self.s.call('plans', self.range)[0]
        for actor in ('alice', 'Administrator'):
            self.s.as_user(actor)
            self.assertEqual(self.detail(plan), {**expected, 'notes': 'Private', 'notes_editable': True})
        for actor in ('lead', 'approver'):
            self.s.as_user(actor)
            self.assertEqual(self.detail(plan), {**expected, 'notes_editable': False})
        for actor in ('bob', 'stranger', 'Guest', 'missing'):
            self.s.as_user(actor)
            with self.assertRaises(Rejected):
                self.detail(plan)

    def test_authentication_project_permission_and_revocation(self):
        self.s.as_user('alice')
        plan = self.plan(notes='Private')
        with patch.object(self.s.f, 'has_permission', side_effect=Rejected('Project read')) as gate:
            with self.assertRaises(Rejected):
                self.detail(plan)
            gate.assert_called_once_with('Project', 'read', throw=True)
        for actor, field in (('lead', 'project_lead'), ('approver', 'timesheet_approver')):
            self.s.as_user(actor)
            self.detail(plan)
            self.s.data['Project']['P'][field] = 'stranger'
            with self.assertRaises(Rejected):
                self.detail(plan)
        self.s.as_user('alice')
        self.s.data['User']['alice'].enabled = 0
        with self.assertRaises(Rejected):
            self.detail(plan)
        self.s.data['User']['alice'].enabled = 1
        with patch.object(self.s.f, 'get_roles', return_value=['Employee']):
            with self.assertRaises(Rejected):
                self.detail(plan)
        self.s.f.conf = {'office_agent_file_readers': {'agent': 'alice'}}
        with self.assertRaises(Rejected):
            self.detail(plan)

    def test_manager_update_preserves_notes_and_does_not_return_them(self):
        self.s.as_user('alice')
        plan = self.plan(notes='Private')
        self.s.as_user('lead')
        detail = self.detail(plan)
        updated = self.s.call('save_plan', {**detail, 'title': 'Moved allocation'})
        self.assertNotIn('notes', updated)
        self.assertFalse(updated['notes_editable'])
        self.assertEqual(self.s.get_doc('Planner Entry', plan['name']).notes, 'Private')
        for value in ('replacement', '', None):
            with self.assertRaises(Rejected):
                self.s.call('save_plan', {**updated, 'notes': value})
        with self.assertRaises(Stale):
            self.s.call('save_plan', {**detail, 'title': 'Stale'})
        self.s.as_user('approver')
        with self.assertRaises(Rejected):
            self.s.call('save_plan', self.detail(plan))

    def test_owner_admin_changes_omission_and_stale_notes(self):
        self.s.as_user('alice')
        plan = self.plan(notes='Private')
        for actor in ('alice', 'Administrator'):
            self.s.as_user(actor)
            old = self.detail(plan)
            updated = self.s.call('save_plan', {**old, 'notes': actor})
            with self.assertRaises(Stale):
                self.s.call('save_plan', {**old, 'notes': 'Lost update'})
            updated.pop('notes')
            self.s.call('save_plan', updated)
            self.assertEqual(self.detail(plan)['notes'], actor)
        self.s.call('save_plan', {**self.detail(plan), 'notes': ''})
        self.assertEqual(self.detail(plan)['notes'], '')

    def test_document_guard_including_cancel_and_creation(self):
        self.s.as_user('alice')
        plan = self.plan(notes='Private')
        self.s.as_user('lead')
        for status in ('Planned', 'Cancelled'):
            doc = self.s.get_doc('Planner Entry', plan['name'])
            doc.notes = 'overwrite'
            doc.status = status
            with self.assertRaises(Rejected):
                doc.save(ignore_permissions=True)
        fresh = {k: v for k, v in plan.items() if k not in ('name', 'modified')}
        fresh.update(plan_start='2030-01-09T09:00:00Z', plan_end='2030-01-09T10:00:00Z')
        with self.assertRaisesRegex(Rejected, 'private planning notes'):
            self.s.call('save_plan', {**fresh, 'notes': 'Manager private note'})

    def test_personal_redaction_and_assignment_revocation(self):
        self.s.as_user('alice')
        plan = self.s.call('save_plan', dict(user='alice', kind='Leave', title='Private leave',
            notes='Private', timezone='UTC', plan_start='2030-01-08T09:00:00Z',
            plan_end='2030-01-08T10:00:00Z'))
        self.s.as_user('lead')
        detail = self.detail(plan)
        self.assertEqual(detail['title'], 'Leave')
        self.assertIsNone(detail['leave_application'])
        self.assertNotIn('notes', detail)
        self.s.call('assignment', dict(activity='AP', employee='alice', assigned=False))
        with self.assertRaises(Rejected):
            self.detail(plan)

    def test_detail_preserves_dst_instants_and_legacy_duration(self):
        self.s.as_user('alice')
        with patch.object(self.s.api, 'get_system_timezone', return_value='America/New_York'):
            plan = self.s.call('save_plan', dict(user='alice', project='P', activity='AP',
                kind='Work', timezone='America/New_York', notes='Private',
                plan_start='2026-11-01T01:15:00-04:00', plan_end='2026-11-01T01:45:00-05:00'))
            detail = self.detail(plan)
            self.assertEqual(detail['plan_start'], '2026-11-01T05:15:00+00:00')
            self.assertEqual(detail['plan_end'], '2026-11-01T06:45:00+00:00')
            self.assertEqual(detail['duration_hours'], 1.5)
        self.s.seed('Planner Entry', 'legacy', user='alice', kind='Work', project='P',
            plan_start='2030-01-07 09:00:00', duration_hours=2, status='Planned')
        self.assertEqual(self.detail({'name': 'legacy'})['plan_end'], '2030-01-07T11:00:00+00:00')
