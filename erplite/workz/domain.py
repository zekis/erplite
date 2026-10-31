"""Pure calendar and financial rules shared by API, import and tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo

CENT = Decimal("0.01")


def decimal(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a decimal number")
    if not number.is_finite() or number < 0:
        raise ValueError("Amount must be finite and nonnegative")
    return number


def instant(value, zone="UTC"):
    """API inputs require offsets; Frappe storage is site-local naive time."""
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        tz = ZoneInfo(zone)
        first = dt.replace(tzinfo=tz, fold=0)
        second = dt.replace(tzinfo=tz, fold=1)
        if first.utcoffset() != second.utcoffset():
            raise ValueError(
                "Ambiguous or nonexistent local time; supply an explicit UTC offset"
            )
        dt = first
    return dt.astimezone(timezone.utc)


def interval(start, end, zone="UTC"):
    start, end = instant(start, zone), instant(end, zone)
    if end <= start:
        raise ValueError("End must be after start")
    if end - start > timedelta(days=366):
        raise ValueError("Choose at most 366 days")
    return start, end


def overlaps(a, b, c, d):
    return a < d and c < b


def hours(start, end):
    return Decimal(str((end - start).total_seconds())) / Decimal(3600)


def clipped_hours(start, end, lower, upper):
    return (
        hours(max(start, lower), min(end, upper))
        if overlaps(start, end, lower, upper)
        else Decimal(0)
    )


def rate_at(rates, employee, project, kind, day):
    eligible = [
        r
        for r in rates
        if r["employee"] == employee
        and r["kind"] == kind
        and (kind == "Pay" or r.get("project") == project)
        and str(r["effective_from"])[:10] <= day
    ]
    return max(eligible, key=lambda r: str(r["effective_from"])) if eligible else None


def projection(entry, rates, lower, upper, zone="UTC"):
    """Split at local midnight: effective-date changes and DST are respected."""
    start, end = interval(entry["plan_start"], entry["plan_end"], zone)
    start, end = max(start, lower), min(end, upper)
    totals = {}
    missing = []
    if entry.get("kind") != "Work" or end <= start:
        return {"currencies": {}, "missing": []}
    while start < end:
        local = start.astimezone(ZoneInfo(zone))
        day = local.date().isoformat()
        midnight = datetime.combine(
            local.date() + timedelta(days=1), datetime.min.time(), ZoneInfo(zone)
        )
        stop = min(end, midnight.astimezone(timezone.utc))
        duration = hours(start, stop)
        day_currencies = set()
        for kind, key in [("Pay", "cost"), ("Sell", "revenue")]:
            if kind == "Sell" and not entry.get("billable"):
                continue
            rate = rate_at(rates, entry["user"], entry.get("project"), kind, day)
            if rate is None:
                missing.append(
                    {
                        "kind": kind,
                        "date": day,
                        "employee": entry["user"],
                        "project": entry.get("project"),
                    }
                )
                continue
            day_currencies.add(rate["currency"])
            bucket = totals.setdefault(
                rate["currency"], {"cost": Decimal(0), "revenue": Decimal(0)}
            )
            bucket[key] += duration * decimal(rate["amount"])
        if len(day_currencies) > 1:
            missing.append(
                {
                    "kind": "Currency conversion required",
                    "date": day,
                    "employee": entry["user"],
                    "project": entry.get("project"),
                }
            )
        start = stop
    return {
        "currencies": {
            c: {
                k: str(v.quantize(CENT, rounding=ROUND_HALF_UP))
                for k, v in amounts.items()
            }
            for c, amounts in totals.items()
        },
        "missing": missing,
    }
