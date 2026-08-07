import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schema import classify_types, make_id, EnforcementPoint, VALID_TYPES


def test_classify_types_red_light_and_double_line():
    assert classify_types("闖紅燈、跨越雙白線") == ["red_light", "cross_double_line"]


def test_classify_types_parking_with_parens():
    assert classify_types("違規(臨時)停車") == ["illegal_parking"]


def test_classify_types_speed_and_double_line():
    assert classify_types("超速、跨越雙白線") == ["speed", "cross_double_line"]


def test_classify_types_multi_function_intersection():
    text = "闖紅燈、跨越雙白線、不依標誌標線號誌指示行駛"
    assert classify_types(text) == ["red_light", "cross_double_line", "illegal_turn"]


def test_classify_types_no_match_returns_empty_list():
    assert classify_types("完全沒有關鍵字的文字") == []


def test_make_id_is_deterministic():
    id1 = make_id("national", "台北市信義路")
    id2 = make_id("national", "台北市信義路")
    assert id1 == id2
    assert len(id1) == 12


def test_make_id_differs_by_source():
    assert make_id("national", "同一個地址") != make_id("taichung", "同一個地址")


def test_enforcement_point_to_dict():
    point = EnforcementPoint(
        id="abc123",
        county="台北市",
        district="信義區",
        address="信義路五段",
        lat=25.03,
        lng=121.56,
        violation_types=["speed"],
        source_name="測試來源",
        source_url="https://example.com",
        data_quality="coords",
        fetched_at="2026-08-07T00:00:00Z",
    )
    d = point.to_dict()
    assert d["id"] == "abc123"
    assert d["violation_types"] == ["speed"]


def test_valid_types_covers_speed_and_red_light():
    assert "speed" in VALID_TYPES
    assert "red_light" in VALID_TYPES
