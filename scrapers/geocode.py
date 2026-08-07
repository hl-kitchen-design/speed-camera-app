"""共用地理編碼工具，用 OpenStreetMap Nominatim 把地址文字轉成經緯度。
有本機快取（geocode_cache.json，需 commit 進 repo），同一個地址字串不會重複打 API，
且遵守 Nominatim 使用政策：每秒最多 1 次請求、附帶 User-Agent。"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

CACHE_PATH = os.path.join(os.path.dirname(__file__), "geocode_cache.json")


def load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def geocode(query: str, cache: dict) -> tuple[float, float] | None:
    if query in cache:
        cached = cache[query]
        return (cached[0], cached[1]) if cached else None

    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "tw"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "speed-camera-app-scraper/1.0"})
    time.sleep(1)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read().decode("utf-8"))
        if not results:
            lat_lng = None
        else:
            lat_lng = (float(results[0]["lat"]), float(results[0]["lon"]))
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError):
        lat_lng = None

    cache[query] = list(lat_lng) if lat_lng else None
    return lat_lng
