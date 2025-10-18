import { useState, useEffect } from 'react'
import MapView from './components/MapView'
import OfflineIndicator from './components/OfflineIndicator'

function App() {
  const [minScore, setMinScore] = useState(0)
  const [spacing, setSpacing] = useState(1000)
  const [headerCollapsed, setHeaderCollapsed] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  // Detect mobile on mount
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768)
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  return (
    <div className="app">
      <OfflineIndicator />
      <header className={`app-header ${headerCollapsed ? 'collapsed' : ''}`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1>Remote Surf</h1>
            {!headerCollapsed && <p>Find unknown surf from your sailboat</p>}
          </div>
          {isMobile && (
            <button
              onClick={() => setHeaderCollapsed(!headerCollapsed)}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--color-text)',
                fontSize: '20px',
                cursor: 'pointer',
                padding: '8px',
                touchAction: 'manipulation'
              }}
            >
              {headerCollapsed ? '▼' : '▲'}
            </button>
          )}
        </div>

        {/* Filter controls */}
        {!headerCollapsed && (
          <div className="app-controls">
            <div className="control-group">
              <label htmlFor="minScore">Min Score: {minScore.toFixed(1)}</label>
              <input
                id="minScore"
                type="range"
                min="0"
                max="10"
                step="0.5"
                value={minScore}
                onChange={(e) => setMinScore(parseFloat(e.target.value))}
              />
            </div>

            <div className="control-group">
              <label htmlFor="spacing">Spacing: {spacing}m</label>
              <input
                id="spacing"
                type="range"
                min="200"
                max="2000"
                step="100"
                value={spacing}
                onChange={(e) => setSpacing(parseInt(e.target.value))}
              />
            </div>
          </div>
        )}
      </header>

      <main className="app-main">
        <MapView minScore={minScore} spacing={spacing} />
      </main>
    </div>
  )
}

export default App
