/**
 * Native Capabilities via Capacitor
 *
 * Provides access to native device features like geolocation,
 * notifications, and status bar control.
 */

import { Capacitor } from '@capacitor/core';
import { Geolocation, Position } from '@capacitor/geolocation';
import { PushNotifications, Token, ActionPerformed } from '@capacitor/push-notifications';
import { LocalNotifications, ActionPerformed as LocalActionPerformed } from '@capacitor/local-notifications';
import { StatusBar, Style } from '@capacitor/status-bar';
import { SplashScreen } from '@capacitor/splash-screen';

/**
 * Check if running on native platform
 */
export function isNativePlatform(): boolean {
  return Capacitor.isNativePlatform();
}

/**
 * Get platform name
 */
export function getPlatform(): string {
  return Capacitor.getPlatform();
}

/**
 * Initialize native app (splash screen, status bar, etc.)
 */
export async function initializeNativeApp(): Promise<void> {
  if (!isNativePlatform()) {
    return;
  }

  try {
    // Set status bar style
    await StatusBar.setStyle({ style: Style.Dark });
    await StatusBar.setBackgroundColor({ color: '#0c4a6e' });

    // Hide splash screen after 2 seconds
    setTimeout(async () => {
      await SplashScreen.hide({ fadeOutDuration: 500 });
    }, 2000);

    console.log('[Native] App initialized');
  } catch (error) {
    console.error('[Native] Initialization failed:', error);
  }
}

/**
 * Get current GPS position
 */
export async function getCurrentPosition(): Promise<Position | null> {
  try {
    // Request permission first
    const permission = await Geolocation.requestPermissions();
    if (permission.location !== 'granted') {
      console.warn('[Native] Location permission denied');
      return null;
    }

    // Get position
    const position = await Geolocation.getCurrentPosition({
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 5000
    });

    return position;
  } catch (error) {
    console.error('[Native] Failed to get position:', error);
    return null;
  }
}

/**
 * Watch GPS position
 */
export function watchPosition(
  callback: (position: Position) => void,
  errorCallback?: (error: any) => void
): string | null {
  if (!isNativePlatform()) {
    // Fall back to browser geolocation
    if ('geolocation' in navigator) {
      const id = navigator.geolocation.watchPosition(
        (pos) => {
          callback({
            coords: {
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
              accuracy: pos.coords.accuracy,
              altitude: pos.coords.altitude,
              altitudeAccuracy: pos.coords.altitudeAccuracy,
              heading: pos.coords.heading,
              speed: pos.coords.speed
            },
            timestamp: pos.timestamp
          });
        },
        errorCallback
      );
      return id.toString();
    }
    return null;
  }

  const watchId = Geolocation.watchPosition(
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 5000
    },
    callback
  );

  return watchId;
}

/**
 * Clear GPS watch
 */
export async function clearWatch(watchId: string): Promise<void> {
  if (!isNativePlatform()) {
    if ('geolocation' in navigator) {
      navigator.geolocation.clearWatch(parseInt(watchId));
    }
    return;
  }

  await Geolocation.clearWatch({ id: watchId });
}

/**
 * Initialize push notifications
 */
export async function initializePushNotifications(
  onToken?: (token: Token) => void,
  onNotification?: (notification: ActionPerformed) => void
): Promise<void> {
  if (!isNativePlatform()) {
    console.log('[Native] Push notifications only available on native platforms');
    return;
  }

  try {
    // Request permission
    const permission = await PushNotifications.requestPermissions();
    if (permission.receive !== 'granted') {
      console.warn('[Native] Push notification permission denied');
      return;
    }

    // Register for push notifications
    await PushNotifications.register();

    // Handle registration token
    if (onToken) {
      PushNotifications.addListener('registration', onToken);
    }

    // Handle notification action
    if (onNotification) {
      PushNotifications.addListener('pushNotificationActionPerformed', onNotification);
    }

    console.log('[Native] Push notifications initialized');
  } catch (error) {
    console.error('[Native] Failed to initialize push notifications:', error);
  }
}

/**
 * Schedule local notification
 */
export async function scheduleLocalNotification(
  title: string,
  body: string,
  scheduledAt?: Date,
  extra?: Record<string, any>
): Promise<void> {
  if (!isNativePlatform()) {
    // Fall back to browser notifications
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(title, { body, ...extra });
    }
    return;
  }

  try {
    // Request permission
    const permission = await LocalNotifications.requestPermissions();
    if (permission.display !== 'granted') {
      console.warn('[Native] Local notification permission denied');
      return;
    }

    // Schedule notification
    await LocalNotifications.schedule({
      notifications: [
        {
          title,
          body,
          id: Date.now(),
          schedule: scheduledAt ? { at: scheduledAt } : undefined,
          extra
        }
      ]
    });

    console.log('[Native] Local notification scheduled');
  } catch (error) {
    console.error('[Native] Failed to schedule notification:', error);
  }
}

/**
 * Handle local notification action
 */
export function onLocalNotificationAction(
  callback: (action: LocalActionPerformed) => void
): void {
  if (!isNativePlatform()) {
    return;
  }

  LocalNotifications.addListener('localNotificationActionPerformed', callback);
}

/**
 * Set status bar color
 */
export async function setStatusBarColor(color: string, darkContent = false): Promise<void> {
  if (!isNativePlatform()) {
    return;
  }

  try {
    await StatusBar.setBackgroundColor({ color });
    await StatusBar.setStyle({ style: darkContent ? Style.Light : Style.Dark });
  } catch (error) {
    console.error('[Native] Failed to set status bar:', error);
  }
}

/**
 * Show/hide status bar
 */
export async function setStatusBarVisible(visible: boolean): Promise<void> {
  if (!isNativePlatform()) {
    return;
  }

  try {
    if (visible) {
      await StatusBar.show();
    } else {
      await StatusBar.hide();
    }
  } catch (error) {
    console.error('[Native] Failed to toggle status bar:', error);
  }
}
