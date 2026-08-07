import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from national_speed import parse_national_speed

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "national_speed_sample.csv")


def test_parse_national_speed_skips_two_header_rows():
    with open(FIXTURE_PATH, encoding="utf-8-sig") as f:
        csv_text = f.read()
    points = parse_national_speed(csv_text)
    assert len(points) == 3


def test_parse_national_speed_fields():
    with open(FIXTURE_PATH, encoding="utf-8-sig") as f:
        csv_text = f.read()
    points = parse_national_speed(csv_text)
    first = points[0]
    assert first.county == "金門縣"
    assert first.district == "金湖鎮"
    assert first.lat == 24.458809
    assert first.lng == 118.43147
    assert first.violation_types == ["speed"]
    assert first.data_quality == "coords"
    assert first.source_name == "警政署測速執法設置點"
