/**
 * Surf Alerts System
 *
 * Manages surf condition alerts and notifications.
 * Notifies users when conditions match their preferences.
 */

import {
  scheduleLocalNotification,
  initializePushNotifications,
  isNativePlatform
} from './nativeCapabilities';

export interface SurfAlert {
  id: string;
  name: string;
  location: {
    lat: number;
    lon: number;
  };
  conditions: {
    minScore: number;
    minHeight?: number;
    maxHeight?: number;
    minPeriod?: number;
    maxWind?: number;
  };
  enabled: boolean;
  lastTriggered?: Date;
  createdAt: Date;
}

export interface SurfCondition {
  score: number;
  height: number;
  period: number;
  windSpeed: number;
  location: {
    lat: number;
    lon: number;
    name?: string;
  };
}

const ALERTS_STORAGE_KEY = 'surf_alerts';
const COOLDOWN_PERIOD = 1000 * 60 * 60 * 3; // 3 hours between alerts

/**
 * Save alerts to localStorage
 */
function saveAlerts(alerts: SurfAlert[]): void {
  localStorage.setItem(ALERTS_STORAGE_KEY, JSON.stringify(alerts));
}

/**
 * Load alerts from localStorage
 */
export function loadAlerts(): SurfAlert[] {
  const stored = localStorage.getItem(ALERTS_STORAGE_KEY);
  if (!stored) return [];

  try {
    const alerts = JSON.parse(stored);
    // Convert date strings back to Date objects
    return alerts.map((alert: any) => ({
      ...alert,
      createdAt: new Date(alert.createdAt),
      lastTriggered: alert.lastTriggered ? new Date(alert.lastTriggered) : undefined
    }));
  } catch (error) {
    console.error('Failed to load alerts:', error);
    return [];
  }
}

/**
 * Create a new surf alert
 */
export function createAlert(alert: Omit<SurfAlert, 'id' | 'createdAt' | 'enabled'>): SurfAlert {
  const newAlert: SurfAlert = {
    ...alert,
    id: `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    enabled: true,
    createdAt: new Date()
  };

  const alerts = loadAlerts();
  alerts.push(newAlert);
  saveAlerts(alerts);

  console.log('[Alerts] Created:', newAlert.name);
  return newAlert;
}

/**
 * Update an existing alert
 */
export function updateAlert(id: string, updates: Partial<SurfAlert>): boolean {
  const alerts = loadAlerts();
  const index = alerts.findIndex(a => a.id === id);

  if (index === -1) {
    return false;
  }

  alerts[index] = { ...alerts[index], ...updates };
  saveAlerts(alerts);

  console.log('[Alerts] Updated:', id);
  return true;
}

/**
 * Delete an alert
 */
export function deleteAlert(id: string): boolean {
  const alerts = loadAlerts();
  const filtered = alerts.filter(a => a.id !== id);

  if (filtered.length === alerts.length) {
    return false;
  }

  saveAlerts(filtered);
  console.log('[Alerts] Deleted:', id);
  return true;
}

/**
 * Toggle alert enabled/disabled
 */
export function toggleAlert(id: string): boolean {
  const alerts = loadAlerts();
  const alert = alerts.find(a => a.id === id);

  if (!alert) {
    return false;
  }

  alert.enabled = !alert.enabled;
  saveAlerts(alerts);

  console.log('[Alerts] Toggled:', id, alert.enabled);
  return alert.enabled;
}

/**
 * Check if conditions match alert criteria
 */
export function matchesAlert(alert: SurfAlert, conditions: SurfCondition): boolean {
  const { conditions: criteria } = alert;

  // Check score
  if (conditions.score < criteria.minScore) {
    return false;
  }

  // Check height
  if (criteria.minHeight !== undefined && conditions.height < criteria.minHeight) {
    return false;
  }
  if (criteria.maxHeight !== undefined && conditions.height > criteria.maxHeight) {
    return false;
  }

  // Check period
  if (criteria.minPeriod !== undefined && conditions.period < criteria.minPeriod) {
    return false;
  }

  // Check wind
  if (criteria.maxWind !== undefined && conditions.windSpeed > criteria.maxWind) {
    return false;
  }

  return true;
}

/**
 * Check if alert is in cooldown period
 */
function isInCooldown(alert: SurfAlert): boolean {
  if (!alert.lastTriggered) {
    return false;
  }

  const timeSinceTriggered = Date.now() - alert.lastTriggered.getTime();
  return timeSinceTriggered < COOLDOWN_PERIOD;
}

/**
 * Check conditions against all alerts
 */
export async function checkAlerts(conditions: SurfCondition[]): Promise<void> {
  const alerts = loadAlerts().filter(a => a.enabled);

  if (alerts.length === 0) {
    return;
  }

  console.log(`[Alerts] Checking ${conditions.length} conditions against ${alerts.length} alerts`);

  for (const alert of alerts) {
    // Skip if in cooldown
    if (isInCooldown(alert)) {
      continue;
    }

    // Check each condition
    for (const condition of conditions) {
      if (matchesAlert(alert, condition)) {
        await triggerAlert(alert, condition);
        break; // Only trigger once per check
      }
    }
  }
}

/**
 * Trigger an alert (send notification)
 */
async function triggerAlert(alert: SurfAlert, conditions: SurfCondition): Promise<void> {
  console.log('[Alerts] Triggering:', alert.name);

  // Update last triggered time
  updateAlert(alert.id, { lastTriggered: new Date() });

  // Prepare notification
  const title = `🌊 ${alert.name}`;
  const body = `Score: ${conditions.score.toFixed(1)}/10 | ${conditions.height.toFixed(1)}m @ ${conditions.period.toFixed(0)}s | Wind: ${conditions.windSpeed.toFixed(1)}m/s`;

  // Send notification
  await scheduleLocalNotification(title, body, undefined, {
    alertId: alert.id,
    lat: conditions.location.lat,
    lon: conditions.location.lon,
    score: conditions.score
  });

  // Analytics/logging
  console.log('[Alerts] Notification sent:', { alert: alert.name, conditions });
}

/**
 * Request notification permissions
 */
export async function requestNotificationPermissions(): Promise<boolean> {
  if (!isNativePlatform()) {
    // Request browser notifications
    if ('Notification' in window) {
      const permission = await Notification.requestPermission();
      return permission === 'granted';
    }
    return false;
  }

  // Native platform permissions handled by Capacitor
  return true;
}

/**
 * Initialize push notifications for surf alerts
 */
export async function initializeSurfAlerts(): Promise<void> {
  await requestNotificationPermissions();

  if (isNativePlatform()) {
    await initializePushNotifications(
      (token) => {
        console.log('[Alerts] Push token:', token.value);
        // TODO: Send token to backend for remote notifications
      },
      (notification) => {
        console.log('[Alerts] Notification action:', notification);
        // Handle notification tap
        if (notification.notification.data?.alertId) {
          const alertId = notification.notification.data.alertId;
          console.log('[Alerts] Opening alert:', alertId);
          // TODO: Navigate to alert location
        }
      }
    );
  }

  console.log('[Alerts] Surf alerts initialized');
}

/**
 * Get alert statistics
 */
export function getAlertStats(): {
  total: number;
  enabled: number;
  triggered: number;
} {
  const alerts = loadAlerts();

  return {
    total: alerts.length,
    enabled: alerts.filter(a => a.enabled).length,
    triggered: alerts.filter(a => a.lastTriggered !== undefined).length
  };
}

/**
 * Export alerts (for backup)
 */
export function exportAlerts(): string {
  const alerts = loadAlerts();
  return JSON.stringify(alerts, null, 2);
}

/**
 * Import alerts (from backup)
 */
export function importAlerts(json: string): boolean {
  try {
    const alerts = JSON.parse(json);
    if (!Array.isArray(alerts)) {
      throw new Error('Invalid format');
    }

    // Validate structure
    for (const alert of alerts) {
      if (!alert.id || !alert.name || !alert.location || !alert.conditions) {
        throw new Error('Invalid alert structure');
      }
    }

    saveAlerts(alerts);
    console.log(`[Alerts] Imported ${alerts.length} alerts`);
    return true;
  } catch (error) {
    console.error('[Alerts] Import failed:', error);
    return false;
  }
}
