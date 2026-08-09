"""臺南市智慧管理科技執法設備設置地點。
資料集頁面：https://data.tainan.gov.tw/dataset/tech-enforcement-location
注意：這個來源沒有經緯度，用 geocode.py 對「設置位置」文字做地理編碼；
違規類型寫在「【...】」括號內；行政區欄位是數字代碼不是區名，不使用。"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone

import requests

from geocode import extract_primary_road, load_cache, resolve_with_centroid_fallback, save_cache
from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "臺南市智慧管理科技執法設備設置地點"
SOURCE_URL = "https://data.tainan.gov.tw/Resource/1c7e82f0-d6b2-4b20-aeff-5c768100f82c"
DOWNLOAD_URL = (
    "https://data.tainan.gov.tw/File/DirectDownload/1c7e82f0-d6b2-4b20-aeff-5c768100f82c"
    "?fileName=tainan"
)

_BRACKET_RE = re.compile(r"【(.+?)】")
_REPEATED_JUNCTION_RE = re.compile(r"(路口)\1.*$")


def _extract_road_name(location_text: str) -> str:
    # 取「【」之前、第一個括號之前的文字當作路段名稱
    before_bracket = location_text.split("【")[0]
    road_name = before_bracket.split("(")[0]
    # 路口型設備常見「OO路口路口多功能違規科技執法系統」，
    # 「路口」重複出現時第二次開始其實是設備說明文字，一併裁掉
    road_name = _REPEATED_JUNCTION_RE.sub(r"\1", road_name)
    return road_name.strip()


def parse_tainan(csv_text: str, cache: dict) -> list[EnforcementPoint]:
    reader = csv.DictReader(io.StringIO(csv_text))
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in reader:
        location_text = (row.get("設置位置") or "").strip()
        if not location_text:
            continue

        road_name = _extract_road_name(location_text)
        bracket_match = _BRACKET_RE.search(location_text)
        raw_types = bracket_match.group(1) if bracket_match else location_text

        full_query = f"台南市{road_name}"
        primary_query = f"台南市{extract_primary_road(road_name)}"
        centroid_query = "台南市"
        coords, quality = resolve_with_centroid_fallback(full_query, primary_query, centroid_query, cache)
        lat, lng = (coords[0], coords[1]) if coords else (None, None)

        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, location_text),
                county="臺南市",
                district="",
                address=road_name,
                lat=lat,
                lng=lng,
                violation_types=classify_types(raw_types),
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                data_quality=quality,
                fetched_at=now,
            )
        )
    return points


def fetch() -> list[EnforcementPoint]:
    resp = requests.get(DOWNLOAD_URL, timeout=30)
    resp.raise_for_status()
    cache = load_cache()
    points = parse_tainan(resp.content.decode("utf-8-sig"), cache)
    save_cache(cache)
    return points


if __name__ == "__main__":
    result = fetch()
    print(f"tainan: {len(result)} 筆")
