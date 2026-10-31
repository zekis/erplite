"""Versioned, deterministic Crew export validation and Frappe import.

No network access, implicit ID matching, automatic source deletion or live-site
selection. python -m erplite.workz.migration manifest.json validates offline.
A manifest must be produced from a reviewed source inventory, not inferred from
Afterz source code. Mapping keys are <doctype>:<source id>.
"""

import argparse
import copy
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
from erplite.workz.domain import interval, hours, decimal

SUPPORTED = {
    "User",
    "Project",
    "Activity",
    "ToDo",
    "Planner Entry",
    "Timesheet Entry",
    "Workz Rate",
}
LINKS = {
    "Project": {"project_lead": "User", "timesheet_approver": "User"},
    "Activity": {"project": "Project"},
    "ToDo": {"allocated_to": "User"},
    "Planner Entry": {
        "user": "User",
        "project": "Project",
        "todo": "ToDo",
        "activity": "Activity",
    },
    "Timesheet Entry": {
        "employee": "User",
        "project": "Project",
        "activity": "Activity",
        "approved_by": "User",
    },
    "Workz Rate": {"employee": "User", "project": "Project"},
}
ORDER = {
    name: i
    for i, name in enumerate(
        [
            "User",
            "Project",
            "Activity",
            "ToDo",
            "Planner Entry",
            "Timesheet Entry",
            "Workz Rate",
        ]
    )
}


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def key(record):
    return record["doctype"] + ":" + record["source_id"]


def reconcile(records, zone):
    result = defaultdict(
        lambda: {"entries": set(), "hours": Decimal(0), "statuses": defaultdict(int)}
    )
    for r in records:
        if r["doctype"] != "Timesheet Entry":
            continue
        f = r["fields"]
        a, b = interval(f["check_in_time"], f["check_out_time"], zone)
        while a < b:
            local = a.astimezone(ZoneInfo(zone))
            month = local.strftime("%Y-%m")
            next_month = (local.replace(day=28) + timedelta(days=4)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            stop = min(b, next_month)
            group = (f["employee"], f["project"], month)
            result[group]["entries"].add(r["source_id"])
            result[group]["hours"] += hours(a, stop)
            result[group]["statuses"][f["status"]] += 1
            a = stop
    return [
        {
            "employee": g[0],
            "project": g[1],
            "month": g[2],
            "entries": len(v["entries"]),
            "hours": str(v["hours"]),
            "statuses": dict(v["statuses"]),
        }
        for g, v in sorted(result.items())
    ]


def validate(manifest):
    errors = []
    records = manifest.get("records", [])
    mappings = manifest.get("identity_map", {})
    if manifest.get("version") != 1:
        errors.append("Manifest version must be 1")
    if not manifest.get("source_site") or not manifest.get("batch_id"):
        errors.append("Explicit source_site and batch_id are required")
    try:
        ZoneInfo(manifest["timezone"])
    except (KeyError, ValueError):
        errors.append("An explicit IANA source timezone is required")
    keys = set()
    for r in records:
        try:
            k = key(r)
            if k in keys:
                errors.append("Duplicate source identity: " + k)
            keys.add(k)
            if r["doctype"] not in SUPPORTED:
                errors.append("Unsupported source type: " + r["doctype"])
            f = r["fields"]
            for field in (
                "name",
                "doctype",
                "owner",
                "creation",
                "modified",
                "modified_by",
            ):
                if field in f:
                    errors.append(
                        k + ": metadata belongs in audit_history, not fields: " + field
                    )
            required = {
                "Timesheet Entry": ("employee", "project", "activity", "check_in_time"),
                "Activity": ("project",),
            }
            for field in required.get(r["doctype"], ()):
                if not f.get(field):
                    errors.append(k + ": required relationship/field " + field)
            if r["doctype"] == "User" and not f.get("email"):
                errors.append(k + ": user email is required")
            if r["doctype"] == "Timesheet Entry":
                if f.get("status") not in (
                    "Draft",
                    "Submitted",
                    "Approved",
                    "Rejected",
                    "Processed",
                ):
                    errors.append(k + ": unknown status")
                if not f.get("check_out_time"):
                    errors.append(
                        k
                        + ": active timers require finalization or a separately reviewed exception"
                    )
                else:
                    a, b = interval(
                        f["check_in_time"],
                        f["check_out_time"],
                        manifest.get("timezone", "UTC"),
                    )
                    if "duration_hours" in f and abs(
                        decimal(f["duration_hours"]) - hours(a, b)
                    ) > Decimal("0.000001"):
                        errors.append(k + ": declared hours differ from timestamps")
                if f.get("status") == "Approved" and (
                    not f.get("approved_by") or not f.get("approval_date")
                ):
                    errors.append(
                        k + ": approved history needs original actor and timestamp"
                    )
            if r["doctype"] == "Workz Rate":
                decimal(f["amount"])
            for attachment in r.get("attachments", []):
                if not attachment.get("sha256") or not attachment.get("path"):
                    errors.append(k + ": attachment path and sha256 required")
        except (KeyError, ValueError, TypeError) as e:
            errors.append(str(r.get("source_id", "record")) + ": " + str(e))
    for r in records:
        links = dict(LINKS.get(r.get("doctype"), {}))
        f = r.get("fields", {})
        if r.get("doctype") == "ToDo" and f.get("reference_name"):
            if f.get("reference_type") not in ("Project", "Activity"):
                errors.append(key(r) + ": unsupported assignment reference")
            else:
                links["reference_name"] = f["reference_type"]
        for field, doctype in links.items():
            if f.get(field):
                ref = doctype + ":" + f[field]
                if ref not in keys and ref not in mappings:
                    errors.append(key(r) + ": unresolved " + field + " " + ref)
    summary = [] if errors else reconcile(records, manifest["timezone"])
    return {
        "valid": not errors,
        "errors": errors,
        "counts": {
            dt: sum(r.get("doctype") == dt for r in records) for dt in sorted(SUPPORTED)
        },
        "reconciliation": summary,
        "manifest_hash": digest(manifest),
    }


def import_manifest(path, apply=False):
    """Operator-only bench execute function; default is read-only dry run.

    Explicit identity_map entries refer to pre-existing destination records.
    Repeated identical records are skipped; changed records are conflicts, never
    overwritten. Final deltas must have new IDs or reviewed conflict resolutions.
    """
    import frappe
    from frappe.utils.file_manager import save_file
    from erplite.workz import policy as p

    p.require(p.admin())
    source = Path(path).resolve()
    manifest = json.loads(source.read_text())
    result = validate(manifest)
    if not result["valid"]:
        return result
    mapping = dict(manifest.get("identity_map", {}))
    records = sorted(manifest["records"], key=lambda r: ORDER[r["doctype"]])
    # Preflight all local attachment content before any writes.
    for r in records:
        for item in r.get("attachments", []):
            file = (source.parent / item["path"]).resolve()
            if (
                not file.is_relative_to(source.parent)
                or not file.is_file()
                or hashlib.sha256(file.read_bytes()).hexdigest() != item["sha256"]
            ):
                result["errors"].append(key(r) + ": attachment content/path mismatch")
    for identity, target in mapping.items():
        if not frappe.db.exists(identity.split(":", 1)[0], target):
            result["errors"].append("Missing mapped target: " + identity)
    for r in records:
        source_key = manifest["source_site"] + "\0" + key(r)
        old = frappe.db.get_value(
            "Workz Import Map",
            {"source_key": hashlib.sha256(source_key.encode()).hexdigest()},
            ["target_name", "source_hash"],
            as_dict=True,
        )
        if old:
            if old.source_hash != digest(r):
                result["errors"].append("Changed imported source record: " + key(r))
            mapping[key(r)] = old.target_name
        elif (
            r["doctype"] == "User"
            and key(r) not in mapping
            and frappe.db.exists("User", r["fields"]["email"])
        ):
            result["errors"].append(
                "User email exists: supply an explicit reviewed identity_map for "
                + key(r)
            )
    result["valid"] = not result["errors"]
    if not apply or not result["valid"]:
        return result
    frappe.db.savepoint("workz_import")
    previous = frappe.flags.workz_history_import
    frappe.flags.workz_history_import = True
    try:
        for r in records:
            identity = key(r)
            if identity in mapping:
                continue
            # Frappe normalizes child dictionaries in place. Keep target child
            # metadata out of the archived source and its idempotency hash.
            fields = copy.deepcopy(r["fields"])
            links = dict(LINKS.get(r["doctype"], {}))
            if r["doctype"] == "ToDo" and fields.get("reference_name"):
                links["reference_name"] = fields["reference_type"]
            for field, doctype in links.items():
                if fields.get(field):
                    fields[field] = mapping[doctype + ":" + fields[field]]
            # Source identity/auth secrets are never blindly copied into User.
            if r["doctype"] == "User":
                fields = {
                    k: fields[k]
                    for k in ("email", "first_name", "last_name", "enabled")
                    if k in fields
                }
                fields.update(send_welcome_email=0, roles=[{"role": "Projects User"}])
            elif r["doctype"] in ("Planner Entry", "Timesheet Entry"):
                for field in (
                    "plan_start",
                    "plan_end",
                    "check_in_time",
                    "check_out_time",
                    "approval_date",
                ):
                    if fields.get(field):
                        from erplite.workz.domain import instant
                        from erplite.workz.api import stored

                        original = instant(fields[field], manifest["timezone"])
                        fields[field] = stored(original)
                        shadow = {
                            "plan_start": "workz_start_utc",
                            "check_in_time": "workz_start_utc",
                            "plan_end": "workz_end_utc",
                            "check_out_time": "workz_end_utc",
                        }.get(field)
                        if shadow:
                            fields[shadow] = original.replace(tzinfo=None)
            # This dynamic import site is constrained by SUPPORTED and validated
            # against the destination metadata before creating a document.
            if "doctype" in fields or "name" in fields:
                raise ValueError("Source payload cannot override document identity")
            payload = dict(fields, doctype=r["doctype"])
            meta = frappe.get_meta(r["doctype"])
            for field in meta.fields:
                if (
                    field.reqd
                    and not field.default
                    and payload.get(field.fieldname) in (None, "")
                ):
                    raise ValueError(
                        "Missing target mandatory field: " + field.fieldname
                    )
            doc = frappe.get_doc(payload)
            doc.insert(ignore_permissions=True)
            mapping[identity] = doc.name
            for item in r.get("attachments", []):
                save_file(
                    Path(item["path"]).name,
                    (source.parent / item["path"]).read_bytes(),
                    doc.doctype,
                    doc.name,
                    is_private=1,
                )
            frappe.get_doc(
                dict(
                    doctype="Workz Import Map",
                    source_key=hashlib.sha256(
                        (manifest["source_site"] + "\0" + identity).encode()
                    ).hexdigest(),
                    target_type=doc.doctype,
                    target_name=doc.name,
                    source_hash=digest(r),
                    batch_id=manifest["batch_id"],
                    source_record=json.dumps(r, ensure_ascii=False),
                )
            ).insert(ignore_permissions=True)
        # Reconcile target values using source identities, never compare renamed IDs.
        target = []
        for r in records:
            if r["doctype"] != "Timesheet Entry":
                continue
            doc = frappe.get_doc("Timesheet Entry", mapping[key(r)])
            f = dict(r["fields"])
            for field in (
                "check_in_time",
                "check_out_time",
                "status",
                "duration_hours",
            ):
                f[field] = str(doc.get(field))
            from erplite.workz.api import zone
            from erplite.workz.domain import instant

            for field in ("check_in_time", "check_out_time"):
                shadow = (
                    "workz_start_utc" if field == "check_in_time" else "workz_end_utc"
                )
                f[field] = (
                    instant(doc.get(shadow), "UTC").isoformat()
                    if doc.get(shadow)
                    else instant(f[field], zone()).isoformat()
                )
            target.append({**r, "fields": f})
        if reconcile(target, manifest["timezone"]) != result["reconciliation"]:
            raise ValueError("Target reconciliation differs; entire import rolled back")
        result["mapping"] = mapping
        result["applied"] = True
        return result
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.flags.workz_history_import = previous


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    args = parser.parse_args()
    output = validate(json.loads(Path(args.manifest).read_text()))
    print(json.dumps(output, indent=2))
    raise SystemExit(0 if output["valid"] else 1)
