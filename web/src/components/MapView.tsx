import { useState, useEffect } from 'react';
import Map, { Marker, Popup, NavigationControl, ScaleControl } from 'react-map-gl/maplibre';
import { api, SurfCandidate } from '../services/api';
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

  // Fetch on mount and when filters change
  useEffect(() => {
    fetchCandidates();
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
                <div><strong>Direction:</strong> {selectedCandidate.properties.swell.dir_deep}°</div>
                <div><strong>Wind:</strong> {selectedCandidate.properties.wind.spd}m/s @ {selectedCandidate.properties.wind.dir}°</div>
                <div><strong>Depth:</strong> {selectedCandidate.properties.depth_m}m</div>
              </div>

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
        onClick={fetchCandidates}
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
    </div>
  );
};

export default MapView;
