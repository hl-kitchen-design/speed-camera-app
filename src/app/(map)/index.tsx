import { useEffect, useRef } from 'react';
import { StyleSheet, View, Text, ActivityIndicator } from 'react-native';
import MapView, { Region } from 'react-native-maps';
import { router } from 'expo-router';
import { useLocationStore } from '../../store/locationStore';
import { VehicleMarker } from '../../components/map/VehicleMarker';
import { EnforcementMarker } from '../../components/map/EnforcementMarker';
import { IconButton } from '../../components/ui/IconButton';
import { useDataStore } from '../../store/dataStore';
import { fallbackPoints } from '../../data/seed/mockPoints';

const DEFAULT_REGION: Region = {
  latitude: 25.0478,
  longitude: 121.517,
  latitudeDelta: 0.02,
  longitudeDelta: 0.02,
};

export default function MapScreen() {
  const { coords, heading, hasPermission, errorMessage, start } = useLocationStore();
  const { points: remotePoints, loadFromCacheOrFetch, refresh } = useDataStore();
  const mapRef = useRef<MapView>(null);

  useEffect(() => {
    start();
  }, [start]);

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
        {enforcementPoints.map((point) => (
          <EnforcementMarker key={point.id} point={point} />
        ))}
      </MapView>

      <View style={styles.controls}>
        <IconButton iconName="locate-outline" label="回到定位" onPress={handleRecenter} />
        <IconButton iconName="filter-outline" label="篩選" onPress={() => {}} />
        <IconButton iconName="refresh-outline" label="更新資料庫" onPress={refresh} />
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
