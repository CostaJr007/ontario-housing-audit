import unittest

from src.analyze import load_year
from src.common import ROOT, read_json
from src.compare_funding import compare


class FundingInterpretationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reference = read_json(ROOT / "data/reference/funding_cases.json")
        cls.rows = {r["municipality"]: r for r in compare(reference, load_year(2024))}

    def test_missing_provincial_coverage_remains_unknown(self):
        row = self.rows["Tecumseh"]
        self.assertIsNone(row["provincial_progress_pct"])
        self.assertIsNone(row["meets_bff_80pct_numeric_threshold"])
        self.assertIsNone(row["bff_award_announced_cad"])

    def test_rejected_application_is_not_a_quantified_cut(self):
        row = self.rows["Windsor"]
        self.assertEqual(row["haf_base_amount_applied_for_cad"], 40000000)
        self.assertIsNone(row["haf_amount_reduced_cad"])

    def test_bff_80pct_threshold_does_not_require_100pct(self):
        row = self.rows["Toronto"]
        self.assertTrue(row["meets_bff_80pct_numeric_threshold"])
        self.assertLess(row["provincial_progress_pct"], 100)
        self.assertIsNone(row["bff_award_announced_cad"])

    def test_money_categories_and_dates_remain_separate(self):
        rows = list(self.rows.values())
        awards = sum(r["bff_award_announced_cad"] or 0 for r in rows)
        cuts = sum(r["haf_amount_reduced_cad"] or 0 for r in rows)
        self.assertEqual(awards, 18400000)
        self.assertEqual(cuts, 17400000)
        self.assertEqual(self.rows["Oakville"]["haf_event_date"], "2024-05")
        self.assertEqual(self.rows["Oakville"]["bff_announcement_date"], "2025-09-24")


if __name__ == "__main__":
    unittest.main()
