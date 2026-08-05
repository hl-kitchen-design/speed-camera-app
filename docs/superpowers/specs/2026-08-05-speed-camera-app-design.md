# 精準定位科技執法提醒 App — 設計文件

日期：2026-08-05
狀態：待使用者審閱

## 1. 專案目標

打造一款遊戲化風格（Pokémon GO / Pikmin Bloom 視覺語彙）的行動 App，讓駕駛人在移動中能直覺辨識前方科技執法內容，涵蓋：

1. 固定點違規（測速、闖紅燈、路口多功能科技執法等）
2. 違規停車科技執法偵測點（臨停超時提醒）
3. 區間測速路段（進入/離開偵測、即時平均車速）

App 使用 React Native + Expo 開發，目標平台為 iOS + Android。

## 2. 範圍與非目標

**這次要做的：**
- 上述三種資料類型的地圖呈現、篩選、接近警報
- 資料遠端自動更新（OTA），含縣市警局公告的排程爬蟲
- 遊戲化 UI/UX（浮空徽章、距離計量條、震動與音效）

**明確不做（Non-goals）：**
- 不做背景常駐定位（僅前景定位），降低 App Store 審查風險與電力消耗
- 不做即時雷達/測速偵測，僅基於官方公告的已知點位/路段
- 不宣稱能精確得知「這個確切車位可以臨停幾分鐘」——沒有全國紅黃線圖資，違停提醒是基於「已知科技執法偵測點＋官方公告依據連結」的提醒，非精確法律判斷
- 第一階段爬蟲不涵蓋全部 22 縣市，僅涵蓋資料結構化程度較高的台北市、新北市、台中市、台南市

## 3. 技術棧

| 項目 | 選擇 | 原因 |
|---|---|---|
| 框架 | Expo（Managed Workflow, SDK 53+）+ React Native + TypeScript | 免原生建置環境即可用 Expo Go 在 iPhone 上測試 |
| 地圖 | `react-native-maps` | iOS 用 Apple Maps 免 API Key；Android 用 Google Maps（需申請 API Key） |
| 定位 | `expo-location` | 前景高精度定位＋heading，平滑更新車輛朝向 |
| 狀態管理 | Zustand | 比 Context 少樣板碼，適合多畫面共享定位/篩選/警報狀態 |
| 本地儲存 | `@react-native-async-storage/async-storage` | 存資料版本號與三種點位/路段資料快取（全台資料量約數千筆，記憶體內 Haversine 過濾即可，不需要 SQLite） |
| 圖示 | `@expo/vector-icons` | Expo 內建，免額外安裝 |
| 動畫 | `react-native-reanimated` | 徽章彈出、光圈、計量條動畫 |
| 震動/音效 | `expo-haptics` + `expo-audio` | 接近警報的觸覺與聲音回饋 |

## 4. 資料模型

### 4.1 固定點違規（PointEnforcement）
```
{
  id: string
  lat: number
  lng: number
  types: string[]        // "speed" | "red_light" | "yield_pedestrian" | "illegal_turn" | "two_stage_turn" | "bus_lane" | "keep_clear"
  speedLimit?: number
  road: string
  city: string
  direction?: string
  jurisdiction: string
  sourceUrl: string       // 官方公告來源
}
```

### 4.2 違規停車科技執法偵測點（ParkingEnforcement）
```
{
  id: string
  lat: number
  lng: number
  violationType: string   // "red_line" | "yellow_line" | "bus_stop_10m" | "double_parking"
  thresholdMinutes: number // 預設 3，併排停車類為 0（無寬限）
  city: string
  road: string
  sourceUrl: string        // 必填，官方公告連結
}
```

### 4.3 區間測速路段（SectionSpeedZone）
```
{
  id: string
  startLat: number
  startLng: number
  endLat: number
  endLng: number
  path: [number, number][]  // 路段中線座標序列，用於比對是否在路段內
  speedLimit: number
  road: string
  city: string
  sourceUrl: string
}
```

### 4.4 版本資訊（version.json）
```
{
  "data_version": "20260805",
  "point_count": number,
  "parking_count": number,
  "section_count": number
}
```

## 5. 警報邏輯

### 5.1 固定點警報
- 每次定位更新，用 Haversine 公式過濾使用者周圍 500m~2km 內的點位（僅渲染附近點位，避免地圖效能問題）
- 進入 300m 觸發半徑：跳出遊戲風格浮空徽章卡片，顯示違規類型 icon 組合＋倒數距離（300m→150m→50m）
- 100m 內觸發 Haptic 震動與提示音
- 同一點位同一趟行程只警報一次（記錄已警報 ID，離開 1km 外才重置，避免掉頭重複觸發時完全不提醒）

### 5.2 違規停車偵測點警報
- 進入偵測點半徑（例如 100m）且 GPS 速度連續低於閾值（視為停等/臨停）→ 啟動浮動倒數計時器
- 計時器顯示：偵測點的官方取締依據（違規類型＋門檻分鐘數）＋倒數
- 明確標示「提醒依據：〔官方公告連結〕」，不宣稱即時偵測到違規
- 車輛重新移動（速度回升）則計時器自動消失

### 5.3 區間測速警報
- 車輛進入路段起點緩衝區（比對是否貼近 `path` 座標序列）→ 記錄進入時間與座標
- 持續計算「目前累積行駛距離 / 經過時間」＝即時平均車速，顯示於地圖上方常駐小卡
- 接近路段終點（如剩餘 300m）→ 若平均車速超過限速，跳出警示提醒
- 離開路段（超出 path 緩衝區或到達終點）→ 顯示摘要卡片（區間平均車速 vs 限速），並清除追蹤狀態

## 6. 遠端資料更新（OTA）架構

1. **靜態資料服務**：GitHub Pages 靜態站，發布三份 JSON（points.json / parking.json / sections.json）＋ version.json
2. **排程爬蟲**：GitHub Actions cron，每 15 天執行一次
   - 第一階段涵蓋：台北市、新北市、台中市、台南市（各自獨立解析腳本，因為每個縣市網站格式不同：PDF、HTML 表格、Open Data 平台 API 皆有）
   - 桃園市、高雄市列為第二波擴充
   - 爬取結果直接自動發布（更新 GitHub Pages 上的 JSON），但每次執行都是一個獨立 git commit，保留完整版本歷史，若解析錯誤可快速回溯到前一版本
3. **App 端**：
   - 啟動時背景比對本地 `data_version` 與遠端 `version.json`，有新版才下載並無感替換 AsyncStorage 快取
   - 設定頁提供手動「檢查更新」圖示按鈕
   - 網路失敗或抓取錯誤時，安靜地沿用本地快取，不擋住 App 使用

## 7. 遊戲化視覺系統

| 違規項目 | 主題色 | Badge 名稱 |
|---|---|---|
| 超速 | 果實紅 `#FF3B30` | SPEED LIMIT |
| 違規停車 | 鮮黃色 `#FFCC00` | NO PARKING |
| 未禮讓行人 | 皮可敏粉紅 `#FF2D55` | PEDESTRIAN |
| 闖紅燈 | 霓虹紅 `#FF0055` | RED LIGHT |
| 違規轉彎/未依標線 | 寶可夢藍 `#007AFF` | NO TURN |
| 機車未兩段式左轉 | 活潑橘 `#FF9500` | 2-STAGE TURN |
| 公車專用道違規 | 深紫羅蘭 `#AF52DE` | BUS ONLY |
| 未保持路口淨空 | 薄荷綠 `#34C759` | KEEP CLEAR |
| 路口多功能科技執法 | 炫彩金 `#FFD700` | MULTI-FUNCTION |

**元件設計：**
- 浮空徽章卡片：圓角 20px、白邊、微陰影，多項違規並排顯示（如 `[⚡60km/h]` + `[🚶禮讓行人]` + `[🚦闖紅燈]`）
- 距離計量條：底部常駐，300m🟢→150m🟡→50m🔴 漸層提示
- 車輛 Marker：可愛車輛圖示，隨 GPS heading 平滑旋轉
- 地圖 Marker：依上表配色的卡通風格浮空立牌，車輛接近時輕微彈跳＋光圈動畫（`react-native-reanimated`）

**圖示控制鍵（主畫面固定 4 個大圖示按鈕）：**
- 🎯 回到定位
- 🔍 篩選違規類型
- 🔄 手動更新資料庫
- ⚙️ 設定/音效

## 8. 專案資料夾結構（初步）

```
speed-camera-app/
  app/                      # Expo Router 畫面
    (map)/index.tsx         # 主地圖畫面
    settings.tsx
  components/
    map/VehicleMarker.tsx
    map/EnforcementMarker.tsx
    alerts/AlertBanner.tsx
    alerts/DistanceGauge.tsx
    ui/IconButton.tsx
  store/                    # Zustand stores
    locationStore.ts
    dataStore.ts
    alertStore.ts
  services/
    dataFetcher.ts          # OTA 版本檢查/下載
    geo.ts                  # Haversine、路段比對
    alertEngine/
      pointAlert.ts
      parkingAlert.ts
      sectionSpeedAlert.ts
  data/
    seed/                   # 內建預載假資料（開發用）
  scrapers/                 # GitHub Actions 用的 Python 爬蟲腳本（獨立於 App）
    taipei.py
    new_taipei.py
    taichung.py
    tainan.py
    publish.py             # 合併輸出 JSON + version.json
  .github/workflows/
    scrape-data.yml         # 每 15 天排程
  app.json                  # Expo 設定（含 iOS/Android 權限文案）
  docs/superpowers/specs/
```

## 9. 分階段實作順序

1. **專案骨架**：Expo 專案初始化、權限設定、遊戲風格地圖主畫面（含車輛 Marker、4 個圖示控制鍵），先用假資料
2. **資料層＋OTA**：三種資料的本地載入、AsyncStorage 版本比對、GitHub Pages 靜態資料串接
3. **警報邏輯**：三種警報引擎（固定點/違停計時/區間測速）＋遊戲化 Alert UI
4. **爬蟲管線**：GitHub Actions cron＋四縣市解析腳本＋版本歷史紀錄
5. **視覺打磨與合規**：配色系統套用、動畫細節、震動/音效、Info.plist 權限說明文案、免責聲明

每個階段完成後在 Expo Go 上實測，確認沒問題再進下一階段。

## 10. 合規與免責聲明

- `app.json` 設定 `NSLocationWhenInUseUsageDescription`，說明僅在使用時定位、用於顯示週邊科技執法資訊
- 設定頁與警報畫面附帶免責聲明：「本 App 資訊來源為政府開放資料與各縣市警局公告，僅供參考，實際執法標準與地點以官方公告為準，請遵守道路交通安全規則」
- 違停提醒卡片額外附上該筆資料的官方公告連結，避免使用者誤以為是即時精確偵測

## 11. 已知限制

- 政府開放資料無版本號、CSV 不定期更新，OTA 版本號由本專案的爬蟲管線自行產生，非政府官方版本號
- 違規停車偵測點資料僅涵蓋已找到官方公告的縣市與地點，非全國完整涵蓋，且會隨時間逐步擴充
- 區間測速的路段內判斷採座標緩衝區比對，非道路網路圖資比對，在複雜路網（交流道、匝道）可能有誤差
- 各縣市網站格式不同，爬蟲腳本需個別維護，網站改版可能導致單一縣市資料中斷更新（需監控 GitHub Actions 執行結果）

## 12. 測試方式

- 主要透過 Expo Go 在 iPhone 上手動測試（地圖互動、定位、警報觸發）
- 純邏輯函式（Haversine 距離、版本比對、路段內判斷）用 Jest 撰寫單元測試
- 爬蟲腳本本地手動執行驗證輸出 JSON 格式正確，再交給 GitHub Actions 排程
