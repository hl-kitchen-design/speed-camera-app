# Phase 2A 收尾 — C1 地理編碼修復 設計文件

日期：2026-08-09
狀態：待使用者審閱

## 1. 背景

Phase 2A 全部 14 個 Task 完成並個別過審後，總體審查（見 `.superpowers/sdd/2026-08-07-phase2a-real-enforcement-data/progress.md` PARKED 段落）抓到 2 個 Critical，本文件處理其中的 C1：地理編碼幾乎全滅（430 筆待編碼地址中只有 19 筆成功，覆蓋率 4.4%），導致高雄市 264 筆只有 5 筆、新北市 94 筆只有 7 筆、台南市 72 筆只有 8 筆在地圖上看得到，共 410 筆（全部真實資料的 15.8%）完全不可見。

C2（地圖無過濾渲染 2168 個 Marker）不在本文件範圍，留待下一份設計文件處理。

## 2. 根因分析

討論過程中確認了三個各自獨立的根因：

1. **路口交叉格式查詢，Nominatim 幾乎無法解析**：三個來源（高雄、台南、新北）的地址原文都是「A路與B路口」這種台灣路口描述，不是 Nominatim（或任何通用地理編碼服務，含內政部 TGOS）擅長的標準門牌格式。已用 WebSearch/WebFetch 確認 TGOS 全國門牌地址定位服務文件只涵蓋門牌比對，同樣不支援路口查詢——換 provider 或雙 provider 並行都無法解決核心問題，因此本設計**只用 Nominatim**，靠查詢字串降級策略處理。
2. **高雄市查詢字串重複行政區名**：`kaohsiung.py` 的 `query = f"高雄市{district}區{location}"` 沒注意到來源資料的「測照地點」欄位本身已經帶行政區前綴，264 筆裡有 189 筆（72%）查詢字串變成「高雄市三民區**三民區**建國二路...」這種重複，進一步降低比對成功率。
3. **快取把「真的查不到」跟「網路暫時性錯誤」混在一起**：`geocode.py` 目前不論是 Nominatim 回應 0 筆、還是連線逾時/例外，一律把 `None` 寫進 `geocode_cache.json` 並 commit 回 repo，之後永遠不會重試，一次 CI 網路不穩就永久毒化那筆地址。

## 3. 設計

### 3.1 快取 schema：分離暫時性錯誤與確定查無結果

`geocode()`（`scrapers/geocode.py`）改成三種結果：

- **成功**：快取值 `[lat, lng]`（不變，向下相容）
- **API 回應正常、確定 0 筆結果**：快取值改成 `{"lat": null, "lng": null, "checked_at": "<ISO 8601>"}`，寫入快取；下次查詢若 `checked_at` 超過 30 天才重新嘗試，否則直接回傳 null，不打 API
- **連線逾時 / URLError / 例外**：**不寫入快取**，直接回傳 null。因為沒有落地，下一次排程（GitHub Actions cron）會自然重新嘗試，不需要額外的重試計數或旗標

**舊格式相容**：現有 411 筆快取值是 bare `null`（沒有 `checked_at`）。載入時偵測到 bare `null`，視為「未知原因、冷卻已過期」，下次查詢時直接重新嘗試一次，之後才進入新的 30 天冷卻機制。不需要額外寫程式批次清除快取。

### 3.2 查詢字串三級回退

`kaohsiung.py`、`tainan.py`、`new_taipei.py` 三個 scraper 共用同一套邏輯，依序嘗試，任一級成功就停止：

**Level 1（完整字串，沿用現有組法，但修好高雄的重複行政區 bug）**：
```python
if location.startswith(district) or location.startswith(f"{district}區"):
    query = f"高雄市{location}"
else:
    query = f"高雄市{district}區{location}"
```

**Level 2（只取主要道路名）**：新增共用函式 `extract_primary_road(text: str) -> str`，放進 `geocode.py`（三個 scraper 本來就已 import 這個模組，不新增檔案）：
1. 去掉括號內文字（`(...)`）
2. 用「與」「、」切開，取第一段（路口的第一條路）
3. 去掉結尾的「路口」「巷口」
4. 回傳 `f"{county}{district}{road_name}"`（或 `f"{county}{road_name}"`，視來源是否有明確 district）

不強求處理每一種寫法（例如帶巷弄門牌號的「420巷口」精簡後可能仍不準確）——查不到就自然落到 Level 3，不是退化成不可控錯誤。

**Level 3（縣市/行政區中心點）**：直接對 `f"{county}{district}"`（高雄，有明確 district 欄位）或 `f"{county}"`（台南、新北，目前沒有切出 district）呼叫 `geocode()`。這一級會讓多筆資料重疊在同一個座標，`data_quality` 標成新值 `"district-centroid"`，跟現有 `"geocoded"` 區分，供未來 Phase 2B（圖示/圖例重設計）使用不同視覺樣式呈現「僅約略區域」。

三級都查不到才是現有的 `"no-coords"`（App 端 `EnforcementMarker.tsx` 已正確處理 null lat/lng，不需要改動渲染邏輯）。

### 3.3 App 端最小改動

`src/services/dataFetcher.ts` 的型別定義：
```ts
data_quality: 'coords' | 'geocoded' | 'no-coords';
```
加上 `'district-centroid'`，維持型別與實際資料一致。不改動任何渲染/篩選邏輯。

## 4. 測試計畫

- `geocode.py`：新增測試涵蓋「成功」「API 確定 0 筆（存快取+30天冷卻，未過期不重打 API）」「連線逾時（不寫快取，下次一定重試）」「舊格式 bare-null 快取視為冷卻已過期」四種情境
- `extract_primary_road()`：獨立函式，針對括號、「與/、」分隔、「路口/巷口」尾綴各寫測試案例
- `kaohsiung.py`：測試行政區重複偵測（`location` 已含行政區前綴 vs 沒有）兩種情況都不再重複
- `tainan.py` / `new_taipei.py`：套用同一套三級回退，補對應測試
- 全部單元測試綠燈後，**手動觸發一次 GitHub Actions scrape workflow**，比對 `version.json`／`points.json` 的座標覆蓋率是否從目前 19/430（4.4%）明顯提升——這是唯一能驗證「真的解決問題」而非只是「程式碼邏輯自洽」的方式

## 5. 範圍邊界（明確不做）

- C2（地圖 2168 點無過濾渲染）—另立設計文件處理
- I1-I5（Important 項目）、9 個 Minor 項目—維持在 ledger PARKED 區塊，下一輪處理
- Task 14 Step 6（手機 Expo Go 實機驗證）—需要使用者手機，仍延後
- 不整合內政部 TGOS API（見第 2 節根因分析，判斷邊際效益不足以支撐多一組金鑰/多一個 CI 失敗點的複雜度）
