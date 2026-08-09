import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tainan import parse_tainan

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "tainan_sample.csv")


def _load(cache):
    with open(FIXTURE_PATH, encoding="utf-8-sig") as f:
        return parse_tainan(f.read(), cache)


def test_parse_tainan_extracts_road_name_before_bracket():
    with patch("tainan.resolve_with_centroid_fallback", return_value=((23.0, 120.2), "geocoded")) as mock_resolve:
        points = _load({})
    full_query = mock_resolve.call_args_list[0][0][0]
    assert full_query == "台南市北門路段"
    assert points[0].address == "北門路段"
    assert points[0].lat == 23.0
    assert points[0].lng == 120.2
    assert points[0].data_quality == "geocoded"


def test_parse_tainan_builds_three_level_queries_for_intersection():
    with patch("tainan.resolve_with_centroid_fallback", return_value=((23.0, 120.2), "geocoded")) as mock_resolve:
        _load({})
    second_call_args = mock_resolve.call_args_list[1][0]
    assert second_call_args[0] == "台南市中華西路與府前路口"
    assert second_call_args[1] == "台南市中華西路"
    assert second_call_args[2] == "台南市"


def test_parse_tainan_extracts_types_from_brackets():
    with patch("tainan.resolve_with_centroid_fallback", return_value=((23.0, 120.2), "geocoded")):
        points = _load({})
    assert "illegal_parking" in points[0].violation_types
    # 括號內文字同時含「未依標誌標線行駛等」，classify_types 會依關鍵字表額外辨識出 illegal_turn
    assert set(points[1].violation_types) == {"red_light", "illegal_turn"}


def test_parse_tainan_passes_through_district_centroid_quality():
    with patch("tainan.resolve_with_centroid_fallback", return_value=((23.0, 120.2), "district-centroid")):
        points = _load({})
    assert points[0].data_quality == "district-centroid"


def test_parse_tainan_no_geocode_result_has_no_coords_quality():
    with patch("tainan.resolve_with_centroid_fallback", return_value=(None, "no-coords")):
        points = _load({})
    assert points[0].lat is None
    assert points[0].lng is None
    assert points[0].data_quality == "no-coords"
