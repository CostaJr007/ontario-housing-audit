"""Build the BFF 80% eligibility maps using the repository's HAF visual layout."""
import argparse
import csv
import html
import json
import re
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from shapely.geometry import box

from src.common import RAW, REPORTS, ROOT, normalize_name, read_json, write_json
from src.ingest_bff import BFF_DATA, ingest
from src.plot_haf import path_data

COLORS = {"eligible": "#18856c", "below_80": "#d6545b", "unassigned": "#d8dde2"}
LABELS = {"eligible": "≥ 80%: meets the funding threshold", "below_80": "< 80%: below the funding threshold", "unassigned": "No assigned target"}
SOUTH_BOUNDS = (-83.7, 41.5, -74.1, 46.8)
OVERRIDES = {"hamilton": "25005", "peterboroughcity": "15014"}


def classify(progress, target):
    if target is None:
        return "unassigned"
    if target <= 0 or progress is None or progress < 0:
        raise ValueError("A municipality with a target requires a positive target and non-negative progress")
    # Compare exact counts, before display rounding.
    return "eligible" if progress * 100 >= target * 80 else "below_80"


def join_municipalities(source, provenance, output_dir=BFF_DATA, classify_row=None):
    geo = gpd.read_file(RAW / "geohub/municipalities.geojson")
    if geo.crs is None:
        raise ValueError("Municipal CRS is missing")
    raw_count = len(geo)
    invalid_count = int((~geo.geometry.is_valid).sum())
    geo["geometry"] = geo.geometry.make_valid(method="structure", keep_collapsed=False)
    if geo.geometry.isna().any():
        raise ValueError("Missing geometry after repair")
    empty_count = int(geo.geometry.is_empty.sum())
    geo = geo[~geo.geometry.is_empty].copy()
    geo["municipality_key"] = geo["MUNICIPAL_NAME_SHORTFORM"].map(normalize_name)
    geo = geo.dissolve(by="MUNID", as_index=False)
    assigned = [r for r in source if r["scope"] == "individual_target"]
    excluded = [r for r in source if r["scope"] != "individual_target"]
    keys = [r["municipality_key"] for r in assigned]
    mapped, unmatched, duplicates, matches = [], [], [], []
    if len(keys) != len(set(keys)):
        duplicates.append("Duplicate source municipality keys")
    for row in assigned:
        key = row["municipality_key"]
        candidates = geo[geo["municipality_key"] == key]
        original_ids = list(candidates["MUNID"])
        method = "unique_normalized_name"
        if key in OVERRIDES:
            candidates = geo[geo["MUNID"] == OVERRIDES[key]]
            method = "reviewed_municipal_identifier"
        if len(candidates) != 1:
            unmatched.append({"municipality": row["municipality"], "candidate_ids": original_ids})
            continue
        candidate = candidates.iloc[0]
        classification = classify_row(row) if classify_row else {
            "category": classify(row["official_progress"], row["target"]),
            "met_80pct": row["official_progress"] * 100 >= row["target"] * 80}
        record = {**row, "MUNID": str(candidate["MUNID"]), "boundary_name": candidate["MUNICIPAL_NAME"],
                  **classification}
        mapped.append(record)
        matches.append({"municipality": row["municipality"], "normalized_name": key,
                        "MUNID": record["MUNID"], "boundary_name": record["boundary_name"],
                        "candidate_ids_before_override": original_ids, "method": method})
    ids = [r["MUNID"] for r in mapped]
    if len(ids) != len(set(ids)):
        duplicates.append("Multiple source rows linked to the same MUNID")
    audit = {"program": "Ontario Building Faster Fund", "year": provenance["year"], "projection": "EPSG:3347",
             "source": provenance, "source_records": len(source), "municipalities_with_targets": len(assigned),
             "municipalities_matched": len(mapped), "municipal_boundary_count": len(geo),
             "raw_boundary_features": raw_count, "geometry_repairs_for_display": invalid_count,
             "collapsed_features_excluded": empty_count,
             "excluded_aggregate_rows": [r["municipality"] for r in excluded],
             "unmatched": unmatched, "duplicates": duplicates, "matches": matches,
             "valid": not unmatched and not duplicates and len(mapped) == len(assigned),
             "boundary_vintage": "Current GeoHub snapshot, not a reconstructed historical boundary",
             "optional_cmhc_comparison": "Unavailable at compatible municipal granularity in the ingested source; no bed-dependent classifications inferred"}
    write_json(output_dir / "join_audit.json", audit)
    if not audit["valid"]:
        raise ValueError(f"BFF join failed; inspect {output_dir / 'join_audit.json'}")
    by_id = {r["MUNID"]: r for r in mapped}
    geo["category"] = geo["MUNID"].map(lambda key: by_id[key]["category"] if key in by_id else "unassigned")
    geo = geo.to_crs(3347)
    province = gpd.read_file(RAW / "geohub/province.geojson").to_crs(3347)
    province["geometry"] = province.geometry.make_valid(method="structure", keep_collapsed=False)
    return geo, province, mapped, audit


def summarize(mapped, geo, year, large_city_count=10):
    if large_city_count < 1:
        raise ValueError("large-city-count must be positive")
    largest = sorted(mapped, key=lambda r: (-r["target"], r["municipality"]))[:large_city_count]
    return {"year": year, "with_targets": len(mapped), "met_80pct": sum(r["met_80pct"] for r in mapped),
            "met_100pct": sum(r["met_100pct"] for r in mapped), "below_80pct": sum(not r["met_80pct"] for r in mapped),
            "without_targets": int((geo["category"] == "unassigned").sum()),
            "large_city_count": large_city_count,
            "large_city_definition": f"The {large_city_count} largest annual targets; a target-size proxy, not a population ranking",
            "large_cities_red": [{"municipality": r["municipality"], "target": r["target"],
                                  "official_progress": r["official_progress"], "pct": r["official_progress_pct"]}
                                 for r in largest if not r["met_80pct"]],
            "classification": "Exact annual official progress / annual target >= 80%; no rounding before classification",
            "funding_interpretation": "Numeric performance eligibility, not a verification of awards or bank transfers"}


def plot_static(geo, province, mapped, summary):
    # Same fonts, palette, figure dimensions and axes positions as plot_haf.plot_static.
    bg, ink, muted = "#f4f2ed", "#172e3c", "#596574"
    fig = plt.figure(figsize=(12, 13), facecolor=bg)
    fig.text(.055, .958, f"ONTARIO  /  BUILDING FASTER FUND  /  {summary['year']}", fontsize=11, weight="bold", color=muted)
    fig.text(.055, .915, f"{summary['met_80pct']} of {summary['with_targets']} municipalities\nreached the 80% threshold.", fontsize=29, weight="bold", color=ink, va="top", linespacing=1.18)
    fig.text(.055, .806, f"Annual targets and official housing progress for {summary['year']}.\nThe fund's numeric performance threshold is 80% of the annual target.", fontsize=12, color=muted, va="top", linespacing=1.5)
    full = fig.add_axes((.04, .36, .32, .39))
    south = fig.add_axes((.365, .31, .60, .43))
    for ax in (full, south):
        ax.set_facecolor(bg)
        province.plot(ax=ax, color="#e9e8e1", edgecolor="#bcc4c8", linewidth=.6)
        geo.plot(ax=ax, color=geo["category"].map(COLORS), edgecolor=bg, linewidth=.22)
        ax.set_axis_off()
    bounds = gpd.GeoSeries([box(*SOUTH_BOUNDS)], crs=4326).to_crs(3347).total_bounds
    south.set_xlim(bounds[0], bounds[2])
    south.set_ylim(bounds[1], bounds[3])
    full.set_title("Entire province", fontsize=10, color=muted)
    south.set_title("Southern and eastern Ontario", fontsize=10, color=muted)
    offsets = {"toronto": (90_000, -10_000), "mississauga": (-150_000, -45_000), "ottawa": (-90_000, 90_000),
               "london": (-40_000, -100_000), "kitchener": (-170_000, 110_000)}
    for row in mapped:
        if row["municipality_key"] in offsets:
            point = geo.loc[geo["MUNID"] == row["MUNID"]].geometry.iloc[0].representative_point()
            dx, dy = offsets[row["municipality_key"]]
            pct = f"{row['official_progress_pct']:.1f}"
            south.annotate(f"{row['municipality']} · {pct}%", (point.x, point.y), (point.x+dx, point.y+dy), fontsize=9, color=ink,
                           bbox={"facecolor": bg, "alpha": .9, "edgecolor": "none", "pad": 2},
                           arrowprops={"arrowstyle": "-", "color": muted, "lw": .6})
    fig.legend(handles=[Patch(facecolor=COLORS[c], label=LABELS[c]) for c in COLORS], loc="lower left",
               bbox_to_anchor=(.05, .19), frameon=False, fontsize=11, ncol=2, columnspacing=2, labelspacing=1.1)
    fig.text(.055, .167, f"{summary['with_targets']} targeted municipalities: {summary['met_80pct']} reached 80%; {summary['below_80pct']} fell below.\n{summary['met_100pct']} reached 100%. Grey: {summary['without_targets']} municipalities without individual targets in this dataset.", color=muted, fontsize=10, linespacing=1.5, va="top")
    fig.text(.055, .102, "Progress is the official total, including categories beyond conventional housing starts.\nColours apply the numeric threshold; actual payments have not been reconciled.", color=ink, fontsize=10, linespacing=1.5, va="top")
    fig.text(.055, .039, f"Sources: Ontario Data Catalogue, Housing Supply Progress ({summary['year']}); current Ontario GeoHub boundaries.\nClassification uses exact annual counts. Audited MUNID join. EPSG:3347.", color=muted, fontsize=9, linespacing=1.5, va="top")
    fig.savefig(REPORTS / "bff_ontario_map.png", dpi=170, facecolor=bg)
    plt.close(fig)


def interactive(geo, province, mapped, summary):
    xmin, ymin, xmax, ymax = province.total_bounds
    scale = 1000 / (xmax-xmin)
    view = [-10, -10, 1020, (ymax-ymin)*scale+20]
    south = gpd.GeoSeries([box(*SOUTH_BOUNDS)], crs=4326).to_crs(3347).total_bounds
    south_view = [(south[0]-xmin)*scale, (ymax-south[3])*scale, (south[2]-south[0])*scale, (south[3]-south[1])*scale]
    by_id = {r["MUNID"]: {**r, "has_target": True, "label": LABELS[r["category"]]} for r in mapped}
    paths = []
    for geometry in province.geometry:
        paths.append(f'<path d="{path_data(geometry, xmin, ymax, scale)}" fill="#e9e8e1" stroke="#aab6bf" stroke-width=".5"/>')
    for row in geo.itertuples():
        record = by_id.get(row.MUNID)
        if record is None:
            record = {"MUNID": row.MUNID, "municipality": row.MUNICIPAL_NAME_SHORTFORM.title(), "has_target": False,
                      "target": None, "official_progress": None, "official_progress_pct": None,
                      "category": "unassigned", "label": LABELS["unassigned"]}
            by_id[row.MUNID] = record
        tooltip = record["municipality"] + (f" | Target: {record['target']} | Official housing progress: {record['official_progress']} | {record['official_progress_pct']:.2f}%" if record["has_target"] else " | No assigned target")
        paths.append(f'<path data-munid="{row.MUNID}" d="{path_data(row.geometry.simplify(150, preserve_topology=True), xmin, ymax, scale)}" fill="{COLORS[row.category]}" fill-rule="evenodd" class="municipality" tabindex="0"><title>{html.escape(tooltip)}</title></path>')
    template = (ROOT / "src/templates/bff_map.html").read_text(encoding="utf-8")
    # Reuse the actual HAF stylesheet rather than maintaining a second visual theme.
    shared_css = re.search(r"<style>(.*?)</style>", (ROOT / "src/templates/haf_map.html").read_text(encoding="utf-8"), re.S)[1]
    payload = {"rows": by_id, "counts": summary, "colors": COLORS,
               "provinceView": " ".join(map(str, view)), "southView": " ".join(map(str, south_view))}
    replacements = {"__SHARED_CSS__": shared_css, "__MAP_PATHS__": "\n".join(paths),
                    "__FULL_VIEW__": payload["provinceView"], "__SOUTH_VIEW__": payload["southView"],
                    "__MAP_DATA__": json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"), "__YEAR__": str(summary["year"])}
    for token, value in replacements.items():
        template = template.replace(token, value)
    (REPORTS / "bff_ontario_map.html").write_text(template, encoding="utf-8")


def write_report(mapped, summary):
    with (BFF_DATA / "municipal_progress.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(mapped[0]));writer.writeheader();writer.writerows(mapped)
    write_json(BFF_DATA/"summary.json",summary)
    lines=[f"# Building Faster Fund — {summary['year']}","",
        f"**{summary['met_80pct']} of {summary['with_targets']} municipalities reached the 80% threshold; {summary['met_100pct']} reached 100%.**","",
        "The BFF's numeric performance threshold was 80% of the annual target. Green reaches that threshold; red is below it; grey has no individual target in this dataset. These colours do not verify allocations or cash payments.","",
        "## Large municipalities below the threshold","",
        f"Reproducible definition: the {summary['large_city_count']} largest annual targets, not a population ranking. Configurable with --large-city-count.",""]
    lines += [f"- {r['municipality']}: {r['official_progress']:,} / {r['target']:,} ({r['pct']:.2f}%)." for r in summary["large_cities_red"]]
    lines += ["","## Municipal results","","| Municipality | MUNID | Annual target | Official progress | % of target | Classification |","|---|---|---:|---:|---:|---|"]
    lines += [f"| {r['municipality']} | {r['MUNID']} | {r['target']} | {r['official_progress']} | {r['official_progress_pct']:.2f}% | {LABELS[r['category']]} |" for r in sorted(mapped,key=lambda r:r["official_progress_pct"])]
    lines += ["","## Sources and methods","",
        "- [Ontario Data Catalogue](https://data.ontario.ca/dataset/ontario-s-housing-supply-progress): annual official progress, including categories beyond conventional CMHC housing starts.",
        "- [Official tracker and BFF threshold](https://www.ontario.ca/page/tracking-housing-supply-progress): 80% for the numeric funding threshold; 100% for the full target.",
        "- [Ontario GeoHub](https://geohub.lio.gov.on.ca/datasets/municipal-boundary-lower-and-single-tier): same current municipal/province snapshots as the HAF maps, EPSG:3347.",
        "- Normalized names identify candidates; MUNID provides the final join. Hamilton and Peterborough City have reviewed identifiers. The aggregate Municipalities without targets row is excluded from the municipal denominator.",
        "- Source provenance and join audit: data/processed/bff/source.json, join_audit.json and data/raw/manifest.json. Ambiguous, missing or duplicate joins fail the pipeline.",
        "- Classification uses exact annual counts before rounding. Geometry repair/simplification is for display; no area measurements are calculated. Current boundaries are not reconstructed historical boundaries.",
        "- This source does not provide a municipal component breakdown. No bed-dependent eligibility is inferred. Separate residential and funding-comparison pipelines document their own coverage.",
        "", "[PNG map](bff_ontario_map.png) · [Interactive offline map](bff_ontario_map.html)"]
    (REPORTS/"bff_findings.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int)
    parser.add_argument("--sources", type=Path, help="Multi-source evidence registry (HTML/PDF/reviewed records)")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--large-city-count", type=int, default=10)
    args = parser.parse_args()
    if args.large_city_count < 1:
        parser.error("--large-city-count must be positive")
    registry = args.sources or (ROOT / f"data/reference/bff_{args.year}_sources.json" if args.year else None)
    if args.sources or (registry and registry.exists()):
        from src.bff_evidence import run
        if args.year and read_json(registry)["year"] != args.year:
            parser.error("--year conflicts with the year in --sources")
        run(registry, args.refresh)
        return
    year, source, provenance = ingest(args.year, args.refresh)
    geo, province, mapped, audit = join_municipalities(source, provenance)
    summary = summarize(mapped, geo, year, args.large_city_count)
    REPORTS.mkdir(parents=True, exist_ok=True)
    plot_static(geo, province, mapped, summary)
    interactive(geo, province, mapped, summary)
    write_report(mapped, summary)
    print(f"Ontario Building Faster Fund | {year}")
    print(f"Municipalities with an annual target: {summary['with_targets']}")
    print(f"Reached >= 80% (green): {summary['met_80pct']}")
    print(f"Reached >= 100%: {summary['met_100pct']}")
    print(f"Below 80% (red): {summary['below_80pct']}")
    print(f"Without individual targets (grey): {summary['without_targets']}")
    print(f"Large cities in red (top {args.large_city_count} annual targets; not a population ranking):")
    for row in summary["large_cities_red"]:
        print(f"  {row['municipality']}: {row['official_progress']:,} / {row['target']:,} = {row['pct']:.2f}%")
    print(f"JOIN: {audit['municipalities_matched']}/{audit['municipalities_with_targets']} matched; unmatched=0; duplicates=0; EPSG:3347")
    print("Audit: data/processed/bff/join_audit.json")
    print("Outputs: reports/bff_ontario_map.png | reports/bff_ontario_map.html")
    print("Measure: official housing progress, including additional categories; no compatible municipal CMHC breakdown ingested.")


if __name__ == "__main__":
    main()
