"""臺中市科技執法取締地點，有經緯度與獨立的違規類型欄位。
資料集頁面：https://data.gov.tw/dataset/170673
注意：CSV 欄名「經度/緯度」實際數值是對調的，見下方 parse_taichung 內的處理。"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import requests

from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "臺中市政府警察局科技執法取締地點"
SOURCE_URL = "https://data.gov.tw/dataset/170673"
DOWNLOAD_URL = "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download?rid=8fa25d05-2d40-47cb-bc6c-459c8dabf165"


def parse_taichung(csv_text: str) -> list[EnforcementPoint]:
    reader = csv.DictReader(io.StringIO(csv_text))
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in reader:
        location = (row.get("設置地點") or "").strip()
        if not location:
            continue
        try:
            # 欄名寫「經度」但實際是緯度數值，「緯度」欄實際是經度數值，這裡對調回正確位置
            lat = float(row["經度"])
            lng = float(row["緯度"])
        except (KeyError, ValueError):
            continue
        raw_types = row.get("取締項目") or ""
        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, location),
                county="臺中市",
                district="",
                address=location,
                lat=lat,
                lng=lng,
                violation_types=classify_types(raw_types),
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                data_quality="coords",
                fetched_at=now,
            )
        )
    return points


def fetch() -> list[EnforcementPoint]:
    resp = requests.get(DOWNLOAD_URL, timeout=30)
    resp.raise_for_status()
    return parse_taichung(resp.content.decode("utf-8-sig"))


if __name__ == "__main__":
    result = fetch()
    print(f"taichung: {len(result)} 筆")
