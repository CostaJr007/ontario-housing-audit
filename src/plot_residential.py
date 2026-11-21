"""Map absolute counts of residential units using the established HAF layout."""
import html
import json
import re

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from shapely.geometry import box

from src.bff import SOUTH_BOUNDS
from src.common import REPORTS, ROOT
from src.plot_haf import path_data
from src.residential import TYPES

PALETTE = ["#d6e9df", "#9bceba", "#56ac90", "#218569", "#07553f"]
BREAKS = [100, 500, 2000, 10000]
BIN_LABELS = ["0–99", "100–499", "500–1,999", "2,000–9,999", "10,000 or more"]
MISSING, OUTSIDE = "#d6b76c", "#d8dde2"


def count_color(value):
    if value is None:
        return MISSING
    return PALETTE[sum(value >= limit for limit in BREAKS)]


def render(geo, province, mapped, summary, source):
    year = summary["year"]
    base = REPORTS / f"residential_{year}_ontario_map"
    by_id = {r["MUNID"]: {**r, "in_cohort": True} for r in mapped}
    bg, ink, muted = "#f4f2ed", "#172e3c", "#596574"
    geo = geo.copy()
    geo["fill"] = geo["MUNID"].map(lambda k: count_color(by_id[k]["starts_total"]) if k in by_id else OUTSIDE)
    fig = plt.figure(figsize=(12, 13), facecolor=bg)
    fig.text(.055, .958, f"ONTARIO  /  SELF-CONTAINED HOMES  /  {year}", fontsize=11, weight="bold", color=muted)
    total = f"{summary['starts_total']:,}"
    houses = f"{summary['starts_houses']:,}"
    apt = f"{summary['starts_apartment_other']:,}"
    fig.text(.055, .915, f"{total} self-contained homes\nstarted construction.", fontsize=29, weight="bold", color=ink, va="top", linespacing=1.18)
    fig.text(.055, .806, f"{houses} detached, semi-detached and row units · {apt} apartments and other.\nFull-year counts for {summary['starts_coverage']} of {summary['program_cohort']} BFF municipalities.", fontsize=12, color=muted, va="top", linespacing=1.5)
    full = fig.add_axes((.04, .36, .32, .39))
    south = fig.add_axes((.365, .31, .60, .43))
    for ax in (full, south):
        ax.set_facecolor(bg)
        province.plot(ax=ax, color="#e9e8e1", edgecolor="#bcc4c8", linewidth=.6)
        geo.plot(ax=ax, color=geo["fill"], edgecolor=bg, linewidth=.22)
        ax.set_axis_off()
    bounds = gpd.GeoSeries([box(*SOUTH_BOUNDS)], crs=4326).to_crs(3347).total_bounds
    south.set_xlim(bounds[0], bounds[2])
    south.set_ylim(bounds[1], bounds[3])
    full.set_title("Entire province", fontsize=10, color=muted)
    south.set_title("Southern and eastern Ontario", fontsize=10, color=muted)
    offsets = {"toronto": (90_000, -10_000), "ottawa": (-90_000, 90_000), "london": (-60_000, -90_000), "kitchener": (-160_000, 100_000)}
    for row in mapped:
        if row["municipality_key"] not in offsets:
            continue
        point = geo.loc[geo["MUNID"] == row["MUNID"]].geometry.iloc[0].representative_point()
        dx,dy = offsets[row["municipality_key"]]
        label = f"{row['starts_total']:,}" if row["starts_total"] is not None else "not available"
        south.annotate(f"{row['municipality']} · {label}", (point.x, point.y), (point.x+dx, point.y+dy), fontsize=9, color=ink,
            bbox={"facecolor": bg, "alpha": .9, "edgecolor": "none", "pad": 2}, arrowprops={"arrowstyle": "-", "color": muted, "lw": .6})
    handles = [Patch(facecolor=c,label=l) for c,l in zip(PALETTE,BIN_LABELS)]
    handles += [Patch(facecolor=MISSING,label="No verified municipal data"), Patch(facecolor=OUTSIDE,label="Outside the 50-municipality scope")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(.05,.18), frameon=False, fontsize=10, ncol=3, labelspacing=1.1)
    fig.text(.055,.163,"Colours show absolute dwelling-unit counts, without adding institutional beds.\nHouses: detached + semi-detached + row. Apartments and other includes duplexes.", fontsize=10,color=ink,va="top",linespacing=1.5)
    fig.text(.055,.104,"Housing starts do not measure completed homes or households actually housed.\nBedrooms, occupancy and prices are unavailable. Existing-building conversions are a separate series.",fontsize=10,color=muted,va="top",linespacing=1.5)
    fig.text(.055,.039,f"Source: CMHC, December {year} edition, municipal tables; boundaries: Ontario GeoHub.\nSame HAF layout and layer, EPSG:3347. Total covers the available sample, not all Ontario.",fontsize=9,color=muted,va="top",linespacing=1.5)
    fig.savefig(base.with_suffix(".png"),dpi=170,facecolor=bg)
    plt.close(fig)

    xmin,ymin,xmax,ymax = province.total_bounds
    scale = 1000/(xmax-xmin)
    view = [-10,-10,1020,(ymax-ymin)*scale+20]
    south_view = [(bounds[0]-xmin)*scale,(ymax-bounds[3])*scale,(bounds[2]-bounds[0])*scale,(bounds[3]-bounds[1])*scale]
    paths = [f'<path d="{path_data(g,xmin,ymax,scale)}" fill="#e9e8e1" stroke="#aab6bf" stroke-width=".5"/>' for g in province.geometry]
    for row in geo.itertuples():
        if row.MUNID not in by_id:
            by_id[row.MUNID] = {"MUNID": row.MUNID,"municipality": row.MUNICIPAL_NAME_SHORTFORM.title(),"in_cohort":False}
        record = by_id[row.MUNID]
        paths.append(f'<path data-munid="{row.MUNID}" d="{path_data(row.geometry.simplify(150,preserve_topology=True),xmin,ymax,scale)}" fill="{row.fill}" fill-rule="evenodd" class="municipality" tabindex="0"><title>{html.escape(record["municipality"])}</title></path>')
    css_match = re.search(r"<style>(.*?)</style>",(ROOT/"src/templates/haf_map.html").read_text(encoding="utf-8"),re.S)
    if css_match is None:
        raise ValueError("Shared HAF stylesheet missing")
    data = {"rows":by_id,"counts":summary,"source":source,"palette":PALETTE,"breaks":BREAKS,"binLabels":BIN_LABELS,
        "missingColor":MISSING,"outsideColor":OUTSIDE,"provinceView":" ".join(map(str,view)),"southView":" ".join(map(str,south_view))}
    template = (ROOT/"src/templates/residential_map.html").read_text(encoding="utf-8")
    for token,value in {"__SHARED_CSS__":css_match[1],"__YEAR__":str(year),"__MAP_PATHS__":"\n".join(paths),
        "__FULL_VIEW__":data["provinceView"],"__SOUTH_VIEW__":data["southView"],"__MAP_DATA__":json.dumps(data,ensure_ascii=False).replace("</","<\\/")}.items():
        template=template.replace(token,value)
    base.with_suffix(".html").write_text(template,encoding="utf-8")
    findings(mapped,summary,source)


def findings(mapped,summary,source):
    year=summary["year"]
    lines=[f"# Self-contained residential units — {year}","",
        "This analysis counts self-contained dwellings for permanent occupancy by dwelling type. It does not count families housed or measure bedroom suitability, affordability or actual occupancy.","",
        f"Housing starts: **{summary['starts_total']:,} units across {summary['starts_coverage']}/50 municipalities**: {summary['starts_houses']:,} detached, semi-detached and row units, plus {summary['starts_apartment_other']:,} apartments and other.","",
        f"Completions: **{summary['completions_total']:,} units across {summary['completions_coverage']}/50 municipalities**. Coverage differs; do not divide these totals to calculate a completion rate. Homes completed in a year may have started in previous years.","",
        "No BFF institutional-bed additions are included. CMHC excludes collective accommodation from this survey. A self-contained home occupied by a student or senior remains a residential dwelling; this workbook does not identify its occupants.","",
        "Additional units and conversions in existing buildings may be legitimate homes for families. They belong to a separate series and are not added to this new-construction measure. Apartments and other includes duplexes and stacked townhouses; it is not a pure-apartment classification.","",
        "## Sources and controls","",f"- [Original CMHC workbook]({source['source_url']}), December {year} edition, January–December totals. No claim is made that this historical edition is the latest revision.",
        f"- [CMHC methodology]({source['methodology']}). Starts and completions remain separate.",
        "- Explicit municipal CSD rows only; CMA/CA aggregates never substitute for municipalities. The 2024 BFF roster supplies names only, without carrying forward targets or progress.",
        "- Tables H6 and H11-3: validated annual columns, four-type reconciliation and symbols. '-' means zero; N/A remains unavailable.",
        "- Same GeoHub municipal layer, HAF layout and EPSG:3347. Reviewed MUNID crosswalk; the workbook does not provide CSD codes.",
        f"- Missing municipal starts: {', '.join(summary['starts_missing']) or 'none'}.",
        f"- Missing municipal completions: {', '.join(summary['completions_missing']) or 'none'}.","",
        "## Municipal units","","| Municipality | Detached starts | Semi-detached | Row | Apartments and other | Total starts | Total completions |","|---|---:|---:|---:|---:|---:|---:|"]
    for row in sorted(mapped,key=lambda r:r["municipality"]):
        values=[row["municipality"]]+[str(row[k]) if row[k] is not None else "—" for k in [*(f"starts_{t}" for t in TYPES),"completions_total"]]
        lines.append("| "+" | ".join(values)+" |")
    lines += ["",f"[PNG map](residential_{year}_ontario_map.png) · [Interactive map](residential_{year}_ontario_map.html)"]
    (REPORTS/f"residential_{year}_findings.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
