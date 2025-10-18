import { useState, useEffect } from 'react';
import { addNetworkListener, isOnline } from '../utils/serviceWorker';

/**
 * Offline Indicator Component
 *
 * Shows a banner when the app is offline, letting users know
 * they can still use cached data.
 */
const OfflineIndicator = () => {
  const [online, setOnline] = useState(isOnline());
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    let timeoutId: NodeJS.Timeout | null = null;

    const cleanup = addNetworkListener(
      () => {
        setOnline(true);
        setShowBanner(true);
        // Hide "back online" message after 3 seconds
        timeoutId = setTimeout(() => setShowBanner(false), 3000);
      },
      () => {
        setOnline(false);
        setShowBanner(true);
      }
    );

    return () => {
      cleanup();
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, []);

  if (!showBanner) {
    return null;
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      padding: '12px',
      textAlign: 'center',
      background: online ? '#22c55e' : '#f59e0b',
      color: 'white',
      fontSize: '14px',
      fontWeight: 'bold',
      zIndex: 9999,
      boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
      animation: 'slideDown 0.3s ease'
    }}>
      {online ? (
        <>
          ✓ Back online
        </>
      ) : (
        <>
          ⚠ You're offline - showing cached data
        </>
      )}
    </div>
  );
};

export default OfflineIndicator;
