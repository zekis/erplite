import copy, json, tempfile, unittest
from pathlib import Path
from fake_site import Site
from erplite.workz.migration import import_manifest


class Import(unittest.TestCase):
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
