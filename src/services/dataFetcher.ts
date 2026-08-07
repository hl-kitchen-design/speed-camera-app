export const DATA_BASE_URL = 'https://hl-kitchen-design.github.io/speed-camera-app';

export interface RemoteEnforcementPoint {
  id: string;
  county: string;
  district: string;
  address: string;
  lat: number | null;
  lng: number | null;
  violation_types: string[];
  source_name: string;
  source_url: string;
  data_quality: 'coords' | 'geocoded' | 'no-coords';
  fetched_at: string;
}

interface VersionInfo {
  data_version: string;
  point_count: number;
  parking_count: number;
  section_count: number;
}

export async function fetchRemoteData(): Promise<{
  points: RemoteEnforcementPoint[];
  dataVersion: string;
}> {
  const pointsResponse = await fetch(`${DATA_BASE_URL}/points.json`);
  if (!pointsResponse.ok) {
    throw new Error(`points.json 下載失敗：HTTP ${pointsResponse.status}`);
  }
  const points: RemoteEnforcementPoint[] = await pointsResponse.json();

  const versionResponse = await fetch(`${DATA_BASE_URL}/version.json`);
  if (!versionResponse.ok) {
    throw new Error(`version.json 下載失敗：HTTP ${versionResponse.status}`);
  }
  const version: VersionInfo = await versionResponse.json();

  return { points, dataVersion: version.data_version };
}
