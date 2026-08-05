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
