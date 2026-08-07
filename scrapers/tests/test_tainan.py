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
    cache = {"台南市北門路段": [23.0, 120.2], "台南市中華西路與府前路口": [24.0, 121.0]}
    with patch("tainan.geocode") as mock_geocode:
        points = _load(cache)
    mock_geocode.assert_not_called()  # 已在快取裡，不應該再呼叫
    assert points[0].address == "北門路段"
    assert points[0].lat == 23.0
    assert points[0].lng == 120.2
    assert points[0].data_quality == "geocoded"


def test_parse_tainan_extracts_types_from_brackets():
    cache = {"台南市北門路段": [23.0, 120.2], "台南市中華西路與府前路口": [23.0, 120.2]}
    points = _load(cache)
    assert "illegal_parking" in points[0].violation_types
    # 括號內文字同時含「未依標誌標線行駛等」，classify_types 會依關鍵字表額外辨識出 illegal_turn
    assert set(points[1].violation_types) == {"red_light", "illegal_turn"}


def test_parse_tainan_no_geocode_result_has_no_coords_quality():
    cache = {"台南市北門路段": None, "台南市中華西路與府前路口": None}
    points = _load(cache)
    assert points[0].lat is None
    assert points[0].lng is None
    assert points[0].data_quality == "no-coords"
