import json
import os
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import geocode as geocode_module


def test_geocode_uses_cache_without_network_call():
    cache = {"台南市北門路": [23.0, 120.2]}
    with patch("geocode.urllib.request.urlopen") as mock_urlopen:
        result = geocode_module.geocode("台南市北門路", cache)
    mock_urlopen.assert_not_called()
    assert result == (23.0, 120.2)


def test_geocode_calls_nominatim_and_caches_result():
    cache: dict = {}
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(
        [{"lat": "22.9998", "lon": "120.2027"}]
    ).encode("utf-8")
    fake_response.__enter__.return_value = fake_response

    with patch("geocode.urllib.request.urlopen", return_value=fake_response) as mock_urlopen, \
         patch("geocode.time.sleep") as mock_sleep:
        result = geocode_module.geocode("台南市中西區某路", cache)

    mock_urlopen.assert_called_once()
    mock_sleep.assert_called_once_with(1)
    assert result == (22.9998, 120.2027)
    assert cache["台南市中西區某路"] == [22.9998, 120.2027]


def test_geocode_no_results_caches_not_found_with_timestamp():
    cache: dict = {}
    fake_response = MagicMock()
    fake_response.read.return_value = b"[]"
    fake_response.__enter__.return_value = fake_response

    with patch("geocode.urllib.request.urlopen", return_value=fake_response), \
         patch("geocode.time.sleep"):
        result = geocode_module.geocode("查不到的地址", cache)

    assert result is None
    cached = cache["查不到的地址"]
    assert cached["lat"] is None
    assert cached["lng"] is None
    assert "checked_at" in cached


def test_geocode_network_error_does_not_write_cache():
    cache: dict = {}

    with patch(
        "geocode.urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ), patch("geocode.time.sleep"):
        result = geocode_module.geocode("會逾時的地址", cache)

    assert result is None
    assert "會逾時的地址" not in cache  # 暫時性錯誤不落地，下次排程會自動重試


def test_geocode_not_found_within_cooldown_skips_network():
    recent = datetime.now(timezone.utc).isoformat()
    cache = {"最近查過查不到": {"lat": None, "lng": None, "checked_at": recent}}
    with patch("geocode.urllib.request.urlopen") as mock_urlopen:
        result = geocode_module.geocode("最近查過查不到", cache)
    mock_urlopen.assert_not_called()
    assert result is None


def test_geocode_not_found_after_cooldown_retries_network():
    expired = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    cache = {"很久以前查過查不到": {"lat": None, "lng": None, "checked_at": expired}}
    fake_response = MagicMock()
    fake_response.read.return_value = b"[]"
    fake_response.__enter__.return_value = fake_response

    with patch("geocode.urllib.request.urlopen", return_value=fake_response) as mock_urlopen, \
         patch("geocode.time.sleep"):
        result = geocode_module.geocode("很久以前查過查不到", cache)

    mock_urlopen.assert_called_once()
    assert result is None


def test_geocode_legacy_bare_null_cache_retries_network():
    cache = {"舊格式查不到": None}
    fake_response = MagicMock()
    fake_response.read.return_value = b"[]"
    fake_response.__enter__.return_value = fake_response

    with patch("geocode.urllib.request.urlopen", return_value=fake_response) as mock_urlopen, \
         patch("geocode.time.sleep"):
        result = geocode_module.geocode("舊格式查不到", cache)

    mock_urlopen.assert_called_once()  # 舊格式沒有 checked_at，視為冷卻已過期
    assert result is None


def test_load_and_save_cache_roundtrip(tmp_path):
    cache_path = tmp_path / "cache.json"
    with patch("geocode.CACHE_PATH", str(cache_path)):
        geocode_module.save_cache({"a": [1.0, 2.0]})
        loaded = geocode_module.load_cache()
    assert loaded == {"a": [1.0, 2.0]}


def test_geocode_with_fallback_stops_at_first_success():
    with patch("geocode.geocode", side_effect=[None, (25.0, 121.0)]) as mock_geocode:
        result = geocode_module.geocode_with_fallback(["查詢一", "查詢二"], {})
    assert result == (25.0, 121.0)
    assert mock_geocode.call_count == 2


def test_geocode_with_fallback_returns_first_query_result_without_trying_rest():
    with patch("geocode.geocode", side_effect=[(23.0, 120.0), (99.0, 99.0)]) as mock_geocode:
        result = geocode_module.geocode_with_fallback(["查詢一", "查詢二"], {})
    assert result == (23.0, 120.0)
    mock_geocode.assert_called_once()


def test_geocode_with_fallback_all_fail_returns_none():
    with patch("geocode.geocode", side_effect=[None, None]) as mock_geocode:
        result = geocode_module.geocode_with_fallback(["查詢一", "查詢二"], {})
    assert result is None
    assert mock_geocode.call_count == 2


def test_extract_primary_road_removes_parenthetical():
    assert geocode_module.extract_primary_road("九如三路(中都街與九如大橋中段)") == "九如三路"


def test_extract_primary_road_splits_on_intersection_marker():
    assert geocode_module.extract_primary_road("民族一路與十全一路口") == "民族一路"


def test_extract_primary_road_splits_on_dun_symbol():
    assert geocode_module.extract_primary_road("大學路、學成路口") == "大學路"


def test_extract_primary_road_strips_trailing_junction_suffix_without_split():
    assert geocode_module.extract_primary_road("大昌二路420巷口") == "大昌二路420"


def test_extract_primary_road_returns_unchanged_when_no_markers():
    assert geocode_module.extract_primary_road("同盟一路高醫大門") == "同盟一路高醫大門"


def test_resolve_with_centroid_fallback_returns_geocoded_when_first_level_succeeds():
    with patch("geocode.geocode_with_fallback", return_value=(23.0, 120.0)) as mock_fallback, \
         patch("geocode.geocode") as mock_geocode:
        coords, quality = geocode_module.resolve_with_centroid_fallback(
            "完整字串", "主要道路", "中心點", {}
        )
    mock_fallback.assert_called_once_with(["完整字串", "主要道路"], {})
    mock_geocode.assert_not_called()
    assert coords == (23.0, 120.0)
    assert quality == "geocoded"


def test_resolve_with_centroid_fallback_returns_district_centroid_when_only_centroid_succeeds():
    with patch("geocode.geocode_with_fallback", return_value=None), \
         patch("geocode.geocode", return_value=(23.0, 120.0)) as mock_geocode:
        coords, quality = geocode_module.resolve_with_centroid_fallback(
            "完整字串", "主要道路", "中心點", {}
        )
    mock_geocode.assert_called_once_with("中心點", {})
    assert coords == (23.0, 120.0)
    assert quality == "district-centroid"


def test_resolve_with_centroid_fallback_returns_no_coords_when_everything_fails():
    with patch("geocode.geocode_with_fallback", return_value=None), \
         patch("geocode.geocode", return_value=None):
        coords, quality = geocode_module.resolve_with_centroid_fallback(
            "完整字串", "主要道路", "中心點", {}
        )
    assert coords is None
    assert quality == "no-coords"
