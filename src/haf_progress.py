"""Collect the CMHC Ontario progress tables and retain their published reporting period."""
import argparse
import csv
import hashlib
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from src.common import PROCESSED, RAW, normalize_name, read_json, write_json
from src.ingest import download

BASE = "https://www.cmhc-schl.gc.ca"
REPORT = BASE + "/professionals/project-funding-and-mortgage-financing/funding-programs/all-funding-programs/housing-accelerator-fund/housing-accelerator-fund-rounds-data/province"
API = BASE + "/api/sitecore/HAFReport/HAFReportFilter"
ROUNDS = {
    2023: ("{74AFF66B-77DF-4C0A-9C5B-28B9FB46EFCA}", "{8FFC3CB1-EAE5-4FF1-8E97-E5CB7887E8CA}"),
    2024: ("{F75AD4D3-A1CB-4341-9736-788407A56DE9}", "{2DBEFFBC-DECD-405F-A870-A69AE5BA689B}"),
}


class ProgressParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.totals = {}
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self.row = {}
        elif tag == "td" and self.row is not None:
            self.cell = attrs.get("class", "")
            self.row[self.cell] = ""
        elif tag == "img" and self.cell == "city-name":
            self.row["overall_assessment"] = attrs.get("alt", "")
        elif tag == "a" and self.cell == "action-plan":
            self.row["action_plan_url"] = attrs.get("href", "")
        elif tag == "input" and attrs.get("id", "").startswith("province-"):
            self.totals[attrs["id"]] = attrs.get("value")

    def handle_data(self, value):
        if self.cell is not None and self.row is not None:
            self.row[self.cell] += value

    def handle_endtag(self, tag):
        if tag == "td":
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append({k: " ".join(v.split()) for k, v in self.row.items()})
            self.row = None


def percentage(value):
    if re.fullmatch(r"\d+(?:\.\d+)?%", value):
        return float(value[:-1])
    if value.strip().lower() in ("", "-", "—", "n/a", "na", "not available", "not applicable"):
        return None
    raise ValueError(f"Unrecognized percentage: {value!r}")


def numeric(value):
    value = value.replace("$", "").replace(",", "").strip()
    if value in ("", "-", "—", "N/A"):
        return None
    return int(value)


def parse_table(payload, intake):
    parser = ProgressParser()
    parser.feed(payload)
    rows = []
    for raw in parser.rows:
        if "city-name" not in raw:
            continue
        pct = percentage(raw["permitted-units"])
        assessment = raw.get("overall_assessment")
        if assessment not in ("good", "moderate", "low", "terminated"):
            raise ValueError(f"Unknown assessment: {raw}")
        category = "terminated" if assessment == "terminated" else "no_value" if pct is None else "at_or_above_forecast" if pct >= 100 else "below_forecast"
        rows.append({"community": raw["city-name"], "community_key": normalize_name(raw["city-name"]),
                     "intake_year": intake, "overall_assessment": assessment,
                     "action_plan_progress": raw["action-plan"], "approved_funding_cad": numeric(raw["total-funding"]),
                     "haf_incented_units": numeric(raw["incented-units"]), "housing_supply_growth_target": numeric(raw["growth-target"]),
                     "permitted_units_pct_of_period_forecast": pct, "category": category,
                     "action_plan_url": raw.get("action_plan_url", ""), "review_cutoff": "2026-03"})
    if not rows:
        raise ValueError("Empty CMHC table")
    return rows, parser.totals


def snapshot(intake, refresh=False):
    path = RAW / "haf" / f"ontario_intake_{intake}.html"
    key = path.relative_to(RAW).as_posix()
    manifest = read_json(RAW / "manifest.json")
    if path.exists() and not refresh:
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest[key]["sha256"]:
            raise ValueError(f"Checksum mismatch: {key}")
        return path.read_text(encoding="utf-8")
    round_id, province_id = ROUNDS[intake]
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    opener.addheaders = [("User-Agent", "OntarioHousingAudit/0.1 (public-data-research)")]
    page_url = REPORT + "?" + urlencode({"round": round_id, "province": province_id})
    with opener.open(page_url, timeout=60) as response:
        page = response.read().decode("utf-8")
    if "up to March 2026" not in page:
        raise ValueError("CMHC reporting period changed: review dates and definitions before updating")
    token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', page)
    if not token:
        raise ValueError("CMHC page verification field not found")
    params = {"Round": round_id, "Province": province_id, "Stream": "", "Order": "", "language": "en"}
    form = {**params, "__RequestVerificationToken": token[1]}
    request = Request(API, data=urlencode(form).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
    with opener.open(request, timeout=60) as response:
        payload = response.read()
    parse_table(payload.decode("utf-8"), intake)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    manifest[key] = {"url": API, "http_method": "POST", "request_parameters": params,
                     "source_page": page_url, "review_cutoff": "2026-03",
                     "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                     "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
    write_json(RAW / "manifest.json", manifest)
    return payload.decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    rows = []
    totals = {}
    for intake in ROUNDS:
        result, displayed = parse_table(snapshot(intake, args.refresh), intake)
        rows.extend(result)
        totals[intake] = displayed
        funding = numeric(displayed["province-funding"])
        row_sum = sum(r["approved_funding_cad"] or 0 for r in result)
        totals[intake]["row_funding_sum_cad"] = row_sum
        totals[intake]["row_sum_minus_header_cad"] = row_sum - funding
        # Keep any difference visible; funding totals do not determine map colors.
    keys = [r["community_key"] for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Repeated communities across intakes require explicit reconciliation")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    with (PROCESSED / "haf_ontario_progress.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_json(PROCESSED / "haf_source_totals.json", totals)
    manifest = read_json(RAW / "manifest.json")
    province = "https://ws.lioservices.lrc.gov.on.ca/arcgis2/rest/services/LIO_OPEN_DATA/LIO_Open03/MapServer/0/query?" + urlencode({
        "where": "1=1", "outFields": "OFFICIAL_NAME", "outSR": "4326", "returnGeometry": "true",
        "geometryPrecision": "4", "maxAllowableOffset": "0.005", "f": "geojson"})
    download(province, RAW / "geohub" / "province.geojson", manifest, args.refresh)
    print(f"CMHC Ontario: {len(rows)} communities; annual reviews up to March 2026.")
    print("Funding reconciliation differences (CAD):", {year: value["row_sum_minus_header_cad"] for year, value in totals.items()})


if __name__ == "__main__":
    main()
