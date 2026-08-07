import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from taipei import parse_taipei

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "taipei_sample.csv")


def _load():
    with open(FIXTURE_PATH, encoding="utf-8-sig") as f:
        return parse_taipei(f.read())


def test_parse_taipei_count():
    assert len(_load()) == 2


def test_parse_taipei_coords_are_already_lat_lng_no_conversion_needed():
    first = _load()[0]
    assert first.lng == 121.549309
    assert first.lat == 25.090898


def test_parse_taipei_handles_multiline_quoted_field():
    first = _load()[0]
    assert first.address == "自強隧道"


def test_parse_taipei_violation_types():
    first = _load()[0]
    assert set(first.violation_types) == {"speed", "cross_double_line"}
