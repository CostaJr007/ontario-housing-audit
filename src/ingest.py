"""Download official snapshots, recording URL, retrieval time and SHA-256."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.common import CATALOGUE, GEO_ITEM, RAW, read_json, write_json


def download(url, path, manifest, refresh=False):
    key = path.relative_to(RAW).as_posix()
    if path.exists() and not refresh:
        if key not in manifest:
            raise ValueError(f"Untracked snapshot: {path}. Use --refresh to establish provenance.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != manifest[key]["sha256"]:
            raise ValueError(f"Snapshot checksum mismatch: {path}")
        return
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "OntarioHousingAudit/0.1 (public-data-research)"})
            with urlopen(request, timeout=120) as response:
                payload = response.read()
            # Do not accept a JSON error response as a successful download.
            if path.suffix in (".json", ".geojson"):
                parsed = json.loads(payload.decode("utf-8-sig"))
                if parsed.get("error") or parsed.get("success") is False:
                    raise ValueError(f"API error from {url}: {parsed}")
            break
        except (HTTPError, URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    manifest[key] = {
        "url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }
    write_json(RAW / "manifest.json", manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Replace snapshots from current official sources")
    args = parser.parse_args()
    manifest_path = RAW / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    def fetch(url, path):
        download(url, path, manifest, args.refresh)
    fetch(CATALOGUE, RAW / "ontario" / "catalogue.json")
    catalogue = read_json(RAW / "ontario" / "catalogue.json")["result"]
    resources = catalogue["resources"]
    for year in (2023, 2024):
        matches = [r for r in resources if r["format"] == "CSV" and f"{year}_-_en.csv" in r["url"]]
        if len(matches) != 1:
            raise ValueError(f"Expected one English CSV for {year}, found {len(matches)}")
        resource = matches[0]
        fetch(resource["url"], RAW / "ontario" / f"housing_{year}.csv")
    csv_names = [r["name"] for r in resources if r["format"] == "CSV" and "_en.csv" in r["url"]]
    print("English CSVs available:", csv_names)

    fetch(GEO_ITEM, RAW / "geohub" / "item.json")
    service = read_json(RAW / "geohub" / "item.json")["url"]
    fetch(service + "?f=json", RAW / "geohub" / "layer.json")
    params = {"where": "1=1", "returnCountOnly": "true", "f": "json"}
    fetch(service + "/query?" + urlencode(params), RAW / "geohub" / "count.json")
    # Display-only generalization, ~100 m; not suitable for area measurements.
    params = {"where": "1=1", "outFields": "*", "returnGeometry": "true",
              "outSR": "4326", "geometryPrecision": "4", "maxAllowableOffset": "0.001", "f": "geojson"}
    fetch(service + "/query?" + urlencode(params), RAW / "geohub" / "municipalities.geojson")
    geo = read_json(RAW / "geohub" / "municipalities.geojson")
    expected = read_json(RAW / "geohub" / "count.json")["count"]
    if len(geo["features"]) != expected or geo.get("exceededTransferLimit"):
        raise ValueError("Incomplete boundary download; implement pagination before continuing")
    print(f"Boundary features: {expected}. Snapshots verified in {RAW}")


if __name__ == "__main__":
    main()

