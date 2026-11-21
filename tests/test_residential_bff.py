import copy
import unittest

from src.common import PROCESSED, ROOT, normalize_name, read_json
from src.compare_residential_bff import compare
from src.plot_residential_bff import scenario


class ResidentialFundingComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {r["municipality"]:r for r in read_json(ROOT / "data/reference/bff_2025_comparison_cases.json")["cases"]}
        cls.residential = {r["municipality_key"]:r for r in read_json(PROCESSED / "residential_2025/municipal_units.json")}

    def result(self,name):
        return compare(self.cases[name],self.residential[normalize_name(name)])

    def test_kitchener_revised_starts_do_not_modify_archived_type_counts(self):
        row = self.result("Kitchener")
        self.assertEqual(row["cmhc_december_starts"],2416)
        self.assertEqual(row["new_starts_used"],2516)
        self.assertFalse(row["new_starts_met_80pct"])

    def test_independent_arus_change_residential_result_without_bed_inference(self):
        row = self.result("Kitchener")
        self.assertEqual(row["independent_including_arus"],2516+489)
        self.assertTrue(row["independent_including_arus_met_80pct"])
        self.assertEqual(row["announced_allocation_cad"],8013600)

    def test_unknown_breakdown_cannot_be_labelled_institutional(self):
        row = self.result("London")
        self.assertFalse(row["new_starts_met_80pct"])
        self.assertTrue(row["official_met_80pct"])
        self.assertIsNone(row["independent_including_arus"])
        self.assertIsNone(row["independent_including_arus_met_80pct"])

    def test_sarnia_and_welland_clear_cutoff_without_additional_categories(self):
        for name in ("Sarnia","Welland"):
            row = self.result(name)
            self.assertTrue(row["new_starts_met_80pct"])
            self.assertGreaterEqual(row["new_starts_pct"],100)

    def test_mismatched_city_and_nonreconciling_breakdown_fail(self):
        with self.assertRaisesRegex(ValueError,"Municipality mismatch"):
            compare(self.cases["Kitchener"],self.residential["london"])
        case = copy.deepcopy(self.cases["Kitchener"])
        case["reviewed_arus"] += 1
        with self.assertRaisesRegex(ValueError,"must reconcile"):
            compare(case,self.residential["kitchener"])

    def test_kitchener_changes_color_when_verified_arus_are_included(self):
        row = self.result("Kitchener")
        self.assertEqual(scenario(row,"new")["category"],"below")
        self.assertEqual(scenario(row,"independent")["category"],"above")
        self.assertEqual(scenario(row,"official")["category"],"above")

    def test_missing_arus_cannot_establish_failure_in_independent_scenario(self):
        self.assertEqual(scenario(self.result("London"),"independent")["category"],"unknown")
        sarnia = scenario(self.result("Sarnia"),"independent")
        self.assertTrue(sarnia["minimum"])
        self.assertEqual(sarnia["category"],"above")

    def test_unvalidated_target_stays_unknown_even_with_funding(self):
        row = {"in_cohort":True,"target":None,"award_confirmed":True}
        self.assertEqual(scenario(row,"new")["category"],"unknown")
        self.assertEqual(scenario({"in_cohort":False},"new")["category"],"outside")


if __name__=="__main__":
    unittest.main()
