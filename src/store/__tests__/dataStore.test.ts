jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock')
);

import AsyncStorage from '@react-native-async-storage/async-storage';
import { useDataStore } from '../dataStore';

global.fetch = jest.fn();

describe('useDataStore.loadFromCacheOrFetch', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockReset();
    useDataStore.setState({ points: [], dataVersion: null, isLoading: false, error: null });
  });

  it('does not get stuck loading when the cache read itself throws', async () => {
    // 2026-08-07 Task 13 review 發現：readCache() 以前沒有包 try/catch，
    // AsyncStorage 讀取失敗或存了損毀的字串時會直接拋出，而 loadFromCacheOrFetch
    // 呼叫 readCache() 那一行沒有包 try/catch，會讓 isLoading 卡在 true 出不來。
    (AsyncStorage.getItem as jest.Mock).mockRejectedValue(new Error('原生模組壞掉'));
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({ ok: true, json: async () => [{ id: 'a' }] })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ data_version: 'v1' }) });

    await useDataStore.getState().loadFromCacheOrFetch();

    expect(useDataStore.getState().isLoading).toBe(false);
    expect(useDataStore.getState().points).toEqual([{ id: 'a' }]);
  });
});
