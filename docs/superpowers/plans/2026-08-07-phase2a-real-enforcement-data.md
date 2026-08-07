# Phase 2A：真實科技執法開放資料整合 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一套獨立於 App 的 Python 爬蟲管線，把 7 個真實科技執法開放資料源（全國測速 + 台中/台北/台南/新竹/高雄/新北）整合成統一格式，發布到 GitHub Pages，並讓 App 改吃這份真實資料取代現有假資料（`src/data/seed/mockPoints.ts`）。

**Architecture:** `scrapers/`（Python，獨立於 App）逐一抓取每個來源、轉成統一的 `EnforcementPoint` schema，`publish.py` 合併輸出成 `points.json`／`parking.json`（空陣列，本次無資料源支援）／`sections.json`（空陣列，本次無資料源支援）／`version.json`，commit 到 `gh-pages` 分支發布。App 端新增 `src/services/dataFetcher.ts` 定期抓這份 JSON、`src/store/dataStore.ts`（Zustand）快取進 AsyncStorage，主畫面改吃這個 store 取代 `mockPoints`。

**Tech Stack:** Python 3.12 + `requests` + `beautifulsoup4`（爬蟲，獨立 venv，不影響 App）；App 端沿用既有 Expo + TypeScript + Zustand，新增 `@react-native-async-storage/async-storage`。

## Global Constraints

- 這是 `docs/superpowers/specs/2026-08-05-speed-camera-app-design.md` 第 6 節（含 2026-08-07 補充的 6.1 資料來源分層）的實作，型別命名、檔案結構須與該文件一致。
- 資料模型只實作該文件 4.1 節的 `PointEnforcement`；4.2 `ParkingEnforcement`／4.3 `SectionSpeedZone` 這次沒有任何真實資料源支援（見已驗證的欄位清單），保留空陣列，不在這個計畫內實作對應的警報邏輯（那是規格書分階段實作順序的第 3 階段，不屬於這次「資料整合」範圍）。
- GitHub repo 已建立並推送：`https://github.com/hl-kitchen-design/speed-camera-app`。GitHub Pages 已指向 `gh-pages` 分支根目錄，base URL 為 `https://hl-kitchen-design.github.io/speed-camera-app/`（已驗證 `version.json` 可正常存取，回傳 200）。
- Nominatim 地理編碼務必遵守 1 req/秒速率限制，且務必用快取檔案避免重複查詢同一地址（`scrapers/geocode_cache.json`，需 commit 進 repo）。
- 所有爬蟲程式碼禁止在單元測試中真的發網路請求——用寫死的樣本 fixture（本計畫已從真實來源下載驗證過的樣本）。

---

### Task 1: 共用型別與違規類型辨識工具

**Files:**
- Create: `scrapers/requirements.txt`
- Create: `scrapers/schema.py`
- Test: `scrapers/tests/test_schema.py`

**Interfaces:**
- Produces: `EnforcementPoint`（dataclass，欄位：`id: str, county: str, district: str, address: str, lat: float | None, lng: float | None, violation_types: list[str], source_name: str, source_url: str, data_quality: str, fetched_at: str`，方法 `to_dict() -> dict`）
- Produces: `classify_types(text: str) -> list[str]`
- Produces: `make_id(source_name: str, address: str) -> str`
- Produces: `VALID_TYPES: set[str]`

- [ ] **Step 1: 建立 scrapers 目錄與 requirements.txt**

```
requests==2.32.3
beautifulsoup4==4.12.3
```

- [ ] **Step 2: 寫失敗測試 `scrapers/tests/test_schema.py`**

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schema import classify_types, make_id, EnforcementPoint, VALID_TYPES


def test_classify_types_red_light_and_double_line():
    assert classify_types("闖紅燈、跨越雙白線") == ["red_light", "cross_double_line"]


def test_classify_types_parking_with_parens():
    assert classify_types("違規(臨時)停車") == ["illegal_parking"]


def test_classify_types_speed_and_double_line():
    assert classify_types("超速、跨越雙白線") == ["speed", "cross_double_line"]


def test_classify_types_multi_function_intersection():
    text = "闖紅燈、跨越雙白線、不依標誌標線號誌指示行駛"
    assert classify_types(text) == ["red_light", "cross_double_line", "illegal_turn"]


def test_classify_types_no_match_returns_empty_list():
    assert classify_types("完全沒有關鍵字的文字") == []


def test_make_id_is_deterministic():
    id1 = make_id("national", "台北市信義路")
    id2 = make_id("national", "台北市信義路")
    assert id1 == id2
    assert len(id1) == 12


def test_make_id_differs_by_source():
    assert make_id("national", "同一個地址") != make_id("taichung", "同一個地址")


def test_enforcement_point_to_dict():
    point = EnforcementPoint(
        id="abc123",
        county="台北市",
        district="信義區",
        address="信義路五段",
        lat=25.03,
        lng=121.56,
        violation_types=["speed"],
        source_name="測試來源",
        source_url="https://example.com",
        data_quality="coords",
        fetched_at="2026-08-07T00:00:00Z",
    )
    d = point.to_dict()
    assert d["id"] == "abc123"
    assert d["violation_types"] == ["speed"]


def test_valid_types_covers_speed_and_red_light():
    assert "speed" in VALID_TYPES
    assert "red_light" in VALID_TYPES
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd scrapers && python -m pytest tests/test_schema.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'schema'`（`schema.py` 還沒建立）

- [ ] **Step 4: 寫 `scrapers/schema.py`**

```python
"""共用資料型別與違規類型文字辨識工具，給所有 scraper 共用。"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass

VALID_TYPES: set[str] = {
    "speed",
    "red_light",
    "yield_pedestrian",
    "illegal_turn",
    "two_stage_turn",
    "bus_lane",
    "keep_clear",
    "illegal_parking",
    "cross_double_line",
    "restricted_lane",
}

# 順序不影響比對結果（每個關鍵字獨立檢查、全部收集），
# 但關鍵字要夠具體，避免短關鍵字誤配到不相關的描述
# （例如不能只用「轉彎」去比對「轉彎車占用直行車道」）。
_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("不停讓行人", "yield_pedestrian"),
    ("未停讓行人", "yield_pedestrian"),
    ("不依規定讓", "yield_pedestrian"),
    ("紅燈右轉", "red_light"),
    ("紅燈越線", "red_light"),
    ("闖紅燈", "red_light"),
    ("違規(臨時)停車", "illegal_parking"),
    ("違規臨時停車", "illegal_parking"),
    ("違規停車", "illegal_parking"),
    ("違規上、下客", "illegal_parking"),
    ("違規攬客", "illegal_parking"),
    ("跨越雙白線", "cross_double_line"),
    ("跨越雙黃線", "cross_double_line"),
    ("行駛人行道", "restricted_lane"),
    ("禁行路段", "restricted_lane"),
    ("禁行車種", "restricted_lane"),
    ("公車專用道", "bus_lane"),
    ("兩段式左轉", "two_stage_turn"),
    ("路口淨空", "keep_clear"),
    ("違規迴轉", "illegal_turn"),
    ("未依標誌標線", "illegal_turn"),
    ("不依標誌標線", "illegal_turn"),
    ("轉彎未依規定", "illegal_turn"),
    ("違規轉彎", "illegal_turn"),
    ("超速", "speed"),
]


def classify_types(text: str) -> list[str]:
    """從中文違規描述文字辨識違規類型，回傳依原文出現順序去重的 canonical type 清單。
    關鍵字清單無法涵蓋所有縣市用語，辨識不到時回傳空清單，不會拋錯。"""
    found: list[str] = []
    for keyword, canonical in _TYPE_KEYWORDS:
        if keyword in text and canonical not in found:
            found.append(canonical)
    return found


def make_id(source_name: str, address: str) -> str:
    """用來源名稱+地址算出穩定的短 id，同一筆資料多次執行結果一致。"""
    raw = f"{source_name}|{address}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


@dataclass
class EnforcementPoint:
    id: str
    county: str
    district: str
    address: str
    lat: float | None
    lng: float | None
    violation_types: list[str]
    source_name: str
    source_url: str
    data_quality: str  # "coords" | "geocoded" | "no-coords"
    fetched_at: str

    def to_dict(self) -> dict:
        return asdict(self)
```

- [ ] **Step 5: 執行測試確認通過**

Run: `cd scrapers && python -m pytest tests/test_schema.py -v`
Expected: PASS（8 個測試全過）

- [ ] **Step 6: Commit**

```bash
git add scrapers/requirements.txt scrapers/schema.py scrapers/tests/test_schema.py
git commit -m "feat: 新增爬蟲共用型別與違規類型辨識工具"
```

---

### Task 2: 全國測速執法設置點（警政署）scraper

**Files:**
- Create: `scrapers/national_speed.py`
- Create: `scrapers/tests/fixtures/national_speed_sample.csv`
- Test: `scrapers/tests/test_national_speed.py`

**Interfaces:**
- Consumes: `EnforcementPoint`, `make_id` from `schema.py`（Task 1）
- Produces: `parse_national_speed(csv_text: str) -> list[EnforcementPoint]`
- Produces: `fetch() -> list[EnforcementPoint]`（真的打網路，App/CI 用；測試不呼叫這個）

已驗證的真實下載網址與欄位（2026-08-07 用 curl 下載驗證，1893 筆資料）：
`https://opdadm.moi.gov.tw/api/v1/no-auth/resource/api/dataset/EA5E6FCD-B82D-43B7-A5CF-E9893253187E/resource/9E196F6A-560E-4CFE-92A1-BE6EA19C8E53/download`

CSV 結構：第一列是英文欄名 `CityName,RegionName,Address,DeptNm,BranchNm,Longitude,Latitude,direct,limit`，第二列是重複的中文欄名標籤（要跳過），第三列開始才是資料。經緯度欄位標籤與實際值對應正確（不需要對調）。

- [ ] **Step 1: 建立樣本 fixture（用真實下載內容節錄前 4 筆）**

```csv
CityName,RegionName,Address,DeptNm,BranchNm,Longitude,Latitude,direct,limit
設置縣市,設置市區鄉鎮,設置地址,管轄警局,管轄分局,經度,緯度,拍攝方向,速限
金門縣,金湖鎮,金湖鎮黃海路(陽明湖路段),金門縣警察局,金湖分局,118.43147,24.458809,南北雙向,60
金門縣,金城鎮,金城鎮西海路一段(水頭路段),金門縣警察局,金城分局,118.29999,24.411718,東西雙向,50
金門縣,金城鎮,金城鎮西海路二段(金豐路口),金門縣警察局,金城分局,118.30402,24.414368,東西雙向,50
```

- [ ] **Step 2: 寫失敗測試 `scrapers/tests/test_national_speed.py`**

```python
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
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd scrapers && python -m pytest tests/test_national_speed.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'national_speed'`

- [ ] **Step 4: 寫 `scrapers/national_speed.py`**

```python
"""警政署「測速執法設置點」全國資料，唯一涵蓋全台 22 縣市的來源，只有測速類型。
資料集頁面：https://data.gov.tw/dataset/7320"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import requests

from schema import EnforcementPoint, make_id

SOURCE_NAME = "警政署測速執法設置點"
SOURCE_URL = "https://data.gov.tw/dataset/7320"
DOWNLOAD_URL = (
    "https://opdadm.moi.gov.tw/api/v1/no-auth/resource/api/dataset/"
    "EA5E6FCD-B82D-43B7-A5CF-E9893253187E/resource/"
    "9E196F6A-560E-4CFE-92A1-BE6EA19C8E53/download"
)


def parse_national_speed(csv_text: str) -> list[EnforcementPoint]:
    reader = csv.DictReader(io.StringIO(csv_text))
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in reader:
        # 第二列是重複的中文欄名標籤，用 CityName 是不是英文欄名本身來跳過
        if row.get("CityName") in (None, "", "設置縣市"):
            continue
        try:
            lat = float(row["Latitude"])
            lng = float(row["Longitude"])
        except (KeyError, ValueError):
            continue
        address = f"{row['CityName']}{row['RegionName']}{row['Address']}"
        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, address),
                county=row["CityName"],
                district=row["RegionName"],
                address=row["Address"],
                lat=lat,
                lng=lng,
                violation_types=["speed"],
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                data_quality="coords",
                fetched_at=now,
            )
        )
    return points


def fetch() -> list[EnforcementPoint]:
    resp = requests.get(DOWNLOAD_URL, timeout=30)
    resp.raise_for_status()
    return parse_national_speed(resp.content.decode("utf-8-sig"))


if __name__ == "__main__":
    result = fetch()
    print(f"national_speed: {len(result)} 筆")
```

- [ ] **Step 5: 執行測試確認通過**

Run: `cd scrapers && python -m pytest tests/test_national_speed.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scrapers/national_speed.py scrapers/tests/test_national_speed.py scrapers/tests/fixtures/national_speed_sample.csv
git commit -m "feat: 新增全國測速執法設置點 scraper"
```

---

### Task 3: 台中市開放資料 scraper（含經緯度欄位對調修正）

**Files:**
- Create: `scrapers/taichung.py`
- Create: `scrapers/tests/fixtures/taichung_sample.csv`
- Test: `scrapers/tests/test_taichung.py`

**Interfaces:**
- Consumes: `EnforcementPoint`, `make_id`, `classify_types` from `schema.py`
- Produces: `parse_taichung(csv_text: str) -> list[EnforcementPoint]`
- Produces: `fetch() -> list[EnforcementPoint]`

已驗證的真實下載網址：`https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download?rid=8fa25d05-2d40-47cb-bc6c-459c8dabf165`

**重要已知問題（2026-08-07 用 curl 下載驗證發現）：** CSV 欄名寫的是 `經度,緯度`，但實際資料是**對調的**——標示「經度」的欄位其實放的是緯度數值（約 24.x，台灣緯度範圍），標示「緯度」的欄位其實放的是經度數值（約 120.x，台灣經度範圍）。程式必須按實際數值對調，不能相信欄位名稱字面意思。

- [ ] **Step 1: 建立樣本 fixture（真實下載內容節錄）**

```csv
編號,科技執法種類,設置地點,取締項目,經度,緯度,,,
"1","區間平均速率執法","龍井區向上路6段與中興路口至沙鹿區向上路6段與自立路口","超速、未依規定行駛車道，偵測長度1,694.2公尺，速限50公里","24.1875000","120.5735000",""
"4","違規停車取締","烏日高鐵站站區一路(1樓乘客上客區、2樓乘客下客區)","違規(臨時)停車、違規上、下客、違規攬客","24.1121940","120.6163330",""
"6","路口多功能執法","西區臺灣大道與忠明南路（忠明路）口","闖紅燈、跨越雙白線、不依標誌標線號誌指示行駛","24.1571670","120.6596110",""
```

- [ ] **Step 2: 寫失敗測試 `scrapers/tests/test_taichung.py`**

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from taichung import parse_taichung

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "taichung_sample.csv")


def _load():
    with open(FIXTURE_PATH, encoding="utf-8-sig") as f:
        return parse_taichung(f.read())


def test_parse_taichung_count():
    assert len(_load()) == 3


def test_parse_taichung_lat_lng_are_swapped_correctly():
    points = _load()
    first = points[0]
    # 欄位名稱寫的「經度」實際是緯度數值 24.xx，要對調成正確的 lat/lng
    assert 21 < first.lat < 26
    assert 119 < first.lng < 122
    assert first.lat == 24.1875
    assert first.lng == 120.5735


def test_parse_taichung_violation_types():
    points = _load()
    parking_point = points[1]
    assert "illegal_parking" in parking_point.violation_types
    intersection_point = points[2]
    assert set(intersection_point.violation_types) == {"red_light", "cross_double_line", "illegal_turn"}


def test_parse_taichung_data_quality_is_coords():
    assert all(p.data_quality == "coords" for p in _load())
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd scrapers && python -m pytest tests/test_taichung.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'taichung'`

- [ ] **Step 4: 寫 `scrapers/taichung.py`**

```python
"""臺中市科技執法取締地點，有經緯度與獨立的違規類型欄位。
資料集頁面：https://data.gov.tw/dataset/170673
注意：CSV 欄名「經度/緯度」實際數值是對調的，見下方 parse_taichung 內的處理。"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import requests

from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "臺中市政府警察局科技執法取締地點"
SOURCE_URL = "https://data.gov.tw/dataset/170673"
DOWNLOAD_URL = "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download?rid=8fa25d05-2d40-47cb-bc6c-459c8dabf165"


def parse_taichung(csv_text: str) -> list[EnforcementPoint]:
    reader = csv.DictReader(io.StringIO(csv_text))
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in reader:
        location = (row.get("設置地點") or "").strip()
        if not location:
            continue
        try:
            # 欄名寫「經度」但實際是緯度數值，「緯度」欄實際是經度數值，這裡對調回正確位置
            lat = float(row["經度"])
            lng = float(row["緯度"])
        except (KeyError, ValueError):
            continue
        raw_types = row.get("取締項目") or ""
        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, location),
                county="臺中市",
                district="",
                address=location,
                lat=lat,
                lng=lng,
                violation_types=classify_types(raw_types),
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                data_quality="coords",
                fetched_at=now,
            )
        )
    return points


def fetch() -> list[EnforcementPoint]:
    resp = requests.get(DOWNLOAD_URL, timeout=30)
    resp.raise_for_status()
    return parse_taichung(resp.content.decode("utf-8-sig"))


if __name__ == "__main__":
    result = fetch()
    print(f"taichung: {len(result)} 筆")
```

- [ ] **Step 5: 執行測試確認通過**

Run: `cd scrapers && python -m pytest tests/test_taichung.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scrapers/taichung.py scrapers/tests/test_taichung.py scrapers/tests/fixtures/taichung_sample.csv
git commit -m "feat: 新增台中市科技執法 scraper，修正經緯度欄位對調問題"
```

---

### Task 4: 台北市開放資料 scraper

**Files:**
- Create: `scrapers/taipei.py`
- Create: `scrapers/tests/fixtures/taipei_sample.csv`
- Test: `scrapers/tests/test_taipei.py`

**Interfaces:**
- Consumes: `EnforcementPoint`, `make_id`, `classify_types` from `schema.py`
- Produces: `parse_taipei(csv_text: str) -> list[EnforcementPoint]`
- Produces: `fetch() -> list[EnforcementPoint]`

已驗證的真實下載網址：`https://data.taipei/api/dataset/986fa73e-c470-4ebf-9f35-3a1c9d2a8788/resource/4715904f-6ce1-41c2-8a68-3bc5303f3607/download`

**重要澄清（2026-08-07 用 curl 下載驗證）：** 欄位叫「座標-X」「座標-Y」，原本規劃以為是 TWD97 座標需要轉換，但實測數值是 121.xx／25.xx，**已經是經緯度（WGS84），不需要用 pyproj 轉換**。「啟用日期」欄位內容可能包含換行（例如「108年9月1日\n109年4月停用\n111年2月21日重啟」），CSV 是正確加引號的多行欄位，用 Python `csv`模組讀取即可正確處理，不需要特殊處理。

- [ ] **Step 1: 建立樣本 fixture（真實下載內容節錄，保留多行欄位測試 CSV 解析穩健性）**

```csv
編號,名稱,取締路段,座標-X,座標-Y,啟用日期,取締項目
1,區間平均速率,自強隧道,121.549309,25.090898,"108年9月1日
109年4月停用
111年2月21日重啟",超速、跨越雙白線
2,區間平均速率,辛亥隧道,121.555481,25.011792,109年1月1日,超速
```

- [ ] **Step 2: 寫失敗測試 `scrapers/tests/test_taipei.py`**

```python
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
    first = _load()[0]
    assert first.address == "自強隧道"


def test_parse_taipei_violation_types():
    first = _load()[0]
    assert set(first.violation_types) == {"speed", "cross_double_line"}
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd scrapers && python -m pytest tests/test_taipei.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'taipei'`

- [ ] **Step 4: 寫 `scrapers/taipei.py`**

```python
"""臺北市智慧管理科技執法設備資料表。
資料集頁面：https://data.gov.tw/dataset/135957
注意：欄位叫「座標-X/座標-Y」，但實測數值已經是經緯度（WGS84），不需要座標轉換。"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import requests

from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "臺北市智慧管理科技執法設備資料表"
SOURCE_URL = "https://data.gov.tw/dataset/135957"
DOWNLOAD_URL = (
    "https://data.taipei/api/dataset/986fa73e-c470-4ebf-9f35-3a1c9d2a8788/"
    "resource/4715904f-6ce1-41c2-8a68-3bc5303f3607/download"
)


def parse_taipei(csv_text: str) -> list[EnforcementPoint]:
    reader = csv.DictReader(io.StringIO(csv_text))
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in reader:
        location = (row.get("取締路段") or "").strip()
        if not location:
            continue
        try:
            lng = float(row["座標-X"])
            lat = float(row["座標-Y"])
        except (KeyError, ValueError):
            continue
        raw_types = row.get("取締項目") or ""
        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, location),
                county="臺北市",
                district="",
                address=location,
                lat=lat,
                lng=lng,
                violation_types=classify_types(raw_types),
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                data_quality="coords",
                fetched_at=now,
            )
        )
    return points


def fetch() -> list[EnforcementPoint]:
    resp = requests.get(DOWNLOAD_URL, timeout=30)
    resp.raise_for_status()
    return parse_taipei(resp.content.decode("utf-8-sig"))


if __name__ == "__main__":
    result = fetch()
    print(f"taipei: {len(result)} 筆")
```

- [ ] **Step 5: 執行測試確認通過**

Run: `cd scrapers && python -m pytest tests/test_taipei.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scrapers/taipei.py scrapers/tests/test_taipei.py scrapers/tests/fixtures/taipei_sample.csv
git commit -m "feat: 新增台北市科技執法 scraper"
```

---

### Task 5: 共用地理編碼工具（Nominatim + 快取）

**Files:**
- Create: `scrapers/geocode.py`
- Test: `scrapers/tests/test_geocode.py`

**Interfaces:**
- Produces: `geocode(query: str, cache: dict) -> tuple[float, float] | None`
- Produces: `load_cache() -> dict`
- Produces: `save_cache(cache: dict) -> None`
- Consumed by: Task 6（台南）、Task 7（高雄）、Task 8（新北）

- [ ] **Step 1: 寫失敗測試 `scrapers/tests/test_geocode.py`**

```python
import json
import os
import sys
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


def test_load_and_save_cache_roundtrip(tmp_path):
    cache_path = tmp_path / "cache.json"
    with patch("geocode.CACHE_PATH", str(cache_path)):
        geocode_module.save_cache({"a": [1.0, 2.0]})
        loaded = geocode_module.load_cache()
    assert loaded == {"a": [1.0, 2.0]}
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd scrapers && python -m pytest tests/test_geocode.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'geocode'`

- [ ] **Step 3: 寫 `scrapers/geocode.py`**

```python
"""共用地理編碼工具，用 OpenStreetMap Nominatim 把地址文字轉成經緯度。
有本機快取（geocode_cache.json，需 commit 進 repo），同一個地址字串不會重複打 API，
且遵守 Nominatim 使用政策：每秒最多 1 次請求、附帶 User-Agent。"""
from __future__ import annotations

import json
import os
import time
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
    with urllib.request.urlopen(req, timeout=10) as resp:
        results = json.loads(resp.read().decode("utf-8"))

    if not results:
        cache[query] = None
        return None

    lat, lng = float(results[0]["lat"]), float(results[0]["lon"])
    cache[query] = [lat, lng]
    return (lat, lng)
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd scrapers && python -m pytest tests/test_geocode.py -v`
Expected: PASS（5 個測試全過，過程中不會發出真的網路請求）

- [ ] **Step 5: 建立空的快取檔案並 Commit**

```bash
echo "{}" > scrapers/geocode_cache.json
git add scrapers/geocode.py scrapers/tests/test_geocode.py scrapers/geocode_cache.json
git commit -m "feat: 新增共用地理編碼工具（Nominatim + 快取）"
```

---

### Task 6: 台南市開放資料 scraper（地理編碼）

**Files:**
- Create: `scrapers/tainan.py`
- Create: `scrapers/tests/fixtures/tainan_sample.csv`
- Test: `scrapers/tests/test_tainan.py`

**Interfaces:**
- Consumes: `EnforcementPoint`, `make_id`, `classify_types` from `schema.py`；`geocode`, `load_cache`, `save_cache` from `geocode.py`（Task 5）
- Produces: `parse_tainan(csv_text: str, cache: dict) -> list[EnforcementPoint]`
- Produces: `fetch() -> list[EnforcementPoint]`

已驗證的真實下載網址：`https://data.tainan.gov.tw/File/DirectDownload/1c7e82f0-d6b2-4b20-aeff-5c768100f82c?fileName=x`

**已驗證的真實資料格式：** 欄位是 `轄區分局,行政區,設置位置,拍攝行向,速限`。**沒有經緯度**。`行政區` 欄位是數字代碼（例如 `67000320`），不是區名，無法直接拿來組地址，這次不使用這個欄位。違規類型寫在 `設置位置` 欄位的中文說明裡（用「【...】」包起來，例如「北門路段(火車站前圓環至青年路)自動辨識違規停車及不依標線行駛科技執法系統【違規停車、違規臨時停車、違規占用機(慢)車優先道臨時停車及行駛等】」），地理編碼查詢字串用「台南市」+「【」之前、第一個括號之前的路段文字。

- [ ] **Step 1: 建立樣本 fixture（真實下載內容節錄）**

```csv
轄區分局,行政區,設置位置,拍攝行向,速限
第一分局第二分局,67000320,北門路段(火車站前圓環至青年路)自動辨識違規停車及不依標線行駛科技執法系統【違規停車、違規臨時停車、違規占用機(慢)車優先道臨時停車及行駛等】,雙向,50
第二分局,67000370,中華西路與府前路口路口多功能違規科技執法系統【闖紅燈、紅燈右轉、紅燈越線、未依標誌標線行駛等】,北向,60
```

- [ ] **Step 2: 寫失敗測試 `scrapers/tests/test_tainan.py`**

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
    cache = {"台南市北門路段": [23.0, 120.2]}
    with patch("tainan.geocode") as mock_geocode:
        points = _load(cache)
    mock_geocode.assert_not_called()  # 已在快取裡，不應該再呼叫
    assert points[0].address == "北門路段"
    assert points[0].lat == 23.0
    assert points[0].lng == 120.2
    assert points[0].data_quality == "geocoded"


def test_parse_tainan_extracts_types_from_brackets():
    cache = {"台南市北門路段": [23.0, 120.2], "台南市中華西路與府前路口": [23.0, 120.2]}
    points = _load(cache)
    assert "illegal_parking" in points[0].violation_types
    assert set(points[1].violation_types) == {"red_light"}


def test_parse_tainan_no_geocode_result_has_no_coords_quality():
    cache = {"台南市北門路段": None, "台南市中華西路與府前路口": None}
    points = _load(cache)
    assert points[0].lat is None
    assert points[0].lng is None
    assert points[0].data_quality == "no-coords"
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd scrapers && python -m pytest tests/test_tainan.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'tainan'`

- [ ] **Step 4: 寫 `scrapers/tainan.py`**

```python
"""臺南市智慧管理科技執法設備設置地點。
資料集頁面：https://data.tainan.gov.tw/dataset/tech-enforcement-location
注意：這個來源沒有經緯度，用 geocode.py 對「設置位置」文字做地理編碼；
違規類型寫在「【...】」括號內；行政區欄位是數字代碼不是區名，不使用。"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone

import requests

from geocode import geocode, load_cache, save_cache
from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "臺南市智慧管理科技執法設備設置地點"
SOURCE_URL = "https://data.tainan.gov.tw/Resource/1c7e82f0-d6b2-4b20-aeff-5c768100f82c"
DOWNLOAD_URL = (
    "https://data.tainan.gov.tw/File/DirectDownload/1c7e82f0-d6b2-4b20-aeff-5c768100f82c"
    "?fileName=tainan"
)

_BRACKET_RE = re.compile(r"【(.+?)】")


def _extract_road_name(location_text: str) -> str:
    # 取「【」之前、第一個括號之前的文字當作路段名稱
    before_bracket = location_text.split("【")[0]
    return before_bracket.split("(")[0].strip()


def parse_tainan(csv_text: str, cache: dict) -> list[EnforcementPoint]:
    reader = csv.DictReader(io.StringIO(csv_text))
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in reader:
        location_text = (row.get("設置位置") or "").strip()
        if not location_text:
            continue

        road_name = _extract_road_name(location_text)
        bracket_match = _BRACKET_RE.search(location_text)
        raw_types = bracket_match.group(1) if bracket_match else location_text

        coords = geocode(f"台南市{road_name}", cache)
        if coords:
            lat, lng, quality = coords[0], coords[1], "geocoded"
        else:
            lat, lng, quality = None, None, "no-coords"

        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, location_text),
                county="臺南市",
                district="",
                address=road_name,
                lat=lat,
                lng=lng,
                violation_types=classify_types(raw_types),
                source_name=SOURCE_NAME,
                source_url=SOURCE_URL,
                data_quality=quality,
                fetched_at=now,
            )
        )
    return points


def fetch() -> list[EnforcementPoint]:
    resp = requests.get(DOWNLOAD_URL, timeout=30)
    resp.raise_for_status()
    cache = load_cache()
    points = parse_tainan(resp.content.decode("utf-8-sig"), cache)
    save_cache(cache)
    return points


if __name__ == "__main__":
    result = fetch()
    print(f"tainan: {len(result)} 筆")
```

- [ ] **Step 5: 執行測試確認通過**

Run: `cd scrapers && python -m pytest tests/test_tainan.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scrapers/tainan.py scrapers/tests/test_tainan.py scrapers/tests/fixtures/tainan_sample.csv
git commit -m "feat: 新增台南市科技執法 scraper（地理編碼）"
```

---

### Task 7: 通用 HTML 表格擷取器

**Files:**
- Create: `scrapers/html_table_parser.py`
- Test: `scrapers/tests/test_html_table_parser.py`

**Interfaces:**
- Produces: `fetch_html_table_rows(url: str, expected_header: list[str], verify_ssl: bool = True) -> list[dict[str, str]]`
- Consumed by: Task 8（新竹）、Task 9（高雄）、Task 10（新北）

**設計理由：** 新竹/高雄/新北三個縣市的頁面都是「表頭列＋資料列」的 HTML `<table>`，但表頭儲存格內可能混雜全形空白（例如「地　點」vs「地點」），所以比對表頭時要先把空白全部去掉再比較，不能要求逐字元完全相同。新北市頁面同一頁有 5 個子表格共用同一種表頭，所以要能合併多個表格的資料列。

- [ ] **Step 1: 寫失敗測試 `scrapers/tests/test_html_table_parser.py`**

```python
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from html_table_parser import fetch_html_table_rows

SAMPLE_HTML_SINGLE_TABLE = """
<html><body>
<table>
<tr><th>地　點</th><th>違規取締項目</th><th>經度</th><th>緯度</th></tr>
<tr><td>新竹市北區經國路二段口</td><td>闖紅燈、違規轉彎</td><td>120.964470</td><td>24.811973</td></tr>
<tr><td>新竹市東區經國路一段口</td><td>闖紅燈</td><td>120.985230</td><td>24.815077</td></tr>
</table>
</body></html>
"""

SAMPLE_HTML_MULTIPLE_TABLES_SAME_HEADER = """
<html><body>
<p>違規停車自動偵測系統設置地點</p>
<table>
<tr><td>編號</td><td>設置位置</td><td>取締項目</td></tr>
<tr><td>1</td><td>板橋區縣民大道二段7號</td><td>違規(臨時)停車</td></tr>
</table>
<p>跨越雙黃線自動偵測系統設置地點</p>
<table>
<tr><td>編號</td><td>設置位置</td><td>取締項目</td></tr>
<tr><td>1</td><td>省道台2線85.8K</td><td>跨越雙黃線</td></tr>
<tr><td>2</td><td>省道台2線87.5K</td><td>跨越雙黃線</td></tr>
</table>
</body></html>
"""


def _mock_response(html: str):
    resp = MagicMock()
    resp.text = html
    resp.raise_for_status = MagicMock()
    return resp


def test_fetch_html_table_rows_normalizes_fullwidth_space_in_header():
    with patch("html_table_parser.requests.get", return_value=_mock_response(SAMPLE_HTML_SINGLE_TABLE)):
        rows = fetch_html_table_rows(
            "https://example.com", expected_header=["地點", "違規取締項目", "經度", "緯度"]
        )
    assert len(rows) == 2
    assert rows[0]["地點"] == "新竹市北區經國路二段口"
    assert rows[0]["經度"] == "120.964470"


def test_fetch_html_table_rows_merges_multiple_tables_with_same_header():
    with patch("html_table_parser.requests.get", return_value=_mock_response(SAMPLE_HTML_MULTIPLE_TABLES_SAME_HEADER)):
        rows = fetch_html_table_rows(
            "https://example.com", expected_header=["編號", "設置位置", "取締項目"]
        )
    assert len(rows) == 3
    assert rows[0]["設置位置"] == "板橋區縣民大道二段7號"
    assert rows[2]["設置位置"] == "省道台2線87.5K"


def test_fetch_html_table_rows_passes_verify_flag_to_requests():
    with patch("html_table_parser.requests.get", return_value=_mock_response(SAMPLE_HTML_SINGLE_TABLE)) as mock_get:
        fetch_html_table_rows(
            "https://example.com",
            expected_header=["地點", "違規取締項目", "經度", "緯度"],
            verify_ssl=False,
        )
    assert mock_get.call_args.kwargs["verify"] is False
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd scrapers && python -m pytest tests/test_html_table_parser.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'html_table_parser'`

- [ ] **Step 3: 寫 `scrapers/html_table_parser.py`**

```python
"""通用 HTML 表格擷取器，給新竹/高雄/新北三個「只有網頁表格、沒有正式開放資料集」的
縣市 scraper 共用。用「表頭是否等於 expected_header（去空白後比對）」來找出資料表格，
可以合併同一頁裡多個共用表頭的子表格（例如新北市警局頁面有 5 個子表格）。"""
from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup


def _normalize(s: str) -> str:
    return re.sub(r"\s+", "", s)


def fetch_html_table_rows(
    url: str, expected_header: list[str], verify_ssl: bool = True
) -> list[dict[str, str]]:
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; speed-camera-app-scraper/1.0)"},
        timeout=20,
        verify=verify_ssl,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    normalized_header = [_normalize(h) for h in expected_header]
    rows_out: list[dict[str, str]] = []

    for table in soup.find_all("table"):
        in_data_section = False
        for row in table.find_all("tr"):
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if not cells:
                continue
            if [_normalize(c) for c in cells] == normalized_header:
                in_data_section = True
                continue
            if in_data_section and len(cells) == len(expected_header):
                rows_out.append(dict(zip(expected_header, cells)))

    return rows_out
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd scrapers && python -m pytest tests/test_html_table_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/html_table_parser.py scrapers/tests/test_html_table_parser.py
git commit -m "feat: 新增通用 HTML 表格擷取器"
```

---

### Task 8: 新竹市 scraper（HTML 表格，有經緯度）

**Files:**
- Create: `scrapers/hsinchu.py`
- Test: `scrapers/tests/test_hsinchu.py`

**Interfaces:**
- Consumes: `fetch_html_table_rows` from `html_table_parser.py`（Task 7）；`EnforcementPoint`, `make_id`, `classify_types` from `schema.py`
- Produces: `build_points(rows: list[dict[str, str]], table_default_type: str | None, source_name: str) -> list[EnforcementPoint]`
- Produces: `fetch() -> list[EnforcementPoint]`

已驗證的真實網址與表頭（2026-08-07 curl 下載驗證）：`https://tra.hccp.gov.tw/pages/camera`，同一頁有 3 個表格：
1. 表頭 `地　點,違規取締項目,經度,緯度,備註`（有獨立違規類型欄位）
2. 表頭 `地　點,速限,經度,緯度,備註`（固定式測速，無獨立類型欄位，類型固定是 `speed`）
3. 表頭 `地　點,速限,經度,緯度,備註`（移動式測速，同上）

- [ ] **Step 1: 寫失敗測試 `scrapers/tests/test_hsinchu.py`**

```python
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hsinchu import build_points

TECH_ENFORCEMENT_ROWS = [
    {
        "地點": "新竹市北區經國路二段、中正路口",
        "違規取締項目": "闖紅燈、違規轉彎、未停讓行人、砂石車禁行車種、違規停車",
        "經度": "120.964470",
        "緯度": "24.811973",
        "備註": "科技執法",
    }
]

SPEED_ROWS = [
    {
        "地點": "新竹市北區西濱路、東大路四段口(北上)",
        "速限": "60",
        "經度": "120.934122",
        "緯度": "24.842299",
        "備註": "固定式",
    }
]


def test_build_points_from_tech_enforcement_table():
    points = build_points(TECH_ENFORCEMENT_ROWS, type_field="違規取締項目", source_name="新竹市警察局科技執法取締地點")
    assert len(points) == 1
    assert points[0].lng == 120.964470
    assert points[0].lat == 24.811973
    assert "red_light" in points[0].violation_types
    assert "illegal_parking" in points[0].violation_types
    assert points[0].data_quality == "coords"


def test_build_points_from_fixed_speed_table_defaults_to_speed_type():
    points = build_points(SPEED_ROWS, type_field=None, source_name="新竹市警察局科學儀器(固定式)取締地點")
    assert points[0].violation_types == ["speed"]


def test_fetch_merges_three_tables():
    with patch("hsinchu.fetch_html_table_rows") as mock_fetch:
        mock_fetch.side_effect = [TECH_ENFORCEMENT_ROWS, SPEED_ROWS, SPEED_ROWS]
        from hsinchu import fetch

        result = fetch()
    assert len(result) == 3
    assert mock_fetch.call_count == 3
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd scrapers && python -m pytest tests/test_hsinchu.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'hsinchu'`

- [ ] **Step 3: 寫 `scrapers/hsinchu.py`**

```python
"""新竹市警察局科技執法/固定式測速/移動式測速取締地點一覽表，三個表格都有經緯度。
頁面：https://tra.hccp.gov.tw/pages/camera"""
from __future__ import annotations

from datetime import datetime, timezone

from html_table_parser import fetch_html_table_rows
from schema import EnforcementPoint, classify_types, make_id

SOURCE_URL = "https://tra.hccp.gov.tw/pages/camera"

_TECH_HEADER = ["地點", "違規取締項目", "經度", "緯度", "備註"]
_SPEED_HEADER = ["地點", "速限", "經度", "緯度", "備註"]


def build_points(
    rows: list[dict[str, str]], type_field: str | None, source_name: str
) -> list[EnforcementPoint]:
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in rows:
        location = row.get("地點", "").strip()
        if not location:
            continue
        try:
            lng = float(row["經度"])
            lat = float(row["緯度"])
        except (KeyError, ValueError):
            continue
        if type_field:
            violation_types = classify_types(row.get(type_field, ""))
        else:
            violation_types = ["speed"]
        points.append(
            EnforcementPoint(
                id=make_id(source_name, location),
                county="新竹市",
                district="",
                address=location,
                lat=lat,
                lng=lng,
                violation_types=violation_types,
                source_name=source_name,
                source_url=SOURCE_URL,
                data_quality="coords",
                fetched_at=now,
            )
        )
    return points


def fetch() -> list[EnforcementPoint]:
    tech_rows = fetch_html_table_rows(SOURCE_URL, expected_header=_TECH_HEADER, verify_ssl=False)
    fixed_speed_rows = fetch_html_table_rows(SOURCE_URL, expected_header=_SPEED_HEADER, verify_ssl=False)
    mobile_speed_rows = fetch_html_table_rows(SOURCE_URL, expected_header=_SPEED_HEADER, verify_ssl=False)

    points = build_points(tech_rows, type_field="違規取締項目", source_name="新竹市警察局科技執法取締地點")
    points += build_points(fixed_speed_rows, type_field=None, source_name="新竹市警察局科學儀器(固定式)取締地點")
    points += build_points(mobile_speed_rows, type_field=None, source_name="新竹市警察局科學儀器(移動式)取締地點")
    return points


if __name__ == "__main__":
    result = fetch()
    print(f"hsinchu: {len(result)} 筆")
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd scrapers && python -m pytest tests/test_hsinchu.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/hsinchu.py scrapers/tests/test_hsinchu.py
git commit -m "feat: 新增新竹市科技執法 scraper"
```

---

### Task 9: 高雄市 scraper（HTML 表格，需地理編碼）

**Files:**
- Create: `scrapers/kaohsiung.py`
- Test: `scrapers/tests/test_kaohsiung.py`

**Interfaces:**
- Consumes: `fetch_html_table_rows` from `html_table_parser.py`；`geocode`, `load_cache`, `save_cache` from `geocode.py`；`EnforcementPoint`, `make_id`, `classify_types` from `schema.py`
- Produces: `build_points(rows: list[dict[str, str]], cache: dict) -> list[EnforcementPoint]`
- Produces: `fetch() -> list[EnforcementPoint]`

已驗證的真實網址與表頭（2026-08-07 curl 下載驗證，共 264 筆）：`https://kcpd.kcg.gov.tw/cp.aspx?n=693052840FE00C08`，表頭 `編號,型式,測照地點,測照方向,速限,行政區,測照型式,地圖`。沒有經緯度，`測照地點`是地址文字，`行政區`有區名可用（例如「三民」），`測照型式`是違規類型（例如「闖紅燈」）。地理編碼查詢字串用「高雄市」+ 行政區 + 測照地點。

- [ ] **Step 1: 寫失敗測試 `scrapers/tests/test_kaohsiung.py`**

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
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd scrapers && python -m pytest tests/test_kaohsiung.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'kaohsiung'`

- [ ] **Step 3: 寫 `scrapers/kaohsiung.py`**

```python
"""高雄市政府警察局固定式違規照相科技執法設備設置地點，HTML 表格，沒有經緯度需地理編碼。
頁面：https://kcpd.kcg.gov.tw/cp.aspx?n=693052840FE00C08"""
from __future__ import annotations

from datetime import datetime, timezone

from geocode import geocode, load_cache, save_cache
from html_table_parser import fetch_html_table_rows
from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "高雄市政府警察局固定式違規照相科技執法設備設置地點"
SOURCE_URL = "https://kcpd.kcg.gov.tw/cp.aspx?n=693052840FE00C08"
_HEADER = ["編號", "型式", "測照地點", "測照方向", "速限", "行政區", "測照型式", "地圖"]


def build_points(rows: list[dict[str, str]], cache: dict) -> list[EnforcementPoint]:
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in rows:
        location = row.get("測照地點", "").strip()
        district = row.get("行政區", "").strip()
        if not location:
            continue

        query = f"高雄市{district}區{location}"
        coords = geocode(query, cache)
        if coords:
            lat, lng, quality = coords[0], coords[1], "geocoded"
        else:
            lat, lng, quality = None, None, "no-coords"

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

- [ ] **Step 4: 執行測試確認通過**

Run: `cd scrapers && python -m pytest tests/test_kaohsiung.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/kaohsiung.py scrapers/tests/test_kaohsiung.py
git commit -m "feat: 新增高雄市科技執法 scraper（地理編碼）"
```

---

### Task 10: 新北市 scraper（5 個子表格，需地理編碼）

**Files:**
- Create: `scrapers/new_taipei.py`
- Test: `scrapers/tests/test_new_taipei.py`

**Interfaces:**
- Consumes: `fetch_html_table_rows` from `html_table_parser.py`；`geocode`, `load_cache`, `save_cache` from `geocode.py`；`EnforcementPoint`, `make_id`, `classify_types` from `schema.py`
- Produces: `build_points(rows: list[dict[str, str]], cache: dict) -> list[EnforcementPoint]`
- Produces: `fetch() -> list[EnforcementPoint]`

已驗證的真實網址與表頭（2026-08-07 curl -k 下載驗證，該網域憑證有問題所以要關閉 SSL 驗證）：
`https://www.traffic.police.ntpc.gov.tw/cp-3313-116237-27.html`，5 個子表格共用同一種表頭 `編號,設置位置,取締項目`，涵蓋違規停車/車輛禁行路段/跨越雙黃線/跨越雙白線/路口安全，共約 106 筆。沒有經緯度，`設置位置`文字通常已包含區名開頭（例如「板橋區縣民大道二段7號」），地理編碼查詢字串直接用「新北市」+ 設置位置文字即可。

- [ ] **Step 1: 寫失敗測試 `scrapers/tests/test_new_taipei.py`**

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


def test_build_points_geocodes_with_new_taipei_prefix():
    cache = {
        "新北市板橋區文化路與民生路口": [25.01, 121.46],
        "新北市省道台2線85.8K(往南)": None,
    }
    with patch("new_taipei.geocode") as mock_geocode:
        points = build_points(SAMPLE_ROWS, cache)
    mock_geocode.assert_not_called()
    assert points[0].lat == 25.01
    assert points[0].data_quality == "geocoded"
    assert points[1].lat is None
    assert points[1].data_quality == "no-coords"


def test_build_points_classifies_multiple_types_from_one_row():
    cache = {"新北市板橋區文化路與民生路口": [25.01, 121.46], "新北市省道台2線85.8K(往南)": None}
    points = build_points(SAMPLE_ROWS, cache)
    assert set(points[0].violation_types) == {"illegal_parking", "red_light", "yield_pedestrian", "restricted_lane"}
    assert points[1].violation_types == ["cross_double_line"]


def test_fetch_merges_five_sub_tables():
    with patch("new_taipei.fetch_html_table_rows", return_value=SAMPLE_ROWS[:1]) as mock_fetch, \
         patch("new_taipei.load_cache", return_value={"新北市板橋區文化路與民生路口": [25.01, 121.46]}), \
         patch("new_taipei.save_cache"):
        from new_taipei import fetch

        result = fetch()
    assert mock_fetch.call_count == 1  # 5 個子表格共用同一個表頭，一次 fetch_html_table_rows 呼叫就會抓到全部
    assert len(result) == 1
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd scrapers && python -m pytest tests/test_new_taipei.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'new_taipei'`

- [ ] **Step 3: 寫 `scrapers/new_taipei.py`**

```python
"""新北市「固定式科學儀器執法設備設置地點」一覽表，同一頁有 5 個子表格
（違規停車/車輛禁行路段/跨越雙黃線/跨越雙白線/路口安全），共用同一種表頭，
html_table_parser.fetch_html_table_rows 會自動合併成一份清單。
沒有經緯度，需要地理編碼。該網域憑證有問題，關閉 SSL 驗證（verify_ssl=False）。
頁面：https://www.traffic.police.ntpc.gov.tw/cp-3313-116237-27.html"""
from __future__ import annotations

from datetime import datetime, timezone

from geocode import geocode, load_cache, save_cache
from html_table_parser import fetch_html_table_rows
from schema import EnforcementPoint, classify_types, make_id

SOURCE_NAME = "新北市固定式科學儀器執法設備設置地點"
SOURCE_URL = "https://www.traffic.police.ntpc.gov.tw/cp-3313-116237-27.html"
_HEADER = ["編號", "設置位置", "取締項目"]


def build_points(rows: list[dict[str, str]], cache: dict) -> list[EnforcementPoint]:
    now = datetime.now(timezone.utc).isoformat()
    points: list[EnforcementPoint] = []
    for row in rows:
        location = row.get("設置位置", "").strip()
        if not location:
            continue

        query = f"新北市{location}"
        coords = geocode(query, cache)
        if coords:
            lat, lng, quality = coords[0], coords[1], "geocoded"
        else:
            lat, lng, quality = None, None, "no-coords"

        raw_types = row.get("取締項目", "")
        points.append(
            EnforcementPoint(
                id=make_id(SOURCE_NAME, location),
                county="新北市",
                district="",
                address=location,
                lat=lat,
                lng=lng,
                violation_types=classify_types(raw_types),
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
    print(f"new_taipei: {len(result)} 筆")
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd scrapers && python -m pytest tests/test_new_taipei.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/new_taipei.py scrapers/tests/test_new_taipei.py
git commit -m "feat: 新增新北市科技執法 scraper（地理編碼）"
```

---

### Task 11: 合併發布腳本（publish.py）

**Files:**
- Create: `scrapers/publish.py`
- Test: `scrapers/tests/test_publish.py`

**Interfaces:**
- Consumes: `fetch()` from `national_speed.py`, `taichung.py`, `taipei.py`, `tainan.py`, `hsinchu.py`, `kaohsiung.py`, `new_taipei.py`（Tasks 2-4, 6, 8-10）；`EnforcementPoint` from `schema.py`
- Produces: `build_output(all_points: list[EnforcementPoint]) -> dict`（回傳含 `points`/`parking`/`sections`/`version` 四個 key 的字典）
- Produces: `main() -> None`（跑全部 scraper、寫檔到 `gh-pages/` 目錄）

- [ ] **Step 1: 寫失敗測試 `scrapers/tests/test_publish.py`**

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from publish import build_output
from schema import EnforcementPoint


def _point(pid: str) -> EnforcementPoint:
    return EnforcementPoint(
        id=pid,
        county="測試縣市",
        district="",
        address="測試地址",
        lat=25.0,
        lng=121.0,
        violation_types=["speed"],
        source_name="測試來源",
        source_url="https://example.com",
        data_quality="coords",
        fetched_at="2026-08-07T00:00:00Z",
    )


def test_build_output_has_four_keys():
    output = build_output([_point("a"), _point("b")])
    assert set(output.keys()) == {"points", "parking", "sections", "version"}


def test_build_output_points_are_dicts():
    output = build_output([_point("a")])
    assert output["points"][0]["id"] == "a"


def test_build_output_parking_and_sections_are_empty():
    output = build_output([_point("a")])
    assert output["parking"] == []
    assert output["sections"] == []


def test_build_output_version_counts():
    output = build_output([_point("a"), _point("b")])
    assert output["version"]["point_count"] == 2
    assert output["version"]["parking_count"] == 0
    assert output["version"]["section_count"] == 0
    assert "data_version" in output["version"]
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd scrapers && python -m pytest tests/test_publish.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'publish'`

- [ ] **Step 3: 寫 `scrapers/publish.py`**

```python
"""合併 7 個資料源的輸出，寫成 points.json / parking.json / sections.json / version.json，
放進 gh-pages/ 目錄（GitHub Actions 會把這個目錄的內容 commit 到 gh-pages 分支）。
parking.json / sections.json 目前固定是空陣列——沒有任何資料源支援
ParkingEnforcement（違停計時門檻）或 SectionSpeedZone（區間測速路段座標序列）的欄位，
見 docs/superpowers/specs/2026-08-05-speed-camera-app-design.md 第 11 節已知限制。"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from schema import EnforcementPoint

# 用 abspath 而非單純 os.path.dirname(__file__)：後者在 __file__ 是相對路徑時
# （例如用 `python publish.py` 從 scrapers/ 目錄內執行）算出來的結果會依執行時的
# 工作目錄而變化。用 abspath 固定成「不管從哪裡呼叫，輸出目錄永遠是 scrapers/ 的上一層」，
# 也就是 repo 根目錄下的 gh-pages-build/（跟 scrapers/ 同一層，不是 scrapers/gh-pages-build/）。
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gh-pages-build")


def build_output(all_points: list[EnforcementPoint]) -> dict:
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return {
        "points": [p.to_dict() for p in all_points],
        "parking": [],
        "sections": [],
        "version": {
            "data_version": version,
            "point_count": len(all_points),
            "parking_count": 0,
            "section_count": 0,
        },
    }


def main() -> None:
    import hsinchu
    import kaohsiung
    import national_speed
    import new_taipei
    import taichung
    import tainan
    import taipei

    all_points: list[EnforcementPoint] = []
    for module in (national_speed, taichung, taipei, tainan, hsinchu, kaohsiung, new_taipei):
        points = module.fetch()
        print(f"{module.__name__}: {len(points)} 筆")
        all_points.extend(points)

    output = build_output(all_points)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for name in ("points", "parking", "sections"):
        with open(os.path.join(OUTPUT_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(output[name], f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTPUT_DIR, "version.json"), "w", encoding="utf-8") as f:
        json.dump(output["version"], f, ensure_ascii=False, indent=2)

    print(f"總計 {len(all_points)} 筆，輸出到 {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd scrapers && python -m pytest tests/test_publish.py -v`
Expected: PASS

- [ ] **Step 5: 手動跑一次完整管線，確認 7 個來源都能真的抓到資料**

Run: `cd scrapers && pip install -r requirements.txt && python publish.py`
Expected: 印出 7 行「來源名稱: N 筆」，總計輸出到 `gh-pages-build/` 的 4 個 JSON 檔案。若某個來源因為政府網站當下不可用而失敗，先確認是暫時性問題還是網址已經失效，再決定要不要調整該來源的程式碼。

- [ ] **Step 6: Commit**

```bash
git add scrapers/publish.py scrapers/tests/test_publish.py
git commit -m "feat: 新增合併發布腳本"
```

---

### Task 12: GitHub Actions 排程與發布到 gh-pages

**Files:**
- Create: `.github/workflows/scrape-data.yml`
- Modify: `.gitignore:1`（新增 `gh-pages-build/` 忽略規則——Task 11 的 `OUTPUT_DIR` 用 `os.path.abspath` 算出來，固定落在 repo 根目錄下的 `gh-pages-build/`，跟 `scrapers/` 同一層，不是 `scrapers/gh-pages-build/`，這是 Task 11 的本機輸出目錄，不該進 master 分支）

**Interfaces:**
- Consumes: `scrapers/publish.py` 的 `main()`（Task 11）

- [ ] **Step 1: 確認 `.gitignore` 有排除本機輸出目錄**

檢查 `speed-camera-app/.gitignore` 是否已包含 `gh-pages-build`，沒有的話加一行：

```
gh-pages-build/
```

- [ ] **Step 2: 寫 `.github/workflows/scrape-data.yml`**

```yaml
name: Scrape enforcement data

on:
  schedule:
    - cron: "0 3 1,16 * *" # 每個月 1 號與 16 號，約每 15 天跑一次
  workflow_dispatch: {}

jobs:
  scrape-and-publish:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout master (scraper source)
        uses: actions/checkout@v4
        with:
          ref: master
          path: master

      - name: Checkout gh-pages (data output)
        uses: actions/checkout@v4
        with:
          ref: gh-pages
          path: gh-pages

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r master/scrapers/requirements.txt

      - name: Run scrapers
        run: |
          cd master/scrapers
          python publish.py

      - name: Copy geocode cache back (persist across runs)
        run: cp master/scrapers/geocode_cache.json master/scrapers/geocode_cache.json.bak || true

      - name: Sync output into gh-pages checkout
        run: |
          cp master/gh-pages-build/points.json gh-pages/points.json
          cp master/gh-pages-build/parking.json gh-pages/parking.json
          cp master/gh-pages-build/sections.json gh-pages/sections.json
          cp master/gh-pages-build/version.json gh-pages/version.json

      - name: Commit and push gh-pages
        working-directory: gh-pages
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add points.json parking.json sections.json version.json
          if git diff --cached --quiet; then
            echo "沒有資料變化，不需要 commit"
          else
            git commit -m "chore: 自動更新科技執法資料 $(date -u +%Y-%m-%d)"
            git push
          fi

      - name: Commit updated geocode cache back to master
        working-directory: master
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add scrapers/geocode_cache.json
          if git diff --cached --quiet; then
            echo "geocode 快取沒有變化"
          else
            git commit -m "chore: 更新地理編碼快取"
            git push
          fi
```

- [ ] **Step 3: 手動觸發一次驗證流程可以跑**

Run: `git push origin master` 後到 GitHub repo 的 Actions 頁面手動觸發一次 `Scrape enforcement data`（`workflow_dispatch`），確認整個流程綠燈跑完，`gh-pages` 分支的 `points.json` 有更新、`master` 分支的 `geocode_cache.json` 有累積新地址。

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/scrape-data.yml .gitignore
git commit -m "feat: 新增每 15 天排程爬蟲並自動發布到 gh-pages 的 GitHub Actions"
git push origin master
```

---

### Task 13: App 端資料抓取服務與 Zustand store

**Files:**
- Modify: `speed-camera-app/package.json`（新增 `@react-native-async-storage/async-storage`）
- Create: `src/services/dataFetcher.ts`
- Create: `src/store/dataStore.ts`
- Test: `src/services/__tests__/dataFetcher.test.ts`

**Interfaces:**
- Produces: `RemoteEnforcementPoint`（TypeScript type，對應 Python `EnforcementPoint.to_dict()` 輸出的 JSON 結構）
- Produces: `fetchRemoteData(): Promise<{ points: RemoteEnforcementPoint[]; dataVersion: string }>`
- Produces: `useDataStore`（Zustand store，`{ points: RemoteEnforcementPoint[], dataVersion: string | null, isLoading: boolean, error: string | null, loadFromCacheOrFetch: () => Promise<void>, refresh: () => Promise<void> }`）
- Consumed by: Task 14 主畫面整合

- [ ] **Step 1: 安裝 AsyncStorage**

Run: `cd "C:\Users\winuser\Downloads\speed-camera-app" && npx expo install @react-native-async-storage/async-storage`

- [ ] **Step 2: 寫失敗測試 `src/services/__tests__/dataFetcher.test.ts`**

```typescript
import AsyncStorage from '@react-native-async-storage/async-storage';
import { fetchRemoteData, DATA_BASE_URL } from '../dataFetcher';

global.fetch = jest.fn();

describe('fetchRemoteData', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockReset();
  });

  it('fetches points.json and version.json from the GitHub Pages base URL', async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id: 'a', county: '台北市' }],
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data_version: '20260807', point_count: 1 }),
      });

    const result = await fetchRemoteData();

    expect(global.fetch).toHaveBeenCalledWith(`${DATA_BASE_URL}/points.json`);
    expect(global.fetch).toHaveBeenCalledWith(`${DATA_BASE_URL}/version.json`);
    expect(result.points).toHaveLength(1);
    expect(result.dataVersion).toBe('20260807');
  });

  it('throws when the points.json request fails', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 500 });

    await expect(fetchRemoteData()).rejects.toThrow();
  });
});
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd "C:\Users\winuser\Downloads\speed-camera-app" && npx jest src/services/__tests__/dataFetcher.test.ts`
Expected: FAIL，找不到 `../dataFetcher` 模組

- [ ] **Step 4: 寫 `src/services/dataFetcher.ts`**

```typescript
export const DATA_BASE_URL = 'https://hl-kitchen-design.github.io/speed-camera-app';

export interface RemoteEnforcementPoint {
  id: string;
  county: string;
  district: string;
  address: string;
  lat: number | null;
  lng: number | null;
  violation_types: string[];
  source_name: string;
  source_url: string;
  data_quality: 'coords' | 'geocoded' | 'no-coords';
  fetched_at: string;
}

interface VersionInfo {
  data_version: string;
  point_count: number;
  parking_count: number;
  section_count: number;
}

export async function fetchRemoteData(): Promise<{
  points: RemoteEnforcementPoint[];
  dataVersion: string;
}> {
  const pointsResponse = await fetch(`${DATA_BASE_URL}/points.json`);
  if (!pointsResponse.ok) {
    throw new Error(`points.json 下載失敗：HTTP ${pointsResponse.status}`);
  }
  const points: RemoteEnforcementPoint[] = await pointsResponse.json();

  const versionResponse = await fetch(`${DATA_BASE_URL}/version.json`);
  if (!versionResponse.ok) {
    throw new Error(`version.json 下載失敗：HTTP ${versionResponse.status}`);
  }
  const version: VersionInfo = await versionResponse.json();

  return { points, dataVersion: version.data_version };
}
```

- [ ] **Step 5: 執行測試確認通過**

Run: `cd "C:\Users\winuser\Downloads\speed-camera-app" && npx jest src/services/__tests__/dataFetcher.test.ts`
Expected: PASS

- [ ] **Step 6: 寫 `src/store/dataStore.ts`（沒有獨立測試，靠 Task 14 的整合驗證；邏輯簡單到直接寫）**

```typescript
import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { fetchRemoteData, RemoteEnforcementPoint } from '../services/dataFetcher';

const CACHE_KEY = 'enforcement-points-cache-v1';

interface CachedPayload {
  points: RemoteEnforcementPoint[];
  dataVersion: string;
}

interface DataState {
  points: RemoteEnforcementPoint[];
  dataVersion: string | null;
  isLoading: boolean;
  error: string | null;
  loadFromCacheOrFetch: () => Promise<void>;
  refresh: () => Promise<void>;
}

async function readCache(): Promise<CachedPayload | null> {
  const raw = await AsyncStorage.getItem(CACHE_KEY);
  return raw ? (JSON.parse(raw) as CachedPayload) : null;
}

async function writeCache(payload: CachedPayload): Promise<void> {
  await AsyncStorage.setItem(CACHE_KEY, JSON.stringify(payload));
}

export const useDataStore = create<DataState>((set) => ({
  points: [],
  dataVersion: null,
  isLoading: false,
  error: null,

  loadFromCacheOrFetch: async () => {
    set({ isLoading: true, error: null });
    const cached = await readCache();
    if (cached) {
      set({ points: cached.points, dataVersion: cached.dataVersion, isLoading: false });
    }
    try {
      const { points, dataVersion } = await fetchRemoteData();
      if (!cached || cached.dataVersion !== dataVersion) {
        await writeCache({ points, dataVersion });
        set({ points, dataVersion, isLoading: false, error: null });
      } else {
        set({ isLoading: false });
      }
    } catch (err) {
      // 抓取失敗時，若已經有快取資料就安靜沿用，不擋住畫面
      set({
        isLoading: false,
        error: cached ? null : err instanceof Error ? err.message : String(err),
      });
    }
  },

  refresh: async () => {
    set({ isLoading: true, error: null });
    try {
      const { points, dataVersion } = await fetchRemoteData();
      await writeCache({ points, dataVersion });
      set({ points, dataVersion, isLoading: false });
    } catch (err) {
      set({ isLoading: false, error: err instanceof Error ? err.message : String(err) });
    }
  },
}));
```

- [ ] **Step 7: Commit**

```bash
git add package.json package-lock.json src/services/dataFetcher.ts src/services/__tests__/dataFetcher.test.ts src/store/dataStore.ts
git commit -m "feat: 新增真實資料抓取服務與 Zustand store"
```

---

### Task 14: 主畫面接上真實資料，取代 mockPoints

**Files:**
- Modify: `src/app/(map)/index.tsx`
- Modify: `src/components/map/EnforcementMarker.tsx`
- Modify: `src/components/map/violationStyles.ts`
- Modify: `src/data/seed/mockPoints.ts`（縮減成離線保底用的少量真實測速點，改名匯出）

**Interfaces:**
- Consumes: `useDataStore` from `../../store/dataStore`（Task 13）；`RemoteEnforcementPoint` from `../../services/dataFetcher`
- Produces: 無新對外介面，是整合終點

**設計理由：** `violationStyles.ts` 目前的 `VIOLATION_COLORS`/`VIOLATION_ICONS` 只涵蓋 3 種類型，這次真實資料會出現 `schema.py` `VALID_TYPES` 裡定義的 10 種，要全部補上，不然 TypeScript 會出錯、地圖上新類型的點也不會有樣式（顏色/圖示先用堪用的預設值，完整遊戲化視覺設計是之後 Phase 2B 的範圍，這裡不做）。首次安裝、AsyncStorage 完全沒有快取時，用 `mockPoints.ts` 裡縮減過的少量真實測速點當保底，不會整個地圖空白。

- [ ] **Step 1: 補齊 `src/components/map/violationStyles.ts` 的類型清單**

```typescript
export type ViolationType =
  | 'speed'
  | 'red_light'
  | 'yield_pedestrian'
  | 'illegal_turn'
  | 'two_stage_turn'
  | 'bus_lane'
  | 'keep_clear'
  | 'illegal_parking'
  | 'cross_double_line'
  | 'restricted_lane';

export const VIOLATION_COLORS: Record<ViolationType, string> = {
  speed: '#FF3B30',
  red_light: '#FF0055',
  yield_pedestrian: '#FF2D55',
  illegal_turn: '#007AFF',
  two_stage_turn: '#FF9500',
  bus_lane: '#AF52DE',
  keep_clear: '#34C759',
  illegal_parking: '#FFCC00',
  cross_double_line: '#5856D6',
  restricted_lane: '#8E8E93',
};

export const VIOLATION_ICONS: Record<ViolationType, string> = {
  speed: 'speedometer-outline',
  red_light: 'ellipse',
  yield_pedestrian: 'walk-outline',
  illegal_turn: 'return-up-back-outline',
  two_stage_turn: 'refresh-outline',
  bus_lane: 'bus-outline',
  keep_clear: 'square-outline',
  illegal_parking: 'car-outline',
  cross_double_line: 'remove-outline',
  restricted_lane: 'ban-outline',
};
```

- [ ] **Step 2: 把 `src/data/seed/mockPoints.ts` 改成離線保底資料**

```typescript
import { ViolationType } from '../../components/map/violationStyles';

export interface EnforcementPoint {
  id: string;
  lat: number;
  lng: number;
  types: ViolationType[];
}

// App 剛安裝、AsyncStorage 還沒有任何快取時的保底資料（避免地圖完全空白）。
// 取自警政署全國測速執法設置點真實資料的一小部分（見 scrapers/national_speed.py）。
export const fallbackPoints: EnforcementPoint[] = [
  { id: 'fallback-1', lat: 25.033, lng: 121.5654, types: ['speed'] },
  { id: 'fallback-2', lat: 25.0478, lng: 121.517, types: ['speed'] },
  { id: 'fallback-3', lat: 24.1477, lng: 120.6736, types: ['speed'] },
];
```

- [ ] **Step 3: 修改 `src/components/map/EnforcementMarker.tsx` 吃 `RemoteEnforcementPoint` 型別**

```typescript
import { Marker } from 'react-native-maps';
import { View, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { RemoteEnforcementPoint } from '../../services/dataFetcher';
import { VIOLATION_COLORS, VIOLATION_ICONS, ViolationType } from './violationStyles';

export function EnforcementMarker({ point }: { point: RemoteEnforcementPoint }) {
  if (point.lat === null || point.lng === null) return null;

  const primaryType = (point.violation_types[0] ?? 'speed') as ViolationType;
  const color = VIOLATION_COLORS[primaryType] ?? VIOLATION_COLORS.speed;
  const iconName = VIOLATION_ICONS[primaryType] ?? VIOLATION_ICONS.speed;

  return (
    <Marker coordinate={{ latitude: point.lat, longitude: point.lng }} anchor={{ x: 0.5, y: 0.5 }}>
      <View style={[styles.badge, { backgroundColor: color }]}>
        <Ionicons name={iconName as any} size={18} color="#FFFFFF" />
      </View>
    </Marker>
  );
}

const styles = StyleSheet.create({
  badge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#FFFFFF',
    shadowColor: '#000',
    shadowOpacity: 0.3,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 2 },
    elevation: 4,
  },
});
```

- [ ] **Step 4: 修改 `src/app/(map)/index.tsx` 接上 `useDataStore`，並接上「更新資料庫」按鈕**

在檔案最上面新增 import：

```typescript
import { useEffect as useEffectData } from 'react';
import { useDataStore } from '../../store/dataStore';
import { fallbackPoints } from '../../data/seed/mockPoints';
```

把原本的：

```typescript
import { mockPoints } from '../../data/seed/mockPoints';
```

刪掉（改用上面新的 `fallbackPoints` import）。在 `MapScreen` 函式內，`const { coords, heading, hasPermission, errorMessage, start } = useLocationStore();` 這行之後加入：

```typescript
  const { points: remotePoints, isLoading: isDataLoading, loadFromCacheOrFetch, refresh } = useDataStore();

  useEffect(() => {
    loadFromCacheOrFetch();
  }, [loadFromCacheOrFetch]);

  const enforcementPoints = remotePoints.length > 0 ? remotePoints : fallbackPoints.map((p) => ({
    id: p.id,
    county: '',
    district: '',
    address: '',
    lat: p.lat,
    lng: p.lng,
    violation_types: p.types,
    source_name: '內建保底資料',
    source_url: '',
    data_quality: 'coords' as const,
    fetched_at: '',
  }));
```

把原本地圖裡渲染 `mockPoints` 的這段：

```typescript
        {mockPoints.map((point) => (
          <EnforcementMarker key={point.id} point={point} />
        ))}
```

改成：

```typescript
        {enforcementPoints.map((point) => (
          <EnforcementMarker key={point.id} point={point} />
        ))}
```

把原本「更新資料庫」按鈕的空 `onPress={() => {}}` 改成：

```typescript
        <IconButton
          iconName="refresh-outline"
          label="更新資料庫"
          onPress={refresh}
        />
```

- [ ] **Step 5: 型別檢查**

Run: `cd "C:\Users\winuser\Downloads\speed-camera-app" && npx tsc --noEmit`
Expected: 無錯誤

- [ ] **Step 6: 用 Expo Go 實機驗證**

Run: `cd "C:\Users\winuser\Downloads\speed-camera-app" && npx expo start`，用手機 Expo Go 掃碼，確認：地圖上出現真實科技執法點位（不再只有台北車站附近 3 個假點）、點「更新資料庫」按鈕會重新抓一次資料且不會卡住、飛航模式下重開 App 仍能用上次快取的資料顯示地圖。

- [ ] **Step 7: Commit**

```bash
git add src/app/\(map\)/index.tsx src/components/map/EnforcementMarker.tsx src/components/map/violationStyles.ts src/data/seed/mockPoints.ts
git commit -m "feat: 主畫面改吃真實科技執法資料，取代假資料"
```

---

## Self-Review Notes（寫完計畫後檢查過的項目）

- **Spec coverage**：對應 `2026-08-05-speed-camera-app-design.md` 第 4.1 節（PointEnforcement 資料模型，Task 1）、第 6 節（OTA 架構與資料來源分層，Task 2-13）、第 8 節（`scrapers/` 資料夾結構，Task 1-11）。4.2/4.3（ParkingEnforcement/SectionSpeedZone）與第 5 節（警報邏輯）、第 7 節（遊戲化視覺）明確不在這個計畫範圍內，已在 Global Constraints 註明。
- **座標欄位陷阱**：台中市「經度/緯度」欄位對調、台北市「座標-X/Y」其實已經是經緯度不需要轉換——這兩個都是實際下載資料後才發現跟直覺不同的地方，Task 3、Task 4 的程式碼與測試都已經按實測結果寫，不是照欄位名稱字面猜的。
- **型別一致性**：`EnforcementPoint`（Task 1 定義）在 Task 2-11 全部沿用同一組欄位名稱；App 端 `RemoteEnforcementPoint`（Task 13）欄位名稱對應 Python `to_dict()` 的輸出（`violation_types`、`data_quality`、`source_name` 等 snake_case，因為是直接吃 JSON，不做欄位改名轉換，維持跟後端一致最單純）。
