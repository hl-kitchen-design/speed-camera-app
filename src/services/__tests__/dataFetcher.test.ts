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
