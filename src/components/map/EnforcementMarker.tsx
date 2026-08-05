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
