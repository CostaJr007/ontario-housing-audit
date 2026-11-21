"""Reconstruct BFF annual evidence from HTML, PDF and reviewed official records."""
import argparse
import csv
import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from src.analyze import load_year
from src.bff import classify, join_municipalities
from src.common import PROCESSED, RAW, REPORTS, ROOT, normalize_name, read_json, write_json
from src.ingest import download


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def normalize_text(value):
    return re.sub(r"\s+", " ", value.replace("\u00ad", "")).strip()


def extract_text(path, source):
    if source["format"] == "pdf":
        reader = PdfReader(path)
        page = source.get("page")
        pages = [reader.pages[page - 1]] if page else reader.pages
        return normalize_text(" ".join(p.extract_text() for p in pages))
    if source["format"] == "html":
        parser = TextExtractor()
        parser.feed(path.read_text(encoding="utf-8-sig"))
        return normalize_text(" ".join(parser.parts))
    raise ValueError(f"Unsupported text source: {source['format']}")


def number(text: str, pattern: str) -> int:
    matches = list(re.finditer(pattern, text, flags=re.S))
    if len(matches) != 1:
        raise ValueError(f"Expected one numeric match, found {len(matches)}: {pattern}")
    return int(matches[0]["value"].replace(",", ""))


def annual_fact(text: str, source: dict[str, Any], year: int) -> dict[str, Any]:
    if source["period_start"] != f"{year}-01-01" or source["period_end"] != f"{year}-12-31":
        raise ValueError("Annual BFF evidence requires a full, matching calendar year")
    if source["metric"] != "bff_comparable_progress":
        raise ValueError("Permits, completions and pure starts cannot substitute for official BFF progress")
    for anchor in source["anchors"]:
        if normalize_text(anchor) not in text:
            raise ValueError(f"Source changed or wrong period: missing anchor {anchor!r}")
    target = number(text, source["target_pattern"])
    progress = number(text, source["progress_pattern"])
    classify(progress, target)  # Validate counts; classification is kept separate from awards.
    return {"target": target, "official_progress": progress,
            "official_progress_pct": progress / target * 100,
            "award_cad": number(text, source["award_cad_pattern"]) if source.get("award_cad_pattern") else None}


def classify_evidence(row):
    if row["target"] is not None and row["official_progress"] is not None:
        category = classify(row["official_progress"], row["target"])
        if row["award_confirmed"] and category == "below_80":
            raise ValueError(f"Conflicting performance and award evidence: {row['municipality']}")
        return {"category": category, "met_80pct": category == "eligible"}
    # An award is financial evidence, not an invented target or percentage.
    return {"category": "award_confirmed" if row["award_confirmed"] else "unknown", "met_80pct": None}


def reconstruct(registry, refresh=False):
    year = registry["year"]
    manifest_path = RAW / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    roster = [r for r in load_year(registry["roster_year"]) if r["scope"] == "individual_target"]
    if len({r["municipality_key"] for r in roster}) != len(roster):
        raise ValueError("Duplicate municipality in the program roster")
    if len({s["id"] for s in registry["sources"]}) != len(registry["sources"]):
        raise ValueError("Duplicate source identifiers")
    rows: dict[str, dict[str, Any]] = {r["municipality_key"]: {
        "municipality": r["municipality"], "municipality_key": r["municipality_key"],
        "scope": "individual_target", "year": year, "target": None,
        "official_progress": None, "official_progress_pct": None, "award_confirmed": False,
        "award_cad": None, "met_100pct": None, "source_ids": [], "evidence": []} for r in roster}
    provenance = []
    for source in registry["sources"]:
        path = (ROOT / source["path"]).resolve()
        if not path.is_relative_to(RAW.resolve()):
            raise ValueError("Source snapshots must stay inside data/raw")
        if source["format"] != "reviewed_extract":
            download(source["url"], path, manifest, refresh)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        provenance.append({**source, "sha256": digest,
                           "snapshot_kind": "reviewed_extract" if source["format"] == "reviewed_extract" else "original_download"})
        locator = {"source_id": source["id"], "url": source["url"], "locator": source["locator"],
                   "published_on": source["published_on"], "note": source.get("note", "")}
        if source["adapter"] == "award_roster":
            facts = read_json(path)
            names = facts["confirmed_award_municipalities"]
            keys = [normalize_name(n) for n in names]
            if facts["performance_year"] != year or facts["program_cohort_count"] != len(rows):
                raise ValueError("Award roster year or cohort does not match")
            if len(names) != facts["confirmed_award_count"] or len(keys) != len(set(keys)):
                raise ValueError("Award roster count mismatch or duplicate names")
            for key in keys:
                if key not in rows:
                    raise ValueError(f"Unmatched award municipality: {key}")
                rows[key]["award_confirmed"] = True
                rows[key]["source_ids"].append(source["id"])
                rows[key]["evidence"].append(locator)
        elif source["adapter"] == "annual_progress":
            key = normalize_name(source["municipality"])
            if key not in rows:
                raise ValueError(f"Unmatched progress municipality: {key}")
            fact = annual_fact(extract_text(path, source), source, year)
            row = rows[key]
            if row["target"] is not None and (row["target"], row["official_progress"]) != (fact["target"], fact["official_progress"]):
                raise ValueError(f"Conflicting annual counts: {row['municipality']}")
            if row["award_cad"] is not None and fact["award_cad"] is not None and row["award_cad"] != fact["award_cad"]:
                raise ValueError(f"Conflicting award amounts: {row['municipality']}")
            row.update({k: v for k, v in fact.items() if v is not None})
            row["met_100pct"] = fact["official_progress"] >= fact["target"]
            if fact["award_cad"] is not None:
                row["award_confirmed"] = True
            row["source_ids"].append(source["id"])
            row["evidence"].append(locator)
        else:
            raise ValueError(f"Unsupported evidence adapter: {source['adapter']}")
    return list(rows.values()), {"year": year, "sources": provenance,
        "roster_year": registry["roster_year"], "roster_note": registry["roster_note"],
        "roster_sha256": hashlib.sha256((RAW / f"ontario/housing_{registry['roster_year']}.csv").read_bytes()).hexdigest(),
        "reviewed_on": registry["reviewed_on"], "mode": "partial_multi_source_evidence"}


def run(sources_path=ROOT / "data/reference/bff_2025_sources.json", refresh=False):
    registry = read_json(sources_path)
    year = registry["year"]
    folder = PROCESSED / f"bff_{year}"
    rows, provenance = reconstruct(registry, refresh)
    provenance["registry_sha256"] = hashlib.sha256(sources_path.read_bytes()).hexdigest()
    geo, province, mapped, audit = join_municipalities(rows, provenance, folder, classify_evidence)
    summary = {"year": year, "with_targets": len(mapped),
        "award_confirmed": sum(r["award_confirmed"] for r in mapped),
        "numeric_coverage": sum(r["target"] is not None for r in mapped),
        "met_80pct_calculated": sum(r["met_80pct"] is True for r in mapped),
        "below_80pct_calculated": sum(r["met_80pct"] is False for r in mapped),
        "met_100pct_calculated": sum(r["met_100pct"] is True for r in mapped),
        "unknown": sum(r["category"] == "unknown" for r in mapped),
        "without_targets": int((geo["category"] == "unassigned").sum()),
        "complete_performance_dataset": all(r["target"] is not None for r in mapped),
        "note": "Awards and numeric performance are distinct measures. Unconfirmed does not mean below 80%. Municipal reports can precede final provincial reconciliation."}
    write_json(folder / "source.json", provenance)
    write_json(folder / "municipal_evidence.json", mapped)
    write_json(folder / "summary.json", summary)
    with (folder / "municipal_evidence.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = [k for k in mapped[0] if k != "evidence"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: ";".join(r[k]) if k == "source_ids" else r[k] for k in fields} for r in mapped)
    from src.plot_bff_evidence import render
    REPORTS.mkdir(parents=True, exist_ok=True)
    render(geo, province, mapped, summary, provenance)
    print(f"BFF {year} | official multi-source reconstruction")
    print(f"Program cohort: {summary['with_targets']} | JOIN: {audit['municipalities_matched']}/50")
    print(f"Confirmed allocations: {summary['award_confirmed']} (not a final list)")
    print(f"Annual target + progress available: {summary['numeric_coverage']}/50")
    print(f"Calculated >=80%: {summary['met_80pct_calculated']} | >=100%: {summary['met_100pct_calculated']} | <80%: {summary['below_80pct_calculated']}")
    print(f"Unresolved municipalities: {summary['unknown']} (never classified as zero or below target)")
    print(f"Outputs: reports/bff_{year}_ontario_map.png | reports/bff_{year}_ontario_map.html")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=ROOT / "data/reference/bff_2025_sources.json")
    parser.add_argument("--refresh", action="store_true", help="Refresh original downloads; reviewed extracts require human source review")
    args = parser.parse_args()
    run(args.sources, args.refresh)


if __name__ == "__main__":
    main()
