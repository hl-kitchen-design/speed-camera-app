import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from publish import build_output
from schema import EnforcementPoint


def _point(pid: str) -> EnforcementPoint:
    return EnforcementPoint(
        id=pid,
        county="測試縣市",
        district="",
        address="測試地址",
        lat=25.0,
        lng=121.0,
        violation_types=["speed"],
        source_name="測試來源",
        source_url="https://example.com",
        data_quality="coords",
        fetched_at="2026-08-07T00:00:00Z",
    )


def test_build_output_has_four_keys():
    output = build_output([_point("a"), _point("b")])
    assert set(output.keys()) == {"points", "parking", "sections", "version"}


def test_build_output_points_are_dicts():
    output = build_output([_point("a")])
    assert output["points"][0]["id"] == "a"


def test_build_output_parking_and_sections_are_empty():
    output = build_output([_point("a")])
    assert output["parking"] == []
    assert output["sections"] == []


def test_build_output_version_counts():
    output = build_output([_point("a"), _point("b")])
    assert output["version"]["point_count"] == 2
    assert output["version"]["parking_count"] == 0
    assert output["version"]["section_count"] == 0
    assert "data_version" in output["version"]


def test_build_output_dedupes_points_with_same_id():
    # 2026-08-07 實跑真實管線發現：高雄市/新北市網頁的原始 HTML 裡同一份表格
    # 重複出現兩次（很可能是響應式版面把「手機版/桌機版」表格都寫進同一份 HTML，
    # 只靠 CSS 隱藏其中一份，但 BeautifulSoup 不理會 CSS），導致每筆資料被抓兩次，
    # 兩次結果的 id 完全相同（make_id 是內容決定的雜湊）。build_output 要在合併時
    # 依 id 去重，只保留第一筆，不能整批原封不動塞進輸出。
    output = build_output([_point("a"), _point("a"), _point("b")])
    assert len(output["points"]) == 2
    assert output["version"]["point_count"] == 2
    assert {p["id"] for p in output["points"]} == {"a", "b"}
