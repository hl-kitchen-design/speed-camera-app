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
