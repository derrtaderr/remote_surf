/**
 * Service Worker Registration
 *
 * Handles registration, updates, and lifecycle management
 * of the service worker for offline capabilities.
 */

export interface ServiceWorkerConfig {
  onSuccess?: (registration: ServiceWorkerRegistration) => void;
  onUpdate?: (registration: ServiceWorkerRegistration) => void;
  onOfflineReady?: () => void;
}

/**
 * Register the service worker
 */
export async function registerServiceWorker(config?: ServiceWorkerConfig): Promise<void> {
  if (!('serviceWorker' in navigator)) {
    console.warn('Service Worker not supported in this browser');
    return;
  }

  // Wait for page load
  if (document.readyState !== 'complete') {
    await new Promise<void>((resolve) => {
      window.addEventListener('load', () => resolve());
    });
  }

  try {
    const registration = await navigator.serviceWorker.register('/sw.js', {
      scope: '/'
    });

    console.log('Service Worker registered:', registration.scope);

    // Handle updates
    registration.addEventListener('updatefound', () => {
      const newWorker = registration.installing;
      if (!newWorker) return;

      newWorker.addEventListener('statechange', () => {
        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
          // New service worker available
          console.log('New service worker available');
          config?.onUpdate?.(registration);
        } else if (newWorker.state === 'activated') {
          // Service worker activated
          console.log('Service worker activated');
          config?.onSuccess?.(registration);
          config?.onOfflineReady?.();
        }
      });
    });

    // Check for updates periodically
    setInterval(() => {
      registration.update();
    }, 1000 * 60 * 60); // Check every hour

  } catch (error) {
    console.error('Service Worker registration failed:', error);
  }
}

/**
 * Unregister service worker
 */
export async function unregisterServiceWorker(): Promise<boolean> {
  if (!('serviceWorker' in navigator)) {
    return false;
  }

  const registration = await navigator.serviceWorker.getRegistration();
  if (registration) {
    return await registration.unregister();
  }

  return false;
}

/**
 * Skip waiting and activate new service worker immediately
 */
export function skipWaiting(): void {
  navigator.serviceWorker.controller?.postMessage({ type: 'SKIP_WAITING' });
}

/**
 * Clear all caches
 */
export async function clearCache(): Promise<void> {
  const registration = await navigator.serviceWorker.getRegistration();
  if (registration && registration.active) {
    registration.active.postMessage({ type: 'CLEAR_CACHE' });
  }

  // Also clear Cache Storage API directly
  if ('caches' in window) {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames.map(name => caches.delete(name)));
  }
}

/**
 * Get cache size
 */
export async function getCacheSize(): Promise<number | null> {
  if (!('caches' in window)) {
    return null;
  }

  try {
    const cacheNames = await caches.keys();
    let totalSize = 0;

    for (const cacheName of cacheNames) {
      const cache = await caches.open(cacheName);
      const keys = await cache.keys();
      totalSize += keys.length;
    }

    return totalSize;
  } catch (error) {
    console.error('Failed to get cache size:', error);
    return null;
  }
}

/**
 * Check if app is running in standalone mode (PWA)
 */
export function isStandalone(): boolean {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    (window.navigator as any).standalone === true
  );
}

/**
 * Check if device is online
 */
export function isOnline(): boolean {
  return navigator.onLine;
}

/**
 * Listen for online/offline events
 */
export function addNetworkListener(
  onOnline: () => void,
  onOffline: () => void
): () => void {
  window.addEventListener('online', onOnline);
  window.addEventListener('offline', onOffline);

  // Return cleanup function
  return () => {
    window.removeEventListener('online', onOnline);
    window.removeEventListener('offline', onOffline);
  };
}
