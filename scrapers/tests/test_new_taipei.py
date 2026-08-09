import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from new_taipei import build_points

SAMPLE_ROWS = [
    {"編號": "", "設置位置": "板橋區文化路與民生路口", "取締項目": "違規停車、闖紅燈、 不停讓行人、車輛行駛人行道"},
    {"編號": "", "設置位置": "省道台2線85.8K(往南)", "取締項目": "跨越雙黃線"},
]


def test_build_points_builds_three_level_queries_correctly():
    with patch("new_taipei.resolve_with_centroid_fallback", return_value=((25.01, 121.46), "geocoded")) as mock_resolve:
        points = build_points(SAMPLE_ROWS, {})
    full_query, primary_query, centroid_query, cache = mock_resolve.call_args_list[0][0]
    assert full_query == "新北市板橋區文化路與民生路口"
    assert primary_query == "新北市板橋區文化路"
    assert centroid_query == "新北市"
    assert points[0].lat == 25.01
    assert points[0].data_quality == "geocoded"


def test_build_points_passes_through_district_centroid_quality():
    with patch("new_taipei.resolve_with_centroid_fallback", return_value=((25.0, 121.5), "district-centroid")):
        points = build_points(SAMPLE_ROWS, {})
    assert points[0].lat == 25.0
    assert points[0].data_quality == "district-centroid"


def test_build_points_no_coords_when_resolve_fails():
    with patch("new_taipei.resolve_with_centroid_fallback", return_value=(None, "no-coords")):
        points = build_points(SAMPLE_ROWS, {})
    assert points[0].lat is None
    assert points[0].data_quality == "no-coords"


def test_build_points_classifies_multiple_types_from_one_row():
    with patch("new_taipei.resolve_with_centroid_fallback", return_value=((25.01, 121.46), "geocoded")):
        points = build_points(SAMPLE_ROWS, {})
    assert set(points[0].violation_types) == {"illegal_parking", "red_light", "yield_pedestrian", "restricted_lane"}
    assert points[1].violation_types == ["cross_double_line"]


def test_fetch_merges_five_sub_tables():
    with patch("new_taipei.fetch_html_table_rows", return_value=SAMPLE_ROWS[:1]) as mock_fetch, \
         patch("new_taipei.load_cache", return_value={}), \
         patch("new_taipei.save_cache"), \
         patch("new_taipei.resolve_with_centroid_fallback", return_value=((25.01, 121.46), "geocoded")):
        from new_taipei import fetch

        result = fetch()
    assert mock_fetch.call_count == 1  # 5 個子表格共用同一個表頭，一次 fetch_html_table_rows 呼叫就會抓到全部
    assert len(result) == 1
