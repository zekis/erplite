import unittest
from concurrent.futures import ThreadPoolExecutor
from fake_site import Site, Rejected, Stale


class Application(unittest.TestCase):
    def setUp(self):
        self.s = Site()
        for name in ("Administrator", "alice", "bob", "lead", "approver", "stranger"):
            self.s.seed("User", name, enabled=1, full_name=name)
        for name, lead, approver in [
            ("P", "lead", "approver"),
            ("Q", "stranger", "stranger"),
        ]:
            self.s.seed(
                "Project",
                name,
                project_name=name,
                status="Open",
                project_lead=lead,
                timesheet_approver=approver,
            )
            self.s.seed(
                "Activity", "A" + name, project=name, activity_name=name, status="Open"
            )
        self.s.call("assignment", dict(activity="AP", employee="alice", assigned=True))
        self.range = dict(start="2030-01-01T00:00:00Z", end="2030-02-01T00:00:00Z")

    def test_context_hides_unassigned_sibling_activity_and_revoked_assignment(self):
        self.s.seed("Activity", "PRIVATE", project="P", activity_name="Private", status="Open")
        self.s.call("assignment", dict(activity="PRIVATE", employee="bob", assigned=True))
        self.s.as_user("alice")
        ctx = self.s.call("context")
        self.assertEqual([r.name for r in ctx["activities"]], ["AP"])
        self.assertEqual({r.allocated_to for r in ctx["assignments"]}, {"alice"})
        self.s.as_user("approver")
        self.assertEqual({r.name for r in self.s.call("context")["activities"]}, {"AP", "PRIVATE"})
        self.s.as_user("Administrator")
        self.s.call("assignment", dict(activity="AP", employee="alice", assigned=False))
        self.s.as_user("alice")
        ctx = self.s.call("context")
        self.assertEqual(ctx["projects"], [])
        self.assertEqual(ctx["activities"], [])
        self.assertEqual(ctx["assignments"], [])

    def test_unknown_disabled_guest_and_unmapped_role_rejected(self):
        for actor in ("Guest", "missing"):
            self.s.as_user(actor)
            with self.assertRaises(Rejected):
                self.s.call("context")
        self.s.as_user("alice")
        self.s.data["User"]["alice"]["enabled"] = 0
        with self.assertRaises(Rejected):
            self.s.call("context")
        self.s.data["User"]["alice"]["enabled"] = 1
        self.s.f.get_roles = lambda user=None: ["Employee"]
        with self.assertRaises(Rejected):
            self.s.call("context")

    def plan(self, **kwargs):
        return self.s.call(
            "save_plan",
            dict(
                user="alice",
                project="P",
                activity="AP",
                title="Synthetic work",
                kind="Work",
                timezone="UTC",
                plan_start="2030-01-07T09:00:00Z",
                plan_end="2030-01-07T11:30:00Z",
                billable=1,
                **kwargs,
            ),
        )

    def accept(self, plan):
        return self.s.call(
            "decision",
            dict(name=plan["name"], modified=plan["modified"], decision="Accepted"),
        )

    def test_full_plan_accept_submit_approve_report(self):
        self.s.as_user("lead")
        plan = self.plan()
        self.s.as_user("alice")
        self.assertEqual(len(self.s.call("suggestions", self.range)), 1)
        self.assertEqual(self.s.call("report", self.range)["totals"]["actual"], "0")
        decision = self.accept(plan)
        entry = self.s.get_doc("Timesheet Entry", decision["timesheet"])
        self.assertEqual(entry.status, "Draft")
        self.s.call(
            "transition",
            dict(name=entry.name, modified=entry.modified, status="Submitted"),
        )
        self.s.as_user("approver")
        entry = self.s.get_doc("Timesheet Entry", entry.name)
        self.s.call(
            "transition",
            dict(name=entry.name, modified=entry.modified, status="Approved"),
        )
        report = self.s.call("report", self.range)
        self.assertEqual(
            report["totals"],
            dict(actual="2.5", submitted="0", approved="2.5", planned="2.5"),
        )
        self.assertEqual(sum(float(e["period_hours"]) for e in report["entries"]), 2.5)
        self.assertEqual(
            sum(
                r.new_status == "Approved" and r.actor == "approver"
                for r in self.s.get_all("Workz Audit")
            ),
            1,
        )

    def test_accept_retries_move_cancel_never_duplicate_or_rewrite(self):
        self.s.as_user("alice")
        plan = self.plan()
        first = self.accept(plan)
        for _ in range(3):
            self.assertEqual(first, self.accept(plan))
        moved = self.s.call(
            "save_plan",
            {
                **plan,
                "plan_start": "2030-01-08T09:00:00Z",
                "plan_end": "2030-01-08T11:30:00Z",
            },
        )
        self.assertEqual(first, self.accept(moved))
        self.s.call("delete_plan", moved)
        self.assertEqual(first, self.accept(moved))
        self.assertEqual(len(self.s.get_all("Timesheet Entry")), 1)
        self.assertIn(
            "2030-01-07",
            str(self.s.get_doc("Timesheet Entry", first["timesheet"]).check_in_time),
        )

    def test_ignore_survives_move_and_accept_attempt(self):
        self.s.as_user("alice")
        plan = self.plan()
        ignored = self.s.call("decision", {**plan, "decision": "Ignored"})
        self.assertEqual(self.accept(plan)["decision"], "Ignored")
        self.assertEqual(self.s.call("suggestions", self.range), [])
        self.assertEqual(self.s.get_all("Timesheet Entry"), [])

    def test_parallel_accept_exact_once(self):
        self.s.as_user("alice")
        plan = self.plan()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.accept(plan), range(20)))
        self.assertEqual(len({r["timesheet"] for r in results}), 1)
        self.assertEqual(len(self.s.get_all("Timesheet Entry")), 1)

    def test_ordinary_cannot_read_or_approve_another_user(self):
        self.s.as_user("alice")
        plan = self.plan()
        decision = self.accept(plan)
        entry = self.s.get_doc("Timesheet Entry", decision["timesheet"])
        self.s.call("transition", {**entry, "status": "Submitted"})
        self.s.as_user("bob")
        self.assertEqual(self.s.call("times", self.range), [])
        with self.assertRaises(Rejected):
            self.s.call(
                "transition",
                {**self.s.get_doc("Timesheet Entry", entry.name), "status": "Approved"},
            )

    def test_manager_is_not_global_approver_or_financial_admin(self):
        self.s.as_user("alice")
        self.accept(self.plan())
        self.s.as_user("lead")
        self.assertEqual(self.s.call("times", self.range), [])
        with self.assertRaises(Rejected):
            self.s.call(
                "save_rate",
                dict(
                    kind="Pay",
                    employee="alice",
                    amount="40",
                    currency="USD",
                    effective_from="2030-01-01",
                ),
            )
        self.s.as_user("approver")
        self.assertEqual(self.s.call("financials", self.range)["currencies"], {})
        with self.assertRaises(Rejected):
            self.s.call("rate_history", dict(employee="alice", project="P"))

    def test_invalid_relationship_overlap_stale_move_rollback(self):
        self.s.as_user("alice")
        plan = self.plan()
        with self.assertRaises(Rejected):
            self.s.call("save_plan", {**plan, "activity": "AQ"})
        with self.assertRaises(Rejected):
            self.plan()
        changed = self.s.call("save_plan", {**plan, "title": "Edited"})
        with self.assertRaises(Stale):
            self.s.call("save_plan", {**plan, "title": "Lost update"})
        self.assertEqual(self.s.get_doc("Planner Entry", plan["name"]).title, "Edited")

    def test_removed_assignment_preserves_history_and_blocks_new_booking(self):
        self.s.as_user("alice")
        plan = self.plan()
        decision = self.accept(plan)
        self.s.as_user("lead")
        self.s.call("assignment", dict(activity="AP", employee="alice", assigned=False))
        self.s.as_user("alice")
        self.assertEqual(len(self.s.call("times", self.range)), 1)
        with self.assertRaises(Rejected):
            self.plan()

    def test_self_approval_denied_and_duplicate_transition_stale(self):
        self.s.as_user("alice")
        decision = self.accept(self.plan())
        entry = self.s.get_doc("Timesheet Entry", decision["timesheet"])
        self.s.call("transition", {**entry, "status": "Submitted"})
        with self.assertRaises(Stale):
            self.s.call("transition", {**entry, "status": "Submitted"})
        self.s.data["Project"]["P"].timesheet_approver = "alice"
        with self.assertRaises(Rejected):
            self.s.call(
                "transition",
                {**self.s.get_doc("Timesheet Entry", entry.name), "status": "Approved"},
            )

    def test_setup_cannot_escalate_roles_or_self_assign(self):
        self.s.as_user("bob")
        with self.assertRaises(Rejected):
            self.s.call(
                "assignment", dict(activity="AP", employee="bob", assigned=True)
            )
        with self.assertRaises(Rejected):
            self.s.call(
                "save_user",
                dict(
                    email="bad@example.invalid",
                    full_name="Bad",
                    roles=["System Manager"],
                ),
            )
        self.s.as_user("Administrator")
        with self.assertRaises(Rejected):
            self.s.call(
                "save_user",
                dict(
                    email="bad@example.invalid",
                    full_name="Bad",
                    roles=["System Manager"],
                ),
            )

    def test_non_post_write_refused(self):
        self.s.f.request.method = "GET"
        with self.assertRaises(Rejected):
            self.plan()

    def test_document_permission_hook_uses_frappes_ptype_argument(self):
        self.s.as_user("alice")
        record = self.accept(self.plan())
        doc = self.s.get_doc("Timesheet Entry", record["timesheet"])
        self.s.as_user("bob")
        self.assertFalse(self.s.guards.time_permission(doc, user="bob", ptype="read"))
        self.assertFalse(self.s.guards.time_permission(doc, user="bob", ptype="write"))

    def test_employee_on_two_projects_does_not_expand_managers_scope(self):
        self.s.call("assignment", dict(activity="AQ", employee="alice", assigned=True))
        self.s.as_user("alice")
        self.plan()
        self.s.call(
            "save_plan",
            dict(
                user="alice",
                project="Q",
                activity="AQ",
                title="Private other project",
                kind="Work",
                timezone="UTC",
                plan_start="2030-01-08T09:00:00Z",
                plan_end="2030-01-08T10:00:00Z",
                billable=1,
            ),
        )
        self.s.as_user("lead")
        self.assertEqual(
            [r["project"] for r in self.s.call("plans", self.range)], ["P"]
        )

    def test_submitted_week_blocks_later_acceptance_without_writing_actual(self):
        self.s.as_user("alice")
        first = self.accept(self.plan())
        entry = self.s.get_doc("Timesheet Entry", first["timesheet"])
        self.s.call("transition", {**entry, "status": "Submitted"})
        next_plan = self.s.call(
            "save_plan",
            dict(
                user="alice",
                project="P",
                activity="AP",
                title="Later",
                kind="Work",
                timezone="UTC",
                plan_start="2030-01-08T09:00:00Z",
                plan_end="2030-01-08T10:00:00Z",
            ),
        )
        with self.assertRaises(Rejected):
            self.accept(next_plan)
        self.assertEqual(len(self.s.get_all("Timesheet Entry")), 1)
        self.assertEqual(len(self.s.call("suggestions", self.range)), 1)

    def test_private_availability_requires_redacted_endpoint(self):
        self.s.as_user("alice")
        result = self.s.call(
            "save_plan",
            dict(
                user="alice",
                kind="Leave",
                title="Private",
                notes="Sensitive",
                timezone="UTC",
                plan_start="2030-01-08T09:00:00Z",
                plan_end="2030-01-08T10:00:00Z",
            ),
        )
        doc = self.s.get_doc("Planner Entry", result["name"])
        self.s.as_user("lead")
        self.assertFalse(self.s.guards.plan_permission(doc, user="lead", ptype="read"))
        self.assertTrue(self.s.guards.plan_permission(doc, user="alice", ptype="read"))
        self.assertTrue(self.s.guards.p.can_read_plan(doc))
