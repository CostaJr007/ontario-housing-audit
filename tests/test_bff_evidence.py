"""Protect the distinctions that matter when reconstructing public funding data."""
import unittest

from src.bff_evidence import TextExtractor, annual_fact, classify_evidence, normalize_text
from src.common import ROOT, read_json


class EvidenceMeaningTests(unittest.TestCase):
    def test_missing_results_are_unknown_even_for_an_assigned_municipality(self):
        result = classify_evidence({"target": None, "official_progress": None, "award_confirmed": False})
        self.assertEqual(result, {"category": "unknown", "met_80pct": None})

    def test_award_does_not_fabricate_a_numeric_percentage(self):
        result = classify_evidence({"target": None, "official_progress": None, "award_confirmed": True})
        self.assertEqual(result, {"category": "award_confirmed", "met_80pct": None})

    def test_numeric_threshold_is_inclusive_and_a_real_zero_is_red(self):
        self.assertEqual(classify_evidence({"target": 100, "official_progress": 80, "award_confirmed": False})["category"], "eligible")
        self.assertEqual(classify_evidence({"target": 100, "official_progress": 0, "award_confirmed": False})["category"], "below_80")

    def test_conflicting_award_and_numeric_result_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            classify_evidence({"municipality": "Example", "target": 100, "official_progress": 79, "award_confirmed": True})

    def test_other_metrics_and_partial_years_cannot_be_mixed_into_annual_bff(self):
        source = {"period_start": "2025-01-01", "period_end": "2025-12-31", "metric": "building_permits"}
        with self.assertRaisesRegex(ValueError, "cannot substitute"):
            annual_fact("", source, 2025)
        source.update(metric="bff_comparable_progress", period_end="2025-10-31")
        with self.assertRaisesRegex(ValueError, "full, matching"):
            annual_fact("", source, 2025)

    def test_changed_document_and_ambiguous_numbers_are_rejected(self):
        source = {"period_start": "2025-01-01", "period_end": "2025-12-31", "metric": "bff_comparable_progress",
                  "anchors": ["2025 result"], "target_pattern": r"target (?P<value>\d+)", "progress_pattern": r"progress (?P<value>\d+)"}
        with self.assertRaisesRegex(ValueError, "missing anchor"):
            annual_fact("2024 result target 100 progress 80", source, 2025)
        with self.assertRaisesRegex(ValueError, "found 2"):
            annual_fact("2025 result target 100 target 120 progress 80", source, 2025)

    def test_html_scripts_do_not_pollute_numeric_extraction(self):
        parser = TextExtractor()
        parser.feed('<script>target 999</script><p>target <strong>430</strong></p><p>progress 528</p>')
        self.assertEqual(normalize_text(" ".join(parser.parts)), "target 430 progress 528")


class EvidenceSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = ROOT / "data/processed/bff_2025"
        cls.rows = read_json(cls.folder / "municipal_evidence.json")
        cls.summary = read_json(cls.folder / "summary.json")

    def test_all_50_join_with_no_inherited_2024_values(self):
        audit = read_json(self.folder / "join_audit.json")
        self.assertTrue(audit["valid"])
        self.assertEqual(len({r["MUNID"] for r in self.rows}), 50)
        self.assertEqual(audit["projection"], "EPSG:3347")
        unknown = next(r for r in self.rows if r["municipality"] == "Ottawa")
        self.assertIsNone(unknown["target"])
        self.assertIsNone(unknown["official_progress"])
        self.assertEqual(unknown["category"], "unknown")

    def test_financial_coverage_is_separate_from_numeric_coverage(self):
        self.assertEqual(self.summary["award_confirmed"], 18)
        self.assertEqual(self.summary["numeric_coverage"], 2)
        self.assertFalse(self.summary["complete_performance_dataset"])
        welland = next(r for r in self.rows if r["municipality"] == "Welland")
        self.assertEqual((welland["target"], welland["official_progress"], welland["award_cad"]), (430, 528, 1669317))
        toronto = next(r for r in self.rows if r["municipality"] == "Toronto")
        self.assertEqual((toronto["target"], toronto["official_progress"]), (28500, 13928))
        self.assertEqual(toronto["category"], "below_80")

    def test_numeric_evidence_can_be_reextracted_from_original_documents(self):
        from src.bff_evidence import extract_text
        registry = read_json(ROOT / "data/reference/bff_2025_sources.json")
        for source in registry["sources"]:
            if source["adapter"] != "annual_progress":
                continue
            fact = annual_fact(extract_text(ROOT / source["path"], source), source, 2025)
            row = next(r for r in self.rows if r["municipality"] == source["municipality"])
            self.assertEqual((fact["target"], fact["official_progress"]), (row["target"], row["official_progress"]))


if __name__ == "__main__":
    unittest.main()
