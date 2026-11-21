import unittest

from src.common import PROCESSED, RAW, read_json
from src.haf_progress import parse_table, percentage


class HAFProgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = []
        for intake in (2023, 2024):
            rows, _ = parse_table((RAW / f"haf/ontario_intake_{intake}.html").read_text(encoding="utf-8"), intake)
            cls.rows.extend(rows)

    def test_approval_progress_is_separate_from_action_plan_rating(self):
        ajax = next(r for r in self.rows if r["community"] == "Ajax")
        self.assertEqual(ajax["overall_assessment"], "good")
        self.assertEqual(ajax["permitted_units_pct_of_period_forecast"], 59)
        self.assertEqual(ajax["category"], "below_forecast")

    def test_cancelled_agreements_are_not_classified_as_zero(self):
        closed = [r for r in self.rows if r["category"] == "terminated"]
        self.assertEqual({r["community"] for r in closed}, {"Oakville", "Tecumseh"})
        self.assertTrue(all(r["permitted_units_pct_of_period_forecast"] is None for r in closed))

    def test_threshold_and_absence_are_distinct(self):
        self.assertEqual(percentage("0%"), 0)
        self.assertEqual(percentage("100%"), 100)
        self.assertIsNone(percentage("—"))
        with self.assertRaises(ValueError):
            percentage("suppressed")

    def test_municipal_denominator_preserves_indigenous_scope(self):
        summary = read_json(PROCESSED / "haf_map_summary.json")
        self.assertEqual(len(self.rows), 61)
        self.assertEqual(summary["municipalities_mapped"], 50)
        self.assertEqual(len(summary["indigenous_governments_outside_municipal_layer"]), 11)
        self.assertEqual(summary["municipalities_with_numeric_forecast_comparison"], 48)
        self.assertEqual(summary["below_forecast"], 32)
        self.assertEqual(summary["at_or_above_forecast"], 16)
        self.assertEqual(summary["unresolved"], [])


if __name__ == "__main__":
    unittest.main()
