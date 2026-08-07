import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hsinchu import build_points

TECH_ENFORCEMENT_ROWS = [
    {
        "地點": "新竹市北區經國路二段、中正路口",
        "違規取締項目": "闖紅燈、違規轉彎、未停讓行人、砂石車禁行車種、違規停車",
        "經度": "120.964470",
        "緯度": "24.811973",
        "備註": "科技執法",
    }
]

SPEED_ROWS = [
    {
        "地點": "新竹市北區西濱路、東大路四段口(北上)",
        "速限": "60",
        "經度": "120.934122",
        "緯度": "24.842299",
        "備註": "固定式",
    },
    {
        "地點": "新竹市北區竹光路竹光國中（往北）",
        "速限": "50",
        "經度": "120.954317",
        "緯度": "24.808516",
        "備註": "移動式",
    },
]


def test_build_points_from_tech_enforcement_table():
    points = build_points(TECH_ENFORCEMENT_ROWS, type_field="違規取締項目", source_name="新竹市警察局科技執法取締地點")
    assert len(points) == 1
    assert points[0].lng == 120.964470
    assert points[0].lat == 24.811973
    assert "red_light" in points[0].violation_types
    assert "illegal_parking" in points[0].violation_types
    assert points[0].data_quality == "coords"


def test_build_points_from_fixed_speed_table_defaults_to_speed_type():
    points = build_points([SPEED_ROWS[0]], type_field=None, source_name="新竹市警察局科學儀器(固定式)取締地點")
    assert points[0].violation_types == ["speed"]


def test_fetch_splits_speed_rows_by_remark_column():
    with patch("hsinchu.fetch_html_table_rows") as mock_fetch:
        mock_fetch.side_effect = [TECH_ENFORCEMENT_ROWS, SPEED_ROWS]
        from hsinchu import fetch

        result = fetch()
    # 固定式/移動式兩個表格表頭完全一樣，fetch_html_table_rows 沒辦法從表頭區分，
    # 所以測速表只會被呼叫「一次」（拿回固定式+移動式合併的列），不是分開呼叫兩次，
    # 靠每一列本來就有的「備註」欄位值（"固定式"/"移動式"）在 hsinchu.py 裡自己切開。
    assert mock_fetch.call_count == 2
    assert len(result) == 3  # 1 科技執法 + 1 固定式 + 1 移動式
    fixed = [p for p in result if p.source_name == "新竹市警察局科學儀器(固定式)取締地點"]
    mobile = [p for p in result if p.source_name == "新竹市警察局科學儀器(移動式)取締地點"]
    assert len(fixed) == 1
    assert len(mobile) == 1
