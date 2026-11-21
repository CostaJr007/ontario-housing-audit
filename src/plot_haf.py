"""Create a verified HAF choropleth, offline interactive map and coverage report."""
import csv
import html
import json
from collections import Counter

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from shapely.geometry import box

from src.common import PROCESSED, RAW, REPORTS, ROOT, normalize_name, write_json

COLORS = {"at_or_above_forecast": "#18856c", "below_forecast": "#d6545b", "terminated": "#73529b", "no_value": "#d49a32", "outside": "#d8dde2"}
LABELS = {"at_or_above_forecast": "At least 100% of forecast", "below_forecast": "Below 100% of forecast", "terminated": "Agreement terminated", "no_value": "No published percentage", "outside": "No municipal record in this dashboard"}


def load_mapped():
    geo = gpd.read_file(RAW / "geohub/municipalities.geojson")
    geo["geometry"] = geo.geometry.make_valid(method="structure", keep_collapsed=False)
    geo = geo[~geo.geometry.is_empty].copy()
    geo["municipality_key"] = geo["MUNICIPAL_NAME_SHORTFORM"].map(normalize_name)
    geo = geo.dissolve(by="MUNID", as_index=False)
    with (PROCESSED / "haf_ontario_progress.csv").open(encoding="utf-8", newline="") as stream:
        communities = list(csv.DictReader(stream))
    mapped, excluded, unresolved = [], [], []
    for row in communities:
        # Indigenous governments are retained in the data, with an explicit separate scope.
        if "first nation" in row["community"].lower() or "indian band" in row["community"].lower():
            excluded.append(row["community"])
            continue
        candidates = geo[geo["municipality_key"] == row["community_key"]]
        if row["community_key"] == "hamilton":
            candidates = candidates[candidates["MUNID"] == "25005"]
        if len(candidates) != 1:
            unresolved.append({"community": row["community"], "candidate_count": len(candidates)})
            continue
        mapped.append({**row, "MUNID": candidates.iloc[0]["MUNID"],
                       "boundary_name": candidates.iloc[0]["MUNICIPAL_NAME"]})
    audit = {"source_communities": len(communities), "municipalities_mapped": len(mapped),
             "indigenous_governments_outside_municipal_layer": excluded, "unresolved": unresolved,
             "review_cutoff": "2026-03", "classification_basis": "CMHC published rounded percent of period forecast; not action-plan rating"}
    write_json(PROCESSED / "haf_join_audit.json", audit)
    if unresolved:
        raise ValueError(f"Resolve HAF boundaries before drawing: {unresolved}")
    if len({r["MUNID"] for r in mapped}) != len(mapped):
        raise ValueError("Multiple HAF records point to the same municipality")
    by_id = {r["MUNID"]: r for r in mapped}
    geo["category"] = geo["MUNID"].map(lambda key: by_id[key]["category"] if key in by_id else "outside")
    geo = geo.to_crs(3347)
    province = gpd.read_file(RAW / "geohub/province.geojson").to_crs(3347)
    province["geometry"] = province.geometry.make_valid(method="structure", keep_collapsed=False)
    counts = Counter(r["category"] for r in mapped)
    summary = {**audit, "counts": dict(counts),
               "municipalities_with_numeric_forecast_comparison": counts["below_forecast"] + counts["at_or_above_forecast"],
               "below_forecast": counts["below_forecast"], "at_or_above_forecast": counts["at_or_above_forecast"],
               "period_description": "HAF1 second annual reviews and HAF2 first annual reviews, up to March 2026; not January-September 2026",
               "not_a_contract_compliance_determination": True}
    write_json(PROCESSED / "haf_map_summary.json", summary)
    with (PROCESSED / "haf_municipal_mapped.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(mapped[0]))
        writer.writeheader()
        writer.writerows(mapped)
    return geo, province, mapped, summary


def plot_static(geo, province, mapped, summary):
    bg, ink, muted = "#f4f2ed", "#172e3c", "#596574"
    fig = plt.figure(figsize=(12, 13), facecolor=bg)
    fig.text(.055, .958, "ONTARIO  /  HOUSING ACCELERATOR FUND", fontsize=11, weight="bold", color=muted)
    fig.text(.055, .915, f"{summary['below_forecast']} of {summary['municipalities_with_numeric_forecast_comparison']} municipalities\nbelow their permit forecast.", fontsize=29, weight="bold", color=ink, va="top", linespacing=1.18)
    fig.text(.055, .806, "CMHC annual reviews up to March 2026.\nPermitted housing units / the forecast for each agreement's reporting period.", fontsize=12, color=muted, va="top", linespacing=1.5)
    full = fig.add_axes((.04, .36, .32, .39))
    south = fig.add_axes((.365, .31, .60, .43))
    for ax in (full, south):
        ax.set_facecolor(bg)
        province.plot(ax=ax, color="#e9e8e1", edgecolor="#bcc4c8", linewidth=.6)
        geo.plot(ax=ax, color=geo["category"].map(COLORS), edgecolor=bg, linewidth=.22)
        ax.set_axis_off()
    bounds = gpd.GeoSeries([box(-83.7, 41.5, -74.1, 46.8)], crs=4326).to_crs(3347).total_bounds
    south.set_xlim(bounds[0], bounds[2])
    south.set_ylim(bounds[1], bounds[3])
    full.set_title("Entire province", fontsize=10, color=muted)
    south.set_title("Southern and eastern Ontario", fontsize=10, color=muted)
    # Selected labels offer orientation; the HTML map exposes every municipality.
    offsets = {"toronto": (90_000, -10_000), "mississauga": (-150_000, -45_000), "ottawa": (-90_000, 90_000),
               "london": (-40_000, -100_000), "kitchener": (-170_000, 110_000)}
    for row in mapped:
        if row["community_key"] not in offsets:
            continue
        point = geo.loc[geo["MUNID"] == row["MUNID"]].geometry.iloc[0].representative_point()
        dx, dy = offsets[row["community_key"]]
        value = row["permitted_units_pct_of_period_forecast"]
        south.annotate(f"{row['community'].rstrip('*')} · {float(value):g}%", (point.x, point.y),
                       (point.x + dx, point.y + dy), fontsize=9, color=ink,
                       bbox={"facecolor": bg, "alpha": .9, "edgecolor": "none", "pad": 2},
                       arrowprops={"arrowstyle": "-", "color": muted, "lw": .6})
    categories = ["below_forecast", "at_or_above_forecast", "terminated", "outside"]
    fig.legend(handles=[Patch(facecolor=COLORS[c], label=LABELS[c]) for c in categories],
               loc="lower left", bbox_to_anchor=(.05, .19), frameon=False, fontsize=11, ncol=2, columnspacing=2, labelspacing=1.1)
    fig.text(.055, .167, f"{summary['municipalities_mapped']} municipalities: {summary['municipalities_with_numeric_forecast_comparison']} with a percentage and {summary['counts'].get('terminated',0)} terminated agreements.\n{len(summary['indigenous_governments_outside_municipal_layer'])} Indigenous governments are retained in the data, outside this municipal layer.", color=muted, fontsize=10, linespacing=1.5, va="top")
    fig.text(.055, .102, "Being below forecast does not establish a breach of the funding agreement.\nColours represent permit performance; action-plan assessments are a separate indicator.", color=ink, fontsize=10, linespacing=1.5, va="top")
    fig.text(.055, .039, "Sources: CMHC HAF Regional Progress Report (August 2026); current Ontario GeoHub boundaries.\nPublished rounded percentages; retrieved November 20, 2026. EPSG:3347.", color=muted, fontsize=9, linespacing=1.5, va="top")
    fig.savefig(REPORTS / "haf_ontario_map.png", dpi=170, facecolor=bg)
    plt.close(fig)


def path_data(geometry, xmin, ymax, scale):
    paths = []
    polygons = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
    for polygon in polygons:
        if polygon.geom_type != "Polygon":
            continue
        for ring in [polygon.exterior, *polygon.interiors]:
            coords = [(round((x-xmin)*scale, 2), round((ymax-y)*scale, 2)) for x, y in ring.coords]
            paths.append("M" + "L".join(f"{x},{y}" for x, y in coords) + "Z")
    return "".join(paths)


def interactive(geo, province, mapped, summary):
    # A self-contained SVG map avoids external CDNs, tiles, servers and network calls.
    xmin, ymin, xmax, ymax = province.total_bounds
    scale = 1000 / (xmax-xmin)
    height = (ymax-ymin)*scale
    shapes = []
    for geometry in province.geometry:
        shapes.append(f'<path d="{path_data(geometry, xmin, ymax, scale)}" fill="#e9e8e1" stroke="#aab6bf" stroke-width=".5"/>')
    for row in geo.itertuples():
        geometry = row.geometry.simplify(150, preserve_topology=True)
        shapes.append(f'<path id="mun-{row.MUNID}" data-munid="{row.MUNID}" d="{path_data(geometry, xmin, ymax, scale)}" fill="{COLORS[row.category]}" fill-rule="evenodd" class="municipality" tabindex="0"><title>{html.escape(row.MUNICIPAL_NAME_SHORTFORM)}</title></path>')
    by_id = {r["MUNID"]: {**r, "label": LABELS[r["category"]]} for r in mapped}
    data = json.dumps({"rows": by_id, "counts": summary, "colors": COLORS}, ensure_ascii=False).replace("</", "<\\/")
    template = (ROOT / "src/templates/haf_map.html").read_text(encoding="utf-8")
    result = template.replace("__SVG_HEIGHT__", str(round(height + 20, 2))).replace("__SVG_PATHS__", "\n".join(shapes)).replace("__MAP_DATA__", data)
    (REPORTS / "haf_ontario_map.html").write_text(result, encoding="utf-8")


def report(mapped,summary):
    lines=["# HAF: permitted units versus period forecast","",
        f"**{summary['below_forecast']} of {summary['municipalities_with_numeric_forecast_comparison']} municipalities with a published percentage were below 100% of forecast.**","",
        "Reference: CMHC annual reviews up to March 2026, covering the second review of 2023-intake agreements and first review of 2024-intake agreements. These are not January–September 2026 totals.","",
        f"Coverage: {summary['source_communities']} communities; {summary['municipalities_mapped']} municipalities joined; {len(summary['indigenous_governments_outside_municipal_layer'])} Indigenous governments retained outside the municipal layer. Terminated agreements and missing percentages are excluded from the numeric denominator.","",
        "CMHC reports permitted units as a percentage of the period/YTD forecast. Classification uses published rounded percentages. It does not replace the agreement or action-plan assessment.","",
        "| Municipality | Intake | % of forecast | Published action-plan progress | Map classification |","|---|---:|---:|---|---|"]
    for row in sorted(mapped,key=lambda r:(r["permitted_units_pct_of_period_forecast"]=="",float(r["permitted_units_pct_of_period_forecast"] or 0))):
        pct=f"{float(row['permitted_units_pct_of_period_forecast']):g}%" if row["permitted_units_pct_of_period_forecast"] else "Not published"
        lines.append(f"| {row['community']} | {row['intake_year']} | {pct} | {row['action_plan_progress']} | {LABELS[row['category']]} |")
    lines += ["","## Sources and limitations","",
        "- [CMHC dashboard](https://www.cmhc-schl.gc.ca/professionals/project-funding-and-mortgage-financing/funding-programs/all-funding-programs/housing-accelerator-fund/housing-accelerator-fund-rounds-data), both Ontario intake tables, loaded through the public HAFReportFilter endpoint.",
        "- [Ontario GeoHub municipal boundaries](https://geohub.lio.gov.on.ca/datasets/municipal-boundary-lower-and-single-tier) and provincial outline: current snapshots simplified for display.",
        "- Asterisks in community names are preserved: the dashboard identifies funding reductions for unmet commitments. This does not determine the permit-performance colour.",
        "- Different intakes cover different annual reporting cycles. The map compares CMHC's normalized indicator, not counts for a common calendar year.",
        "- Approved funding is not a disbursement. Small CAD differences between summed rows and published headers remain recorded in haf_source_totals.json; amounts do not determine map classification.",
        "- Sources, hashes and crosswalk: data/raw/manifest.json, haf_ontario_progress.csv, haf_municipal_mapped.csv and haf_join_audit.json.",
        "","[PNG map](haf_ontario_map.png) · [Interactive offline map](haf_ontario_map.html)"]
    (REPORTS/"haf_map_findings.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    geo, province, mapped, summary = load_mapped()
    plot_static(geo, province, mapped, summary)
    interactive(geo, province, mapped, summary)
    report(mapped, summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
