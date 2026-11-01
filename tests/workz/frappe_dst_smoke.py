"""Explicit-offset DST regression on a disposable Frappe/MariaDB site."""

import os

site = os.environ["SITE"]
assert site.startswith("workz-synthetic"), "Disposable sites only"
os.chdir(os.environ["SITES_PATH"])
import frappe

frappe.init(site=site, sites_path=os.environ["SITES_PATH"])
frappe.connect()
frappe.set_user("Administrator")
frappe.local.request = frappe._dict(method="POST")
from erplite.workz.api import run as workz_run

# Use Frappe's request-local settings cache, never save global site settings.
# Each action gets a fresh copy because User insertion can clear local caches.
settings = frappe.get_single("System Settings").as_dict()
settings["time_zone"] = "America/New_York"


def run(action, payload):
    frappe.local.system_settings = frappe._dict(settings)
    return workz_run(action, payload)


try:
    prefix = frappe.generate_hash(length=8)
    email = prefix + "-dst@example.invalid"
    run(
        "save_user",
        dict(
            email=email,
            full_name="DST synthetic",
            roles=["Projects User"],
            enabled=True,
        ),
    )
    project = run("save_project", dict(project_name="DST " + prefix, status="Open"))
    activity = run(
        "save_activity",
        dict(project=project["name"], activity_name="DST " + prefix, status="Open"),
    )
    run("assignment", dict(activity=activity["name"], employee=email, assigned=True))
    frappe.db.commit()
    frappe.set_user(email)
    plan = run(
        "save_plan",
        dict(
            user=email,
            project=project["name"],
            activity=activity["name"],
            title="Repeated clock",
            kind="Work",
            plan_start="2026-11-01T01:15:00-04:00",
            plan_end="2026-11-01T01:45:00-05:00",
            timezone="America/New_York",
            billable=1,
        ),
    )
    frappe.db.commit()
    entry = run(
        "decision",
        dict(name=plan["name"], modified=str(plan["modified"]), decision="Accepted"),
    )
    frappe.db.commit()
    actual = frappe.get_doc("Timesheet Entry", entry["timesheet"])
    assert actual.duration_hours == 1.5, actual.duration_hours
    report = run(
        "report",
        dict(
            start="2026-11-01T00:00:00-04:00",
            end="2026-12-01T00:00:00-05:00",
            project=project["name"],
        ),
    )
    assert report["totals"]["actual"] == "1.5", report
    run(
        "transition",
        dict(name=actual.name, modified=str(actual.modified), status="Submitted"),
    )
    frappe.db.commit()
    for status, day in (("Submitted", 16), ("Approved", 18)):
        if status == "Approved":
            frappe.set_user("Administrator")
            actual.reload()
            run(
                "transition",
                dict(
                    name=actual.name, modified=str(actual.modified), status="Approved"
                ),
            )
            frappe.db.commit()
            frappe.set_user(email)
        manual = run(
            "save_time",
            dict(
                project=project["name"],
                activity=activity["name"],
                check_in_time=f"2026-11-{day}T14:00:00Z",
                check_out_time=f"2026-11-{day}T15:00:00Z",
            ),
        )
        assert manual["status"] == "Draft"
        future = run(
            "save_plan",
            dict(
                user=email,
                project=project["name"],
                activity=activity["name"],
                kind="Work",
                title="After folded history",
                timezone="America/New_York",
                plan_start=f"2026-11-{day + 1}T14:00:00Z",
                plan_end=f"2026-11-{day + 1}T15:00:00Z",
            ),
        )
        decision = run(
            "decision",
            dict(
                name=future["name"],
                modified=str(future["modified"]),
                decision="Accepted",
            ),
        )
        assert (
            frappe.get_doc("Timesheet Entry", decision["timesheet"]).status == "Draft"
        )
        frappe.db.commit()
        # Different time, same local week: reject for week lock, not overlap.
        try:
            run(
                "save_time",
                dict(
                    project=project["name"],
                    activity=activity["name"],
                    check_in_time="2026-10-28T14:00:00Z",
                    check_out_time="2026-10-28T15:00:00Z",
                ),
            )
        except frappe.ValidationError as exc:
            assert "week contains" in str(exc), str(exc)
            frappe.db.rollback()
        else:
            raise AssertionError("Same-week booking was not locked: " + status)
    print(
        "Real MariaDB DST: 1.5 fold hours preserved; Submitted and Approved history allow later manual bookings and Accept, while the same week stays locked."
    )
finally:
    frappe.destroy()
