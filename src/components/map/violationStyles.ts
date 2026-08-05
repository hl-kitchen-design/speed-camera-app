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
