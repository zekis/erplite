import unittest
from datetime import datetime, timezone
from erplite.workz.domain import interval, projection, decimal
from erplite.workz.migration import validate, reconcile


class Finance(unittest.TestCase):
    def setUp(self):
        self.rates = [
            dict(
                employee="u",
                kind="Pay",
                effective_from="2030-01-01",
                amount="20.125",
                currency="USD",
            ),
            dict(
                employee="u",
                project="P",
                kind="Sell",
                effective_from="2030-01-01",
                amount="60",
                currency="USD",
            ),
            dict(
                employee="u",
                project="Q",
                kind="Sell",
                effective_from="2030-01-01",
                amount="90",
                currency="USD",
            ),
        ]
        self.bounds = interval("2030-01-01T00:00:00Z", "2030-02-01T00:00:00Z")

    def entry(self, **fields):
        return dict(
            user="u",
            project="P",
            kind="Work",
            plan_start="2030-01-07T09:00:00Z",
            plan_end="2030-01-07T10:30:00Z",
            billable=True,
            **fields,
        )

    def test_two_project_rates_partial_hours_and_money_rounding(self):
        a = self.entry()
        b = {**a, "project": "Q"}
        self.assertEqual(
            projection(a, self.rates, *self.bounds)["currencies"]["USD"],
            {"cost": "30.19", "revenue": "90.00"},
        )
        self.assertEqual(
            projection(b, self.rates, *self.bounds)["currencies"]["USD"]["revenue"],
            "135.00",
        )

    def test_midnight_effective_change_and_old_period_unchanged(self):
        self.rates.append(
            dict(
                employee="u",
                kind="Pay",
                effective_from="2030-01-08",
                amount="40",
                currency="USD",
            )
        )
        e = {
            **self.entry(),
            "plan_start": "2030-01-07T23:30:00Z",
            "plan_end": "2030-01-08T00:30:00Z",
        }
        self.assertEqual(
            projection(e, self.rates, *self.bounds)["currencies"]["USD"]["cost"],
            "30.06",
        )
        self.assertEqual(
            projection(self.entry(), self.rates, *self.bounds)["currencies"]["USD"][
                "cost"
            ],
            "30.19",
        )

    def test_missing_and_zero_different_nonbillable_no_sell(self):
        rates = [{**self.rates[0], "amount": "0"}]
        result = projection(self.entry(), rates, *self.bounds)
        self.assertEqual(result["currencies"]["USD"]["cost"], "0.00")
        self.assertEqual(result["missing"][0]["kind"], "Sell")
        self.assertEqual(
            projection({**self.entry(), "billable": False}, rates, *self.bounds)[
                "missing"
            ],
            [],
        )

    def test_different_currencies_are_separate(self):
        self.rates[1]["currency"] = "AUD"
        self.assertEqual(
            set(projection(self.entry(), self.rates, *self.bounds)["currencies"]),
            {"USD", "AUD"},
        )

    def test_leave_holiday_availability_never_costed(self):
        for kind in ("Leave", "Holiday", "Availability"):
            self.assertEqual(
                projection({**self.entry(), "kind": kind}, self.rates, *self.bounds),
                {"currencies": {}, "missing": []},
            )

    def test_nonfinite_negative_rejected(self):
        for value in ("NaN", "Infinity", "-1", "oops"):
            with self.assertRaises(ValueError):
                decimal(value)

    def test_dst_all_day_and_boundary_clipping(self):
        bounds = interval("2030-03-10T00:00:00-05:00", "2030-03-11T00:00:00-04:00")
        self.assertEqual((bounds[1] - bounds[0]).total_seconds() / 3600, 23)


class Migration(unittest.TestCase):
    def manifest(self):
        return dict(
            version=1,
            source_site="synthetic.invalid",
            batch_id="fixture-1",
            timezone="UTC",
            identity_map={
                "User:old": "u",
                "Project:old-p": "P",
                "Activity:old-a": "A",
                "User:boss": "b",
            },
            records=[
                dict(
                    doctype="Timesheet Entry",
                    source_id="old-t",
                    fields=dict(
                        employee="old",
                        project="old-p",
                        activity="old-a",
                        status="Approved",
                        approved_by="boss",
                        approval_date="2030-02-02T10:00:00Z",
                        check_in_time="2030-01-31T23:30:00Z",
                        check_out_time="2030-02-01T01:00:00Z",
                        duration_hours="1.5",
                    ),
                )
            ],
        )

    def test_month_split_preserves_status_and_decimal_hours(self):
        result = validate(self.manifest())
        self.assertTrue(result["valid"], result)
        self.assertEqual([r["hours"] for r in result["reconciliation"]], ["0.5", "1.0"])
        self.assertTrue(
            all(r["statuses"] == {"Approved": 1} for r in result["reconciliation"])
        )

    def test_missing_identity_duplicate_and_hours_conflicts_rejected(self):
        for change in ("mapping", "duplicate", "hours", "actor", "employee", "metadata"):
            m = self.manifest()
            if change == "mapping":
                m["identity_map"].pop("Activity:old-a")
            if change == "duplicate":
                m["records"] *= 2
            if change == "hours":
                m["records"][0]["fields"]["duration_hours"] = "5"
            if change == "actor":
                m["records"][0]["fields"].pop("approved_by")
            if change == "employee":
                m["records"][0]["fields"].pop("employee")
            if change == "metadata":
                m["records"][0]["fields"]["name"] = "override"
            self.assertFalse(validate(m)["valid"], change)

    def test_repeatable_manifest_hash(self):
        self.assertEqual(validate(self.manifest()), validate(self.manifest()))
