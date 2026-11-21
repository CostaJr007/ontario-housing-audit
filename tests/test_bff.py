import csv
import unittest

from src.bff import classify
from src.common import ROOT, normalize_name, read_json
from src.ingest_bff import annual_resources


class BFFThresholdTests(unittest.TestCase):
    def test_inclusive_80pct_without_rounding(self):
        self.assertEqual(classify(80, 100), "eligible")
        self.assertEqual(classify(79, 100), "below_80")
        self.assertEqual(classify(79999, 100000), "below_80")
        self.assertEqual(classify(100, 100), "eligible")

    def test_missing_target_is_grey_but_missing_progress_is_an_error(self):
        self.assertEqual(classify(None, None), "unassigned")
        self.assertEqual(classify(0, 100), "below_80")
        with self.assertRaises(ValueError):
            classify(None, 100)
        with self.assertRaises(ValueError):
            classify(0, 0)

    def test_name_normalization_preserves_hamilton_ambiguity_for_auditing(self):
        self.assertEqual(normalize_name("City of Ottawa"), "ottawa")
        self.assertEqual(normalize_name("Town of Ajax"), "ajax")
        self.assertEqual(normalize_name("CITY OF HAMILTON"), normalize_name("TOWNSHIP OF HAMILTON"))

    def test_catalogue_discovery_uses_english_annual_resources(self):
        resources = [
            {"format": "CSV", "url": "https://example.org/housing_2024_-_en.csv"},
            {"format": "CSV", "url": "https://example.org/housing_2025_-_fr.csv"},
            {"format": "DOCX", "url": "https://example.org/dictionary_2025_-_en.docx"},
        ]
        self.assertEqual(set(annual_resources(resources)), {2024})


class BFFPublishedArtifactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = ROOT / "data/processed/bff"
        cls.audit = read_json(cls.folder / "join_audit.json")
        cls.summary = read_json(cls.folder / "summary.json")
        with (cls.folder / "municipal_progress.csv").open(encoding="utf-8", newline="") as stream:
            cls.rows = list(csv.DictReader(stream))

    def test_join_is_complete_and_uses_reviewed_identifiers(self):
        self.assertTrue(self.audit["valid"])
        self.assertEqual(self.audit["unmatched"], [])
        self.assertEqual(self.audit["duplicates"], [])
        self.assertEqual(len(self.rows), self.audit["municipalities_with_targets"])
        self.assertEqual(len({r["MUNID"] for r in self.rows}), len(self.rows))
        self.assertEqual(next(r for r in self.rows if r["municipality"] == "Hamilton")["MUNID"], "25005")
        self.assertNotIn("Municipalities without targets", [r["municipality"] for r in self.rows])

    def test_2024_denominators_and_toronto_between_80_and_100(self):
        if self.summary["year"] != 2024:
            self.skipTest("Golden counts apply to the archived 2024 edition")
        self.assertEqual(self.summary["with_targets"], 50)
        self.assertEqual(self.summary["met_80pct"], 25)
        self.assertEqual(self.summary["met_100pct"], 15)
        toronto = next(r for r in self.rows if r["municipality"] == "Toronto")
        self.assertEqual(toronto["category"], "eligible")
        self.assertLess(float(toronto["official_progress_pct"]), 100)

    def test_every_color_matches_exact_source_counts(self):
        for row in self.rows:
            self.assertEqual(row["category"], classify(int(row["official_progress"]), int(row["target"])))


if __name__ == "__main__":
    unittest.main()
