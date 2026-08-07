"""新竹市警察局科技執法/固定式測速/移動式測速取締地點一覽表，三個表格都有經緯度。
頁面：https://tra.hccp.gov.tw/pages/camera"""
from __future__ import annotations

from datetime import datetime, timezone

from html_table_parser import fetch_html_table_rows
from schema import EnforcementPoint, classify_types, make_id

SOURCE_URL = "https://tra.hccp.gov.tw/pages/camera"

_TECH_HEADER = ["地點", "違規取締項目", "經度", "緯度", "備註"]
_SPEED_HEADER = ["地點", "速限", "經度", "緯度", "備註"]


def build_points(
    rows: list[dict[str, str]], type_field: str | None, source_name: str
) -> list[EnforcementPoint]:
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in rows:
        location = row.get("地點", "").strip()
        if not location:
            continue
        try:
            lng = float(row["經度"])
            lat = float(row["緯度"])
        except (KeyError, ValueError):
            continue
        if type_field:
            violation_types = classify_types(row.get(type_field, ""))
        else:
            violation_types = ["speed"]
        points.append(
            EnforcementPoint(
                id=make_id(source_name, location),
                county="新竹市",
                district="",
                address=location,
                lat=lat,
                lng=lng,
                violation_types=violation_types,
                source_name=source_name,
                source_url=SOURCE_URL,
                data_quality="coords",
                fetched_at=now,
            )
        )
    return points


def fetch() -> list[EnforcementPoint]:
    tech_rows = fetch_html_table_rows(SOURCE_URL, expected_header=_TECH_HEADER, verify_ssl=False)
    # 「固定式」跟「移動式」測速兩個表格的表頭完全一樣（都是 _SPEED_HEADER），
    # fetch_html_table_rows 是靠比對表頭字串找表格，沒辦法區分兩個表頭相同的表格，
    # 呼叫兩次只會兩次都拿到「固定式+移動式合併」的同一份結果——不能這樣寫，
    # 那樣每個點都會被算兩次、而且來源標籤還會分錯。正確做法：只呼叫一次拿到全部
    # 測速列，再用每一列本來就有的「備註」欄位（值是"固定式"或"移動式"）分開。
    speed_rows = fetch_html_table_rows(SOURCE_URL, expected_header=_SPEED_HEADER, verify_ssl=False)
    fixed_speed_rows = [r for r in speed_rows if r.get("備註") == "固定式"]
    mobile_speed_rows = [r for r in speed_rows if r.get("備註") == "移動式"]

    points = build_points(tech_rows, type_field="違規取締項目", source_name="新竹市警察局科技執法取締地點")
    points += build_points(fixed_speed_rows, type_field=None, source_name="新竹市警察局科學儀器(固定式)取締地點")
    points += build_points(mobile_speed_rows, type_field=None, source_name="新竹市警察局科學儀器(移動式)取締地點")
    return points


if __name__ == "__main__":
    result = fetch()
    print(f"hsinchu: {len(result)} 筆")
