/**
 * Service Worker for Remote Surf
 *
 * Provides offline capabilities by caching:
 * - App shell (HTML, CSS, JS)
 * - Map tiles
 * - API responses
 * - Static assets
 */

const CACHE_VERSION = 'v1';
const CACHE_NAME = `remote-surf-${CACHE_VERSION}`;

// Cache strategies
const CACHE_STRATEGIES = {
  APP_SHELL: 'app-shell',
  API_DATA: 'api-data',
  MAP_TILES: 'map-tiles',
  STATIC: 'static'
};

// Resources to cache immediately on install
const APP_SHELL_CACHE = [
  '/index.html',
  '/manifest.json'
];

// Cache duration (in ms)
const CACHE_DURATION = {
  API: 1000 * 60 * 30,        // 30 minutes
  MAP_TILES: 1000 * 60 * 60 * 24 * 7,  // 7 days
  STATIC: 1000 * 60 * 60 * 24 * 30     // 30 days
};

/**
 * Install event - cache app shell
 */
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');

  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Caching app shell');
      return cache.addAll(APP_SHELL_CACHE);
    }).then(() => {
      // Force activation immediately
      return self.skipWaiting();
    })
  );
});

/**
 * Activate event - clean up old caches
 */
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      // Take control of all pages immediately
      return self.clients.claim();
    })
  );
});

/**
 * Fetch event - serve from cache or network
 */
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Determine cache strategy
  let strategy;

  if (url.pathname.startsWith('/api/')) {
    strategy = CACHE_STRATEGIES.API_DATA;
  } else if (url.hostname.includes('cartocdn.com') || url.hostname.includes('tile')) {
    strategy = CACHE_STRATEGIES.MAP_TILES;
  } else if (url.pathname.match(/\.(js|css|woff2?|ttf|eot|svg|png|jpg|jpeg|gif|webp)$/)) {
    strategy = CACHE_STRATEGIES.STATIC;
  } else {
    strategy = CACHE_STRATEGIES.APP_SHELL;
  }

  event.respondWith(handleFetch(request, strategy));
});

/**
 * Handle fetch with appropriate caching strategy
 */
async function handleFetch(request, strategy) {
  const cache = await caches.open(CACHE_NAME);

  switch (strategy) {
    case CACHE_STRATEGIES.APP_SHELL:
      // Network first, fall back to cache
      return networkFirst(request, cache);

    case CACHE_STRATEGIES.API_DATA:
      // Network first with timed cache
      return networkFirstWithTimeout(request, cache, CACHE_DURATION.API);

    case CACHE_STRATEGIES.MAP_TILES:
      // Cache first, fall back to network
      return cacheFirst(request, cache, CACHE_DURATION.MAP_TILES);

    case CACHE_STRATEGIES.STATIC:
      // Cache first for static assets
      return cacheFirst(request, cache, CACHE_DURATION.STATIC);

    default:
      return fetch(request);
  }
}

/**
 * Network first strategy - try network, fall back to cache
 */
async function networkFirst(request, cache) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) {
      console.log('[SW] Serving from cache (offline):', request.url);
      return cached;
    }
    throw error;
  }
}

/**
 * Network first with timeout - check cache age
 */
async function networkFirstWithTimeout(request, cache, maxAge) {
  const cached = await cache.match(request);

  // Check if cached response is fresh enough
  if (cached) {
    const cachedDate = new Date(cached.headers.get('date'));
    const age = Date.now() - cachedDate.getTime();

    if (age < maxAge) {
      console.log('[SW] Serving fresh cached data:', request.url);
      // Fetch in background to update cache
      fetch(request).then((response) => {
        if (response.ok) {
          cache.put(request, response.clone());
        }
      }).catch(() => {});

      return cached;
    }
  }

  // Fetch from network
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    // Fall back to stale cache if network fails
    if (cached) {
      console.log('[SW] Serving stale cache (offline):', request.url);
      return cached;
    }
    throw error;
  }
}

/**
 * Cache first strategy - serve from cache, fall back to network
 */
async function cacheFirst(request, cache, maxAge) {
  const cached = await cache.match(request);

  if (cached) {
    // Check age if maxAge specified
    if (maxAge) {
      const cachedDate = new Date(cached.headers.get('date'));
      const age = Date.now() - cachedDate.getTime();

      if (age > maxAge) {
        console.log('[SW] Cache expired, fetching fresh:', request.url);
        try {
          const response = await fetch(request);
          if (response.ok) {
            cache.put(request, response.clone());
          }
          return response;
        } catch (error) {
          console.log('[SW] Network failed, serving stale cache:', request.url);
          return cached;
        }
      }
    }

    return cached;
  }

  // Not in cache, fetch from network
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    console.error('[SW] Fetch failed:', request.url, error);
    throw error;
  }
}

/**
 * Message handler for cache management
 */
self.addEventListener('message', (event) => {
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
    event.ports[0]?.postMessage({ success: true });
  }

  if (event.data.type === 'CLEAR_CACHE') {
    event.waitUntil(
      caches.delete(CACHE_NAME).then(() => {
        console.log('[SW] Cache cleared');
        event.ports[0]?.postMessage({ success: true });
      })
    );
  }

  if (event.data.type === 'CACHE_SIZE') {
    event.waitUntil(
      caches.open(CACHE_NAME).then(async (cache) => {
        const keys = await cache.keys();
        event.ports[0]?.postMessage({ size: keys.length });
      })
    );
  }
});
