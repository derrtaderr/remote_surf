import { useState } from 'react'
import MapView from './components/MapView'

function App() {
  const [minScore, setMinScore] = useState(0)
  const [spacing, setSpacing] = useState(1000)

  return (
    <div className="app">
      <header className="app-header">
        <h1>Remote Surf</h1>
        <p>Find unknown surf from your sailboat</p>

        {/* Filter controls */}
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
      </header>

      <main className="app-main">
        <MapView minScore={minScore} spacing={spacing} />
      </main>
    </div>
  )
}

export default App
