"""Run only on a disposable synthetic Frappe site after installing ERPLite.

Use `bench --site <isolated-site> execute tests.workz.frappe_smoke.run` only if
this module is importable, or execute this file with SITE and SITES_PATH set.
Refuses any site name not beginning with workz-synthetic. Never production data.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def run():
    import frappe
    from erplite.workz.api import run as api
    from erplite.workz.migration import import_manifest

    assert frappe.local.site.startswith(
        "workz-synthetic"
    ), "Disposable synthetic site only"
    frappe.set_user("Administrator")
    frappe.local.request = frappe._dict(method="POST")
    # Unique prefix allows reruns without mutating records from prior test runs.
    prefix = frappe.generate_hash(length=8)
    people = {
        role: f"{prefix}-{role}@example.invalid"
        for role in ("employee", "lead", "approver", "stranger")
    }

    def call(action, **payload):
        result = api(action, payload)
        frappe.db.commit()
        return result

    for role, email in people.items():
        call(
            "save_user",
            email=email,
            full_name=f"Synthetic {role}",
            enabled=True,
            roles=["Projects User"],
        )
    project = call(
        "save_project",
        project_name=f"Synthetic {prefix}",
        status="Open",
        project_lead=people["lead"],
        timesheet_approver=people["approver"],
    )
    activity = call(
        "save_activity",
        project=project["name"],
        activity_name=f"Synthetic work {prefix}",
        status="Open",
    )
    call(
        "assignment",
        employee=people["employee"],
        activity=activity["name"],
        assigned=True,
    )
    call(
        "assignment",
        employee=people["employee"],
        activity=activity["name"],
        assigned=True,
    )
    assert (
        frappe.db.count(
            "ToDo",
            {
                "reference_name": activity["name"],
                "allocated_to": people["employee"],
                "status": "Open",
            },
        )
        == 1
    )
    from frappe.utils import nowdate

    if not frappe.db.exists("Currency", "AUD"):
        call("save_currency", code="AUD", symbol="$")
    for kind, amount in [("Pay", "40"), ("Sell", "100")]:
        call(
            "save_rate",
            kind=kind,
            amount=amount,
            employee=people["employee"],
            project=project["name"] if kind == "Sell" else None,
            currency="AUD",
            effective_from=nowdate(),
        )
    frappe.set_user(people["lead"])
    plan = call(
        "save_plan",
        user=people["employee"],
        project=project["name"],
        activity=activity["name"],
        kind="Work",
        title="Synthetic allocation",
        plan_start="2035-01-08T09:00:00Z",
        plan_end="2035-01-08T11:30:00Z",
        timezone="UTC",
        billable=1,
    )
    period = {
        "start": "2035-01-01T00:00:00Z",
        "end": "2035-02-01T00:00:00Z",
        "project": project["name"],
    }
    finance = call("financials", **period)
    assert finance["currencies"]["AUD"]["cost"] == "100.00", finance
    frappe.set_user(people["employee"])
    assert len(call("suggestions", **period)) == 1
    assert call("report", **period)["totals"]["actual"] == "0"
    site = frappe.local.site
    sites_path = str(frappe.local.sites_path)

    def accept(_):
        frappe.init(site=site, sites_path=sites_path)
        frappe.connect()
        frappe.set_user(people["employee"])
        frappe.local.request = frappe._dict(method="POST")
        try:
            result = api(
                "decision",
                {
                    "name": plan["name"],
                    "modified": str(plan["modified"]),
                    "decision": "Accepted",
                },
            )
            frappe.db.commit()
            return result["timesheet"]
        finally:
            frappe.destroy()

    # Real independent MariaDB transactions, not a serialized fake database.
    with ThreadPoolExecutor(max_workers=4) as pool:
        names = list(pool.map(accept, range(8)))
    assert len(set(names)) == 1, names
    frappe.db.rollback()  # release read snapshot before checking worker commits
    entry = frappe.get_doc("Timesheet Entry", names[0])
    assert entry.status == "Draft"
    call(
        "transition", name=entry.name, modified=str(entry.modified), status="Submitted"
    )
    frappe.set_user(people["stranger"])
    assert call("times", **period) == []
    assert not frappe.has_permission(
        "Timesheet Entry", "read", doc=frappe.get_doc("Timesheet Entry", entry.name)
    )
    frappe.set_user(people["approver"])
    entry.reload()
    call("transition", name=entry.name, modified=str(entry.modified), status="Approved")
    report = call("report", **period)
    assert report["totals"]["approved"] == "2.5", report
    assert call("financials", **period)["currencies"] == {}
    assert any(
        r.new_status == "Approved" and r.actor == people["approver"]
        for r in frappe.get_all(
            "Workz Audit",
            filters={"reference_name": entry.name},
            fields=["new_status", "actor"],
        )
    )
    frappe.set_user("Administrator")
    manifest = (
        Path(__file__).resolve().parents[2] / "docs/workz/synthetic-manifest.json"
    )
    first = import_manifest(str(manifest), apply=True)
    frappe.db.commit()
    assert first["valid"], first
    second = import_manifest(str(manifest), apply=True)
    frappe.db.commit()
    assert second["valid"], second
    assert first["reconciliation"] == second["reconciliation"]
    print(
        json.dumps(
            {
                "site": site,
                "concurrent_accepts": len(names),
                "actual_entries": len(set(names)),
                "approved_hours": report["totals"]["approved"],
                "finance": finance["currencies"],
                "import_reconciliation": first["reconciliation"],
            }
        )
    )


if __name__ == "__main__":
    import frappe

    site = os.environ["SITE"]
    assert site.startswith("workz-synthetic")
    os.chdir(os.environ["SITES_PATH"])
    frappe.init(site=site, sites_path=os.environ["SITES_PATH"])
    frappe.connect()
    try:
        run()
    finally:
        frappe.destroy()
