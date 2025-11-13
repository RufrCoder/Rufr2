# 🚀 Quick Install - Get Your APK NOW!

## Option 1: Build APK Locally (Fastest Method)

If you want to install the app immediately without waiting for GitHub Actions:

### Step 1: Install Flutter
```bash
# For Linux/Mac:
wget https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_3.24.5-stable.tar.xz
tar xf flutter_linux_3.24.5-stable.tar.xz
export PATH="$PATH:`pwd`/flutter/bin"

# For Windows: Download from https://flutter.dev/docs/get-started/install/windows

# Verify installation
flutter doctor
```

### Step 2: Navigate to Project
```bash
cd frontend
```

### Step 3: Build APK
```bash
# Install dependencies
flutter pub get

# Build debug APK (fast, for testing)
flutter build apk --debug

# APK will be at: build/app/outputs/flutter-apk/app-debug.apk
```

### Step 4: Install on Android
1. Transfer the APK to your phone
2. Enable "Install from unknown sources"
3. Open the APK and install

## Option 2: Download Pre-built APK (When Available)

1. Go to: https://github.com/YOUR_USERNAME/Rufr2/releases/latest
2. Download: `roofing-business-app-release.apk`
3. Install on your Android device

## Option 3: Try Web Version

1. Open: https://YOUR_USERNAME.github.io/Rufr2/
2. Works in any web browser
3. No installation required

---

**🎉 Your roofing business management app is ready to use!**