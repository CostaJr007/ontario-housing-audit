import unittest

from src.common import RAW, ROOT, read_json
from src.residential import cell_count, cmhc_key, metric_counts, parse_workbook


class ResidentialMeaningTests(unittest.TestCase):
    def test_zero_and_unavailable_are_different(self):
        self.assertEqual(cell_count("-"), 0)
        self.assertEqual(cell_count(0), 0)
        self.assertIsNone(cell_count("N/A"))
        self.assertIsNone(cell_count(None))
        for bad in ("--", "suppressed", -1, 0.5, True):
            with self.assertRaises(ValueError):
                cell_count(bad)

    def test_houses_are_units_in_three_types_and_apartments_stay_separate(self):
        result = metric_counts([10, 4, 20, 66, 100])
        self.assertEqual(result["houses"], 34)
        self.assertEqual(result["apartment_other"], 66)
        self.assertEqual(result["total"], 100)

    def test_invalid_component_totals_fail(self):
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            metric_counts([10, 4, 20, 66, 101])

    def test_unknown_components_do_not_turn_into_zero(self):
        result = metric_counts([None]*5)
        self.assertIsNone(result["total"])
        self.assertIsNone(result["houses"])

    def test_reviewed_name_aliases_do_not_remove_regional_suffixes(self):
        self.assertEqual(cmhc_key("Greater Sudbury / Grand Sudbury CV"), "greatersudbury")
        self.assertEqual(cmhc_key("Peterborough CY"), "peterboroughcity")
        self.assertNotEqual(cmhc_key("Woodstock CA"), "woodstock")


class ResidentialSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.excluded = parse_workbook(RAW / "cmhc/csd_december_2025.xlsx", 2025)
        cls.folder = ROOT / "data/processed/residential_2025"
        cls.rows = read_json(cls.folder / "municipal_units.json")
        cls.summary = read_json(cls.folder / "summary.json")

    def test_annual_columns_are_used_instead_of_monthly_or_under_construction(self):
        toronto = self.records["toronto"]
        self.assertEqual(toronto["starts_total"], 10561)
        self.assertNotEqual(toronto["starts_total"], 1245)  # December alone.
        self.assertEqual(toronto["completions_total"], 14753)
        self.assertEqual(toronto["starts_houses"], 544+44+261)
        self.assertEqual(toronto["starts_apartment_other"], 9712)

    def test_regional_aggregates_cannot_fill_a_municipal_gap(self):
        self.assertTrue(any(r["label"] == "Woodstock CA" for r in self.excluded))
        woodstock = next(r for r in self.rows if r["municipality"] == "Woodstock")
        self.assertIsNone(woodstock["starts_total"])
        self.assertFalse(woodstock["has_cmhc_municipal_row"])

    def test_starts_and_completions_have_different_explicit_coverage(self):
        self.assertEqual(self.summary["starts_coverage"], 49)
        self.assertEqual(self.summary["completions_coverage"], 42)
        sarnia = self.records["sarnia"]
        self.assertEqual(sarnia["starts_total"], 299)
        self.assertIsNone(sarnia["completions_total"])

    def test_each_published_total_reconciles_without_bff_additions(self):
        self.assertEqual(self.summary["starts_total"], 54032)
        self.assertEqual(self.summary["starts_houses"]+self.summary["starts_apartment_other"], self.summary["starts_total"])
        for row in self.rows:
            for metric in ("starts", "completions"):
                if row[f"{metric}_total"] is not None:
                    self.assertEqual(sum(row[f"{metric}_{t}"] for t in ("single","semi","row","apartment_other")), row[f"{metric}_total"])
        audit = read_json(self.folder / "join_audit.json")
        self.assertTrue(audit["valid"])
        self.assertEqual(audit["municipalities_matched"], 50)


if __name__ == "__main__":
    unittest.main()
