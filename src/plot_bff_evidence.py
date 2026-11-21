"""Map officially confirmed BFF allocations using the existing GeoHub/HAF design."""
import html
import json
import re
from typing import Any

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from shapely.geometry import box

from src.bff import SOUTH_BOUNDS
from src.common import REPORTS, ROOT
from src.plot_haf import path_data

COLORS = {"award_confirmed": "#3477a5", "context": "#d8dde2"}
LABELS = {"award_confirmed": "Funding confirmed in the October 5 update",
          "context": "Other municipalities"}


def render(geo, province, mapped, summary, provenance):
    year = summary["year"]
    confirmed = {row["MUNID"]: row for row in mapped if row["award_confirmed"]}
    display_colors = geo["MUNID"].map(lambda mid: COLORS["award_confirmed" if mid in confirmed else "context"])
    base = REPORTS / f"bff_{year}_ontario_map"
    bg, ink, muted = "#f4f2ed", "#172e3c", "#596574"
    fig = plt.figure(figsize=(12, 13), facecolor=bg)
    fig.text(.055, .958, f"ONTARIO  /  BUILDING FASTER FUND  /  {year}", fontsize=11, weight="bold", color=muted)
    fig.text(.055, .915, f"{summary['award_confirmed']} of {summary['with_targets']} targeted municipalities\nhad funding confirmed.", fontsize=29, weight="bold", color=ink, va="top", linespacing=1.18)
    fig.text(.055, .806, f"BFF: up to C$1.2 billion for infrastructure; funding threshold: 80% of the annual target.\n{year} performance; confirmations as of October 5, 2026; further reviews were pending.", fontsize=11, color=muted, va="top", linespacing=1.5)
    full = fig.add_axes((.04, .36, .32, .39))
    south = fig.add_axes((.365, .31, .60, .43))
    for ax in (full, south):
        ax.set_facecolor(bg)
        province.plot(ax=ax, color="#e9e8e1", edgecolor="#bcc4c8", linewidth=.6)
        geo.plot(ax=ax, color=display_colors, edgecolor=bg, linewidth=.22)
        ax.set_axis_off()
    bounds = gpd.GeoSeries([box(*SOUTH_BOUNDS)], crs=4326).to_crs(3347).total_bounds
    south.set_xlim(bounds[0], bounds[2])
    south.set_ylim(bounds[1], bounds[3])
    full.set_title("Entire province", fontsize=10, color=muted)
    south.set_title("Southern and eastern Ontario", fontsize=10, color=muted)
    offsets = {"kitchener": (-170_000, 100_000), "welland": (90_000, -90_000),
               "london": (-90_000, -100_000)}
    for row in mapped:
        if not row["award_confirmed"] or row["municipality_key"] not in offsets:
            continue
        point = geo.loc[geo["MUNID"] == row["MUNID"]].geometry.iloc[0].representative_point()
        dx, dy = offsets[row["municipality_key"]]
        south.annotate(row["municipality"], (point.x, point.y), (point.x+dx, point.y+dy), fontsize=9, color=ink,
                       bbox={"facecolor": bg, "alpha": .9, "edgecolor": "none", "pad": 2},
                       arrowprops={"arrowstyle": "-", "color": muted, "lw": .6})
    fig.legend(handles=[Patch(facecolor=COLORS[c], label=LABELS[c]) for c in COLORS], loc="lower left",
               bbox_to_anchor=(.05, .173), frameon=False, fontsize=10, ncol=2, columnspacing=2, labelspacing=1.1)
    fig.text(.055, .153, "Highlighted: the 18 municipalities named in the official funding update.\nThe 50-municipality figure refers to the program's individual housing-target cohort.", fontsize=10, color=ink, va="top", linespacing=1.5)
    fig.text(.055, .096, "2025 performance; allocations confirmed as of October 5, 2026.\nFurther reviews were pending. Confirmed allocations are distinct from cash received.", fontsize=10, color=muted, va="top", linespacing=1.5)
    fig.text(.055, .039, "Sources: Ontario Legislature, October 5, 2026; Ontario GeoHub municipal boundaries.\nProvince-wide view and southern/eastern detail. EPSG:3347. Audited by MUNID.", fontsize=9, color=muted, va="top", linespacing=1.5)
    fig.savefig(base.with_suffix(".png"), dpi=170, facecolor=bg)
    plt.close(fig)

    from src.plot_bff_linkedin import render as render_linkedin
    render_linkedin(geo, province, mapped, summary)

    xmin, ymin, xmax, ymax = province.total_bounds
    scale = 1000 / (xmax-xmin)
    view = [-10, -10, 1020, (ymax-ymin)*scale+20]
    south_view = [(bounds[0]-xmin)*scale, (ymax-bounds[3])*scale, (bounds[2]-bounds[0])*scale, (bounds[3]-bounds[1])*scale]
    by_id: dict[str, dict[str, Any]] = {mid: {
        "MUNID": mid, "municipality": r["municipality"], "award_cad": r["award_cad"],
        "category": "award_confirmed", "label": LABELS["award_confirmed"], "evidence": r["evidence"],
    } for mid, r in confirmed.items()}
    paths = [f'<path d="{path_data(g, xmin, ymax, scale)}" fill="#e9e8e1" stroke="#aab6bf" stroke-width=".5"/>' for g in province.geometry]
    for row in geo.itertuples():
        record = by_id.get(row.MUNID)
        attributes = f'data-munid="{row.MUNID}" tabindex="0"' if record else 'aria-hidden="true"'
        tooltip = '<title>' + html.escape(record["municipality"] + " | " + record["label"]) + '</title>' if record else ''
        color = COLORS["award_confirmed" if record else "context"]
        paths.append(f'<path {attributes} d="{path_data(row.geometry.simplify(150, preserve_topology=True), xmin, ymax, scale)}" fill="{color}" fill-rule="evenodd" class="municipality">{tooltip}</path>')
    style_match = re.search(r"<style>(.*?)</style>", (ROOT / "src/templates/haf_map.html").read_text(encoding="utf-8"), re.S)
    if style_match is None:
        raise ValueError("Shared HAF stylesheet is missing")
    shared_css = style_match[1]
    payload = {"rows": by_id, "counts": {key: summary[key] for key in ("year", "award_confirmed", "with_targets")}, "colors": COLORS, "labels": LABELS,
        "provinceView": " ".join(map(str, view)), "southView": " ".join(map(str, south_view))}
    template = (ROOT / "src/templates/bff_evidence_map.html").read_text(encoding="utf-8")
    for token, value in {"__SHARED_CSS__": shared_css, "__YEAR__": str(year),
        "__MAP_DATA__": json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"),
        "__MAP_PATHS__": "\n".join(paths), "__FULL_VIEW__": payload["provinceView"], "__SOUTH_VIEW__": payload["southView"]}.items():
        template = template.replace(token, value)
    base.with_suffix(".html").write_text(template, encoding="utf-8")
    write_findings(mapped, summary, provenance)


def write_findings(mapped, summary, provenance):
    year = summary["year"]
    lines = [f"# Building Faster Fund — {year}: official evidence register", "",
        "The Building Faster Fund (BFF) was Ontario's three-year program of up to C$1.2 billion for housing-enabling infrastructure. Its numeric performance threshold was at least 80% of the annual municipal housing target; 100% represents the full target.", "",
        f"**{summary['award_confirmed']} of {summary['with_targets']} targeted municipalities had funding confirmed in the October 5, 2026 statement.** Further reviews were pending. This does not establish that the other municipalities failed the threshold.", "",
        f"Numeric coverage: {summary['numeric_coverage']}/{summary['with_targets']}; {summary['met_80pct_calculated']} ≥80%, {summary['below_80pct_calculated']} <80%, {summary['met_100pct_calculated']} ≥100%. These are results for the documented numeric sample, not program-wide performance totals.", "",
        "HTML, PDF and reviewed factual extracts feed one municipal evidence model. The 2024 cohort supplies municipality names only; targets and results are not carried forward into 2025.", "",
        "The publication map highlights only the 18 confirmed allocations in blue. All other municipalities provide neutral geographic context. Numeric performance remains in the research tables and is not mixed into the funding map.", "",
        "Toronto's dashboard was updated in February 2026 and may precede final provincial reconciliation. Confirmed allocations have not been reconciled to actual cash receipts.", "",
        "## Sources", ""]
    for s in provenance["sources"]:
        lines.append(f"- [{s['id']}]({s['url']}): {s['locator']}. Capture: {s['snapshot_kind']}. {s.get('note', '')}")
    lines += ["", "The Hansard transcript was reviewed through web research; direct downloads returned HTTP 403. Its local file is explicitly a reviewed factual extract, not the full original document. Other sources are original downloads. URLs, hashes and locators are in source.json; the download manifest records retrieval times.", "",
        "## Municipal evidence", "", "| Municipality | Annual target | Official progress | % | Funding confirmed | Sources |", "|---|---:|---:|---:|---|---|"]
    for r in sorted(mapped,key=lambda x:x["municipality"]):
        values=[r["municipality"],str(r["target"]) if r["target"] is not None else "—",
            str(r["official_progress"]) if r["official_progress"] is not None else "—",
            f"{r['official_progress_pct']:.2f}" if r["official_progress_pct"] is not None else "—",
            "Yes" if r["award_confirmed"] else "Not confirmed","; ".join(r["source_ids"]) or "Pending verification"]
        lines.append("| "+" | ".join(values)+" |")
    lines += ["", f"[PNG map](bff_{year}_ontario_map.png) · [Interactive map](bff_{year}_ontario_map.html)"]
    (REPORTS/f"bff_{year}_findings.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
