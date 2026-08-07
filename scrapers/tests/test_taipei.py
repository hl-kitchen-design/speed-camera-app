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
    rows = _load()
    # Multiline field (啟用日期) sits between address and violation_types in the CSV.
    # A naive line-splitting parser would break the row count (not 2) and would
    # mangle 取締項目 (the field after the multiline column) — asserting on those
    # two things, not just address, is what actually proves multiline handling.
    assert len(rows) == 2
    first = rows[0]
    assert first.address == "自強隧道"
    assert set(first.violation_types) == {"speed", "cross_double_line"}


def test_parse_taipei_violation_types():
    first = _load()[0]
    assert set(first.violation_types) == {"speed", "cross_double_line"}
