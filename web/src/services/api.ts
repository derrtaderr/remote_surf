/**
 * API client for Remote Surf backend
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface BBox {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

export interface ScanParams {
  bbox: BBox;
  minScore?: number;
  spacing?: number;
  time?: string;
}

export interface SurfCandidate {
  type: 'Feature';
  geometry: {
    type: 'Point';
    coordinates: [number, number];
  };
  properties: {
    id: string;
    time: string | null;
    final_score: number;
    physics_score: number;
    components: {
      base: number;
      expo: number;
      refract: number;
      wind: number;
      tide: number;
      period: number;
      quality: number;
    };
    swell: {
      hs: number;
      tp: number;
      dir_deep: number;
      dir_nearshore: number;
    };
    wind: {
      spd: number;
      dir: number;
    };
    shore_normal: number;
    curvature: number;
    depth_m: number;
    slope: number;
  };
}

export interface ScanResponse {
  type: 'FeatureCollection';
  features: SurfCandidate[];
  metadata?: {
    bbox: [number, number, number, number];
    time: string | null;
    min_score: number;
    spacing_m: number;
    num_candidates: number;
    data_sources: {
      grib: string;
      bathymetry: string;
      coastline: string;
    };
  };
}

export interface WindFeature {
  type: 'Feature';
  geometry: {
    type: 'Point';
    coordinates: [number, number];
  };
  properties: {
    speed: number;
    direction: number;
    u: number;
    v: number;
  };
}

export interface SwellFeature {
  type: 'Feature';
  geometry: {
    type: 'LineString';
    coordinates: [[number, number], [number, number]];
  };
  properties: {
    height: number;
    period: number;
    direction: number;
    dir_from: number;
    dir_to: number;
  };
}

export interface WindLayerResponse {
  type: 'FeatureCollection';
  features: WindFeature[];
}

export interface SwellLayerResponse {
  type: 'FeatureCollection';
  features: SwellFeature[];
}

export class RemoteSurfAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Scan coastline for surf candidates
   */
  async scan(params: ScanParams): Promise<ScanResponse> {
    const { bbox, minScore = 0, spacing = 500, time } = params;

    const bboxStr = `${bbox.minLon},${bbox.minLat},${bbox.maxLon},${bbox.maxLat}`;

    const queryParams = new URLSearchParams({
      bbox: bboxStr,
      min_score: minScore.toString(),
      spacing: spacing.toString(),
    });

    if (time) {
      queryParams.append('time', time);
    }

    const url = `${this.baseUrl}/scan?${queryParams}`;

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get wind layer (barbs)
   */
  async getWindLayer(
    bbox: BBox,
    spacing: number = 0.5,
    time?: string
  ): Promise<WindLayerResponse> {
    const bboxStr = `${bbox.minLon},${bbox.minLat},${bbox.maxLon},${bbox.maxLat}`;

    const queryParams = new URLSearchParams({
      bbox: bboxStr,
      spacing: spacing.toString(),
    });

    if (time) {
      queryParams.append('time', time);
    }

    const url = `${this.baseUrl}/layer/wind?${queryParams}`;

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Wind layer error: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get deep-water swell layer (arrows)
   */
  async getSwellLayer(
    bbox: BBox,
    spacing: number = 0.5,
    time?: string
  ): Promise<SwellLayerResponse> {
    const bboxStr = `${bbox.minLon},${bbox.minLat},${bbox.maxLon},${bbox.maxLat}`;

    const queryParams = new URLSearchParams({
      bbox: bboxStr,
      spacing: spacing.toString(),
    });

    if (time) {
      queryParams.append('time', time);
    }

    const url = `${this.baseUrl}/layer/swell/deep?${queryParams}`;

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Swell layer error: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Health check
   */
  async health(): Promise<{ status: string; version: string }> {
    const response = await fetch(`${this.baseUrl}/health`);

    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }

    return response.json();
  }
}

// Export singleton instance
export const api = new RemoteSurfAPI();
