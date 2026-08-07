import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from taichung import parse_taichung

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "taichung_sample.csv")


def _load():
    with open(FIXTURE_PATH, encoding="utf-8-sig") as f:
        return parse_taichung(f.read())


def test_parse_taichung_count():
    assert len(_load()) == 3


def test_parse_taichung_lat_lng_are_swapped_correctly():
    points = _load()
    first = points[0]
    # 欄位名稱寫的「經度」實際是緯度數值 24.xx，要對調成正確的 lat/lng
    assert 21 < first.lat < 26
    assert 119 < first.lng < 122
    assert first.lat == 24.1875
    assert first.lng == 120.5735


def test_parse_taichung_violation_types():
    points = _load()
    parking_point = points[1]
    assert "illegal_parking" in parking_point.violation_types
    intersection_point = points[2]
    assert set(intersection_point.violation_types) == {"red_light", "cross_double_line", "illegal_turn"}


def test_parse_taichung_data_quality_is_coords():
    assert all(p.data_quality == "coords" for p in _load())
