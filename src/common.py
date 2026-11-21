"""Shared paths and conservative municipality-name normalization."""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
CATALOGUE = "https://data.ontario.ca/api/3/action/package_show?id=ontario-s-housing-supply-progress"
GEO_ITEM = "https://www.arcgis.com/sharing/rest/content/items/64fb702e16204c3e88b528d9759f1174?f=json"


def normalize_name(value):
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower().strip()
    text = re.sub(r"^(?:the )?corporation of the ", "", text)
    text = re.sub(r"^(?:city|town|township|municipality|county) of (?:the )?", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

