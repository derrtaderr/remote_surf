# Building Native Apps with Capacitor

This guide explains how to build iOS and Android versions of Remote Surf using Capacitor.

## Prerequisites

### For iOS Development:
- macOS computer
- Xcode 14+ installed
- Apple Developer account (for distribution)
- CocoaPods installed: `sudo gem install cocoapods`

### For Android Development:
- Android Studio installed
- Java Development Kit (JDK) 11+
- Android SDK 21+ (Android 5.0+)

## Initial Setup

1. **Build the web app:**
   ```bash
   npm run build
   ```

2. **Add platforms:**
   ```bash
   # Add iOS
   npx cap add ios

   # Add Android
   npx cap add android
   ```

## Building for iOS

1. **Sync web assets to iOS:**
   ```bash
   npx cap sync ios
   ```

2. **Open in Xcode:**
   ```bash
   npx cap open ios
   ```

3. **Configure in Xcode:**
   - Select your Development Team in Signing & Capabilities
   - Set a unique Bundle Identifier (e.g., `com.yourname.remotesurf`)
   - Add required capabilities:
     - Location When In Use
     - Push Notifications
     - Background Modes (if needed)

4. **Update Info.plist:**
   Add location permission descriptions:
   ```xml
   <key>NSLocationWhenInUseUsageDescription</key>
   <string>Remote Surf needs your location to find nearby surf spots</string>
   <key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
   <string>Remote Surf needs your location to alert you about nearby surf conditions</string>
   ```

5. **Build and run:**
   - Select your device or simulator
   - Click the Play button in Xcode
   - Or use CLI: `xcodebuild -workspace ios/App/App.xcworkspace -scheme App -destination 'platform=iOS Simulator,name=iPhone 15' build`

6. **Deploy to TestFlight:**
   - Archive the app in Xcode (Product > Archive)
   - Upload to App Store Connect
   - Configure TestFlight testing

## Building for Android

1. **Sync web assets to Android:**
   ```bash
   npx cap sync android
   ```

2. **Open in Android Studio:**
   ```bash
   npx cap open android
   ```

3. **Configure in Android Studio:**
   - Set application ID in `android/app/build.gradle`
   - Update `minSdkVersion` to 22+ (Android 5.1+)
   - Add permissions in `AndroidManifest.xml`:
     ```xml
     <uses-permission android:name="android.permission.INTERNET" />
     <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
     <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
     <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
     ```

4. **Generate signing key (for release builds):**
   ```bash
   keytool -genkey -v -keystore remote-surf.keystore -alias remote-surf -keyalg RSA -keysize 2048 -validity 10000
   ```

5. **Configure signing in `android/app/build.gradle`:**
   ```gradle
   android {
       signingConfigs {
           release {
               keyAlias 'remote-surf'
               keyPassword 'YOUR_KEY_PASSWORD'
               storeFile file('remote-surf.keystore')
               storePassword 'YOUR_STORE_PASSWORD'
           }
       }
       buildTypes {
           release {
               signingConfig signingConfigs.release
           }
       }
   }
   ```

6. **Build APK:**
   ```bash
   cd android
   ./gradlew assembleRelease
   # Output: android/app/build/outputs/apk/release/app-release.apk
   ```

7. **Build App Bundle (for Play Store):**
   ```bash
   cd android
   ./gradlew bundleRelease
   # Output: android/app/build/outputs/bundle/release/app-release.aab
   ```

8. **Deploy to Google Play Console:**
   - Create a new app in Play Console
   - Upload the .aab file
   - Configure internal testing or production release

## Updating the App

When you make changes to the web app:

1. **Rebuild web assets:**
   ```bash
   npm run build
   ```

2. **Sync to native projects:**
   ```bash
   npx cap sync
   ```

3. **Update native code (if plugin changes):**
   ```bash
   npx cap update
   ```

## Live Reload During Development

For faster development, you can use live reload:

1. **Start dev server:**
   ```bash
   npm run dev
   ```

2. **Update capacitor.config.ts:**
   ```typescript
   server: {
     url: 'http://YOUR_IP:5173',
     cleartext: true
   }
   ```

3. **Sync and run:**
   ```bash
   npx cap sync
   npx cap run ios  # or android
   ```

## Common Issues

### iOS Build Errors

**"Command PhaseScriptExecution failed"**
- Solution: `cd ios/App && pod install`

**"No profiles for 'com.remotesurf.app' were found"**
- Solution: Select a Development Team in Xcode

**"This app has crashed because it attempted to access privacy-sensitive data"**
- Solution: Add permission descriptions to Info.plist

### Android Build Errors

**"Could not find com.android.tools.build:gradle"**
- Solution: Update Android Studio and sync Gradle

**"Execution failed for task ':app:processReleaseResources'"**
- Solution: Clean build with `./gradlew clean`

**"Installation failed with message INSTALL_FAILED_INSUFFICIENT_STORAGE"**
- Solution: Free up space on device/emulator

## App Icons and Splash Screens

1. **Generate icons:**
   - Create 1024x1024 PNG icon
   - Use tool like https://appicon.co or https://capacitorjs.com/docs/guides/splash-screens-and-icons

2. **Replace icons:**
   - iOS: `ios/App/App/Assets.xcassets/AppIcon.appiconset/`
   - Android: `android/app/src/main/res/mipmap-*/`

3. **Replace splash screens:**
   - iOS: `ios/App/App/Assets.xcassets/Splash.imageset/`
   - Android: `android/app/src/main/res/drawable-*/`

## App Store Submission Checklist

### iOS App Store
- [ ] App icons (all sizes)
- [ ] Screenshots (all required device sizes)
- [ ] App description and keywords
- [ ] Privacy policy URL
- [ ] Support URL
- [ ] Age rating
- [ ] Pricing and availability

### Google Play Store
- [ ] App icons (512x512 PNG)
- [ ] Feature graphic (1024x500 PNG)
- [ ] Screenshots (at least 2)
- [ ] App description
- [ ] Privacy policy URL
- [ ] Content rating questionnaire
- [ ] Pricing and distribution

## Resources

- [Capacitor Documentation](https://capacitorjs.com/docs)
- [iOS App Distribution Guide](https://developer.apple.com/app-store/submitting/)
- [Android App Publishing Guide](https://developer.android.com/studio/publish)
- [Capacitor iOS Plugin Development](https://capacitorjs.com/docs/ios)
- [Capacitor Android Plugin Development](https://capacitorjs.com/docs/android)

## Next Steps

After building the native apps, you can:
1. Implement push notifications for surf alerts (see `src/utils/nativeCapabilities.ts`)
2. Add background location tracking
3. Integrate with native mapping features
4. Add biometric authentication
5. Implement in-app purchases
