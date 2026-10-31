"""Offline install-hook contracts. Real Frappe rehearsal is still required."""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]


class CurrencyCompatibility(unittest.TestCase):
    def setUp(self):
        self.core = {name: SimpleNamespace(fieldtype=kind) for name, kind in (
            ("currency_name", "Data"), ("enabled", "Check"),
            ("fraction", "Data"), ("fraction_units", "Int"),
            ("smallest_currency_fraction_value", "Currency"),
            ("symbol", "Data"), ("symbol_on_right", "Check"),
            ("number_format", "Select"),
        )}
        self.fields = self.core.copy()
        self.frappe = ModuleType("frappe")
        self.frappe.db = SimpleNamespace(get_value=Mock(return_value="Geo"), sql=Mock())
        self.frappe.get_meta = Mock(return_value=SimpleNamespace(get_field=self.fields.get))
        self.frappe.reload_doc = Mock()
        self.frappe.clear_cache = Mock()
        self.frappe.throw = Mock(side_effect=ValueError)
        custom = ModuleType("frappe.custom.doctype.custom_field.custom_field")
        custom.create_custom_fields = Mock(side_effect=self.create)
        self.create_fields = custom.create_custom_fields
        with patch.dict("sys.modules", {"frappe": self.frappe, custom.__name__: custom}):
            spec = importlib.util.spec_from_file_location(
                "currency_compat_test", ROOT / "erplite/setup/currency_compat.py")
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)

    def create(self, declarations, update):
        self.assertFalse(update)
        for definition in declarations["Currency"]:
            self.fields[definition["fieldname"]] = SimpleNamespace(**definition)

    def test_install_and_repeat_keep_core_metadata(self):
        self.module.ensure_currency_fields()
        self.module.ensure_currency_fields()
        self.frappe.reload_doc.assert_not_called()
        self.create_fields.assert_called_once()
        for name, field in self.core.items():
            self.assertIs(self.fields[name], field)
        self.assertEqual(len(self.fields), len(self.core) + 4)

    def test_legacy_owner_restored_before_custom_fields(self):
        self.frappe.db.get_value.return_value = "Setup"
        events = []
        self.frappe.reload_doc.side_effect = lambda *a, **k: events.append("restore")
        original_create = self.create
        def create(*args, **kwargs):
            events.append("extend")
            original_create(*args, **kwargs)
        self.create_fields.side_effect = create
        self.module.ensure_currency_fields()
        self.assertEqual(events, ["restore", "extend"])
        self.frappe.reload_doc.assert_called_once_with(
            "geo", "doctype", "currency", force=True, reset_permissions=True)

    def test_existing_compatible_custom_fields_are_not_rewritten(self):
        for definition in self.module.CURRENCY_FIELDS:
            self.fields[definition["fieldname"]] = SimpleNamespace(**definition)
        original = self.fields.copy()
        self.module.ensure_currency_fields()
        self.create_fields.assert_not_called()
        self.assertEqual(self.fields, original)

    def test_conflicting_field_type_stops_without_writes(self):
        self.fields["exchange_rate"] = SimpleNamespace(fieldtype="Data")
        with self.assertRaises(ValueError):
            self.module.ensure_currency_fields()
        self.create_fields.assert_not_called()
        self.frappe.db.sql.assert_not_called()

    def test_unexpected_owner_stops_without_writes(self):
        self.frappe.db.get_value.return_value = "Another App"
        with self.assertRaises(ValueError):
            self.module.ensure_currency_fields()
        self.frappe.reload_doc.assert_not_called()
        self.create_fields.assert_not_called()
        self.frappe.db.sql.assert_not_called()

    def test_legacy_field_conflict_stops_before_metadata_reload(self):
        self.frappe.db.get_value.return_value = "Setup"
        self.fields["exchange_rate"] = SimpleNamespace(fieldtype="Data")
        with self.assertRaises(ValueError):
            self.module.ensure_currency_fields()
        self.frappe.reload_doc.assert_not_called()
        self.create_fields.assert_not_called()
        self.frappe.db.sql.assert_not_called()

    def test_backfill_only_targets_blank_compatibility_codes(self):
        self.module.ensure_currency_fields()
        statement = " ".join(self.frappe.db.sql.call_args.args[0].split())
        self.assertEqual(statement, "UPDATE `tabCurrency` SET currency_code = name "
                         "WHERE currency_code IS NULL OR currency_code = ''")

    def test_no_app_owned_currency_schema_can_be_synced(self):
        self.assertFalse((ROOT / "erplite/setup/doctype/currency/currency.json").exists())


if __name__ == "__main__":
    unittest.main()
