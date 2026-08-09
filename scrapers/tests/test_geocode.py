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
