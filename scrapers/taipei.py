"""臺北市智慧管理科技執法設備資料表。
資料集頁面：https://data.gov.tw/dataset/135957
注意：欄位叫「座標-X/座標-Y」，但實測數值已經是經緯度（WGS84），不需要座標轉換。"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import requests

from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "臺北市智慧管理科技執法設備資料表"
SOURCE_URL = "https://data.gov.tw/dataset/135957"
DOWNLOAD_URL = (
    "https://data.taipei/api/dataset/986fa73e-c470-4ebf-9f35-3a1c9d2a8788/"
    "resource/4715904f-6ce1-41c2-8a68-3bc5303f3607/download"
)


def parse_taipei(csv_text: str) -> list[EnforcementPoint]:
    reader = csv.DictReader(io.StringIO(csv_text))
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in reader:
        location = (row.get("取締路段") or "").strip()
        if not location:
            continue
        try:
            lng = float(row["座標-X"])
            lat = float(row["座標-Y"])
        except (KeyError, ValueError):
            continue
        raw_types = row.get("取締項目") or ""
        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, location),
                county="臺北市",
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
    return parse_taipei(resp.content.decode("utf-8-sig"))


if __name__ == "__main__":
    result = fetch()
    print(f"taipei: {len(result)} 筆")
