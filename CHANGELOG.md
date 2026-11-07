# Changelog

## 2.5.2

### Added
- **Native macOS Support (Apple Silicon arm64).** ZenLink now runs natively on macOS (Apple Silicon arm64 / `aarch64-apple-darwin`), complete with Slint GUI, AppKit window handle integration, and native macOS clipboard.
- **Embedded Segoe Fluent Icons.** Bundled `Segoe Fluent Icons` font directly into the Slint application binary so that all action, navigation, and status icons render natively on macOS without missing glyphs.
- **macOS Developer & Helper Tools.**
  - `tools/get-adb`: Native POSIX bash script that downloads official Google Darwin platform-tools, verifies SHA-256 checksum, and checks Apple Developer ID codesign (`Google LLC`).
  - `tools/ocr.swift` & `zenlink/ocr.py`: Apple Vision framework (`VNRecognizeTextRequest`) OCR extraction with graceful fallback.
  - `Start ZenLink.sh` & `run.sh`: Native launcher scripts for macOS developer workflow and console diagnostics.
  - `native/playfair/build.sh`: Builds native `libplayfair.dylib` for AirPlay decryption on Apple Silicon.
- **macOS Installer (`.dmg`).** Added automated packaging for macOS creating `ZenLink.app` bundle and compressed `.dmg` disk image.

## 2.5.1
- Pick connected iPhone / iPad from the Apple screen.
- Android apps launcher: searchable grid of installed apps with virtual display windows.
- Drag and drop files to mirrored devices.
- In-app update check and background log directory consolidation.

## 2.2.2

### Added
- **Hybrid Control for iOS 17–26 (Experimental).** In Apple Driver mode, an iOS 17–26 device mirrors its picture and sound to ZenLink over AirPlay, while touch, keyboard, gestures and buttons go over Apple's own driver through CoreDevice HID. Both run at once without touching the USB driver. Not yet confirmed on a real iOS 17–26 device.
- **Control level, from what actually opened:** Native Control, Hybrid Control (Experimental), Mirroring Only or Unsupported. Shown on the device chip, in the idle screen and under Settings → Connection & Drivers → Control level.
- **AirPlay guide for Hybrid:** while ZenLink waits for the device to mirror, the step-by-step guide is shown in the app.
- **Capability check on the device:** before claiming control, ZenLink checks that the device offers the display and HID services (mounting the developer image when needed). When they're missing, the picture keeps running and the reason is shown.
- iOS compatibility matrix in the README.

### Changed
- Apple Driver mode now starts on iOS 17 and later; iOS 16 and older get a clear message pointing to ZenLink Studio.
- iOS 27 and later keep the native Apple mode unchanged.

### Fixed
- **Apple Driver mode in the exe failed at "Secure connection"** with "No package metadata was found for pyimg4". The build left out a package's metadata that the developer-image code reads, and also `wintun.dll`, which the tunnel code loads. Both are included now, and every build checks itself (`ZenLink.exe --selftest`) before it can be released.

### Not changed
- ZenLink Studio (cable and AirPlay), the USB driver switch, restore, automatic rollback and the error 259 handling.

## 2.2.1
- Fixed switching to ZenLink Studio failing with "A parameter cannot be found that matches parameter name 'DeleteKey'".
- Driver switching works on Windows in any language, survives Apple Mobile Device Service holding the device (error 259), says when a restart is needed, and undoes a failed switch cleanly.
- Apple Driver mode on iOS 26 and older showed a clear message instead of a black screen.

## 2.2
- Apple mode sound no longer crackles; App Switcher, Notifications and Control Center buttons toggle; double-click no longer goes full screen in Apple mode.
- Language choice in the first menu, stats beside the device name, single Portable.exe, opening ZenLink again shows its window.
