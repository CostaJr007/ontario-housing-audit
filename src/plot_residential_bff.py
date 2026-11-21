"""Map the documented BFF/residential comparison, preserving its coverage limits."""
import html
import json
import re

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from shapely.geometry import box

from src.bff import SOUTH_BOUNDS, join_municipalities
from src.common import PROCESSED, REPORTS, ROOT, read_json, write_json
from src.plot_haf import path_data

COLORS = {"above": "#18856c", "below": "#d6545b", "unknown": "#d6b76c", "outside": "#d8dde2"}
BLUE = "#3477a5"


def scenario(row, mode="new"):
    if not row.get("in_cohort", True):
        return {"category": "outside", "pct": None, "minimum": False}
    if row.get("target") is None:
        return {"category": "unknown", "pct": None, "minimum": False}
    if mode == "official":
        pct = row.get("official_pct")
        passes = row.get("official_met_80pct")
    elif mode == "new":
        pct = row.get("new_starts_pct")
        passes = row.get("new_starts_met_80pct")
    elif mode == "independent":
        pct = row.get("independent_including_arus_pct")
        passes = row.get("independent_including_arus_met_80pct")
        if pct is None:
            # More independent units could improve an incomplete count. A lower
            # bound can prove a pass but cannot establish a failure.
            if row.get("new_starts_met_80pct") is True:
                return {"category": "above", "pct": row["new_starts_pct"], "minimum": True}
            return {"category": "unknown", "pct": None, "minimum": False}
    else:
        raise ValueError(f"Unknown scenario: {mode}")
    return {"category": "unknown" if passes is None else "above" if passes else "below", "pct": pct, "minimum": False}


def prepare(rows, summary):
    year = summary["year"]
    folder = PROCESSED / f"residential_bff_{year}"
    units = read_json(PROCESSED / f"residential_{year}/municipal_units.json")
    awards = {r["MUNID"]: r for r in read_json(PROCESSED / f"bff_{year}/municipal_evidence.json")}
    cases = {r["MUNID"]: r for r in rows}
    source = []
    for city in units:
        case = cases.get(city["MUNID"], {})
        award = awards.get(city["MUNID"], {})
        amount = case.get("announced_allocation_cad", award.get("award_cad"))
        source.append({"municipality": city["municipality"], "municipality_key": city["municipality_key"],
            "scope": "individual_target", "year": year, "in_cohort": True,
            "target": None, "official_pct": None, "official_progress": None, "official_met_80pct": None,
            "new_starts_used": city["starts_total"], "new_starts_pct": None, "new_starts_met_80pct": None,
            "independent_including_arus": None, "independent_including_arus_pct": None,
            "independent_including_arus_met_80pct": None, "reviewed_arus": None,
            "announced_allocation_cad": amount, "note": "Annual target not yet verified in this comparison.",
            **case, "award_confirmed": bool(award.get("award_confirmed") or amount is not None),
            "comparison_documented": bool(case)})
    provenance = {"year": year, "purpose": "Residential-only counterfactual and official BFF allocations",
        "comparison_source": f"data/processed/residential_bff_{year}/municipal_comparison.json",
        "award_source": f"data/processed/bff_{year}/municipal_evidence.json",
        "residential_source": f"data/processed/residential_{year}/municipal_units.json"}
    geo, province, mapped, audit = join_municipalities(source, provenance, folder,
        lambda row: {"category": scenario(row)["category"], "met_80pct": row["new_starts_met_80pct"]})
    audit["purpose"] = provenance["purpose"]
    audit["targets_validated_in_comparison"] = len(rows)
    audit["counterfactual_not_official_funding_decision"] = True
    write_json(folder / "join_audit.json", audit)
    return geo, province, mapped


def render(rows, summary):
    year = summary["year"]
    geo, province, mapped = prepare(rows, summary)
    by_id = {r["MUNID"]: r for r in mapped}
    confirmed = sum(r["award_confirmed"] for r in mapped)
    base = REPORTS / f"residential_bff_{year}_ontario_map"
    bg, ink, muted = "#f4f2ed", "#172e3c", "#596574"
    fig = plt.figure(figsize=(12, 13), facecolor=bg)
    fig.text(.055, .958, f"ONTARIO  /  TARGETS, HOMES AND FUNDING  /  {year}", fontsize=11, weight="bold", color=muted)
    n = len(summary["below_80pct_if_new_construction_only"])
    fig.text(.055, .915, f"{n} of {len(rows)} documented award cases\nwould fall below 80%.", fontsize=29, weight="bold", color=ink, va="top", linespacing=1.18)
    fig.text(.055, .806, f"Scenario: new houses and apartments only.\n{len(rows)}/50 annual targets verified here; {confirmed} confirmed allocations in the register.", fontsize=12, color=muted, va="top", linespacing=1.5)
    full = fig.add_axes((.04, .36, .32, .39))
    south = fig.add_axes((.365, .31, .60, .43))
    awarded_ids = [r["MUNID"] for r in mapped if r["award_confirmed"]]
    for ax in (full, south):
        ax.set_facecolor(bg)
        province.plot(ax=ax, color="#e9e8e1", edgecolor="#bcc4c8", linewidth=.6)
        geo.plot(ax=ax, color=geo["category"].map(lambda c: COLORS.get(c, COLORS["outside"])), edgecolor=bg, linewidth=.22)
        geo[geo["MUNID"].isin(awarded_ids)].boundary.plot(ax=ax, color=BLUE, linewidth=.65)
        ax.set_axis_off()
    bounds = gpd.GeoSeries([box(*SOUTH_BOUNDS)], crs=4326).to_crs(3347).total_bounds
    south.set_xlim(bounds[0], bounds[2]); south.set_ylim(bounds[1], bounds[3])
    full.set_title("Entire province", fontsize=10, color=muted)
    south.set_title("Southern and eastern Ontario", fontsize=10, color=muted)
    offsets = {"london": (-100_000, -90_000), "kitchener": (-160_000, 100_000),
               "sarnia": (-155_000, 10_000), "welland": (35_000, -80_000)}
    for row in mapped:
        if not row["comparison_documented"]:
            continue
        point = geo.loc[geo["MUNID"] == row["MUNID"]].geometry.iloc[0].representative_point()
        dx, dy = offsets[row["municipality_key"]]
        pct = f"{row['new_starts_pct']:.1f}%"
        amount = f"{row['announced_allocation_cad']/1e6:.2f}"
        south.annotate(f"{row['municipality']} · {pct}\nC$ {amount} M", (point.x,point.y), (point.x+dx,point.y+dy),
            fontsize=9, color=ink, bbox={"facecolor":bg,"alpha":.94,"edgecolor":"none","pad":2},
            arrowprops={"arrowstyle":"-","color":muted,"lw":.6})
    handles = [Patch(facecolor=COLORS["above"],label="≥ 80%: new construction only"),
        Patch(facecolor=COLORS["below"],label="< 80%: new construction only"),
        Patch(facecolor=COLORS["unknown"],label="Annual target not yet verified"),
        Patch(facecolor=COLORS["outside"],label="Outside the 50-municipality scope"),
        Patch(facecolor="none",edgecolor=BLUE,linewidth=1.5,label="Blue outline: confirmed funding")]
    fig.legend(handles=handles,loc="lower left",bbox_to_anchor=(.05,.175),frameon=False,fontsize=10,ncol=2,labelspacing=1.1)
    fig.text(.055,.155,"London + Kitchener: C$19.28 million in announced allocations.\nKitchener reaches 85.9% when 489 additional residential units are included.",fontsize=10,color=ink,va="top",linespacing=1.5)
    fig.text(.055,.097,"This scenario excludes ARUs and conversions, which can also house families.\nColours do not establish improper payments or dependence on institutional beds.",fontsize=10,color=muted,va="top",linespacing=1.5)
    fig.text(.055,.039,"Sources: CMHC and official municipal/provincial releases; boundaries: Ontario GeoHub.\nSame HAF layout and municipal layer. EPSG:3347. Four cases; no province-wide extrapolation.",fontsize=9,color=muted,va="top",linespacing=1.5)
    fig.savefig(base.with_suffix(".png"),dpi=170,facecolor=bg); plt.close(fig)

    xmin,ymin,xmax,ymax = province.total_bounds; scale = 1000/(xmax-xmin)
    view = [-10,-10,1020,(ymax-ymin)*scale+20]
    south_view = [(bounds[0]-xmin)*scale,(ymax-bounds[3])*scale,(bounds[2]-bounds[0])*scale,(bounds[3]-bounds[1])*scale]
    paths = [f'<path d="{path_data(g,xmin,ymax,scale)}" fill="#e9e8e1" stroke="#aab6bf" stroke-width=".5"/>' for g in province.geometry]
    for row in geo.itertuples():
        record = by_id.get(row.MUNID)
        if record is None:
            record = {"MUNID":row.MUNID,"municipality":row.MUNICIPAL_NAME_SHORTFORM.title(),"in_cohort":False,
                "award_confirmed":False,"comparison_documented":False}
            by_id[row.MUNID] = record
        color = COLORS[scenario(record)["category"]]
        stroke = f' stroke="{BLUE}" stroke-width="1.3"' if record["award_confirmed"] else ''
        paths.append(f'<path data-munid="{row.MUNID}" d="{path_data(row.geometry.simplify(150,preserve_topology=True),xmin,ymax,scale)}" fill="{color}" fill-rule="evenodd" class="municipality" tabindex="0"{stroke}><title>{html.escape(record["municipality"])}</title></path>')
    css = re.search(r"<style>(.*?)</style>",(ROOT/"src/templates/haf_map.html").read_text(encoding="utf-8"),re.S)
    if css is None:
        raise ValueError("Shared HAF stylesheet missing")
    payload = {"rows":by_id,"summary":summary,"colors":COLORS,"confirmed":confirmed,
        "provinceView":" ".join(map(str,view)),"southView":" ".join(map(str,south_view))}
    template = (ROOT/"src/templates/residential_bff_map.html").read_text(encoding="utf-8")
    for token,value in {"__SHARED_CSS__":css[1],"__YEAR__":str(year),"__MAP_PATHS__":"\n".join(paths),
        "__FULL_VIEW__":payload["provinceView"],"__SOUTH_VIEW__":payload["southView"],
        "__MAP_DATA__":json.dumps(payload,ensure_ascii=False).replace("</","<\\/")}.items():
        template = template.replace(token,value)
    base.with_suffix(".html").write_text(template,encoding="utf-8")
    write_json(PROCESSED/f"residential_bff_{year}/map_data.json",payload)
