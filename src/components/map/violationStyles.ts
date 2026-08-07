export type ViolationType =
  | 'speed'
  | 'red_light'
  | 'yield_pedestrian'
  | 'illegal_turn'
  | 'two_stage_turn'
  | 'bus_lane'
  | 'keep_clear'
  | 'illegal_parking'
  | 'cross_double_line'
  | 'restricted_lane';

export const VIOLATION_COLORS: Record<ViolationType, string> = {
  speed: '#FF3B30',
  red_light: '#FF0055',
  yield_pedestrian: '#FF2D55',
  illegal_turn: '#007AFF',
  two_stage_turn: '#FF9500',
  bus_lane: '#AF52DE',
  keep_clear: '#34C759',
  illegal_parking: '#FFCC00',
  cross_double_line: '#5856D6',
  restricted_lane: '#8E8E93',
};

export const VIOLATION_ICONS: Record<ViolationType, string> = {
  speed: 'speedometer-outline',
  red_light: 'ellipse',
  yield_pedestrian: 'walk-outline',
  illegal_turn: 'return-up-back-outline',
  two_stage_turn: 'refresh-outline',
  bus_lane: 'bus-outline',
  keep_clear: 'square-outline',
  illegal_parking: 'car-outline',
  cross_double_line: 'remove-outline',
  restricted_lane: 'ban-outline',
};
