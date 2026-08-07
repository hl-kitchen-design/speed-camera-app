import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from new_taipei import build_points

SAMPLE_ROWS = [
    {"編號": "", "設置位置": "板橋區文化路與民生路口", "取締項目": "違規停車、闖紅燈、 不停讓行人、車輛行駛人行道"},
    {"編號": "", "設置位置": "省道台2線85.8K(往南)", "取締項目": "跨越雙黃線"},
]


def test_build_points_geocodes_with_new_taipei_prefix():
    cache = {
        "新北市板橋區文化路與民生路口": [25.01, 121.46],
        "新北市省道台2線85.8K(往南)": None,
    }
    with patch("new_taipei.geocode") as mock_geocode:
        points = build_points(SAMPLE_ROWS, cache)
    mock_geocode.assert_not_called()
    assert points[0].lat == 25.01
    assert points[0].data_quality == "geocoded"
    assert points[1].lat is None
    assert points[1].data_quality == "no-coords"


def test_build_points_classifies_multiple_types_from_one_row():
    cache = {"新北市板橋區文化路與民生路口": [25.01, 121.46], "新北市省道台2線85.8K(往南)": None}
    points = build_points(SAMPLE_ROWS, cache)
    assert set(points[0].violation_types) == {"illegal_parking", "red_light", "yield_pedestrian", "restricted_lane"}
    assert points[1].violation_types == ["cross_double_line"]


def test_fetch_merges_five_sub_tables():
    with patch("new_taipei.fetch_html_table_rows", return_value=SAMPLE_ROWS[:1]) as mock_fetch, \
         patch("new_taipei.load_cache", return_value={"新北市板橋區文化路與民生路口": [25.01, 121.46]}), \
         patch("new_taipei.save_cache"):
        from new_taipei import fetch

        result = fetch()
    assert mock_fetch.call_count == 1  # 5 個子表格共用同一個表頭，一次 fetch_html_table_rows 呼叫就會抓到全部
    assert len(result) == 1
