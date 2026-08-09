# Phase 2A C1 地理編碼修復 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓高雄市、新北市、臺南市共 410 筆（目前因地理編碼幾乎全滅而在地圖上不可見的真實資料）恢復可見，靠查詢字串三級回退與正確的快取重試邏輯，不整合新的 geocoding provider。

**Architecture:** `geocode.py` 新增三個共用工具：`geocode_with_fallback()`（依序嘗試多個查詢字串）、`extract_primary_road()`（從路口交叉描述擷取主要道路名）、`resolve_with_centroid_fallback()`（把「完整字串→主要道路名→縣市/行政區中心點」三級回退跟 `data_quality` 判定整個包起來，三個 scraper 共用同一份邏輯，不各自重複）。並重寫 `geocode()` 的快取 schema 以區分「暫時性錯誤」（不落地、下次自動重試）與「確定查無結果」（存 30 天冷卻期）。三個受影響的 scraper（`kaohsiung.py`、`tainan.py`、`new_taipei.py`）改成只負責組出三段查詢字串再交給 `resolve_with_centroid_fallback()`，高雄額外修復查詢字串重複行政區名的 bug。

**Tech Stack:** Python 3.12、pytest、`urllib`（不換套件）、TypeScript（App 端型別更新）。

## Global Constraints

- 不整合內政部 TGOS API（設計文件第 2 節已確認 TGOS 同樣不支援路口查詢，邊際效益不足）
- 確定查無結果的快取冷卻期固定 30 天（`NOT_FOUND_COOLDOWN_DAYS = 30`）
- Nominatim 呼叫頻率限制維持每秒最多 1 次（現有 `time.sleep(1)` 不變）
- 新的 `data_quality` 值固定字串 `"district-centroid"`（縣市/行政區中心點回退）
- 三個 scraper 的「三級回退 + quality 判定」邏輯必須共用同一個 `geocode.py` 裡的函式（`resolve_with_centroid_fallback`），不得各自重複實作同一段 if/else
- 範圍不含：C2（地圖 2168 點無過濾渲染）、I1-I5、9 個 Minor 項目、Task 14 Step 6 手機實機驗證——這些留在 ledger PARKED 區塊，不在本計畫處理
- 所有變更都在 master 分支直接開發（這個 repo 的既有慣例，不開 worktree/PR）

---

## Task 1: geocode.py 快取 schema — 分離暫時性錯誤與確定查無結果

**Files:**
- Modify: `scrapers/geocode.py`
- Test: `scrapers/tests/test_geocode.py`

**Interfaces:**
- Produces: `geocode(query: str, cache: dict) -> tuple[float, float] | None`（簽章不變，行為改變：確定查無結果存 `{"lat": null, "lng": null, "checked_at": "<ISO8601>"}` 並有 30 天冷卻；暫時性錯誤不寫入快取；舊格式 bare `null` 視為冷卻已過期）
- Produces: 模組常數 `NOT_FOUND_COOLDOWN_DAYS = 30`

- [ ] **Step 1: 改寫 `test_geocode.py`，替換兩個舊行為測試、新增冷卻與舊格式相容測試**

把整份 `scrapers/tests/test_geocode.py` 換成：

```python
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
```

- [ ] **Step 2: 執行測試，確認新增/改寫的測試會失敗**

Run: `cd scrapers && python -m pytest tests/test_geocode.py -v`
Expected: `test_geocode_no_results_caches_not_found_with_timestamp`、`test_geocode_network_error_does_not_write_cache`、`test_geocode_not_found_within_cooldown_skips_network`、`test_geocode_not_found_after_cooldown_retries_network`、`test_geocode_legacy_bare_null_cache_retries_network` 這 5 個 FAIL（其餘沿用的測試應該還是 PASS，因為 `geocode()` 還沒改）

- [ ] **Step 3: 改寫 `geocode.py` 的快取 schema**

把 `scrapers/geocode.py` 換成：

```python
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
```

（這一步先不加 `geocode_with_fallback`、`extract_primary_road`、`resolve_with_centroid_fallback`，那是 Task 2）

- [ ] **Step 4: 執行測試，確認全部通過**

Run: `cd scrapers && python -m pytest tests/test_geocode.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
cd scrapers && git add geocode.py tests/test_geocode.py
git commit -m "fix: geocode 快取分離暫時性錯誤與確定查無結果，避免CI網路不穩永久毒化地址

暫時性錯誤（逾時/連線失敗）不再寫入快取，下次排程自動重試；
確定查無結果（API回應0筆）存30天冷卻期；舊格式bare null視為冷卻已過期。"
```

---

## Task 2: geocode.py 新增查詢降級工具與共用回退函式

**Files:**
- Modify: `scrapers/geocode.py`
- Test: `scrapers/tests/test_geocode.py`

**Interfaces:**
- Consumes: `geocode(query: str, cache: dict) -> tuple[float, float] | None`（Task 1 產出）
- Produces: `geocode_with_fallback(queries: list[str], cache: dict) -> tuple[float, float] | None`
- Produces: `extract_primary_road(text: str) -> str`
- Produces: `resolve_with_centroid_fallback(full_query: str, primary_query: str, centroid_query: str, cache: dict) -> tuple[tuple[float, float] | None, str]`——回傳 `(座標或None, data_quality字串)`，`data_quality` 是 `"geocoded"` / `"district-centroid"` / `"no-coords"` 三選一。三個 scraper（Task 3/4/5）唯一該呼叫的進入點，取代各自重複「試 fallback → 查中心點 → 組 quality」的 if/else。

- [ ] **Step 1: 在 `test_geocode.py` 追加三個新函式的測試**

在檔案最後追加：

```python


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
```

- [ ] **Step 2: 執行測試，確認新測試會失敗**

Run: `cd scrapers && python -m pytest tests/test_geocode.py -v`
Expected: 上面 11 個新測試 FAIL，錯誤是 `AttributeError: module 'geocode' has no attribute 'geocode_with_fallback'`（或 `extract_primary_road`、`resolve_with_centroid_fallback`）

- [ ] **Step 3: 在 `geocode.py` 加入三個新函式**

先把檔案開頭的 import 區塊加上 `import re`（跟現有的 `import json` 等排在一起，按字母順序插在 `import os` 之後）：

```python
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
```

再到 `geocode()` 函式後面（檔案最後）追加：

```python


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
```

- [ ] **Step 4: 執行測試，確認全部通過**

Run: `cd scrapers && python -m pytest tests/test_geocode.py -v`
Expected: 全部 PASS（共 18 個測試）

- [ ] **Step 5: Commit**

```bash
cd scrapers && git add geocode.py tests/test_geocode.py
git commit -m "feat: geocode 新增多級查詢回退、主要道路名擷取、三級回退共用進入點

geocode_with_fallback() 依序嘗試多個查詢字串直到成功；
extract_primary_road() 從路口交叉描述擷取主要道路名；
resolve_with_centroid_fallback() 把三級回退+quality判定包成單一進入點，
給三個scraper共用，避免各自重複實作同一段if/else。"
```

---

## Task 3: kaohsiung.py 套用三級回退並修復行政區重複 bug

**Files:**
- Modify: `scrapers/kaohsiung.py`
- Test: `scrapers/tests/test_kaohsiung.py`

**Interfaces:**
- Consumes: `extract_primary_road(text)`、`resolve_with_centroid_fallback(full_query, primary_query, centroid_query, cache)`（Task 1、2 產出，從 `geocode` 模組 import）
- Produces: `build_points(rows: list[dict[str, str]], cache: dict) -> list[EnforcementPoint]`（簽章不變，行為改變：三級回退 + 不再重複行政區名）

- [ ] **Step 1: 改寫 `test_kaohsiung.py`**

把整份 `scrapers/tests/test_kaohsiung.py` 換成：

```python
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

DUPLICATE_DISTRICT_ROWS = [
    {
        "編號": "2",
        "型式": "非線圈數位-雷射",
        "測照地點": "三民區建國二路與復興一路",
        "測照方向": "北向南",
        "速限": "50",
        "行政區": "三民",
        "測照型式": "超速",
        "地圖": "",
    }
]


def test_build_points_builds_three_level_queries_correctly():
    with patch("kaohsiung.resolve_with_centroid_fallback", return_value=((22.65, 120.31), "geocoded")) as mock_resolve:
        points = build_points(SAMPLE_ROWS, {})
    full_query, primary_query, centroid_query, cache = mock_resolve.call_args[0]
    assert full_query == "高雄市三民區民族一路與十全一路口"
    assert primary_query == "高雄市三民區民族一路"
    assert centroid_query == "高雄市三民區"
    assert points[0].lat == 22.65
    assert points[0].lng == 120.31
    assert points[0].data_quality == "geocoded"
    assert points[0].district == "三民"
    assert points[0].violation_types == ["red_light"]


def test_build_points_does_not_duplicate_district_when_location_already_has_it():
    with patch("kaohsiung.resolve_with_centroid_fallback", return_value=((22.6, 120.3), "geocoded")) as mock_resolve:
        build_points(DUPLICATE_DISTRICT_ROWS, {})
    full_query = mock_resolve.call_args[0][0]
    assert full_query == "高雄市三民區建國二路與復興一路"  # 不是「高雄市三民區三民區建國二路與復興一路」


def test_build_points_passes_through_district_centroid_quality():
    with patch("kaohsiung.resolve_with_centroid_fallback", return_value=((22.6, 120.3), "district-centroid")):
        points = build_points(SAMPLE_ROWS, {})
    assert points[0].lat == 22.6
    assert points[0].data_quality == "district-centroid"


def test_build_points_no_coords_when_resolve_fails():
    with patch("kaohsiung.resolve_with_centroid_fallback", return_value=(None, "no-coords")):
        points = build_points(SAMPLE_ROWS, {})
    assert points[0].lat is None
    assert points[0].data_quality == "no-coords"
```

- [ ] **Step 2: 執行測試，確認會失敗**

Run: `cd scrapers && python -m pytest tests/test_kaohsiung.py -v`
Expected: 全部 FAIL 或 ERROR（`build_points` 還沒改，`kaohsiung.resolve_with_centroid_fallback` 還不存在）

- [ ] **Step 3: 改寫 `kaohsiung.py`**

把整份 `scrapers/kaohsiung.py` 換成：

```python
"""高雄市政府警察局固定式違規照相科技執法設備設置地點，HTML 表格，沒有經緯度需地理編碼。
頁面：https://kcpd.kcg.gov.tw/cp.aspx?n=693052840FE00C08"""
from __future__ import annotations

from datetime import datetime, timezone

from geocode import extract_primary_road, load_cache, resolve_with_centroid_fallback, save_cache
from html_table_parser import fetch_html_table_rows
from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "高雄市政府警察局固定式違規照相科技執法設備設置地點"
SOURCE_URL = "https://kcpd.kcg.gov.tw/cp.aspx?n=693052840FE00C08"
_HEADER = ["編號", "型式", "測照地點", "測照方向", "速限", "行政區", "測照型式", "地圖"]


def _build_full_query(district: str, location: str) -> str:
    # 來源資料的「測照地點」欄位有時已經自帶行政區前綴（例如「三民區建國二路與復興一路」），
    # 這種情況不能再加一次「{district}區」，否則查詢字串會變成「三民區三民區...」查不到任何結果。
    # 只判斷「{district}區」這個完整前綴（不是單純 startswith(district)），
    # 避免誤判路名剛好跟行政區同名開頭的情況（例如「楠梓路」不該被當成「楠梓區」重複）。
    if location.startswith(f"{district}區"):
        return f"高雄市{location}"
    return f"高雄市{district}區{location}"


def build_points(rows: list[dict[str, str]], cache: dict) -> list[EnforcementPoint]:
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in rows:
        location = row.get("測照地點", "").strip()
        district = row.get("行政區", "").strip()
        if not location:
            continue

        full_query = _build_full_query(district, location)
        primary_query = f"高雄市{district}區{extract_primary_road(location)}"
        centroid_query = f"高雄市{district}區"
        coords, quality = resolve_with_centroid_fallback(full_query, primary_query, centroid_query, cache)
        lat, lng = (coords[0], coords[1]) if coords else (None, None)

        raw_type = row.get("測照型式", "")
        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, location),
                county="高雄市",
                district=district,
                address=location,
                lat=lat,
                lng=lng,
                violation_types=classify_types(raw_type),
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                data_quality=quality,
                fetched_at=now,
            )
        )
    return points


def fetch() -> list[EnforcementPoint]:
    rows = fetch_html_table_rows(SOURCE_URL, expected_header=_HEADER, verify_ssl=False)
    cache = load_cache()
    points = build_points(rows, cache)
    save_cache(cache)
    return points


if __name__ == "__main__":
    result = fetch()
    print(f"kaohsiung: {len(result)} 筆")
```

- [ ] **Step 4: 執行測試，確認全部通過**

Run: `cd scrapers && python -m pytest tests/test_kaohsiung.py -v`
Expected: 全部 PASS（4 個測試）

- [ ] **Step 5: Commit**

```bash
cd scrapers && git add kaohsiung.py tests/test_kaohsiung.py
git commit -m "fix: 高雄scraper改用三級查詢回退，修復查詢字串重複行政區名的bug

264筆裡189筆(72%)因「測照地點」欄位自帶行政區前綴又被程式重複加一次
（如「高雄市三民區三民區建國二路...」）導致查詢字串Nominatim完全比對不到。"
```

---

## Task 4: tainan.py 套用三級回退

**Files:**
- Modify: `scrapers/tainan.py`
- Test: `scrapers/tests/test_tainan.py`

**Interfaces:**
- Consumes: `extract_primary_road(text)`、`resolve_with_centroid_fallback(full_query, primary_query, centroid_query, cache)`（Task 1、2 產出）
- Produces: `parse_tainan(csv_text: str, cache: dict) -> list[EnforcementPoint]`（簽章不變，行為改變：三級回退）

- [ ] **Step 1: 改寫 `test_tainan.py`**

把整份 `scrapers/tests/test_tainan.py` 換成：

```python
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tainan import parse_tainan

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "tainan_sample.csv")


def _load(cache):
    with open(FIXTURE_PATH, encoding="utf-8-sig") as f:
        return parse_tainan(f.read(), cache)


def test_parse_tainan_extracts_road_name_before_bracket():
    with patch("tainan.resolve_with_centroid_fallback", return_value=((23.0, 120.2), "geocoded")) as mock_resolve:
        points = _load({})
    full_query = mock_resolve.call_args_list[0][0][0]
    assert full_query == "台南市北門路段"
    assert points[0].address == "北門路段"
    assert points[0].lat == 23.0
    assert points[0].lng == 120.2
    assert points[0].data_quality == "geocoded"


def test_parse_tainan_builds_three_level_queries_for_intersection():
    with patch("tainan.resolve_with_centroid_fallback", return_value=((23.0, 120.2), "geocoded")) as mock_resolve:
        _load({})
    second_call_args = mock_resolve.call_args_list[1][0]
    assert second_call_args[0] == "台南市中華西路與府前路口"
    assert second_call_args[1] == "台南市中華西路"
    assert second_call_args[2] == "台南市"


def test_parse_tainan_extracts_types_from_brackets():
    with patch("tainan.resolve_with_centroid_fallback", return_value=((23.0, 120.2), "geocoded")):
        points = _load({})
    assert "illegal_parking" in points[0].violation_types
    # 括號內文字同時含「未依標誌標線行駛等」，classify_types 會依關鍵字表額外辨識出 illegal_turn
    assert set(points[1].violation_types) == {"red_light", "illegal_turn"}


def test_parse_tainan_passes_through_district_centroid_quality():
    with patch("tainan.resolve_with_centroid_fallback", return_value=((23.0, 120.2), "district-centroid")):
        points = _load({})
    assert points[0].data_quality == "district-centroid"


def test_parse_tainan_no_geocode_result_has_no_coords_quality():
    with patch("tainan.resolve_with_centroid_fallback", return_value=(None, "no-coords")):
        points = _load({})
    assert points[0].lat is None
    assert points[0].lng is None
    assert points[0].data_quality == "no-coords"
```

- [ ] **Step 2: 執行測試，確認會失敗**

Run: `cd scrapers && python -m pytest tests/test_tainan.py -v`
Expected: 全部 FAIL 或 ERROR

- [ ] **Step 3: 改寫 `tainan.py`**

把 `scrapers/tainan.py` 裡 `from geocode import geocode, load_cache, save_cache` 這行（第 14 行）換成：

```python
from geocode import extract_primary_road, load_cache, resolve_with_centroid_fallback, save_cache
```

把 `parse_tainan` 函式裡（第 38-77 行）查詢/座標判斷這段：

```python
        query = f"台南市{road_name}"
        if query in cache:
            cached = cache[query]
            coords = (cached[0], cached[1]) if cached else None
        else:
            coords = geocode(query, cache)
        if coords:
            lat, lng, quality = coords[0], coords[1], "geocoded"
        else:
            lat, lng, quality = None, None, "no-coords"
```

換成：

```python
        full_query = f"台南市{road_name}"
        primary_query = f"台南市{extract_primary_road(road_name)}"
        centroid_query = "台南市"
        coords, quality = resolve_with_centroid_fallback(full_query, primary_query, centroid_query, cache)
        lat, lng = (coords[0], coords[1]) if coords else (None, None)
```

- [ ] **Step 4: 執行測試，確認全部通過**

Run: `cd scrapers && python -m pytest tests/test_tainan.py -v`
Expected: 全部 PASS（5 個測試）

- [ ] **Step 5: Commit**

```bash
cd scrapers && git add tainan.py tests/test_tainan.py
git commit -m "fix: 台南scraper改用三級查詢回退（完整字串→主要道路名→縣市中心點）"
```

---

## Task 5: new_taipei.py 套用三級回退

**Files:**
- Modify: `scrapers/new_taipei.py`
- Test: `scrapers/tests/test_new_taipei.py`

**Interfaces:**
- Consumes: `extract_primary_road(text)`、`resolve_with_centroid_fallback(full_query, primary_query, centroid_query, cache)`（Task 1、2 產出）
- Produces: `build_points(rows: list[dict[str, str]], cache: dict) -> list[EnforcementPoint]`（簽章不變，行為改變：三級回退）

- [ ] **Step 1: 改寫 `test_new_taipei.py`**

把整份 `scrapers/tests/test_new_taipei.py` 換成：

```python
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from new_taipei import build_points

SAMPLE_ROWS = [
    {"編號": "", "設置位置": "板橋區文化路與民生路口", "取締項目": "違規停車、闖紅燈、 不停讓行人、車輛行駛人行道"},
    {"編號": "", "設置位置": "省道台2線85.8K(往南)", "取締項目": "跨越雙黃線"},
]


def test_build_points_builds_three_level_queries_correctly():
    with patch("new_taipei.resolve_with_centroid_fallback", return_value=((25.01, 121.46), "geocoded")) as mock_resolve:
        points = build_points(SAMPLE_ROWS, {})
    full_query, primary_query, centroid_query, cache = mock_resolve.call_args[0]
    assert full_query == "新北市板橋區文化路與民生路口"
    assert primary_query == "新北市板橋區文化路"
    assert centroid_query == "新北市"
    assert points[0].lat == 25.01
    assert points[0].data_quality == "geocoded"


def test_build_points_passes_through_district_centroid_quality():
    with patch("new_taipei.resolve_with_centroid_fallback", return_value=((25.0, 121.5), "district-centroid")):
        points = build_points(SAMPLE_ROWS, {})
    assert points[0].lat == 25.0
    assert points[0].data_quality == "district-centroid"


def test_build_points_no_coords_when_resolve_fails():
    with patch("new_taipei.resolve_with_centroid_fallback", return_value=(None, "no-coords")):
        points = build_points(SAMPLE_ROWS, {})
    assert points[0].lat is None
    assert points[0].data_quality == "no-coords"


def test_build_points_classifies_multiple_types_from_one_row():
    with patch("new_taipei.resolve_with_centroid_fallback", return_value=((25.01, 121.46), "geocoded")):
        points = build_points(SAMPLE_ROWS, {})
    assert set(points[0].violation_types) == {"illegal_parking", "red_light", "yield_pedestrian", "restricted_lane"}
    assert points[1].violation_types == ["cross_double_line"]


def test_fetch_merges_five_sub_tables():
    with patch("new_taipei.fetch_html_table_rows", return_value=SAMPLE_ROWS[:1]) as mock_fetch, \
         patch("new_taipei.load_cache", return_value={}), \
         patch("new_taipei.save_cache"), \
         patch("new_taipei.resolve_with_centroid_fallback", return_value=((25.01, 121.46), "geocoded")):
        from new_taipei import fetch

        result = fetch()
    assert mock_fetch.call_count == 1  # 5 個子表格共用同一個表頭，一次 fetch_html_table_rows 呼叫就會抓到全部
    assert len(result) == 1
```

- [ ] **Step 2: 執行測試，確認會失敗**

Run: `cd scrapers && python -m pytest tests/test_new_taipei.py -v`
Expected: 全部 FAIL 或 ERROR

- [ ] **Step 3: 改寫 `new_taipei.py`**

把 `scrapers/new_taipei.py` 裡 `from geocode import geocode, load_cache, save_cache` 這行（第 10 行）換成：

```python
from geocode import extract_primary_road, load_cache, resolve_with_centroid_fallback, save_cache
```

把 `build_points` 函式裡（第 19-57 行）查詢/座標判斷這段：

```python
        query = f"新北市{location}"
        # 呼叫端先查一次快取，理由跟高雄市/台南市 scraper 一樣（Task 6 review 時發現的
        # 系統性問題）：測試 patch("new_taipei.geocode") 會整個換掉函式，繞過它內部的
        # 快取檢查，所以「快取已有答案時不該呼叫 geocode()」這件事要靠呼叫端自己判斷。
        if query in cache:
            cached = cache[query]
            coords = (cached[0], cached[1]) if cached else None
        else:
            coords = geocode(query, cache)
        if coords:
            lat, lng, quality = coords[0], coords[1], "geocoded"
        else:
            lat, lng, quality = None, None, "no-coords"
```

換成：

```python
        full_query = f"新北市{location}"
        primary_query = f"新北市{extract_primary_road(location)}"
        centroid_query = "新北市"
        coords, quality = resolve_with_centroid_fallback(full_query, primary_query, centroid_query, cache)
        lat, lng = (coords[0], coords[1]) if coords else (None, None)
```

- [ ] **Step 4: 執行測試，確認全部通過**

Run: `cd scrapers && python -m pytest tests/test_new_taipei.py -v`
Expected: 全部 PASS（5 個測試）

- [ ] **Step 5: 跑全部 scraper 測試，確認沒有連帶破壞**

Run: `cd scrapers && python -m pytest -v`
Expected: 全部 PASS（原本 47 個 + 這次新增的測試）

- [ ] **Step 6: Commit**

```bash
cd scrapers && git add new_taipei.py tests/test_new_taipei.py
git commit -m "fix: 新北scraper改用三級查詢回退（完整字串→主要道路名→縣市中心點）"
```

---

## Task 6: App 端 TypeScript 型別新增 district-centroid

**Files:**
- Modify: `src/services/dataFetcher.ts:13`

**Interfaces:**
- Consumes: 無（純型別變更，不影響任何函式簽章或渲染邏輯）

- [ ] **Step 1: 更新型別定義**

把 `src/services/dataFetcher.ts` 第 13 行：

```ts
  data_quality: 'coords' | 'geocoded' | 'no-coords';
```

換成：

```ts
  data_quality: 'coords' | 'geocoded' | 'district-centroid' | 'no-coords';
```

- [ ] **Step 2: 執行 TypeScript 型別檢查**

Run: `npx tsc --noEmit`
Expected: 沒有型別錯誤（這個欄位目前沒有任何地方用 switch/if 窮舉判斷所有可能值，純粹補型別定義使其與後端實際資料一致）

- [ ] **Step 3: Commit**

```bash
git add src/services/dataFetcher.ts
git commit -m "chore: EnforcementPoint型別補上district-centroid，跟後端新的資料品質分級對齊"
```

---

## Task 7: 全套驗收 — 單元測試 + 真實資料座標覆蓋率驗證

**Files:** 無新增/修改檔案，純驗證步驟。

**Interfaces:** 無

- [ ] **Step 1: 跑全部 Python 測試**

Run: `cd scrapers && python -m pytest -v`
Expected: 全部 PASS

- [ ] **Step 2: 跑 TypeScript 型別檢查**

Run: `npx tsc --noEmit`
Expected: 無錯誤

- [ ] **Step 3: 確認目前分支狀態，準備手動觸發 CI**

Run: `git status && git log --oneline -8`
Expected: 工作目錄乾淨（Task 1-6 都已個別 commit），確認最新 6 個 commit 都在

- [ ] **Step 4: 手動觸發 GitHub Actions scrape workflow**

Run: `gh workflow run scrape-data.yml`
Expected: 觸發成功（這次執行會用新的三級回退邏輯重新查詢所有目前 `geocode_cache.json` 裡沒有 list 格式成功結果的地址，包含所有舊格式 bare-null 跟新格式已過冷卻的 dict null——預期會比平常這次跑得久，因為很多地址第一次要嘗試到第二、三級才成功或才確定失敗）

- [ ] **Step 5: 等待 workflow 執行完成**

Run: `gh run watch $(gh run list --workflow=scrape-data.yml --limit=1 --json databaseId --jq '.[0].databaseId')`
Expected: 執行成功（綠色），耗時可能超過 Phase 2A 記錄的 11m50s（因為新增了查詢降級的重試次數）

- [ ] **Step 6: 比對修復前後的座標覆蓋率**

Run:
```bash
curl -s https://hl-kitchen-design.github.io/speed-camera-app/version.json
curl -s https://hl-kitchen-design.github.io/speed-camera-app/points.json | python -c "
import json, sys
points = json.load(sys.stdin)
by_source = {}
for p in points:
    key = p['source_name']
    by_source.setdefault(key, [0, 0])
    by_source[key][0] += 1
    if p.get('lat') is not None:
        by_source[key][1] += 1
for k, (total, has_coords) in by_source.items():
    print(f'{k}: {has_coords}/{total}')
"
```
Expected: 高雄市政府警察局固定式違規照相科技執法設備設置地點、臺南市智慧管理科技執法設備設置地點、新北市固定式科學儀器執法設備設置地點 這三個來源的 `has_coords/total` 比例應該遠高於修復前的 5/264、8/72、7/94——這是唯一能驗證「真的解決問題」而非只是「程式碼邏輯自洽」的方式，記錄實際數字回報給使用者

- [ ] **Step 7: 更新 ledger，標記 C1 已完成**

在 `.superpowers/sdd/2026-08-07-phase2a-real-enforcement-data/progress.md` 檔案最後追加一段（不要改動既有內容）：

```markdown

## C1 修復完成（2026-08-09）

見 `docs/superpowers/specs/2026-08-09-geocoding-fix-design.md` 與
`docs/superpowers/plans/2026-08-09-geocoding-fix.md`。查詢字串三級回退
+ 快取schema分離暫時性錯誤與確定查無結果 + 修復高雄重複行政區名bug。
座標覆蓋率驗證結果：把 Step 6 實際跑出來的數字貼在這裡，不要留空。

C2（地圖2168點無過濾渲染）跟 I1-I5、9個Minor、Task 14 Step 6 仍未處理。
```

Run: `git add .superpowers/sdd/2026-08-07-phase2a-real-enforcement-data/progress.md && git commit -m "docs: 更新ledger標記C1地理編碼問題已修復"`

---

## Self-Review 紀錄

- **Spec 覆蓋**：第 3.1 節（快取 schema）→ Task 1；第 3.2 節（三級回退 + extract_primary_road）→ Task 2-5；第 3.3 節（App 型別）→ Task 6；第 4 節（測試計畫）→ 每個 Task 內含 + Task 7 驗收；第 5 節範圍邊界 → Global Constraints 已列出不做的項目。
- **Placeholder 掃描**：無 TBD/TODO，每個程式碼步驟都是可直接執行的完整內容。
- **型別一致性**：`geocode_with_fallback(queries: list[str], cache: dict) -> tuple[float, float] | None`、`extract_primary_road(text: str) -> str`、`resolve_with_centroid_fallback(full_query, primary_query, centroid_query, cache) -> tuple[tuple[float, float] | None, str]` 的簽章在 Task 2 定義後，Task 3/4/5 全部一致引用，沒有改名或參數順序不一致的狀況。
- **DRY 修正**：原本 Task 3/4/5 會各自重複實作「試 fallback → 查中心點 → 組 quality」同一段 if/else，執行前重新檢視時發現這會被 code review 判定為重複邏輯，已收斂成 Task 2 的 `resolve_with_centroid_fallback()` 共用函式，三個 scraper 現在只負責組查詢字串。
- **邊界情況修正**：高雄行政區重複判斷原本用 `location.startswith(district) or location.startswith(f"{district}區")`，後者的裸 `startswith(district)` 條件在路名剛好跟行政區同名開頭時（例如「楠梓路」對上「楠梓區」）會誤判成重複而漏加前綴，已收斂成只用 `location.startswith(f"{district}區")` 這個精確條件（同步修正了設計文件）。
