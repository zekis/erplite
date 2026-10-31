"""Regression for PR #71: folded local history must not poison later bookings."""

import unittest
from unittest.mock import patch
from fake_site import Rejected
import test_application
from erplite.workz.domain import interval


class DSTWeekLocks(unittest.TestCase):
    setUp = test_application.Application.setUp

    def history(
        self, status, start="2026-11-01 01:15:00", end="2026-11-01 01:45:00", **shadows
    ):
        self.s.seed(
            "Timesheet Entry",
            "history",
            employee="alice",
            project="P",
            activity="AP",
            status=status,
            check_in_time=start,
            check_out_time=end,
            **shadows,
        )

    def lock(self, start, end):
        self.s.api.check_locked_period("alice", *interval(start, end))

    def test_fold_history_allows_later_manual_and_accepted_time_but_locks_same_week(
        self,
    ):
        for status in ("Submitted", "Approved"):
            with self.subTest(status=status):
                self.setUp()
                with patch.object(
                    self.s.api, "get_system_timezone", return_value="America/New_York"
                ):
                    self.history(
                        status,
                        workz_start_utc="2026-11-01 05:15:00",
                        workz_end_utc="2026-11-01 06:45:00",
                    )
                    self.s.as_user("alice")
                    self.lock("2026-11-16T14:00:00Z", "2026-11-16T15:00:00Z")
                    manual = self.s.call(
                        "save_time",
                        dict(
                            project="P",
                            activity="AP",
                            check_in_time="2026-11-16T14:00:00Z",
                            check_out_time="2026-11-16T15:00:00Z",
                        ),
                    )
                    self.assertEqual(manual["status"], "Draft")
                    plan = self.s.call(
                        "save_plan",
                        dict(
                            user="alice",
                            project="P",
                            activity="AP",
                            kind="Work",
                            title="Later week",
                            timezone="America/New_York",
                            plan_start="2026-11-17T14:00:00Z",
                            plan_end="2026-11-17T15:00:00Z",
                        ),
                    )
                    accepted = self.s.call(
                        "decision",
                        dict(
                            name=plan["name"],
                            modified=plan["modified"],
                            decision="Accepted",
                        ),
                    )
                    self.assertEqual(
                        self.s.get_doc("Timesheet Entry", accepted["timesheet"]).status,
                        "Draft",
                    )
                    for start, end in [
                        ("2026-10-28T14:00:00Z", "2026-10-28T15:00:00Z"),
                        ("2026-11-01T20:00:00Z", "2026-11-01T21:00:00Z"),
                    ]:
                        with self.assertRaisesRegex(Rejected, "week contains"):
                            self.s.call(
                                "save_time",
                                dict(
                                    project="P",
                                    activity="AP",
                                    check_in_time=start,
                                    check_out_time=end,
                                ),
                            )
                    locked_plan = self.s.call(
                        "save_plan",
                        dict(
                            user="alice",
                            project="P",
                            activity="AP",
                            kind="Work",
                            title="Locked week",
                            timezone="America/New_York",
                            plan_start="2026-10-29T14:00:00Z",
                            plan_end="2026-10-29T15:00:00Z",
                        ),
                    )
                    with self.assertRaisesRegex(Rejected, "week contains"):
                        self.s.call(
                            "decision",
                            dict(
                                name=locked_plan["name"],
                                modified=locked_plan["modified"],
                                decision="Accepted",
                            ),
                        )
                    self.assertEqual(len(self.s.get_all("Timesheet Entry")), 3)
                    self.assertEqual(len(self.s.get_all("Workz Decision")), 1)
                    # Adjacent elapsed instants do not overlap despite folded clocks.
                    self.s.api.check_overlap(
                        "alice",
                        *interval("2026-11-01T06:45:00Z", "2026-11-01T07:00:00Z"),
                        "Work",
                        actual=True,
                    )
                    # Overlap across the two occurrences of 01:xx uses elapsed instants.
                    with self.assertRaisesRegex(Rejected, "Conflicts"):
                        self.s.api.check_overlap(
                            "alice",
                            *interval("2026-11-01T06:00:00Z", "2026-11-01T06:30:00Z"),
                            "Work",
                            actual=True,
                        )

    def test_week_overlap_and_exclusive_boundaries_with_legacy_history(self):
        with patch.object(
            self.s.api, "get_system_timezone", return_value="America/New_York"
        ):
            # Spans Sunday/Monday: both touched local weeks remain locked.
            self.history("Approved", "2026-11-08 23:30:00", "2026-11-09 00:30:00")
            for start, end in [
                ("2026-11-03T14:00:00Z", "2026-11-03T15:00:00Z"),
                ("2026-11-10T14:00:00Z", "2026-11-10T15:00:00Z"),
            ]:
                with self.assertRaisesRegex(Rejected, "week contains"):
                    self.lock(start, end)
            self.lock("2026-11-16T14:00:00Z", "2026-11-16T15:00:00Z")
            # Ending exactly at Monday midnight does not lock the following week.
            self.history("Submitted", "2026-11-08 23:30:00", "2026-11-09 00:00:00")
            self.lock("2026-11-10T14:00:00Z", "2026-11-10T15:00:00Z")
            # A new booking ending at the prior Monday boundary does not touch it.
            self.lock("2026-11-01T23:00:00-05:00", "2026-11-02T00:00:00-05:00")
