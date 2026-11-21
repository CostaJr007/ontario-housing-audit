"""Count self-contained residential units by dwelling type, without BFF bed additions."""
import argparse
import csv
import re
from datetime import date

from openpyxl import load_workbook

from src.analyze import load_year
from src.bff import join_municipalities
from src.common import PROCESSED, RAW, REPORTS, normalize_name, read_json, write_json
from src.ingest import download

PAGE = "https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/housing-market-data/starts-completions-under-construction-census-subdivisions"
METHOD = "https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-research/surveys/methods/methodologies-starts-completions-market-absorption-survey"
ASSET = "https://assets.cmhc-schl.gc.ca/sites/cmhc/professional/housing-markets-data-and-research/housing-data-tables/housing-market-data/housing-information-monthly/{year}/december/starts-completions-under-construction-12-{short}-en.xlsx"
TYPES = ("single", "semi", "row", "apartment_other", "total")
SUFFIX = re.compile(r" (?:CY|CV|C|T|TP|MU|M|VL|NO)$")
ALIASES = {"greatersudburygrandsudbury": "greatersudbury", "peterborough": "peterboroughcity"}


def cell_count(value):
    if value == "-":
        return 0  # The workbook's Symbols sheet explicitly defines '-' as zero.
    if value is None or value in ("N/A", "**", "..", "..."):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or int(value) != value:
        raise ValueError(f"Unrecognized residential count or symbol: {value!r}")
    return int(value)


def metric_counts(values):
    counts = dict(zip(TYPES, (cell_count(v) for v in values), strict=True))
    components = [counts[k] for k in TYPES[:-1]]
    if all(v is not None for v in components) and counts["total"] is not None and sum(components) != counts["total"]:
        raise ValueError(f"Dwelling types do not reconcile: {counts}")
    counts["houses"] = sum(counts[k] for k in TYPES[:3]) if all(counts[k] is not None for k in TYPES[:3]) else None
    return counts


def cmhc_key(name):
    key = normalize_name(SUFFIX.sub("", name.strip()))
    return ALIASES.get(key, key)


def parse_workbook(path, year):
    book = load_workbook(path, read_only=True, data_only=True)
    records, excluded = {}, []
    try:
        for name in ("Table H6", "Table H11-3"):
            table = list(book[name].values)
            if table[2][0] != "Ontario" or str(year) not in str(table[4][0]):
                raise ValueError(f"Unexpected province/year in {name}")
            expected = [f"Starts/{t}" for t in ("Single", "Semi", "Row", "Apt", "Total")]
            if list(table[6][7:12]) != expected or any(v != "January to December" for v in table[7][7:12]) or any(v != year for v in table[8][7:12]):
                raise ValueError(f"Annual start columns changed in {name}")
            if name == "Table H6":
                if list(table[6][17:22]) != [s.replace("Starts/", "Completions/") for s in expected] or any(v != "January to December" for v in table[7][17:22]) or any(v != year for v in table[8][17:22]):
                    raise ValueError("Annual completion columns changed")
            for row_number, values in enumerate(table[9:], 10):
                label = values[1]
                if not isinstance(label, str) or label == "Total":
                    continue
                if not SUFFIX.search(label):
                    # E.g. Woodstock CA: do not paint a regional aggregate as a municipality.
                    excluded.append({"sheet": name, "row": row_number, "label": label, "reason": "not an explicit municipal CSD row"})
                    continue
                key = cmhc_key(label)
                if key in records:
                    raise ValueError(f"Duplicate municipal CMHC key: {key}")
                starts = metric_counts(values[7:12])
                completions = metric_counts(values[17:22] if name == "Table H6" else [None]*5)
                records[key] = {"cmhc_label": label, "cmhc_parent": values[0], "cmhc_sheet": name,
                    "cmhc_row": row_number, "cmhc_geography": "CSD (municipal row)",
                    **{f"starts_{k}": v for k,v in starts.items()},
                    **{f"completions_{k}": v for k,v in completions.items()}}
    finally:
        book.close()
    return records, excluded


def assemble(roster, cmhc, year):
    rows = []
    for city in roster:
        if city["scope"] != "individual_target":
            continue
        evidence = cmhc.get(city["municipality_key"])
        empty = {f"{m}_{t}": None for m in ("starts", "completions") for t in (*TYPES, "houses")}
        rows.append({"municipality": city["municipality"], "municipality_key": city["municipality_key"],
            "scope": "individual_target", "year": year, "cmhc_label": None, "cmhc_parent": None,
            "cmhc_sheet": None, "cmhc_row": None, "cmhc_geography": None,
            **empty, **(evidence or {}), "has_cmhc_municipal_row": evidence is not None})
    return rows


def run(year=2025, refresh=False):
    if year >= date.today().year:
        raise ValueError("This pipeline requires a complete calendar year; no annual extrapolation is performed")
    folder = PROCESSED / f"residential_{year}"
    url = ASSET.format(year=year, short=str(year)[2:])
    path = RAW / f"cmhc/csd_december_{year}.xlsx"
    manifest = read_json(RAW / "manifest.json")
    download(url, path, manifest, refresh)
    cmhc, excluded = parse_workbook(path, year)
    rows = assemble(load_year(2024), cmhc, year)
    source = {"year": year, "source_url": url, "landing_page": PAGE, "methodology": METHOD,
        "source_sha256": manifest[f"cmhc/csd_december_{year}.xlsx"]["sha256"],
        "retrieved_at_utc": manifest[f"cmhc/csd_december_{year}.xlsx"]["retrieved_at_utc"],
        "vintage": f"December {year} edition, not a claim to latest revised data",
        "period": f"January to December {year}", "geography": "Explicit municipal CSD rows only; never CMA/CA totals",
        "unit": "Self-contained year-round residential dwelling units, not buildings or beds",
        "cohort": "50 BFF municipalities from the 2024 program roster; names only, no inherited annual targets",
        "included": ["single-detached", "semi-detached", "row", "apartment and other; includes duplexes and stacked townhouses"],
        "not_added": ["LTC beds", "student beds", "institutional suites", "conversions/ARUs in existing buildings"],
        "limitations": ["No residents, family composition, bedroom counts, affordability or actual occupancy in this workbook",
            "An independent unit occupied by a student or senior remains a residential unit; the data cannot identify the occupant",
            "Apartment and other cannot be separated into pure apartments and other types with this table",
            "Starts and completions are distinct annual flows, not the same construction cohort"],
        "excluded_nonmunicipal_rows": excluded}
    def classification(row):
        return {"category": "available" if row["starts_total"] is not None else "unknown", "met_80pct": None}
    geo, province, mapped, audit = join_municipalities(rows, source, folder, classification)
    audit["purpose"] = "Municipal crosswalk for residential counts; no BFF eligibility classification"
    write_json(folder / "join_audit.json", audit)
    summary = {"year": year, "program_cohort": len(mapped), "boundary_municipalities": len(geo)}
    for metric in ("starts", "completions"):
        eligible = [r for r in mapped if r[f"{metric}_total"] is not None]
        summary[f"{metric}_coverage"] = len(eligible)
        summary[f"{metric}_missing"] = [r["municipality"] for r in mapped if r[f"{metric}_total"] is None]
        for kind in (*TYPES, "houses"):
            summary[f"{metric}_{kind}"] = sum(r[f"{metric}_{kind}"] for r in eligible)
    write_json(folder / "source.json", source)
    write_json(folder / "summary.json", summary)
    write_json(folder / "municipal_units.json", mapped)
    with (folder / "municipal_units.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(mapped[0]))
        writer.writeheader()
        writer.writerows(mapped)
    from src.plot_residential import render
    REPORTS.mkdir(parents=True, exist_ok=True)
    render(geo, province, mapped, summary, source)
    print(f"Self-contained residential units | {year} | annual CMHC municipal rows")
    print(f"Starts: {summary['starts_total']:,} | houses: {summary['starts_houses']:,} | apartments/other: {summary['starts_apartment_other']:,} | coverage: {summary['starts_coverage']}/50")
    print(f"Completions: {summary['completions_total']:,} | coverage: {summary['completions_coverage']}/50 (different coverage, not a starts-to-completions conversion rate)")
    print(f"Missing starts: {summary['starts_missing']} | missing completions: {summary['completions_missing']}")
    print(f"JOIN: {audit['municipalities_matched']}/50 | EPSG:3347 | no regional totals substituted")
    print(f"Outputs: reports/residential_{year}_ontario_map.png | reports/residential_{year}_ontario_map.html")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    run(args.year, args.refresh)


if __name__ == "__main__":
    main()
