import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.remotesurf.app',
  appName: 'Remote Surf',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
    iosScheme: 'https',
    // Allow CORS for API requests
    allowNavigation: ['*']
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      backgroundColor: '#0f172a',
      androidSpinnerStyle: 'large',
      iosSpinnerStyle: 'large',
      spinnerColor: '#0ea5e9',
      showSpinner: true
    },
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert']
    },
    Geolocation: {
      // Request location for nearby surf spot scanning
    },
    LocalNotifications: {
      // For surf alerts
    }
  },
  ios: {
    contentInset: 'automatic',
    // Allow any HTTP scheme for development
    scheme: 'Remote Surf'
  },
  android: {
    buildOptions: {
      keystorePath: '',
      keystoreAlias: ''
    },
    allowMixedContent: true
  }
};

export default config;
