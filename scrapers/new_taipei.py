"""新北市「固定式科學儀器執法設備設置地點」一覽表，同一頁有 5 個子表格
（違規停車/車輛禁行路段/跨越雙黃線/跨越雙白線/路口安全），共用同一種表頭，
html_table_parser.fetch_html_table_rows 會自動合併成一份清單。
沒有經緯度，需要地理編碼。該網域憑證有問題，關閉 SSL 驗證（verify_ssl=False）。
頁面：https://www.traffic.police.ntpc.gov.tw/cp-3313-116237-27.html"""
from __future__ import annotations

from datetime import datetime, timezone

from geocode import extract_primary_road, load_cache, resolve_with_centroid_fallback, save_cache
from html_table_parser import fetch_html_table_rows
from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "新北市固定式科學儀器執法設備設置地點"
SOURCE_URL = "https://www.traffic.police.ntpc.gov.tw/cp-3313-116237-27.html"
_HEADER = ["編號", "設置位置", "取締項目"]


def build_points(rows: list[dict[str, str]], cache: dict) -> list[EnforcementPoint]:
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in rows:
        location = row.get("設置位置", "").strip()
        if not location:
            continue

        full_query = f"新北市{location}"
        primary_query = f"新北市{extract_primary_road(location)}"
        centroid_query = "新北市"
        coords, quality = resolve_with_centroid_fallback(full_query, primary_query, centroid_query, cache)
        lat, lng = (coords[0], coords[1]) if coords else (None, None)

        raw_types = row.get("取締項目", "")
        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, location),
                county="新北市",
                district="",
                address=location,
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
    rows = fetch_html_table_rows(SOURCE_URL, expected_header=_HEADER, verify_ssl=False)
    cache = load_cache()
    points = build_points(rows, cache)
    save_cache(cache)
    return points


if __name__ == "__main__":
    result = fetch()
    print(f"new_taipei: {len(result)} 筆")
