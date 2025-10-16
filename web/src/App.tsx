import { useState } from 'react'
import Map from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

function App() {
  const [viewState, setViewState] = useState({
    longitude: -111.234,
    latitude: 26.543,
    zoom: 10
  })

  return (
    <div className="app">
      <header className="app-header">
        <h1>Remote Surf</h1>
        <p>Find unknown surf from your sailboat</p>
      </header>

      <main className="app-main">
        <Map
          {...viewState}
          onMove={evt => setViewState(evt.viewState)}
          style={{ width: '100%', height: '100%' }}
          mapStyle="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"
        >
          {/* TODO: Add markers, layers, controls */}
        </Map>
      </main>

      <div className="app-info">
        <p>🚧 MVP in development - API integration coming soon</p>
      </div>
    </div>
  )
}

export default App
