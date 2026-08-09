"""高雄市政府警察局固定式違規照相科技執法設備設置地點，HTML 表格，沒有經緯度需地理編碼。
頁面：https://kcpd.kcg.gov.tw/cp.aspx?n=693052840FE00C08"""
from __future__ import annotations

from datetime import datetime, timezone

from geocode import extract_primary_road, load_cache, resolve_with_centroid_fallback, save_cache
from html_table_parser import fetch_html_table_rows
from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "高雄市政府警察局固定式違規照相科技執法設備設置地點"
SOURCE_URL = "https://kcpd.kcg.gov.tw/cp.aspx?n=693052840FE00C08"
_HEADER = ["編號", "型式", "測照地點", "測照方向", "速限", "行政區", "測照型式", "地圖"]


def _build_full_query(district: str, location: str) -> str:
    # 來源資料的「測照地點」欄位有時已經自帶行政區前綴（例如「三民區建國二路與復興一路」），
    # 這種情況不能再加一次「{district}區」，否則查詢字串會變成「三民區三民區...」查不到任何結果。
    # 只判斷「{district}區」這個完整前綴（不是單純 startswith(district)），
    # 避免誤判路名剛好跟行政區同名開頭的情況（例如「楠梓路」不該被當成「楠梓區」重複）。
    if location.startswith(f"{district}區"):
        return f"高雄市{location}"
    return f"高雄市{district}區{location}"


def build_points(rows: list[dict[str, str]], cache: dict) -> list[EnforcementPoint]:
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in rows:
        location = row.get("測照地點", "").strip()
        district = row.get("行政區", "").strip()
        if not location:
            continue

        full_query = _build_full_query(district, location)
        primary_query = _build_full_query(district, extract_primary_road(location))
        centroid_query = f"高雄市{district}區"
        coords, quality = resolve_with_centroid_fallback(full_query, primary_query, centroid_query, cache)
        lat, lng = (coords[0], coords[1]) if coords else (None, None)

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
