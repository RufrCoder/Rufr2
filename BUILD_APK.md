# Building APK for Roofing Business App

## Prerequisites

1. **Flutter SDK**: Make sure Flutter is installed and configured
2. **Android Studio**: Install for Android SDK and tools
3. **Java JDK**: Version 8 or higher
4. **Physical Android device** or **Android Emulator**

## Quick Build Steps

### 1. Set Up Environment

```bash
# Navigate to frontend directory
cd frontend

# Install Flutter dependencies
flutter pub get

# Check Flutter doctor
flutter doctor -v

# Accept Android licenses (if needed)
flutter doctor --android-licenses
```

### 2. Create Debug APK (Fast)

```bash
# Navigate to Flutter project
cd frontend

# Build debug APK (fast, for testing)
flutter build apk --debug

# APK will be created at:
# build/app/outputs/flutter-apk/app-debug.apk
```

### 3. Create Release APK (For Distribution)

```bash
# Build release APK (optimized, smaller size)
flutter build apk --release

# APK will be created at:
# build/app/outputs/flutter-apk/app-release.apk
```

### 4. Create App Bundle (Recommended for Play Store)

```bash
# Build app bundle (required for Google Play Store)
flutter build appbundle --release

# App Bundle will be created at:
# build/app/outputs/bundle/release/app-release.aab
```

## Build Variants

### Development Build
```bash
flutter build apk --debug --flavor dev
```

### Production Build
```bash
flutter build apk --release --flavor prod
```

## Installing the APK

### Option 1: Install on Connected Device
```bash
# Build and install directly to connected device
flutter build apk --debug && flutter install
```

### Option 2: Transfer APK File

1. Locate the APK file:
   - Debug: `build/app/outputs/flutter-apk/app-debug.apk`
   - Release: `build/app/outputs/flutter-apk/app-release.apk`

2. Transfer to Android device via:
   - USB cable
   - Email attachment
   - Cloud storage (Google Drive, Dropbox)

3. On Android device:
   - Go to Settings > Security
   - Enable "Install from unknown sources"
   - Open the APK file to install

### Option 3: Use ADB (Android Debug Bridge)
```bash
# Install via ADB (requires Android SDK)
adb install build/app/outputs/flutter-apk/app-debug.apk

# Install with reinstall (if already installed)
adb install -r build/app/outputs/flutter-apk/app-debug.apk
```

## Configuration for Production

### 1. Update App Configuration

Edit `frontend/lib/core/app.dart`:
```dart
class AppConstants {
  // Update to your production server URL
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://your-production-server.com/api',
  );
}
```

### 2. Create Production Keystore (Optional but Recommended)

For a production-ready signed APK:

```bash
# Generate keystore (run once)
keytool -genkey -v -keystore ~/release-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias release

# Update build.gradle with keystore information
```

Edit `frontend/android/app/build.gradle`:
```gradle
android {
    ...
    signingConfigs {
        release {
            storeFile file('~/release-key.jks')
            storePassword 'your_store_password'
            keyAlias 'release'
            keyPassword 'your_key_password'
        }
    }
    buildTypes {
        release {
            signingConfig signingConfigs.release
            ...
        }
    }
}
```

### 3. Update App Details

Edit these files to customize your app:

- `frontend/android/app/src/main/AndroidManifest.xml` (app name, permissions)
- `frontend/android/app/src/main/res/values/colors.xml` (brand colors)
- `frontend/android/app/src/main/res/mipmap-*` (app icons)

## Troubleshooting

### Common Issues

1. **"android:exported" error**:
   ```bash
   flutter clean && flutter pub get
   ```

2. **Build failed: "minSdkVersion"**:
   - Update `android/app/build.gradle` minSdkVersion to 21 or higher

3. **License issues**:
   ```bash
   flutter doctor --android-licenses
   ```

4. **Gradle build failed**:
   ```bash
   cd android
   ./gradlew clean
   ./gradlew build
   ```

### Verification Commands

```bash
# Check connected devices
flutter devices

# Check build configuration
flutter doctor -v

# Test on web (alternative)
flutter run -d web-server --web-port 3000
```

## Features in the APK

✅ **Working Features**:
- User authentication
- Dashboard with metrics
- Calendar and job scheduling
- Message hub (when backend is running)
- Checklists and templates
- Analytics dashboard
- Materials management
- AI assistant (with API key)
- Settings and preferences

✅ **Android-Specific Features**:
- Native file picker for photos
- Camera integration
- Push notifications
- Local storage
- Offline support (cached data)
- Material Design theming

## Next Steps

1. **Test the APK**: Install and test all features
2. **Set Up Backend**: Deploy the Flask backend to a server
3. **Configure API URLs**: Update app to point to your server
4. **Test Integration**: Verify frontend-backend communication
5. **Publish**: Upload to Google Play Store or distribute directly

## Support

- Check Flutter logs: `flutter logs`
- Monitor network traffic (use Charles Proxy or similar)
- Test on multiple Android versions
- Ensure permissions are granted in device settings

---

**Your APK is ready!** Follow the steps above to build and install your roofing business management app.