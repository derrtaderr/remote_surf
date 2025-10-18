import { useState, useEffect } from 'react';
import {
  loadAlerts,
  createAlert,
  deleteAlert,
  toggleAlert,
  getAlertStats,
  SurfAlert
} from '../utils/surfAlerts';

/**
 * Surf Alerts Management Panel
 *
 * Allows users to create and manage surf condition alerts.
 */
const SurfAlertsPanel = () => {
  const [alerts, setAlerts] = useState<SurfAlert[]>([]);
  const [showPanel, setShowPanel] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    lat: 0,
    lon: 0,
    minScore: 6,
    minHeight: 1.0,
    maxHeight: 6.0,
    minPeriod: 10,
    maxWind: 8
  });

  useEffect(() => {
    loadAlertsFromStorage();
  }, []);

  const loadAlertsFromStorage = () => {
    const loaded = loadAlerts();
    setAlerts(loaded);
  };

  const handleCreate = () => {
    if (!formData.name.trim()) {
      alert('Please enter an alert name');
      return;
    }

    createAlert({
      name: formData.name,
      location: {
        lat: formData.lat,
        lon: formData.lon
      },
      conditions: {
        minScore: formData.minScore,
        minHeight: formData.minHeight,
        maxHeight: formData.maxHeight,
        minPeriod: formData.minPeriod,
        maxWind: formData.maxWind
      }
    });

    // Reset form
    setFormData({
      name: '',
      lat: 0,
      lon: 0,
      minScore: 6,
      minHeight: 1.0,
      maxHeight: 6.0,
      minPeriod: 10,
      maxWind: 8
    });

    setShowCreateForm(false);
    loadAlertsFromStorage();
  };

  const handleToggle = (id: string) => {
    toggleAlert(id);
    loadAlertsFromStorage();
  };

  const handleDelete = (id: string) => {
    if (confirm('Delete this alert?')) {
      deleteAlert(id);
      loadAlertsFromStorage();
    }
  };

  const stats = getAlertStats();

  return (
    <>
      {/* Alert Button */}
      <button
        onClick={() => setShowPanel(!showPanel)}
        style={{
          position: 'absolute',
          top: '16px',
          right: '60px',
          background: showPanel ? '#0c4a6e' : '#0ea5e9',
          color: 'white',
          border: 'none',
          borderRadius: '50%',
          width: '44px',
          height: '44px',
          fontSize: '20px',
          cursor: 'pointer',
          boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
          zIndex: 100,
          touchAction: 'manipulation',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
        title="Surf Alerts"
      >
        🔔
        {stats.enabled > 0 && (
          <span style={{
            position: 'absolute',
            top: '-4px',
            right: '-4px',
            background: '#ef4444',
            color: 'white',
            borderRadius: '50%',
            width: '18px',
            height: '18px',
            fontSize: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold'
          }}>
            {stats.enabled}
          </span>
        )}
      </button>

      {/* Alerts Panel */}
      {showPanel && (
        <div style={{
          position: 'absolute',
          top: '70px',
          right: '16px',
          background: 'rgba(255,255,255,0.98)',
          borderRadius: '8px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
          zIndex: 100,
          width: '320px',
          maxHeight: '500px',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}>
          {/* Header */}
          <div style={{
            padding: '16px',
            borderBottom: '1px solid #e5e7eb',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px', color: '#0c4a6e' }}>
                Surf Alerts
              </h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#6b7280' }}>
                {stats.enabled} active
              </p>
            </div>
            <button
              onClick={() => setShowCreateForm(true)}
              style={{
                background: '#0ea5e9',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                padding: '6px 12px',
                fontSize: '14px',
                fontWeight: 'bold',
                cursor: 'pointer'
              }}
            >
              + New
            </button>
          </div>

          {/* Alert List */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '8px'
          }}>
            {alerts.length === 0 ? (
              <div style={{
                padding: '32px 16px',
                textAlign: 'center',
                color: '#6b7280',
                fontSize: '14px'
              }}>
                No alerts yet. Create one to get notified when surf conditions match your preferences.
              </div>
            ) : (
              alerts.map((alert) => (
                <div
                  key={alert.id}
                  style={{
                    background: alert.enabled ? 'white' : '#f3f4f6',
                    border: `1px solid ${alert.enabled ? '#0ea5e9' : '#d1d5db'}`,
                    borderRadius: '6px',
                    padding: '12px',
                    marginBottom: '8px',
                    opacity: alert.enabled ? 1 : 0.6
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '8px' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '14px', fontWeight: 'bold', color: '#0c4a6e' }}>
                        {alert.name}
                      </div>
                      <div style={{ fontSize: '11px', color: '#6b7280', marginTop: '2px' }}>
                        {alert.location.lat.toFixed(4)}°, {alert.location.lon.toFixed(4)}°
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <button
                        onClick={() => handleToggle(alert.id)}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          fontSize: '18px',
                          cursor: 'pointer',
                          padding: '4px'
                        }}
                        title={alert.enabled ? 'Disable' : 'Enable'}
                      >
                        {alert.enabled ? '🔔' : '🔕'}
                      </button>
                      <button
                        onClick={() => handleDelete(alert.id)}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          fontSize: '16px',
                          cursor: 'pointer',
                          padding: '4px',
                          color: '#ef4444'
                        }}
                        title="Delete"
                      >
                        ×
                      </button>
                    </div>
                  </div>

                  <div style={{ fontSize: '12px', color: '#4b5563', lineHeight: '1.5' }}>
                    <div>Score ≥ {alert.conditions.minScore}/10</div>
                    {alert.conditions.minHeight !== undefined && (
                      <div>Height: {alert.conditions.minHeight}-{alert.conditions.maxHeight}m</div>
                    )}
                    {alert.conditions.minPeriod !== undefined && (
                      <div>Period ≥ {alert.conditions.minPeriod}s</div>
                    )}
                    {alert.conditions.maxWind !== undefined && (
                      <div>Wind ≤ {alert.conditions.maxWind}m/s</div>
                    )}
                  </div>

                  {alert.lastTriggered && (
                    <div style={{ fontSize: '10px', color: '#9ca3af', marginTop: '6px' }}>
                      Last triggered: {new Date(alert.lastTriggered).toLocaleDateString()}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Create Alert Form */}
      {showCreateForm && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '16px'
        }}>
          <div style={{
            background: 'white',
            borderRadius: '8px',
            padding: '24px',
            maxWidth: '400px',
            width: '100%',
            maxHeight: '80vh',
            overflowY: 'auto'
          }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '18px', color: '#0c4a6e' }}>
              Create Surf Alert
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4b5563', display: 'block', marginBottom: '4px' }}>
                  Alert Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Baja Point Break"
                  style={{
                    width: '100%',
                    padding: '8px',
                    border: '1px solid #d1d5db',
                    borderRadius: '4px',
                    fontSize: '14px'
                  }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4b5563', display: 'block', marginBottom: '4px' }}>
                    Latitude
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    value={formData.lat}
                    onChange={(e) => setFormData({ ...formData, lat: parseFloat(e.target.value) })}
                    style={{
                      width: '100%',
                      padding: '8px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      fontSize: '14px'
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4b5563', display: 'block', marginBottom: '4px' }}>
                    Longitude
                  </label>
                  <input
                    type="number"
                    step="0.0001"
                    value={formData.lon}
                    onChange={(e) => setFormData({ ...formData, lon: parseFloat(e.target.value) })}
                    style={{
                      width: '100%',
                      padding: '8px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      fontSize: '14px'
                    }}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4b5563', display: 'block', marginBottom: '4px' }}>
                  Min Score: {formData.minScore}/10
                </label>
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="0.5"
                  value={formData.minScore}
                  onChange={(e) => setFormData({ ...formData, minScore: parseFloat(e.target.value) })}
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4b5563', display: 'block', marginBottom: '4px' }}>
                    Min Height (m)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={formData.minHeight}
                    onChange={(e) => setFormData({ ...formData, minHeight: parseFloat(e.target.value) })}
                    style={{
                      width: '100%',
                      padding: '8px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      fontSize: '14px'
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4b5563', display: 'block', marginBottom: '4px' }}>
                    Max Height (m)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={formData.maxHeight}
                    onChange={(e) => setFormData({ ...formData, maxHeight: parseFloat(e.target.value) })}
                    style={{
                      width: '100%',
                      padding: '8px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      fontSize: '14px'
                    }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4b5563', display: 'block', marginBottom: '4px' }}>
                    Min Period (s)
                  </label>
                  <input
                    type="number"
                    value={formData.minPeriod}
                    onChange={(e) => setFormData({ ...formData, minPeriod: parseInt(e.target.value) })}
                    style={{
                      width: '100%',
                      padding: '8px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      fontSize: '14px'
                    }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 'bold', color: '#4b5563', display: 'block', marginBottom: '4px' }}>
                    Max Wind (m/s)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    value={formData.maxWind}
                    onChange={(e) => setFormData({ ...formData, maxWind: parseFloat(e.target.value) })}
                    style={{
                      width: '100%',
                      padding: '8px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      fontSize: '14px'
                    }}
                  />
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '8px', marginTop: '20px' }}>
              <button
                onClick={() => setShowCreateForm(false)}
                style={{
                  flex: 1,
                  background: '#e5e7eb',
                  color: '#4b5563',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '10px',
                  fontSize: '14px',
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                style={{
                  flex: 1,
                  background: '#0ea5e9',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '10px',
                  fontSize: '14px',
                  fontWeight: 'bold',
                  cursor: 'pointer'
                }}
              >
                Create Alert
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default SurfAlertsPanel;
