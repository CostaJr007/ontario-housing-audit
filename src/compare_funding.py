"""Compare verified funding events with provincial performance, retaining different dates and units."""
import argparse
import csv

from src.analyze import load_year
from src.common import PROCESSED, RAW, REPORTS, ROOT, normalize_name, read_json, write_json
from src.ingest import download


def compare(reference, provincial_rows):
    provincial = {r["municipality_key"]: r for r in provincial_rows if r["scope"] == "individual_target"}
    result = []
    seen = set()
    for case in reference["cases"]:
        key = normalize_name(case["municipality"])
        if key in seen:
            raise ValueError(f"Duplicate funding case: {key}")
        seen.add(key)
        source = reference["sources"][case["haf_source"]]
        p = provincial.get(key)
        award = case["bff_award_announced_cad"]
        reduction = case["haf_amount_reduced_cad"]
        if award is not None and award <= 0:
            raise ValueError("An award must be positive or explicitly unknown (null)")
        if reduction is not None and (reduction <= 0 or case["haf_event"] != "funding_reduced"):
            raise ValueError("Only a quantified reduction can populate the reduction field")
        if award is not None and (p is None or p["official_progress"] * 100 < p["target"] * 80):
            raise ValueError("Selected award does not match annual provincial threshold; inspect evidence")
        result.append({
            "municipality": case["municipality"], "municipality_key": key,
            "provincial_year": reference["provincial_performance_year"] if p else None,
            "provincial_target": p["target"] if p else None,
            "provincial_official_progress": p["official_progress"] if p else None,
            "provincial_progress_pct": p["official_progress_pct"] if p else None,
            "meets_bff_80pct_numeric_threshold": p["official_progress"] * 100 >= p["target"] * 80 if p else None,
            "bff_award_announced_cad": award,
            "bff_announcement_date": case["bff_announcement_date"],
            "bff_source_url": reference["sources"][case["bff_source"]] if case["bff_source"] else None,
            "haf_event": case["haf_event"], "haf_event_label_en": case["haf_event_label_en"],
            "haf_event_date": case["haf_event_date"], "haf_date_meaning": case["haf_date_meaning"],
            "haf_amount_reduced_cad": reduction,
            "haf_base_amount_applied_for_cad": case["haf_base_amount_applied_for_cad"],
            "haf_source_url": source, "haf_source_locator": case["haf_source_locator"],
            "reason_en": case["reason_en"],
        })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-sources", action="store_true", help="Archive available official supporting documents")
    args = parser.parse_args()
    reference = read_json(ROOT / "data/reference/funding_cases.json")
    if args.download_sources:
        manifest = read_json(RAW / "manifest.json")
        failures = {}
        # The two provincial releases were verified through indexed official text;
        # archive their municipal confirmation pages as well, avoiding JS-only shells.
        snapshots = {
            "windsor_haf": "windsor_council_2024.pdf",
            "oakville_haf": "oakville_whitepaper_2025.pdf",
            "cmhc_reductions": "cmhc_reductions_2026.html",
            "cmhc_tecumseh": "cmhc_tecumseh_2026.html",
            "haf_rules": "cmhc_haf_rules_2026.html",
        }
        for key, name in snapshots.items():
            try:
                download(reference["sources"][key], RAW / "funding" / name, manifest)
                if name.endswith(".pdf") and not (RAW / "funding" / name).read_bytes().startswith(b"%PDF-"):
                    raise ValueError(f"Not a PDF: {name}")
            except (OSError, ValueError) as error:
                failures[key] = str(error)
        write_json(PROCESSED / "funding_source_capture.json", {"failures": failures})
        if failures:
            print("Source capture failures:", failures)
    rows = compare(reference, load_year(2024))
    PROCESSED.mkdir(parents=True, exist_ok=True)
    with (PROCESSED / "funding_comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    provincial = [r for r in load_year(2024) if r["scope"] == "individual_target"]
    award_cases = [r for r in rows if r["bff_award_announced_cad"] is not None]
    summary = {
        "selection": reference["selection"],
        "documented_cases": len(rows),
        "cases_with_bff_award_and_adverse_haf_event": len(award_cases),
        "selected_bff_awards_announced_cad": sum(r["bff_award_announced_cad"] for r in award_cases),
        "selected_quantified_haf_reductions_cad": sum(r["haf_amount_reduced_cad"] for r in rows if r["haf_amount_reduced_cad"] is not None),
        "provincial_2024_meet_80pct_numeric_threshold": sum(r["official_progress"] * 100 >= r["target"] * 80 for r in provincial),
        "provincial_2024_meet_100pct": sum(r["met_100pct"] for r in provincial),
        "note": "Awards are announced amounts, not verified bank transfers. Different program periods. No balance is calculated between provincial awards and federal reductions. An unresearched city is not classified as HAF-compliant.",
    }
    write_json(PROCESSED / "funding_summary.json", summary)
    text=["# Funding criteria and documented decisions","",
        "Generated by `python -m src.compare_funding`, using identified official sources and the provincial municipal CSV.","",
        f"In 2024, {summary['provincial_2024_meet_80pct_numeric_threshold']} of 50 targeted municipalities reached the 80% numeric BFF threshold; {summary['provincial_2024_meet_100pct']} reached 100%. This does not verify payments to all of them.","",
        "| Municipality | Provincial 2024 performance | Announced BFF award C$ | Federal HAF event | Event date | Quantified reduction C$ |","|---|---:|---:|---|---|---:|"]
    for r in rows:
        pct=f"{r['provincial_progress_pct']:.2f}%" if r["provincial_progress_pct"] is not None else "Outside the 50"
        award=f"{r['bff_award_announced_cad']:,}" if r["bff_award_announced_cad"] is not None else "Not researched"
        reduction=f"{r['haf_amount_reduced_cad']:,}" if r["haf_amount_reduced_cad"] is not None else "Not quantified"
        text.append(f"| {r['municipality']} | {pct} | {award} | {r['haf_event_label_en']} | {r['haf_event_date']} | {reduction} |")
    text += ["","## Interpretation","",
        "Windsor and Oakville total C$18.4 million in provincial awards announced in 2025 for 2024 performance, alongside documented adverse HAF events in 2024. These are two selected cases, not a count of every municipality in that situation.","",
        "BFF rewards counted housing progress from 80% of the annual target. HAF also involves committed reforms and permitted-unit targets. High provincial performance does not establish federal application approval or continuing compliance.","",
        "Toronto and Vaughan's quantified HAF reductions total C$17.4 million in January 2026 decisions. This is separate from Windsor/Oakville's provincial awards. Rejected applications and ended participation are not treated as known monetary cuts.","",
        "## Case evidence",""]
    for r in rows:
        text += [f"### {r['municipality']}","",r["reason_en"],"",
            f"- [HAF evidence]({r['haf_source_url']}); {r['haf_source_locator']}.",
            f"- Date: {r['haf_event_date']}. {r['haf_date_meaning']}"]
        if r["bff_source_url"]:
            text.append(f"- [Provincial announcement]({r['bff_source_url']}), {r['bff_announcement_date']}.")
        text.append("")
    text += ["## Limitations","",summary["note"],"",
        "Events are historical and dated, not a complete register of current agreement status. Unresearched municipalities remain unclassified. Reaching 80% is the identified numeric BFF criterion, not an administrative decision or proof of payment.","",
        "Research context: reports/funding_research.md."]
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "funding_comparison.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
