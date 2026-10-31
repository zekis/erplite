"""Legacy rejection must remain correctable through Workz without Desk."""

import copy
import json
import unittest
import test_application
from fake_site import Rejected, Stale


class RejectedEntries(unittest.TestCase):
    def setUp(self):
        test_application.Application.setUp(self)
        self.s.as_user("alice")
        plan = test_application.Application.plan(self)
        accepted = test_application.Application.accept(self, plan)
        doc = self.s.get_doc("Timesheet Entry", accepted["timesheet"])
        self.s.call("transition", {**doc, "status": "Submitted"})
        self.s.as_user("approver")
        doc = self.s.get_doc("Timesheet Entry", doc.name)
        # Existing reject_timesheet uses this document save, not the Workz API.
        doc.status = "Rejected"
        doc.approval_notes = "Please correct the description and end time"
        doc.save()
        self.name = doc.name
        self.rejection = {
            k: doc[k] for k in ("approved_by", "approval_date", "approval_notes")
        }
        self.original_audit = copy.deepcopy(self.s.get_all("Workz Audit"))
        self.s.as_user("alice")

    def doc(self):
        return self.s.get_doc("Timesheet Entry", self.name)

    def test_owner_corrects_resubmits_then_scoped_approver_approves(self):
        corrected = self.s.call(
            "save_time",
            {
                **self.doc(),
                "description": "Corrected",
                "check_out_time": "2030-01-07T12:00:00Z",
            },
        )
        self.assertEqual(corrected["status"], "Rejected")
        self.assertEqual(corrected["duration_hours"], 3)
        self.assertEqual({k: corrected[k] for k in self.rejection}, self.rejection)
        submitted = self.s.call("transition", {**corrected, "status": "Submitted"})
        self.assertEqual({k: submitted[k] for k in self.rejection}, self.rejection)
        with self.assertRaises(Rejected):
            self.s.call("transition", {**submitted, "status": "Approved"})
        self.s.as_user("approver")
        self.s.call("transition", {**self.doc(), "status": "Approved"})
        self.assertEqual(self.s.call("report", self.range)["totals"]["approved"], "3.0")
        audit = self.s.get_all("Workz Audit")
        for original in self.original_audit:
            self.assertIn(original, audit)
        changes = [a for a in audit if a.action == "correction"]
        self.assertEqual(len(changes), 1)
        details = json.loads(changes[0].details)
        self.assertEqual(details["after"]["description"], "Corrected")
        self.assertIn("check_out_time", details["before"])
        self.assertEqual(changes[0].actor, "alice")
        transitions = [
            (a.old_status, a.new_status) for a in audit if a.action == "status"
        ]
        self.assertIn(("Submitted", "Rejected"), transitions)
        self.assertIn(("Rejected", "Submitted"), transitions)

    def test_scoped_approver_correction_and_direct_doc_resubmission(self):
        self.s.as_user("approver")
        corrected = self.s.call(
            "save_time", {**self.doc(), "description": "Scoped correction"}
        )
        self.assertEqual(corrected["status"], "Rejected")
        self.s.as_user("alice")
        doc = self.doc()
        doc.description = "Direct correction"
        doc.save()
        doc.status = "Submitted"
        doc.save()
        self.assertEqual(self.doc().status, "Submitted")
        self.s.as_user("approver")
        rejected = self.s.call(
            "transition",
            {**self.doc(), "status": "Rejected", "reason": "Still needs correction"},
        )
        self.assertEqual(rejected["status"], "Rejected")
        self.s.call("transition", {**rejected, "status": "Submitted"})
        self.assertEqual(self.doc().status, "Submitted")

    def test_unrelated_user_stale_writes_and_rejection_metadata_denied(self):
        original = self.doc()
        self.s.as_user("bob")
        for action, change in [
            ("save_time", {"description": "Intrusion"}),
            ("transition", {"status": "Submitted"}),
        ]:
            with self.assertRaises(Rejected):
                self.s.call(action, {**original, **change})
        direct = self.doc()
        direct.description = "Intrusion"
        with self.assertRaises(Rejected):
            direct.save()
        self.s.as_user("alice")
        self.s.call("save_time", {**original, "description": "First correction"})
        for action, change in [
            ("save_time", {"description": "Stale"}),
            ("transition", {"status": "Submitted"}),
        ]:
            with self.assertRaises((Stale, Rejected)):
                self.s.call(action, {**original, **change})
        original.description = "Stale direct write"
        with self.assertRaises(Stale):
            original.save()
        for status in ("Rejected", "Submitted"):
            direct = self.doc()
            direct.status = status
            direct.approval_notes = "Erase rejection"
            with self.assertRaisesRegex(Rejected, "metadata is immutable"):
                direct.save()
        with self.assertRaises(Rejected):
            self.s.call("delete_time", self.doc())
        self.assertEqual(self.doc().approval_notes, self.rejection["approval_notes"])

    def test_submitted_and_approved_remain_immutable(self):
        self.s.call("transition", {**self.doc(), "status": "Submitted"})
        for status in ("Submitted", "Approved"):
            if status == "Approved":
                self.s.as_user("approver")
                self.s.call("transition", {**self.doc(), "status": "Approved"})
            for actor in ("alice", "approver"):
                self.s.as_user(actor)
                with self.assertRaises(Rejected):
                    self.s.call("save_time", {**self.doc(), "description": "Rewrite"})
                direct = self.doc()
                direct.description = "Rewrite"
                with self.assertRaisesRegex(Rejected, "history is locked"):
                    direct.save()
