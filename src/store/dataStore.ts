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
  // 讀取或解析失敗（AsyncStorage 原生模組錯誤、或存了損毀/舊格式的字串）時
  // 視同「沒有快取」，不能整個拋出去——loadFromCacheOrFetch 呼叫這裡時沒有包
  // try/catch，一旦拋出例外會讓 isLoading 卡在 true 永遠出不來。
  try {
    const raw = await AsyncStorage.getItem(CACHE_KEY);
    return raw ? (JSON.parse(raw) as CachedPayload) : null;
  } catch {
    return null;
  }
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
