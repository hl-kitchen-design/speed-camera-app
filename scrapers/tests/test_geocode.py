import json
import os
import sys
import urllib.error
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import geocode as geocode_module


def test_geocode_uses_cache_without_network_call():
    cache = {"台南市北門路": [23.0, 120.2]}
    with patch("geocode.urllib.request.urlopen") as mock_urlopen:
        result = geocode_module.geocode("台南市北門路", cache)
    mock_urlopen.assert_not_called()
    assert result == (23.0, 120.2)


def test_geocode_cached_none_returns_none_without_network_call():
    cache = {"查不到的地址": None}
    with patch("geocode.urllib.request.urlopen") as mock_urlopen:
        result = geocode_module.geocode("查不到的地址", cache)
    mock_urlopen.assert_not_called()
    assert result is None


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


def test_geocode_no_results_caches_none():
    cache: dict = {}
    fake_response = MagicMock()
    fake_response.read.return_value = b"[]"
    fake_response.__enter__.return_value = fake_response

    with patch("geocode.urllib.request.urlopen", return_value=fake_response), \
         patch("geocode.time.sleep"):
        result = geocode_module.geocode("查不到的地址", cache)

    assert result is None
    assert cache["查不到的地址"] is None


def test_geocode_network_error_caches_none_and_does_not_raise():
    cache: dict = {}

    with patch(
        "geocode.urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ), patch("geocode.time.sleep"):
        result = geocode_module.geocode("會逾時的地址", cache)

    assert result is None
    assert cache["會逾時的地址"] is None


def test_load_and_save_cache_roundtrip(tmp_path):
    cache_path = tmp_path / "cache.json"
    with patch("geocode.CACHE_PATH", str(cache_path)):
        geocode_module.save_cache({"a": [1.0, 2.0]})
        loaded = geocode_module.load_cache()
    assert loaded == {"a": [1.0, 2.0]}
