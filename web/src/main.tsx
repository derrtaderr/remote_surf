import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/index.css'
import { registerServiceWorker } from './utils/serviceWorker'
import { initializeNativeApp, isNativePlatform } from './utils/nativeCapabilities'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// Initialize native app if running on mobile
if (isNativePlatform()) {
  initializeNativeApp()
    .then(() => console.log('Native app initialized'))
    .catch(err => console.error('Native init failed:', err))
}

// Register service worker for offline support
if (import.meta.env.PROD) {
  registerServiceWorker({
    onSuccess: () => console.log('App ready for offline use'),
    onUpdate: () => console.log('New version available'),
    onOfflineReady: () => console.log('Offline mode enabled')
  })
}
