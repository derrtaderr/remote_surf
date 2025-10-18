import { useState, useEffect } from 'react';
import Map, { Marker, Popup, NavigationControl, ScaleControl, Source, Layer } from 'react-map-gl/maplibre';
import { api, SurfCandidate, WindFeature, SwellFeature } from '../services/api';
import type { CircleLayer, LineLayer } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

interface MapViewProps {
  minScore: number;
  spacing: number;
}

const MapView = ({ minScore, spacing }: MapViewProps) => {
  const [candidates, setCandidates] = useState<SurfCandidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<SurfCandidate | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Layer data
  const [windData, setWindData] = useState<{ type: 'FeatureCollection', features: WindFeature[] } | null>(null);
  const [swellData, setSwellData] = useState<{ type: 'FeatureCollection', features: SwellFeature[] } | null>(null);

  // Layer toggles
  const [showWind, setShowWind] = useState(true);
  const [showSwell, setShowSwell] = useState(true);

  const [viewState, setViewState] = useState({
    longitude: -112,
    latitude: 25,
    zoom: 7
  });

  // Fetch candidates when filters change or map moves significantly
  const fetchCandidates = async () => {
    setLoading(true);
    setError(null);

    try {
      // Calculate bbox from current view
      const padding = 2; // degrees
      const bbox = {
        minLon: viewState.longitude - padding,
        minLat: viewState.latitude - padding,
        maxLon: viewState.longitude + padding,
        maxLat: viewState.latitude + padding,
      };

      const response = await api.scan({ bbox, minScore, spacing });
      setCandidates(response.features);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch candidates');
      console.error('Scan error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch wind and swell layers
  const fetchLayers = async () => {
    try {
      const padding = 2; // degrees
      const bbox = {
        minLon: viewState.longitude - padding,
        minLat: viewState.latitude - padding,
        maxLon: viewState.longitude + padding,
        maxLat: viewState.latitude + padding,
      };

      // Fetch wind and swell in parallel
      const [wind, swell] = await Promise.all([
        api.getWindLayer(bbox, 0.5),
        api.getSwellLayer(bbox, 0.5)
      ]);

      setWindData(wind);
      setSwellData(swell);
    } catch (err) {
      console.error('Layer fetch error:', err);
    }
  };

  // Fetch on mount and when filters change
  useEffect(() => {
    fetchCandidates();
    fetchLayers();
  }, [minScore, spacing]);

  // Get marker color based on score
  const getMarkerColor = (score: number): string => {
    if (score >= 8) return '#22c55e'; // green
    if (score >= 6) return '#eab308'; // yellow
    if (score >= 4) return '#f97316'; // orange
    if (score >= 2) return '#ef4444'; // red
    return '#6b7280'; // gray
  };

  // Get score label
  const getScoreLabel = (score: number): string => {
    if (score >= 8) return 'Excellent';
    if (score >= 6) return 'Good';
    if (score >= 4) return 'Fair';
    if (score >= 2) return 'Poor';
    return 'Minimal';
  };

  // Wind barb layer style (simplified to circles, full barbs would need custom symbols)
  const windPointLayer: CircleLayer = {
    id: 'wind-points',
    type: 'circle',
    paint: {
      'circle-radius': [
        'interpolate',
        ['linear'],
        ['get', 'speed'],
        0, 3,
        15, 8
      ],
      'circle-color': '#3b82f6',
      'circle-opacity': 0.6,
      'circle-stroke-width': 1,
      'circle-stroke-color': '#1e40af'
    }
  };

  // Swell arrow layer style
  const swellArrowLayer: LineLayer = {
    id: 'swell-arrows',
    type: 'line',
    paint: {
      'line-color': [
        'interpolate',
        ['linear'],
        ['get', 'height'],
        0, '#60a5fa',
        2, '#3b82f6',
        4, '#2563eb'
      ],
      'line-width': [
        'interpolate',
        ['linear'],
        ['get', 'height'],
        0, 2,
        4, 6
      ],
      'line-opacity': 0.7
    }
  };

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Map
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        style={{ width: '100%', height: '100%' }}
        mapStyle="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"
      >
        <NavigationControl position="top-right" />
        <ScaleControl />

        {/* Swell arrows layer */}
        {showSwell && swellData && (
          <Source id="swell-source" type="geojson" data={swellData}>
            <Layer {...swellArrowLayer} />
          </Source>
        )}

        {/* Wind points layer */}
        {showWind && windData && (
          <Source id="wind-source" type="geojson" data={windData}>
            <Layer {...windPointLayer} />
          </Source>
        )}

        {/* Render candidate markers */}
        {candidates.map((candidate) => (
          <Marker
            key={candidate.properties.id}
            longitude={candidate.geometry.coordinates[0]}
            latitude={candidate.geometry.coordinates[1]}
            anchor="bottom"
            onClick={(e) => {
              e.originalEvent.stopPropagation();
              setSelectedCandidate(candidate);
            }}
          >
            <div
              style={{
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                backgroundColor: getMarkerColor(candidate.properties.final_score),
                border: '2px solid white',
                boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '10px',
                fontWeight: 'bold',
                color: 'white',
              }}
              title={`Score: ${candidate.properties.final_score.toFixed(1)}`}
            >
              {candidate.properties.final_score.toFixed(0)}
            </div>
          </Marker>
        ))}

        {/* Popup for selected candidate */}
        {selectedCandidate && (
          <Popup
            longitude={selectedCandidate.geometry.coordinates[0]}
            latitude={selectedCandidate.geometry.coordinates[1]}
            anchor="top"
            onClose={() => setSelectedCandidate(null)}
            closeButton={true}
            closeOnClick={false}
          >
            <div style={{ minWidth: '250px', padding: '8px' }}>
              <h3 style={{ margin: '0 0 8px 0', fontSize: '16px' }}>
                Surf Candidate
              </h3>

              <div style={{ marginBottom: '12px' }}>
                <div style={{
                  fontSize: '24px',
                  fontWeight: 'bold',
                  color: getMarkerColor(selectedCandidate.properties.final_score)
                }}>
                  {selectedCandidate.properties.final_score.toFixed(1)} / 10
                </div>
                <div style={{ fontSize: '12px', color: '#6b7280' }}>
                  {getScoreLabel(selectedCandidate.properties.final_score)}
                </div>
              </div>

              <div style={{ fontSize: '13px', lineHeight: '1.6' }}>
                <div><strong>Swell:</strong> {selectedCandidate.properties.swell.hs}m @ {selectedCandidate.properties.swell.tp}s</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <strong>Deep-water:</strong> {selectedCandidate.properties.swell.dir_deep}°
                  <svg width="20" height="20" style={{ transform: `rotate(${selectedCandidate.properties.swell.dir_deep}deg)` }}>
                    <path d="M10 2 L10 18 M10 2 L6 6 M10 2 L14 6" stroke="#2563eb" strokeWidth="2" fill="none"/>
                  </svg>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <strong>Nearshore:</strong> {selectedCandidate.properties.swell.dir_nearshore}°
                  <svg width="20" height="20" style={{ transform: `rotate(${selectedCandidate.properties.swell.dir_nearshore}deg)` }}>
                    <path d="M10 2 L10 18 M10 2 L6 6 M10 2 L14 6" stroke="#22c55e" strokeWidth="2" fill="none"/>
                  </svg>
                </div>
                <div><strong>Wind:</strong> {selectedCandidate.properties.wind.spd}m/s @ {selectedCandidate.properties.wind.dir}°</div>
                {selectedCandidate.properties.tide ? (
                  <div><strong>Tide:</strong> {selectedCandidate.properties.tide.height_m}m ({selectedCandidate.properties.tide.label})</div>
                ) : (
                  <div><strong>Tide:</strong> N/A</div>
                )}
                <div><strong>Depth:</strong> {selectedCandidate.properties.depth_m}m</div>
              </div>

              {selectedCandidate.properties.anchorage && (
                <div style={{ marginTop: '12px', fontSize: '12px', lineHeight: '1.5', borderTop: '1px solid #e5e7eb', paddingTop: '8px' }}>
                  <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>Anchorage</div>
                  <div>Distance: {selectedCandidate.properties.anchorage.distance_nm}nm</div>
                  <div>Depth: {selectedCandidate.properties.anchorage.depth_m}m</div>
                  <div>Lee shore: {selectedCandidate.properties.anchorage.lee_shore_risk}</div>
                  <div>Dinghy: {selectedCandidate.properties.anchorage.dinghy_landing}</div>
                </div>
              )}

              {selectedCandidate.properties.flags && selectedCandidate.properties.flags.length > 0 && (
                <div style={{ marginTop: '8px', fontSize: '11px' }}>
                  {selectedCandidate.properties.flags.map((flag: string, i: number) => (
                    <div key={i} style={{ color: '#dc2626', marginBottom: '2px' }}>⚠ {flag}</div>
                  ))}
                </div>
              )}

              <div style={{ marginTop: '12px', fontSize: '11px', color: '#6b7280' }}>
                {selectedCandidate.geometry.coordinates[1].toFixed(4)}°N, {selectedCandidate.geometry.coordinates[0].toFixed(4)}°E
              </div>
            </div>
          </Popup>
        )}
      </Map>

      {/* Loading overlay */}
      {loading && (
        <div style={{
          position: 'absolute',
          top: '16px',
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'rgba(0,0,0,0.8)',
          color: 'white',
          padding: '8px 16px',
          borderRadius: '4px',
          fontSize: '14px',
          zIndex: 10
        }}>
          Loading candidates...
        </div>
      )}

      {/* Error message */}
      {error && (
        <div style={{
          position: 'absolute',
          top: '16px',
          left: '50%',
          transform: 'translateX(-50%)',
          background: '#ef4444',
          color: 'white',
          padding: '8px 16px',
          borderRadius: '4px',
          fontSize: '14px',
          zIndex: 10
        }}>
          Error: {error}
        </div>
      )}

      {/* Candidate count */}
      <div style={{
        position: 'absolute',
        bottom: '16px',
        left: '16px',
        background: 'rgba(255,255,255,0.95)',
        padding: '8px 12px',
        borderRadius: '4px',
        fontSize: '13px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
        zIndex: 10
      }}>
        {candidates.length} candidates found
      </div>

      {/* Refresh button */}
      <button
        onClick={() => {
          fetchCandidates();
          fetchLayers();
        }}
        disabled={loading}
        style={{
          position: 'absolute',
          bottom: '16px',
          right: '16px',
          background: '#0ea5e9',
          color: 'white',
          border: 'none',
          padding: '10px 16px',
          borderRadius: '4px',
          fontSize: '14px',
          fontWeight: 'bold',
          cursor: 'pointer',
          boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
          zIndex: 10,
          opacity: loading ? 0.6 : 1
        }}
      >
        {loading ? 'Loading...' : 'Refresh'}
      </button>

      {/* Layer toggles */}
      <div style={{
        position: 'absolute',
        top: '16px',
        left: '16px',
        background: 'rgba(255,255,255,0.95)',
        padding: '12px',
        borderRadius: '4px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
        zIndex: 10,
        fontSize: '13px'
      }}>
        <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>Layers</div>

        <label style={{ display: 'flex', alignItems: 'center', marginBottom: '6px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showSwell}
            onChange={(e) => setShowSwell(e.target.checked)}
            style={{ marginRight: '6px' }}
          />
          <span style={{ display: 'flex', alignItems: 'center' }}>
            <span style={{
              width: '20px',
              height: '3px',
              background: 'linear-gradient(to right, #60a5fa, #2563eb)',
              marginRight: '6px',
              borderRadius: '2px'
            }}></span>
            Swell
          </span>
        </label>

        <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showWind}
            onChange={(e) => setShowWind(e.target.checked)}
            style={{ marginRight: '6px' }}
          />
          <span style={{ display: 'flex', alignItems: 'center' }}>
            <span style={{
              width: '12px',
              height: '12px',
              background: '#3b82f6',
              marginRight: '6px',
              borderRadius: '50%',
              border: '1px solid #1e40af'
            }}></span>
            Wind
          </span>
        </label>
      </div>
    </div>
  );
};

export default MapView;
