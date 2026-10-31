"""Run ONLY on the disposable Currency rehearsal site, before real install.

bench --site workz-synthetic-migration-20261031.local execute \
    tests.workz.frappe_currency_smoke.run

If tests is not an importable package in the bench, run this file with bench
execute runpy.run_path, then invoke run(). This test changes rehearsal metadata
and commits it to prove repeated framework sync preserves compatibility fields.
"""


def run():
    import frappe
    from erplite.setup.currency_compat import ensure_currency_fields

    assert frappe.local.site == "workz-synthetic-migration-20261031.local", \
        "Currency smoke test is restricted to the disposable rehearsal site"
    names = ("name", "currency_name", "enabled", "fraction", "fraction_units",
             "smallest_currency_fraction_value", "symbol", "symbol_on_right", "number_format")
    # DB columns survive the previous legacy-schema rehearsal, even where the
    # legacy metadata hid framework fields. Read directly to capture all values.
    columns = ", ".join("`" + name + "`" for name in names)
    before = frappe.db.sql("SELECT " + columns + " FROM `tabCurrency` ORDER BY name")
    legacy_fields = ("currency_code", "is_base_currency", "exchange_rate", "last_update")
    retained = [name for name in legacy_fields if frappe.db.has_column("Currency", name)]
    legacy_before = {}
    for name in retained:
        legacy_before[name] = dict(frappe.db.sql(
            "SELECT name, `" + name + "` FROM `tabCurrency`"))

    ensure_currency_fields()
    frappe.db.commit()
    for _ in range(2):
        frappe.reload_doc("geo", "doctype", "currency", force=True)
        ensure_currency_fields()
        frappe.db.commit()

    assert frappe.db.get_value("DocType", "Currency", "module") == "Geo"
    after = frappe.db.sql("SELECT " + columns + " FROM `tabCurrency` ORDER BY name")
    assert before == after, "Framework currency values changed"
    for name in retained:
        current = dict(frappe.db.sql("SELECT name, `" + name + "` FROM `tabCurrency`"))
        for key, value in legacy_before[name].items():
            if name == "currency_code" and not value:
                assert current[key] == key
            else:
                assert current[key] == value, "Legacy currency value changed: " + name
    meta = frappe.get_meta("Currency", cached=False)
    assert all(meta.has_field(name) for name in (*names[1:], *legacy_fields))
    from frappe.model.base_document import get_controller
    from frappe.geo.doctype.currency.currency import Currency as FrameworkCurrency
    assert issubclass(get_controller("Currency"), FrameworkCurrency)
    print({"currency_compatibility": "passed", "rows_preserved": len(before),
           "framework_reload_repeats": 2})
