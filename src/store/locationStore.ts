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
