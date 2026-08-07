"""高雄市政府警察局固定式違規照相科技執法設備設置地點，HTML 表格，沒有經緯度需地理編碼。
頁面：https://kcpd.kcg.gov.tw/cp.aspx?n=693052840FE00C08"""
from __future__ import annotations

from datetime import datetime, timezone

from geocode import geocode, load_cache, save_cache
from html_table_parser import fetch_html_table_rows
from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "高雄市政府警察局固定式違規照相科技執法設備設置地點"
SOURCE_URL = "https://kcpd.kcg.gov.tw/cp.aspx?n=693052840FE00C08"
_HEADER = ["編號", "型式", "測照地點", "測照方向", "速限", "行政區", "測照型式", "地圖"]


def build_points(rows: list[dict[str, str]], cache: dict) -> list[EnforcementPoint]:
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in rows:
        location = row.get("測照地點", "").strip()
        district = row.get("行政區", "").strip()
        if not location:
            continue

        query = f"高雄市{district}區{location}"
        # 呼叫端先查一次快取，不要無條件呼叫 geocode()：geocode() 內部雖然也會查快取，
        # 但測試用 patch("kaohsiung.geocode") 整個換掉函式時，patch 換掉的是包含內部
        # 快取檢查在內的整個函式本體，所以測試判斷「快取已經有答案時不該呼叫 geocode()」
        # 這件事，必須由呼叫端自己先判斷，不能依賴被 mock 掉的函式內部邏輯
        # （Task 6 台南市 scraper review 時發現的同一個問題，這裡照同樣方式先修正）。
        if query in cache:
            cached = cache[query]
            coords = (cached[0], cached[1]) if cached else None
        else:
            coords = geocode(query, cache)
        if coords:
            lat, lng, quality = coords[0], coords[1], "geocoded"
        else:
            lat, lng, quality = None, None, "no-coords"

        raw_type = row.get("測照型式", "")
        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, location),
                county="高雄市",
                district=district,
                address=location,
                lat=lat,
                lng=lng,
                violation_types=classify_types(raw_type),
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
    print(f"kaohsiung: {len(result)} 筆")
