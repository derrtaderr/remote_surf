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
    tide?: {
      height_m: number;
      label: string;
      station: string;
    };
    anchorage?: {
      distance_nm: number;
      depth_m: number;
      lee_shore_risk: string;
      fetch: string;
      dinghy_landing: string;
    };
    remoteness?: number;
    flags?: string[];
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

export interface BestWindow {
  start: string;
  end: string;
  avg_score: number;
  peak_score: number;
  duration_hours: number;
}

export interface TimeseriesResponse {
  location: {
    lat: number;
    lon: number;
    shore_normal: number;
    depth_m: number;
  };
  forecast: {
    start: string;
    end: string;
    interval_hours: number;
    hours: number;
  };
  timeseries: {
    times: string[];
    scores: number[];
    tide_heights_m: number[];
    wave_heights_m: number[];
  };
  best_windows: BestWindow[];
  summary: {
    avg_score: number;
    max_score: number;
    min_score: number;
  };
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
   * Get timeseries forecast for a location
   */
  async getTimeseries(
    lat: number,
    lon: number,
    shore_normal: number,
    depth: number = 10.0,
    slope: number = 0.05,
    hours: number = 120
  ): Promise<TimeseriesResponse> {
    const queryParams = new URLSearchParams({
      lat: lat.toString(),
      lon: lon.toString(),
      shore_normal: shore_normal.toString(),
      depth: depth.toString(),
      slope: slope.toString(),
      hours: hours.toString(),
    });

    const url = `${this.baseUrl}/timeseries?${queryParams}`;

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Timeseries error: ${response.statusText}`);
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
