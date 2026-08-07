import { ViolationType } from '../../components/map/violationStyles';

export interface EnforcementPoint {
  id: string;
  lat: number;
  lng: number;
  types: ViolationType[];
}

// App 剛安裝、AsyncStorage 還沒有任何快取時的保底資料（避免地圖完全空白）。
// 取自警政署全國測速執法設置點真實資料的一小部分（見 scrapers/national_speed.py）。
export const fallbackPoints: EnforcementPoint[] = [
  { id: 'fallback-1', lat: 25.033, lng: 121.5654, types: ['speed'] },
  { id: 'fallback-2', lat: 25.0478, lng: 121.517, types: ['speed'] },
  { id: 'fallback-3', lat: 24.1477, lng: 120.6736, types: ['speed'] },
];
