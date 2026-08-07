"""警政署「測速執法設置點」全國資料，唯一涵蓋全台 22 縣市的來源，只有測速類型。
資料集頁面：https://data.gov.tw/dataset/7320"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import requests

from schema import EnforcementPoint, make_id

SOURCE_NAME = "警政署測速執法設置點"
SOURCE_URL = "https://data.gov.tw/dataset/7320"
DOWNLOAD_URL = (
    "https://opdadm.moi.gov.tw/api/v1/no-auth/resource/api/dataset/"
    "EA5E6FCD-B82D-43B7-A5CF-E9893253187E/resource/"
    "9E196F6A-560E-4CFE-92A1-BE6EA19C8E53/download"
)


def parse_national_speed(csv_text: str) -> list[EnforcementPoint]:
    reader = csv.DictReader(io.StringIO(csv_text))
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in reader:
        # 第二列是重複的中文欄名標籤，用 CityName 是不是英文欄名本身來跳過
        if row.get("CityName") in (None, "", "設置縣市"):
            continue
        try:
            lat = float(row["Latitude"])
            lng = float(row["Longitude"])
        except (KeyError, ValueError):
            continue
        address = f"{row['CityName']}{row['RegionName']}{row['Address']}"
        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, address),
                county=row["CityName"],
                district=row["RegionName"],
                address=row["Address"],
                lat=lat,
                lng=lng,
                violation_types=["speed"],
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
    return parse_national_speed(resp.content.decode("utf-8-sig"))


if __name__ == "__main__":
    result = fetch()
    print(f"national_speed: {len(result)} 筆")
