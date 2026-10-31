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
from erplite.workz.api import run

settings = frappe.get_single("System Settings")
from frappe.utils import get_system_timezone

old = get_system_timezone()
settings.language = settings.language or "en"
settings.time_zone = "America/New_York"
settings.save()
frappe.db.commit()
frappe.clear_cache()
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
            plan_start="2030-11-03T01:15:00-04:00",
            plan_end="2030-11-03T01:45:00-05:00",
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
            start="2030-11-01T00:00:00-04:00",
            end="2030-12-01T00:00:00-05:00",
            project=project["name"],
        ),
    )
    assert report["totals"]["actual"] == "1.5", report
    print(
        "Real MariaDB DST fold: 1.5 elapsed hours preserved through plan, accept and report."
    )
finally:
    frappe.set_user("Administrator")
    settings = frappe.get_single("System Settings")
    settings.time_zone = old
    settings.save()
    frappe.db.commit()
    frappe.clear_cache()
    frappe.destroy()
