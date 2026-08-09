import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kaohsiung import build_points

SAMPLE_ROWS = [
    {
        "編號": "1",
        "型式": "非線圈數位-雷射",
        "測照地點": "民族一路與十全一路口",
        "測照方向": "北向南",
        "速限": "60",
        "行政區": "三民",
        "測照型式": "闖紅燈",
        "地圖": "",
    }
]

DUPLICATE_DISTRICT_ROWS = [
    {
        "編號": "2",
        "型式": "非線圈數位-雷射",
        "測照地點": "三民區建國二路與復興一路",
        "測照方向": "北向南",
        "速限": "50",
        "行政區": "三民",
        "測照型式": "超速",
        "地圖": "",
    }
]


def test_build_points_builds_three_level_queries_correctly():
    with patch("kaohsiung.resolve_with_centroid_fallback", return_value=((22.65, 120.31), "geocoded")) as mock_resolve:
        points = build_points(SAMPLE_ROWS, {})
    full_query, primary_query, centroid_query, cache = mock_resolve.call_args[0]
    assert full_query == "高雄市三民區民族一路與十全一路口"
    assert primary_query == "高雄市三民區民族一路"
    assert centroid_query == "高雄市三民區"
    assert points[0].lat == 22.65
    assert points[0].lng == 120.31
    assert points[0].data_quality == "geocoded"
    assert points[0].district == "三民"
    assert points[0].violation_types == ["red_light"]


def test_build_points_does_not_duplicate_district_when_location_already_has_it():
    with patch("kaohsiung.resolve_with_centroid_fallback", return_value=((22.6, 120.3), "geocoded")) as mock_resolve:
        build_points(DUPLICATE_DISTRICT_ROWS, {})
    full_query, primary_query, centroid_query, cache = mock_resolve.call_args[0]
    assert full_query == "高雄市三民區建國二路與復興一路"  # 不是「高雄市三民區三民區建國二路與復興一路」
    assert primary_query == "高雄市三民區建國二路"  # 主要道路名也不能重複行政區名


def test_build_points_passes_through_district_centroid_quality():
    with patch("kaohsiung.resolve_with_centroid_fallback", return_value=((22.6, 120.3), "district-centroid")):
        points = build_points(SAMPLE_ROWS, {})
    assert points[0].lat == 22.6
    assert points[0].data_quality == "district-centroid"


def test_build_points_no_coords_when_resolve_fails():
    with patch("kaohsiung.resolve_with_centroid_fallback", return_value=(None, "no-coords")):
        points = build_points(SAMPLE_ROWS, {})
    assert points[0].lat is None
    assert points[0].data_quality == "no-coords"
