<!-- Release notes for v2.5.2. -->

**ZenLink 2.5.2** brings native support for **macOS on Apple Silicon (arm64)** alongside full Windows compatibility.

### ✨ What's new

- **🍎 Native macOS Support (Apple Silicon arm64).**
  - Compiled as a native Mach-O 64-bit binary for `aarch64-apple-darwin`.
  - Native Slint Liquid Glass UI with AppKit window handle integration and system clipboard (`pbcopy` / `pbpaste`).
  - Standard macOS filesystem conventions: configuration and local data in `~/Library/Application Support/ZenLink-Next`, logs in `~/Library/Logs/ZenLink-Next/logs`.
- **🎨 Embedded Fluent Icon Font.**
  - Embedded `Segoe Fluent Icons` directly into the UI bundle so all navigation buttons, control icons, WiFi badges, and dialog glyphs render natively on macOS without missing characters or tofu boxes.
- **🛠️ macOS Helper & Developer Tools.**
  - `tools/get-adb`: Native POSIX script downloading official Google Darwin platform-tools with SHA-256 validation and codesign verification.
  - `tools/ocr.swift`: Apple Vision framework (`VNRecognizeTextRequest`) native OCR with clean fallbacks.
  - `Start ZenLink.sh` & `run.sh`: Automated macOS setup, environment checking, Rust compilation, and launch.
- **📦 macOS Installer (`.dmg`).**
  - Standalone `ZenLink.app` packaged in an Apple Silicon `.dmg` disk image with one-drag install to `/Applications`.

### 🛠️ Compatibility

- Existing Windows functionality, build scripts, tests, and configurations remain 100% intact and unaffected.
- Audio and AirPlay decryption modules ported natively for macOS (`libplayfair.dylib`).

**Assets:** `ZenLink-v2.5.2-mac-arm64.dmg` (macOS installer), `Setup.exe` (Windows installer), `Portable.exe` (Windows portable), `Portable-Source.zip`.
