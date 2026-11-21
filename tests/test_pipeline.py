"""Checks that protect the audit's denominators, boundaries and source accounting."""
import unittest

from src.analyze import AGGREGATE, load_year
from src.common import ROOT, normalize_name, read_json


class SourceAccountingTests(unittest.TestCase):
    def test_2024_aggregate_is_excluded_from_municipality_count(self):
        rows = load_year(2024)
        municipal = [r for r in rows if r["scope"] == "individual_target"]
        self.assertEqual(len(municipal), 50)
        self.assertNotIn(AGGREGATE, [r["municipality"] for r in municipal])
        self.assertEqual(sum(r["met_100pct"] for r in municipal), 15)
        self.assertEqual(sum(r["official_progress"] for r in rows), 94908)

    def test_individual_published_percentages_reconcile(self):
        for year in (2023, 2024):
            for row in load_year(year):
                if row["scope"] == "individual_target":
                    self.assertTrue(row["percentage_reconciles"], row["municipality"])

    def test_known_aggregate_source_discrepancy_is_visible(self):
        aggregate = next(r for r in load_year(2023) if r["municipality"] == AGGREGATE)
        self.assertFalse(aggregate["percentage_reconciles"])
        self.assertEqual(aggregate["published_progress_pct"], 128.20)

    def test_provincial_components_reconcile_to_csv(self):
        reference = read_json(ROOT / "data/reference/tracker_composition_2024.json")
        self.assertEqual(sum(reference["components"].values()), reference["official_progress"])
        self.assertEqual(reference["official_progress"], sum(r["official_progress"] for r in load_year(2024)))

    def test_hamilton_names_require_identifier_disambiguation(self):
        self.assertEqual(normalize_name("CITY OF HAMILTON"), normalize_name("TOWNSHIP OF HAMILTON"))
        self.assertEqual(normalize_name("Whitchurch–Stouffville"), normalize_name("Whitchurch-Stouffville"))


if __name__ == "__main__":
    unittest.main()
