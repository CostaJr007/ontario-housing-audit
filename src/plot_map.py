"""Render the official 2024 baseline; fail if any targeted municipality is unmatched."""
import json

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd
from shapely.geometry import box

from src.common import PROCESSED, RAW, REPORTS, normalize_name, write_json


def main():
    geo = gpd.read_file(RAW / "geohub" / "municipalities.geojson")
    if geo.crs is None:
        raise ValueError("Boundary CRS is missing")
    invalid_count = int((~geo.geometry.is_valid).sum())
    geo["geometry"] = geo.geometry.make_valid(method="structure", keep_collapsed=False)
    if geo.geometry.isna().any():
        raise ValueError("Missing boundaries after geometry repair")
    empty_count = int(geo.geometry.is_empty.sum())
    geo = geo[~geo.geometry.is_empty].copy()
    # One municipality can contain several mainland/island features.
    geo["municipality_key"] = geo["MUNICIPAL_NAME_SHORTFORM"].map(normalize_name)
    geo = geo.dissolve(by="MUNID", as_index=False)
    data = pd.read_csv(PROCESSED / "municipal_progress.csv")
    data = data[(data["year"] == 2024) & (data["scope"] == "individual_target")]
    # Explicitly reviewed: City of Hamilton (25005), not Township of Hamilton (14019).
    overrides = {"hamilton": "25005", "peterboroughcity": "15014"}
    crosswalk = []
    unmatched = []
    for row in data.itertuples():
        candidates = geo[geo["municipality_key"] == row.municipality_key]
        if row.municipality_key in overrides:
            candidates = geo[geo["MUNID"] == overrides[row.municipality_key]]
        if len(candidates) != 1:
            unmatched.append(row.municipality)
            continue
        candidate = candidates.iloc[0]
        crosswalk.append({"municipality": row.municipality, "municipality_key": row.municipality_key,
                          "MUNID": candidate["MUNID"], "boundary_name": candidate["MUNICIPAL_NAME"],
                          "method": "reviewed_identifier" if row.municipality_key in overrides else "unique_normalized_name"})
    pd.DataFrame(crosswalk).to_csv(PROCESSED / "municipality_crosswalk.csv", index=False)
    audit = {"year": 2024, "targeted_municipalities": len(data), "unmatched": unmatched,
             "boundary_municipalities": len(geo), "projection": "EPSG:3347",
             "invalid_features_repaired_for_display": invalid_count,
             "collapsed_features_excluded_from_display": empty_count,
             "boundary_vintage": "current snapshot; not a reconstructed 2024 boundary"}
    write_json(PROCESSED / "join_audit.json", audit)
    if unmatched:
        raise ValueError(f"Resolve municipality crosswalk before mapping: {unmatched}")
    data = data.merge(pd.DataFrame(crosswalk)[["municipality_key", "MUNID"]], on="municipality_key", validate="one_to_one")
    geo = geo.merge(data.drop(columns="municipality_key"), on="MUNID", how="left", validate="one_to_one")
    geo["category"] = "No individual target in this dataset"
    covered = geo["target"].notna()
    geo.loc[covered & (geo["official_progress"] < geo["target"]), "category"] = "Below 100%"
    geo.loc[covered & (geo["official_progress"] >= geo["target"]), "category"] = "Reached 100% or more"
    total = len(data)
    met = int((data["official_progress"] >= data["target"]).sum())
    geo = geo.to_crs(3347)
    colors = {"Reached 100% or more": "#218b72", "Below 100%": "#d55459", "No individual target in this dataset": "#d7dae1"}
    background = "#f5f3ee"
    fig = plt.figure(figsize=(12, 12), facecolor=background)
    fig.text(.06, .94, "ONTARIO  /  HOUSING  /  2024", fontsize=12, color="#606776", weight="bold")
    fig.text(.06, .90, f"{met} of {total} municipalities\nmet the full official target.", fontsize=30, weight="bold", color="#182b3a", linespacing=1.15, va="top")
    fig.text(.06, .785, "Measure: official annual progress ≥ 100% of the municipal target.", fontsize=12, color="#414d5c")
    full = fig.add_axes((.04, .42, .35, .34))
    south = fig.add_axes((.38, .27, .60, .49))
    for ax in (full, south):
        ax.set_facecolor(background)
        geo.plot(ax=ax, color=geo["category"].map(colors), edgecolor=background, linewidth=.22)
        ax.set_axis_off()
    bounds = gpd.GeoSeries([box(-83.7, 41.5, -74.1, 46.7)], crs=4326).to_crs(3347).total_bounds
    south.set_xlim(bounds[0], bounds[2])
    south.set_ylim(bounds[1], bounds[3])
    full.set_title("Province: municipal boundaries", fontsize=11, color="#606776")
    south.set_title("Southern and eastern Ontario", fontsize=11, color="#606776")
    fig.legend(handles=[Patch(facecolor=c, label=l) for l, c in colors.items()], loc="lower left",
               bbox_to_anchor=(.055, .20), frameon=False, fontsize=12, labelspacing=.8)
    fig.text(.06, .15, f"{total-met} municipalities fell below 100%. Grey means no individual target in this dataset;\nareas outside municipal polygons retain the background colour.", fontsize=11, color="#414d5c", linespacing=1.5)
    fig.text(.06, .085, "Official housing progress includes categories beyond conventional housing starts.\nIt does not measure completions or isolate the effects of municipal policy.", fontsize=10, color="#606776", linespacing=1.5)
    fig.text(.06, .035, f"Sources: Ontario Data Catalogue (revised 2024 CSV); current Ontario GeoHub boundaries.\nScope: {total} targeted municipalities. Statistics Canada Lambert projection (EPSG:3347).", fontsize=9, color="#606776", linespacing=1.5)
    REPORTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(REPORTS / "ontario_targets_2024.png", dpi=160, facecolor=background)
    plt.close(fig)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
