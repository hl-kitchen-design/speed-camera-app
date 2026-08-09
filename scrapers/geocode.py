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
import re
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


def geocode_with_fallback(queries: list[str], cache: dict) -> tuple[float, float] | None:
    """依序嘗試查詢字串清單，任一個成功就停止並回傳該筆座標；全部失敗回傳 None。
    快取判斷（含冷卻重試）完全交給 geocode() 處理，這裡不重複快取邏輯。"""
    for query in queries:
        coords = geocode(query, cache)
        if coords:
            return coords
    return None


_PAREN_RE = re.compile(r"\([^)]*\)")
_INTERSECTION_SPLIT_RE = re.compile(r"[與、]")
_TRAILING_JUNCTION_RE = re.compile(r"(路口|巷口)$")


def extract_primary_road(text: str) -> str:
    """從路口交叉描述擷取第一條路的名稱，作為地理編碼查詢降級用（完整路口字串查不到時，
    改查單一道路名，Nominatim 對單一道路名的比對成功率遠高於台灣路口交叉寫法）。
    不保證處理每一種寫法（例如帶巷弄門牌號的「420巷口」精簡後可能仍不夠準確）——
    這只是三級回退的第二級，查不到會自然落到第三級（縣市/行政區中心點），不是最終保底。"""
    without_paren = _PAREN_RE.sub("", text)
    primary = _INTERSECTION_SPLIT_RE.split(without_paren)[0]
    primary = _TRAILING_JUNCTION_RE.sub("", primary)
    return primary.strip()


def resolve_with_centroid_fallback(
    full_query: str, primary_query: str, centroid_query: str, cache: dict
) -> tuple[tuple[float, float] | None, str]:
    """三級查詢回退的共用進入點：完整字串→主要道路名→縣市/行政區中心點，
    回傳 (座標或None, data_quality)。kaohsiung.py/tainan.py/new_taipei.py 三個
    scraper 共用同一份邏輯，各自只需要組出三段查詢字串。"""
    coords = geocode_with_fallback([full_query, primary_query], cache)
    if coords:
        return coords, "geocoded"
    coords = geocode(centroid_query, cache)
    if coords:
        return coords, "district-centroid"
    return None, "no-coords"
