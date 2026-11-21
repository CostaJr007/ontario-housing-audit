"""Download and normalize a complete annual BFF dataset and the existing GeoHub layers."""
import argparse
import csv
import re
from datetime import date
from urllib.parse import urlencode

from src.analyze import load_year
from src.common import CATALOGUE, GEO_ITEM, PROCESSED, RAW, read_json, write_json
from src.ingest import download

BFF_DATA = PROCESSED / "bff"


def annual_resources(resources):
    result = {}
    for resource in resources:
        match = re.search(r"(20\d{2})_-_en\.csv(?:\?.*)?$", resource.get("url", ""))
        if resource.get("format", "").upper() == "CSV" and match:
            year = int(match[1])
            if year in result:
                raise ValueError(f"Multiple English CSVs found for {year}")
            result[year] = resource
    return result


def ingest(year=None, refresh=False):
    manifest_file = RAW / "manifest.json"
    manifest = read_json(manifest_file) if manifest_file.exists() else {}

    def fetch(url, path):
        download(url, path, manifest, refresh)

    fetch(CATALOGUE, RAW / "ontario/catalogue.json")
    resources = annual_resources(read_json(RAW / "ontario/catalogue.json")["result"]["resources"])
    complete_years = sorted(y for y in resources if y < date.today().year)
    if year is None:
        if not complete_years:
            raise ValueError("No complete annual English CSV available")
        year = complete_years[-1]
    if year not in complete_years:
        raise ValueError(f"Year {year} unavailable as a complete annual CSV; available: {complete_years}")
    fetch(resources[year]["url"], RAW / f"ontario/housing_{year}.csv")
    fetch(GEO_ITEM, RAW / "geohub/item.json")
    service = read_json(RAW / "geohub/item.json")["url"]
    fetch(service + "?f=json", RAW / "geohub/layer.json")
    fetch(service + "/query?" + urlencode({"where": "1=1", "returnCountOnly": "true", "f": "json"}), RAW / "geohub/count.json")
    params = {"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": "4326",
              "geometryPrecision": "4", "maxAllowableOffset": "0.001", "f": "geojson"}
    fetch(service + "/query?" + urlencode(params), RAW / "geohub/municipalities.geojson")
    boundaries = read_json(RAW / "geohub/municipalities.geojson")
    if len(boundaries["features"]) != read_json(RAW / "geohub/count.json")["count"] or boundaries.get("exceededTransferLimit"):
        raise ValueError("Incomplete municipal boundary download")
    params = {"where": "1=1", "outFields": "OFFICIAL_NAME", "outSR": "4326", "returnGeometry": "true",
              "geometryPrecision": "4", "maxAllowableOffset": "0.005", "f": "geojson"}
    fetch(service.rsplit("/", 1)[0] + "/0/query?" + urlencode(params), RAW / "geohub/province.geojson")
    rows = load_year(year)
    BFF_DATA.mkdir(parents=True, exist_ok=True)
    with (BFF_DATA / "normalized_source.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    provenance = {"year": year, "available_complete_years": complete_years,
                  "source_url": resources[year]["url"], "raw_snapshot": f"data/raw/ontario/housing_{year}.csv",
                  "source_sha256": manifest[f"ontario/housing_{year}.csv"]["sha256"],
                  "measure": "Official total housing progress; includes categories beyond CMHC housing starts",
                  "municipal_cmhc_components_available": False}
    write_json(BFF_DATA / "source.json", provenance)
    return year, rows, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, help="Default: latest complete year in the archived catalogue")
    parser.add_argument("--refresh", action="store_true", help="Download current source versions")
    args = parser.parse_args()
    year, rows, _ = ingest(args.year, args.refresh)
    print(f"BFF {year}: {len(rows)} source records normalized; snapshots verified.")


if __name__ == "__main__":
    main()
