"""Add ERPLite fields to framework Currency without replacing its schema.

Older ERPLite releases shipped a conflicting Setup/Currency DocType. Frappe
retains table columns when reloading metadata, so its values can be exposed as
Custom Fields after restoring the framework definition. No currency row is
deleted, renamed, enabled, repriced or selected as a base currency here.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


CURRENCY_FIELDS = (
    dict(fieldname="currency_code", label="Currency Code", fieldtype="Data",
         insert_after="currency_name", read_only=1),
    dict(fieldname="is_base_currency", label="Is Base Currency", fieldtype="Check",
         insert_after="number_format", default="0"),
    dict(fieldname="exchange_rate", label="Exchange Rate", fieldtype="Float",
         insert_after="is_base_currency", precision="9", default="1"),
    dict(fieldname="last_update", label="Last Update", fieldtype="Datetime",
         insert_after="exchange_rate", read_only=1),
)


def ensure_currency_fields():
    """Idempotent install/migrate hook; retain existing custom field settings."""
    module = frappe.db.get_value("DocType", "Currency", "module")
    if module not in ("Geo", "Setup"):
        frappe.throw("ERPLite requires Frappe Geo Currency; unexpected Currency owner")

    # Reject collisions before a legacy metadata reload can change any schema.
    existing_meta = frappe.get_meta("Currency", cached=False)
    for definition in CURRENCY_FIELDS:
        existing = existing_meta.get_field(definition["fieldname"])
        if existing and existing.fieldtype != definition["fieldtype"]:
            frappe.throw("Incompatible Currency field: " + definition["fieldname"])

    if module == "Setup":
        # Restore metadata only. Do not delete Currency or its table. This runs
        # before model sync on upgrades, while legacy column values still exist.
        frappe.reload_doc("geo", "doctype", "currency", force=True,
                          reset_permissions=True)
        frappe.clear_cache(doctype="Currency")

    meta = frappe.get_meta("Currency", cached=False)
    missing = []
    for definition in CURRENCY_FIELDS:
        existing = meta.get_field(definition["fieldname"])
        if not existing:
            missing.append(definition.copy())

    if missing:
        create_custom_fields({"Currency": missing}, update=False)

    # Core Currency's name is its identifier (e.g. AUD). Populate only a new or
    # blank compatibility field; preserve legacy codes and all core row values,
    # including enabled flags and modification timestamps.
    frappe.db.sql("""
        UPDATE `tabCurrency` SET currency_code = name
        WHERE currency_code IS NULL OR currency_code = ''
    """)
