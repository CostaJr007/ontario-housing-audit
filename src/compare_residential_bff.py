"""Compare BFF targets and announced allocations with residential-only measures."""
import csv
import hashlib

from src.bff import classify
from src.common import PROCESSED, REPORTS, ROOT, normalize_name, read_json, write_json


def compare(case, residential):
    if normalize_name(case["municipality"]) != residential["municipality_key"]:
        raise ValueError("Municipality mismatch")
    target = case["target"]
    classify(case["official_progress"], target)
    archived = residential["starts_total"]
    reviewed = case.get("reviewed_new_starts")
    starts = reviewed if reviewed is not None else archived
    arus = case.get("reviewed_arus")
    complete = case["complete_residential_breakdown"]
    independent = None
    if complete:
        if reviewed is None or arus is None or reviewed + arus != case["official_progress"]:
            raise ValueError("Complete residential breakdown must reconcile to the official total")
        independent = reviewed + arus
    return {"municipality":case["municipality"],"MUNID":residential["MUNID"],"year":residential["year"],
        "target":target,"cutoff_80pct_units":(target*80+99)//100,
        "official_progress":case["official_progress"],"official_pct":case["official_progress"]/target*100,
        "official_met_80pct":classify(case["official_progress"],target)=="eligible",
        "announced_allocation_cad":case["award_cad"],"allocation_status":"official announcement, not bank-transfer audit",
        "cmhc_december_starts":archived,"new_starts_used":starts,
        "new_starts_vintage":"municipal award release" if reviewed is not None else "CMHC December annual edition",
        "new_starts_pct":starts/target*100 if starts is not None else None,
        "new_starts_met_80pct":classify(starts,target)=="eligible" if starts is not None else None,
        "reviewed_arus":arus,"independent_including_arus":independent,
        "independent_including_arus_pct":independent/target*100 if independent is not None else None,
        "independent_including_arus_met_80pct":classify(independent,target)=="eligible" if independent is not None else None,
        "complete_residential_breakdown":complete,"target_source":case["target_source"],"award_source":case["award_source"],
        "note":case["note"]}


def main():
    reference = ROOT / "data/reference/bff_2025_comparison_cases.json"
    registry = read_json(reference)
    year = registry["year"]
    residential_path = PROCESSED / f"residential_{year}/municipal_units.json"
    source_path = PROCESSED / f"residential_{year}/source.json"
    units = read_json(residential_path)
    by_key = {r["municipality_key"]:r for r in units}
    if len(by_key) != len(units) or len({r["MUNID"] for r in units}) != len(units):
        raise ValueError("Duplicate residential municipality or MUNID")
    rows=[]
    for case in registry["cases"]:
        residential = by_key[normalize_name(case["municipality"])]
        if residential["year"] != year:
            raise ValueError("Cannot compare different performance years")
        rows.append(compare(case,residential))
    if len({r["MUNID"] for r in rows}) != len(rows):
        raise ValueError("Duplicate comparison cases")
    changed = [r for r in rows if r["official_met_80pct"] and r["new_starts_met_80pct"] is False]
    summary={"year":year,"documented_award_cases":len(rows),"program_cohort":len(units),
        "announced_allocations_in_sample_cad":sum(r["announced_allocation_cad"] for r in rows),
        "below_80pct_if_new_construction_only":[r["municipality"] for r in changed],
        "announced_allocations_in_new_construction_counterfactual_cad":sum(r["announced_allocation_cad"] for r in changed),
        "complete_independent_unit_breakdown_count":sum(r["complete_residential_breakdown"] for r in rows),
        "proven_bed_dependent_award_count":None,
        "interpretation":"Counterfactual new-construction-only comparison, not a finding of improper payments. Independent ARUs can house families and must not be called institutional beds."}
    folder=PROCESSED/f"residential_bff_{year}"
    write_json(folder/"municipal_comparison.json",rows)
    write_json(folder/"summary.json",summary)
    write_json(folder/"merge_audit.json",{"valid":True,"year":year,"matched":len(rows),"duplicates":[],"unmatched":[],
        "reference_sha256":hashlib.sha256(reference.read_bytes()).hexdigest(),
        "residential_data_sha256":hashlib.sha256(residential_path.read_bytes()).hexdigest(),
        "cmhc_source":read_json(source_path),"case_registry":str(reference.relative_to(ROOT)),
        "case_evidence_capture_method":registry["capture_method"],"reviewed_on":registry["reviewed_on"],
        "vintage_handling":"Kitchener award-release starts override archived total for the comparison only; archived dwelling-type detail is not scaled or overwritten"})
    with (folder/"municipal_comparison.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=[f"# Targets, self-contained housing and funding — {year}","",
        "Four documented award cases are compared against the same annual targets using different measures: official BFF progress; new residential construction only; and new construction plus independent ARUs where a complete breakdown is verified.","",
        "The Building Faster Fund (BFF) was Ontario's three-year program of up to C$1.2 billion supporting housing-enabling infrastructure. The numeric funding threshold was 80% of the annual target, not full target achievement.","",
        "| Municipality | Annual target | Official BFF progress | Official % | New-construction count used | New-construction % | Announced allocation C$ |","|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append(f"| {r['municipality']} | {r['target']} | {r['official_progress']} | {r['official_pct']:.2f}% | {r['new_starts_used']} | {r['new_starts_pct']:.2f}% | {r['announced_allocation_cad']:,} |")
    lines += ["",f"London and Kitchener total C${summary['announced_allocations_in_new_construction_counterfactual_cad']:,} in announced allocations and fall below 80% in a new-construction-only scenario. This does not establish improper payments or dependence on institutional beds.","",
        "**Kitchener provides an important control:** its municipality reports 2,516 starts + 489 ARUs = 3,005 units, or 85.86% of its target. Self-contained homes explain the published total without attributing the difference to institutional beds. The archived December CMHC edition reported 2,416 starts; the 100-unit difference in the later release is preserved as a vintage difference.","",
        "Sarnia (299/100) and Welland (458/430) already clear the threshold with conventional new construction in the edition consulted.","",
        "**London:** 54.32% from new construction alone versus 89.87% officially. The 4,224 official total still needs a component breakdown separating ARUs/conversions, institutional categories and revisions. Do not claim London qualified only by counting beds.","",
        "Independent ARUs and conversions can house families. Excluding them is appropriate only for an explicitly new-construction-only measure. A residential measure that excludes beds should include verified independent ARUs. Starts are not completions, occupancy or affordability.","",
        "## Sources and evidence","",f"- [CMHC municipal workbook, December {year} edition]({read_json(source_path)['source_url']}); municipal CSD totals, preserved in data/raw/cmhc/."]
    for r in rows:
        lines += [f"- **{r['municipality']}**: [annual target]({r['target_source']}); [result and announced allocation]({r['award_source']}). {r['note']}"]
    lines += ["","Official municipal/provincial facts were reviewed through web research and transcribed into the case registry; this is not automatic document extraction. Registry and residential-data hashes are in merge_audit.json. The four cases do not represent a complete audit of the 18 confirmed recipients and cannot establish a total amount attributable to institutional beds."]
    REPORTS.mkdir(parents=True,exist_ok=True)
    (REPORTS/f"residential_bff_{year}_findings.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    from src.plot_residential_bff import render
    render(rows, summary)
    with (REPORTS/f"residential_bff_{year}_findings.md").open("a",encoding="utf-8") as stream:
        stream.write(f"\n## Maps\n\n[PNG: targets and funding](residential_bff_{year}_ontario_map.png) · [Interactive map](residential_bff_{year}_ontario_map.html).\n\nThe PNG shows new construction only. The HTML switches between new construction, self-contained homes including verified ARUs, and official BFF progress. Blue outlines identify confirmed allocations; yellow preserves missing evidence. Four annual targets are verified in this comparison.\n")
    print(f"BFF {year}: targets + residential construction + announced allocations")
    for r in rows:
        print(f"{r['municipality']}: target {r['target']}; official {r['official_pct']:.2f}%; new construction {r['new_starts_pct']:.2f}%; C$ {r['announced_allocation_cad']:,}")
    print(f"Below 80% in new-construction-only scenario: {summary['below_80pct_if_new_construction_only']}; C$ {summary['announced_allocations_in_new_construction_counterfactual_cad']:,}")
    print("Kitchener including documented ARUs: 85.86%; no bed dependence inferred.")
    print(f"Report: reports/residential_bff_{year}_findings.md")
    print(f"Maps: reports/residential_bff_{year}_ontario_map.png | reports/residential_bff_{year}_ontario_map.html")


if __name__=="__main__":
    main()
