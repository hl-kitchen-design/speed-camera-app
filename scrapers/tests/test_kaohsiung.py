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


def test_build_points_geocodes_with_district_prefix():
    cache = {"高雄市三民區民族一路與十全一路口": [22.65, 120.31]}
    with patch("kaohsiung.geocode") as mock_geocode:
        points = build_points(SAMPLE_ROWS, cache)
    mock_geocode.assert_not_called()  # 已在快取裡
    assert points[0].lat == 22.65
    assert points[0].lng == 120.31
    assert points[0].data_quality == "geocoded"
    assert points[0].district == "三民"
    assert points[0].violation_types == ["red_light"]
