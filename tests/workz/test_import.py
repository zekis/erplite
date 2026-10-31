import copy, json, tempfile, unittest
from pathlib import Path
from fake_site import Site
from erplite.workz.migration import import_manifest


class Import(unittest.TestCase):
    def test_processed_history_import_preserves_status_and_existing_approval(self):
        self.manifest["records"][-1]["fields"]["status"] = "Processed"
        result = self.run_import(True)
        self.assertTrue(result.get("applied"), result)
        row = self.s.get_all("Timesheet Entry")[0]
        self.assertEqual(row.status, "Processed")
        self.assertEqual(row.approved_by, "approver@example.invalid")
        self.assertEqual(self.s.call("report", dict(start="2030-01-01T00:00:00Z", end="2030-03-01T00:00:00Z"))["totals"]["actual"], "1.5")
        before = copy.deepcopy(self.s.data)
        self.run_import(True)
        self.assertEqual(before, self.s.data)

    def test_processed_without_approval_is_not_silently_approved_and_stays_locked(self):
        source = self.manifest["records"][-1]
        source["fields"]["status"] = "Processed"
        source["fields"].pop("approved_by")
        source["fields"].pop("approval_date")
        source["audit_history"][0]["status"] = "Processed"
        result = self.run_import(True)
        self.assertTrue(result.get("applied"), result)
        row = self.s.get_all("Timesheet Entry")[0]
        self.assertEqual(row.status, "Processed")
        self.assertFalse(row.approved_by)
        self.assertFalse(row.approval_date)
        self.assertEqual(self.s.get_all("Workz Audit"), [])
        for actor in (row.employee, "Administrator"):
            self.s.as_user(actor)
            direct = self.s.get_doc("Timesheet Entry", row.name)
            direct.description = "Rewrite processed history"
            with self.assertRaisesRegex(Exception, "history is locked"):
                direct.save()
        from erplite.workz.domain import interval
        with self.assertRaisesRegex(Exception, "week contains"):
            self.s.api.check_locked_period(row.employee, *interval("2030-02-02T09:00:00Z", "2030-02-02T10:00:00Z"))
        self.s.api.check_locked_period(row.employee, *interval("2030-02-11T09:00:00Z", "2030-02-11T10:00:00Z"))

    def setUp(self):
        self.s = Site()
        self.s.seed("User", "Administrator", enabled=1)
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "manifest.json"
        self.manifest = {
            "version": 1,
            "source_site": "synthetic.invalid",
            "batch_id": "test-1",
            "timezone": "UTC",
            "identity_map": {},
            "records": [
                {
                    "doctype": "User",
                    "source_id": "u",
                    "fields": {
                        "email": "person@example.invalid",
                        "first_name": "Synthetic",
                        "enabled": 1,
                    },
                },
                {
                    "doctype": "User",
                    "source_id": "a",
                    "fields": {
                        "email": "approver@example.invalid",
                        "first_name": "Approver",
                        "enabled": 1,
                    },
                },
                {
                    "doctype": "Project",
                    "source_id": "p",
                    "fields": {
                        "project_name": "Synthetic import",
                        "status": "Archived",
                        "timesheet_approver": "a",
                    },
                },
                {
                    "doctype": "Activity",
                    "source_id": "t",
                    "fields": {
                        "project": "p",
                        "activity_name": "Imported activity",
                        "status": "Closed",
                    },
                },
                {
                    "doctype": "Timesheet Entry",
                    "source_id": "time",
                    "fields": {
                        "employee": "u",
                        "project": "p",
                        "activity": "t",
                        "status": "Approved",
                        "approved_by": "a",
                        "approval_date": "2030-02-02T09:00:00Z",
                        "check_in_time": "2030-01-31T23:30:00Z",
                        "check_out_time": "2030-02-01T01:00:00Z",
                        "duration_hours": "1.5",
                    },
                    "audit_history": [
                        {
                            "actor": "a",
                            "status": "Approved",
                            "when": "2030-02-02T09:00:00Z",
                        }
                    ],
                },
            ],
        }

    def tearDown(self):
        self.temp.cleanup()

    def run_import(self, apply=False):
        self.path.write_text(json.dumps(self.manifest))
        return import_manifest(str(self.path), apply)

    def test_dry_run_write_repeat_reconcile_and_preserve_approval_provenance(self):
        result = self.run_import()
        self.assertTrue(result["valid"], result)
        self.assertEqual(self.s.get_all("Timesheet Entry"), [])
        result = self.run_import(True)
        self.assertTrue(result["applied"])
        self.assertEqual([r["hours"] for r in result["reconciliation"]], ["0.5", "1.0"])
        imported = self.s.get_all("Timesheet Entry")[0]
        self.assertEqual(imported.status, "Approved")
        self.assertEqual(imported.approved_by, "approver@example.invalid")
        before = copy.deepcopy(self.s.data)
        self.run_import(True)
        self.assertEqual(before, self.s.data)
        self.assertEqual(
            self.s.get_all("Workz Audit"),
            [],
            "An import must never record a fresh approval",
        )
        archived = self.s.get_all(
            "Workz Import Map", {"target_type": "Timesheet Entry"}
        )[0]
        self.assertEqual(
            json.loads(archived.source_record)["audit_history"],
            self.manifest["records"][-1]["audit_history"],
        )

    def test_changed_source_rejected_without_overwrite(self):
        self.run_import(True)
        before = copy.deepcopy(self.s.data)
        self.manifest["records"][-1]["fields"]["description"] = "Changed source"
        result = self.run_import(True)
        self.assertFalse(result["valid"])
        self.assertEqual(before, self.s.data)

    def test_missing_attachment_rejected_before_mutation(self):
        self.manifest["records"][-1]["attachments"] = [
            {"path": "missing.pdf", "sha256": "bad"}
        ]
        before = copy.deepcopy(self.s.data)
        self.assertFalse(self.run_import(True)["valid"])
        self.assertEqual(before, self.s.data)

    def test_failure_mid_import_rolls_back_entire_batch(self):
        self.manifest["records"][2]["fields"].pop("project_name")
        before = copy.deepcopy(self.s.data)
        with self.assertRaises(ValueError):
            self.run_import(True)
        self.assertEqual(before, self.s.data)

    def test_rejected_import_stays_rejected_until_explicit_resubmission(self):
        self.manifest["records"][2]["fields"]["status"] = "Open"
        self.manifest["records"][3]["fields"]["status"] = "Open"
        source = self.manifest["records"][-1]
        source["fields"]["status"] = "Rejected"
        source["fields"]["approval_notes"] = "Original rejection"
        source["audit_history"][0]["status"] = "Rejected"
        self.assertTrue(self.run_import(True)["applied"])
        imported = self.s.get_all("Timesheet Entry")[0]
        self.assertEqual(imported.status, "Rejected")
        self.assertEqual(self.s.get_all("Workz Audit"), [])
        archive = copy.deepcopy(self.s.get_all("Workz Import Map"))
        self.s.call(
            "assignment",
            dict(employee=imported.employee, activity=imported.activity, assigned=True),
        )
        self.s.as_user(imported.employee)
        corrected = self.s.call(
            "save_time", {**imported, "description": "Corrected imported rejection"}
        )
        self.assertEqual(corrected["status"], "Rejected")
        self.assertEqual(corrected["approval_notes"], "Original rejection")
        entries = self.s.call(
            "times", dict(start="2030-01-01T00:00:00Z", end="2030-03-01T00:00:00Z")
        )
        self.assertEqual(entries[0]["approval_notes"], "Original rejection")
        self.s.call("transition", {**corrected, "status": "Submitted"})
        self.assertEqual(
            self.s.get_doc("Timesheet Entry", imported.name).status, "Submitted"
        )
        self.assertEqual(self.s.get_all("Workz Import Map"), archive)
