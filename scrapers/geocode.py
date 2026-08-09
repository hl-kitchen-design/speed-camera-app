"""共用地理編碼工具，用 OpenStreetMap Nominatim 把地址文字轉成經緯度。
有本機快取（geocode_cache.json，需 commit 進 repo），同一個地址字串不會重複打 API，
且遵守 Nominatim 使用政策：每秒最多 1 次請求、附帶 User-Agent。

快取值有三種格式：
- 成功：[lat, lng]
- 確定查無結果（API 回應正常但 0 筆）：{"lat": null, "lng": null, "checked_at": "<ISO 8601>"}，
  超過 NOT_FOUND_COOLDOWN_DAYS 天會重新嘗試一次
- 連線逾時/例外：不會寫入快取，下次呼叫一定會重新嘗試，不需要額外的重試計數
- 舊格式 bare null（沒有 checked_at）：視為冷卻已過期，下次查詢會重新嘗試
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

CACHE_PATH = os.path.join(os.path.dirname(__file__), "geocode_cache.json")
NOT_FOUND_COOLDOWN_DAYS = 30


def load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)


def _not_found_expired(cached: dict) -> bool:
    checked_at = datetime.fromisoformat(cached["checked_at"])
    return datetime.now(timezone.utc) - checked_at > timedelta(days=NOT_FOUND_COOLDOWN_DAYS)


def geocode(query: str, cache: dict) -> tuple[float, float] | None:
    if query in cache:
        cached = cache[query]
        if isinstance(cached, list):
            return (cached[0], cached[1])
        if isinstance(cached, dict) and not _not_found_expired(cached):
            return None
        # 沒有快取、快取是舊格式 bare null、或確定查無結果已過冷卻期：往下重新查詢

    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 1, "countrycodes": "tw"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "speed-camera-app-scraper/1.0"})
    time.sleep(1)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read().decode("utf-8"))
        lat_lng = (float(results[0]["lat"]), float(results[0]["lon"])) if results else None
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError):
        # 暫時性錯誤（連線/逾時/回應格式異常）：不寫入快取，下次排程會自動重試
        return None

    if lat_lng:
        cache[query] = list(lat_lng)
    else:
        cache[query] = {"lat": None, "lng": None, "checked_at": datetime.now(timezone.utc).isoformat()}
    return lat_lng
