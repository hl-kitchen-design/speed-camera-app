# 第一階段：專案骨架與遊戲風格地圖主畫面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 Expo 專案骨架，做出遊戲風格地圖主畫面：可愛車輛 Marker 隨 GPS 位置與朝向移動、假資料科技執法 Marker（依違規類型上色）、4 個圖示控制鍵（回到定位／篩選／更新資料庫／設定），並有一個顯示免責聲明的設定頁 stub。

**Architecture:** Expo Router 檔案式路由，主地圖畫面 `app/(map)/index.tsx` 搭配 `react-native-maps`；定位狀態放在 Zustand store（`store/locationStore.ts`），透過 `expo-location` 前景定位取得座標與朝向；地圖上的兩種 Marker（車輛、執法點）與 4 個圖示按鈕都是獨立可重用元件；本階段資料來源是寫死在專案內的假資料（`data/seed/mockPoints.ts`），不接任何遠端服務。

**Tech Stack:** Expo (Managed Workflow, SDK 53+, TypeScript), Expo Router, react-native-maps, expo-location, zustand, @expo/vector-icons (Ionicons)

## Global Constraints

- 平台：iOS + Android 同時支援
- 只做前景定位（App 開啟時），不做背景常駐定位
- 語言：TypeScript
- 狀態管理統一用 Zustand，不用 Redux/Context
- 程式碼預設不加註解，除非有非顯而易見的原因需要說明
- 本階段不接任何真實資料來源，全部使用假資料；資料層與 OTA 更新留給下一階段的計畫

---

### Task 1: 初始化 Expo 專案與相依套件

**Files:**
- Create: `speed-camera-app/`（Expo CLI 產生的整個專案骨架：`package.json`、`app.json`、`app/`、`tsconfig.json` 等）

**Interfaces:**
- Produces: 可執行的 Expo 專案，後續所有 Task 都在此專案內新增檔案

- [ ] **Step 1: 產生 Expo 專案骨架**

在 `C:\Users\winuser\Downloads\speed-camera-app` 資料夾內執行（這個資料夾已經有 `.git` 與 `docs/`，如果 CLI 提示資料夾非空，選擇繼續，不會動到既有的 `.git` 或 `docs/`）：

```bash
npx create-expo-app@latest . --template default
```

- [ ] **Step 2: 安裝本階段需要的套件**

```bash
npx expo install react-native-maps expo-location zustand
```

- [ ] **Step 3: 確認專案型別檢查通過**

Run: `npx tsc --noEmit`
Expected: 沒有錯誤輸出（exit code 0）

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: 初始化 Expo 專案骨架"
```

---

### Task 2: 設定定位權限（app.json）

**Files:**
- Modify: `app.json`

**Interfaces:**
- Consumes: Task 1 產生的 `app.json`
- Produces: 具備 iOS/Android 定位權限說明文字的 App 設定

- [ ] **Step 1: 在 `app.json` 的 `"ios"` 物件內加入 `infoPlist`**

```json
"infoPlist": {
  "NSLocationWhenInUseUsageDescription": "此 App 需要使用您的位置，以顯示附近的科技執法提醒資訊。"
}
```

- [ ] **Step 2: 在 `app.json` 的 `"android"` 物件內加入 `permissions`**

```json
"permissions": ["ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION"]
```

- [ ] **Step 3: 在 `app.json` 的 `"plugins"` 陣列內加入 `expo-location` 設定**

```json
[
  "expo-location",
  {
    "locationWhenInUsePermission": "此 App 需要使用您的位置，以顯示附近的科技執法提醒資訊。"
  }
]
```

- [ ] **Step 4: 驗證設定檔正確**

Run: `npx expo-doctor`
Expected: 沒有跟 `app.json` 或 `expo-location` 相關的錯誤訊息

- [ ] **Step 5: Commit**

```bash
git add app.json
git commit -m "feat: 設定定位權限說明文字"
```

---

### Task 3: 建立假資料與違規類型樣式對照表

**Files:**
- Create: `data/seed/mockPoints.ts`
- Create: `components/map/violationStyles.ts`

**Interfaces:**
- Produces:
  - `type ViolationType = 'speed' | 'red_light' | 'yield_pedestrian'`
  - `interface EnforcementPoint { id: string; lat: number; lng: number; types: ViolationType[] }`
  - `mockPoints: EnforcementPoint[]`
  - `VIOLATION_COLORS: Record<ViolationType, string>`
  - `VIOLATION_ICONS: Record<ViolationType, string>`（Ionicons glyph 名稱）

- [ ] **Step 1: 建立 `data/seed/mockPoints.ts`**

座標先用台北車站周邊（方便之後在該區域測試；若你實際測試地點不同，之後可自行調整座標）：

```typescript
export type ViolationType = 'speed' | 'red_light' | 'yield_pedestrian';

export interface EnforcementPoint {
  id: string;
  lat: number;
  lng: number;
  types: ViolationType[];
}

export const mockPoints: EnforcementPoint[] = [
  { id: 'p1', lat: 25.0478, lng: 121.517, types: ['speed'] },
  { id: 'p2', lat: 25.0463, lng: 121.5178, types: ['red_light', 'yield_pedestrian'] },
  { id: 'p3', lat: 25.045, lng: 121.52, types: ['speed', 'red_light'] },
];
```

- [ ] **Step 2: 建立 `components/map/violationStyles.ts`**

顏色對照表取自設計文件第 7 節（本階段只用到假資料涵蓋的三種類型，其餘類型會在後續階段擴充）：

```typescript
import { ViolationType } from '../../data/seed/mockPoints';

export const VIOLATION_COLORS: Record<ViolationType, string> = {
  speed: '#FF3B30',
  red_light: '#FF0055',
  yield_pedestrian: '#FF2D55',
};

export const VIOLATION_ICONS: Record<ViolationType, string> = {
  speed: 'speedometer-outline',
  red_light: 'ellipse',
  yield_pedestrian: 'walk-outline',
};
```

- [ ] **Step 3: 確認型別檢查通過**

Run: `npx tsc --noEmit`
Expected: 沒有錯誤輸出

- [ ] **Step 4: Commit**

```bash
git add data/seed/mockPoints.ts components/map/violationStyles.ts
git commit -m "feat: 新增假資料與違規類型樣式對照表"
```

---

### Task 4: 定位狀態 Store

**Files:**
- Create: `store/locationStore.ts`

**Interfaces:**
- Consumes: `expo-location`、`zustand`
- Produces: `useLocationStore` hook，狀態形狀：
  ```typescript
  {
    coords: { latitude: number; longitude: number } | null;
    heading: number;
    hasPermission: boolean;
    errorMessage: string | null;
    start: () => Promise<void>;
  }
  ```

- [ ] **Step 1: 建立 `store/locationStore.ts`**

```typescript
import { create } from 'zustand';
import * as Location from 'expo-location';

interface LocationState {
  coords: { latitude: number; longitude: number } | null;
  heading: number;
  hasPermission: boolean;
  errorMessage: string | null;
  start: () => Promise<void>;
}

export const useLocationStore = create<LocationState>((set) => {
  let subscription: Location.LocationSubscription | null = null;

  return {
    coords: null,
    heading: 0,
    hasPermission: false,
    errorMessage: null,
    start: async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        set({ hasPermission: false, errorMessage: '未取得定位權限，請至系統設定開啟' });
        return;
      }

      set({ hasPermission: true, errorMessage: null });

      subscription?.remove();
      subscription = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.BestForNavigation,
          timeInterval: 1000,
          distanceInterval: 5,
        },
        (location) => {
          set({
            coords: {
              latitude: location.coords.latitude,
              longitude: location.coords.longitude,
            },
            heading: location.coords.heading ?? 0,
          });
        }
      );
    },
  };
});
```

- [ ] **Step 2: 確認型別檢查通過**

Run: `npx tsc --noEmit`
Expected: 沒有錯誤輸出

- [ ] **Step 3: Commit**

```bash
git add store/locationStore.ts
git commit -m "feat: 新增定位狀態 store"
```

---

### Task 5: 車輛 Marker 元件

**Files:**
- Create: `components/map/VehicleMarker.tsx`

**Interfaces:**
- Consumes: `react-native-maps` 的 `Marker`
- Produces: `VehicleMarker` component，props：`{ latitude: number; longitude: number; heading: number }`

- [ ] **Step 1: 建立 `components/map/VehicleMarker.tsx`**

車輛圖示暫用 Ionicons 的方向箭頭圖示，第五階段（視覺打磨）會換成客製車輛美術素材：

```tsx
import { Marker } from 'react-native-maps';
import { View, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface VehicleMarkerProps {
  latitude: number;
  longitude: number;
  heading: number;
}

export function VehicleMarker({ latitude, longitude, heading }: VehicleMarkerProps) {
  return (
    <Marker
      coordinate={{ latitude, longitude }}
      anchor={{ x: 0.5, y: 0.5 }}
      flat
      rotation={heading}
    >
      <View style={styles.wrapper}>
        <Ionicons name="navigate-outline" size={28} color="#007AFF" />
      </View>
    </Marker>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#007AFF',
  },
});
```

- [ ] **Step 2: 確認型別檢查通過**

Run: `npx tsc --noEmit`
Expected: 沒有錯誤輸出

- [ ] **Step 3: Commit**

```bash
git add components/map/VehicleMarker.tsx
git commit -m "feat: 新增車輛 Marker 元件"
```

---

### Task 6: 科技執法 Marker 元件

**Files:**
- Create: `components/map/EnforcementMarker.tsx`

**Interfaces:**
- Consumes: `EnforcementPoint`、`VIOLATION_COLORS`、`VIOLATION_ICONS`（Task 3）
- Produces: `EnforcementMarker` component，props：`{ point: EnforcementPoint }`

- [ ] **Step 1: 建立 `components/map/EnforcementMarker.tsx`**

```tsx
import { Marker } from 'react-native-maps';
import { View, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { EnforcementPoint } from '../../data/seed/mockPoints';
import { VIOLATION_COLORS, VIOLATION_ICONS } from './violationStyles';

export function EnforcementMarker({ point }: { point: EnforcementPoint }) {
  const primaryType = point.types[0];
  const color = VIOLATION_COLORS[primaryType];
  const iconName = VIOLATION_ICONS[primaryType];

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

- [ ] **Step 2: 確認型別檢查通過**

Run: `npx tsc --noEmit`
Expected: 沒有錯誤輸出

- [ ] **Step 3: Commit**

```bash
git add components/map/EnforcementMarker.tsx
git commit -m "feat: 新增科技執法 Marker 元件"
```

---

### Task 7: 圖示按鈕元件

**Files:**
- Create: `components/ui/IconButton.tsx`

**Interfaces:**
- Produces: `IconButton` component，props：`{ iconName: React.ComponentProps<typeof Ionicons>['name']; label: string; onPress: () => void }`

- [ ] **Step 1: 建立 `components/ui/IconButton.tsx`**

```tsx
import { Pressable, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface IconButtonProps {
  iconName: React.ComponentProps<typeof Ionicons>['name'];
  label: string;
  onPress: () => void;
}

export function IconButton({ iconName, label, onPress }: IconButtonProps) {
  return (
    <Pressable style={styles.button} onPress={onPress} accessibilityLabel={label}>
      <Ionicons name={iconName} size={24} color="#FFFFFF" />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#007AFF',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.25,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 2 },
    elevation: 4,
  },
});
```

- [ ] **Step 2: 確認型別檢查通過**

Run: `npx tsc --noEmit`
Expected: 沒有錯誤輸出

- [ ] **Step 3: Commit**

```bash
git add components/ui/IconButton.tsx
git commit -m "feat: 新增圖示按鈕元件"
```

---

### Task 8: 根路由與地圖主畫面

**Files:**
- Modify: `app/_layout.tsx`（覆蓋 Task 1 產生的預設內容）
- Create: `app/(map)/index.tsx`
- Delete: `app/(tabs)/`（Expo 預設範本產生的分頁範例畫面，本專案不使用）

**Interfaces:**
- Consumes: `useLocationStore`（Task 4）、`VehicleMarker`（Task 5）、`EnforcementMarker`（Task 6）、`IconButton`（Task 7）、`mockPoints`（Task 3）
- Produces: App 進入後看到的地圖主畫面；`router.push('/settings')` 導向 Task 9 建立的設定頁

- [ ] **Step 1: 刪除 Expo 預設範本的分頁畫面**

```bash
rm -rf "app/(tabs)"
```

- [ ] **Step 2: 覆蓋 `app/_layout.tsx`**

```tsx
import { Stack } from 'expo-router';

export default function RootLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(map)/index" />
      <Stack.Screen name="settings" options={{ headerShown: true, title: '設定' }} />
    </Stack>
  );
}
```

- [ ] **Step 3: 建立 `app/(map)/index.tsx`**

```tsx
import { useEffect, useRef } from 'react';
import { StyleSheet, View, Text, ActivityIndicator } from 'react-native';
import MapView, { Region } from 'react-native-maps';
import { router } from 'expo-router';
import { useLocationStore } from '../../store/locationStore';
import { VehicleMarker } from '../../components/map/VehicleMarker';
import { EnforcementMarker } from '../../components/map/EnforcementMarker';
import { IconButton } from '../../components/ui/IconButton';
import { mockPoints } from '../../data/seed/mockPoints';

const DEFAULT_REGION: Region = {
  latitude: 25.0478,
  longitude: 121.517,
  latitudeDelta: 0.02,
  longitudeDelta: 0.02,
};

export default function MapScreen() {
  const { coords, heading, hasPermission, errorMessage, start } = useLocationStore();
  const mapRef = useRef<MapView>(null);

  useEffect(() => {
    start();
  }, [start]);

  const handleRecenter = () => {
    if (!coords) return;
    mapRef.current?.animateToRegion(
      {
        latitude: coords.latitude,
        longitude: coords.longitude,
        latitudeDelta: 0.01,
        longitudeDelta: 0.01,
      },
      500
    );
  };

  if (errorMessage) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{errorMessage}</Text>
      </View>
    );
  }

  if (!hasPermission || !coords) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
        <Text>正在取得定位...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <MapView ref={mapRef} style={StyleSheet.absoluteFill} initialRegion={DEFAULT_REGION}>
        <VehicleMarker latitude={coords.latitude} longitude={coords.longitude} heading={heading} />
        {mockPoints.map((point) => (
          <EnforcementMarker key={point.id} point={point} />
        ))}
      </MapView>

      <View style={styles.controls}>
        <IconButton iconName="locate-outline" label="回到定位" onPress={handleRecenter} />
        <IconButton iconName="filter-outline" label="篩選" onPress={() => {}} />
        <IconButton iconName="refresh-outline" label="更新資料庫" onPress={() => {}} />
        <IconButton iconName="settings-outline" label="設定" onPress={() => router.push('/settings')} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  errorText: { textAlign: 'center', color: '#FF3B30' },
  controls: {
    position: 'absolute',
    bottom: 32,
    left: 0,
    right: 0,
    flexDirection: 'row',
    justifyContent: 'space-evenly',
  },
});
```

註：篩選／更新資料庫按鈕本階段先接空函式，功能留給第二、三階段的計畫實作。

- [ ] **Step 4: 確認型別檢查通過**

Run: `npx tsc --noEmit`
Expected: 沒有錯誤輸出

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: 建立地圖主畫面與根路由"
```

---

### Task 9: 設定頁 stub（含免責聲明）

**Files:**
- Create: `app/settings.tsx`

**Interfaces:**
- Consumes: 無
- Produces: `/settings` 路由畫面

- [ ] **Step 1: 建立 `app/settings.tsx`**

```tsx
import { View, Text, StyleSheet, ScrollView } from 'react-native';

export default function SettingsScreen() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.disclaimerTitle}>免責聲明</Text>
      <Text style={styles.disclaimerBody}>
        本 App 資訊來源為政府開放資料與各縣市警局公告，僅供參考，實際執法標準與地點以官方公告為準，請遵守道路交通安全規則。
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F2F2F7' },
  content: { padding: 20 },
  disclaimerTitle: { fontSize: 18, fontWeight: '600', marginBottom: 8 },
  disclaimerBody: { fontSize: 14, color: '#3C3C43', lineHeight: 20 },
});
```

- [ ] **Step 2: 確認型別檢查通過**

Run: `npx tsc --noEmit`
Expected: 沒有錯誤輸出

- [ ] **Step 3: Commit**

```bash
git add app/settings.tsx
git commit -m "feat: 新增設定頁與免責聲明"
```

---

### Task 10: 實機驗證（Expo Go）

**Files:**
- 無新增檔案，僅驗證

**Interfaces:**
- Consumes: Task 1-9 的全部產出

- [ ] **Step 1: 啟動開發伺服器**

Run: `npx expo start`
Expected: 終端機顯示 QR Code 與 "Metro waiting on..." 訊息

- [ ] **Step 2: 用 iPhone 的 Expo Go App 掃描 QR Code**

- [ ] **Step 3: 逐項確認以下行為**

  - [ ] App 啟動後跳出定位權限請求，允許後地圖正常顯示
  - [ ] 地圖上出現車輛 Marker，隨你移動位置更新（室內測試可原地觀察座標是否有微幅飄移更新）
  - [ ] 地圖上出現 3 個假資料科技執法 Marker，顏色與圖示依違規類型不同（測速紅色／閃電圖示、闖紅燈紅色圓點、未禮讓行人粉紅色行走圖示）
  - [ ] 點擊「回到定位」按鈕，地圖視角會移回目前位置
  - [ ] 點擊「設定」按鈕，會導向設定頁並看到免責聲明文字
  - [ ] 「篩選」「更新資料庫」按鈕存在且可點擊（本階段無實際功能，屬預期行為）

- [ ] **Step 4: 若座標不在假資料涵蓋範圍（台北車站周邊），修改 `data/seed/mockPoints.ts` 內座標為你目前實際所在地附近，重新整理 App 再驗證一次 Marker 是否正確顯示**

- [ ] **Step 5: 全部確認無誤後，記錄完成狀態**

```bash
git log --oneline
```

Expected: 看到 Task 1-9 的所有 commit 記錄

---

## 完成後

第一階段完成、實機驗證通過後，回報結果。下一步會針對設計文件第 9 節的第二階段（資料層＋OTA 更新模組）另外出一份實作計畫。
