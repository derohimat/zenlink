#!/usr/bin/env bash
# ==============================================================================
# Build macOS .app bundle and .dmg installer for ZenLink (Apple Silicon arm64)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSION="${1:-2.5.2}"
ARCH="arm64"
TARGET="aarch64-apple-darwin"

echo "=================================================================="
echo " ZenLink macOS Package & DMG Builder"
echo " Version: $VERSION ($ARCH)"
echo " Repository Root: $REPO_ROOT"
echo "=================================================================="

DIST_DIR="$REPO_ROOT/dist"
BUILD_DIR="$REPO_ROOT/build/mac"
APP_NAME="ZenLink"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
DMG_NAME="ZenLink-v$VERSION-mac-$ARCH.dmg"
DMG_PATH="$DIST_DIR/$DMG_NAME"

mkdir -p "$DIST_DIR" "$BUILD_DIR"

# 1. Ensure official Darwin platform-tools (adb) is present
echo "[1/7] Ensuring adb platform-tools are present..."
chmod +x "$REPO_ROOT/tools/get-adb"
"$REPO_ROOT/tools/get-adb" "$REPO_ROOT/third_party/platform-tools"

# 2. Build libplayfair.dylib if needed
echo "[2/7] Checking AirPlay playfair dylib..."
if [[ ! -f "$REPO_ROOT/zenlink/airplay/libplayfair.dylib" ]]; then
    chmod +x "$REPO_ROOT/native/playfair/build.sh"
    "$REPO_ROOT/native/playfair/build.sh"
fi

# 3. Build native Rust application (release)
echo "[3/7] Compiling native Rust binary ($TARGET)..."
cargo build --release --manifest-path "$REPO_ROOT/rust/Cargo.toml" -p zenlink-app --target "$TARGET"
RUST_BIN="$REPO_ROOT/rust/target/$TARGET/release/ZenLink"
if [[ ! -f "$RUST_BIN" ]]; then
    echo "Error: Rust binary not found at $RUST_BIN" >&2
    exit 1
fi

# 4. Freeze Python backend (ZenLinkService) using PyInstaller
echo "[4/7] Freezing Python backend (ZenLinkService)..."
PY_BIN="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then
    echo "Error: Virtualenv python not found at $PY_BIN" >&2
    exit 1
fi

PYTHONPATH="$REPO_ROOT" "$PY_BIN" -m PyInstaller "$REPO_ROOT/packaging/launch.py" \
    --name ZenLinkService \
    --onedir \
    --noconfirm \
    --clean \
    --noupx \
    --paths "$REPO_ROOT" \
    --collect-all zenlink \
    --collect-all sounddevice \
    --collect-all usb \
    --add-data "$REPO_ROOT/assets:assets" \
    --add-data "$REPO_ROOT/tools:tools" \
    --collect-all pymobiledevice3 \
    --recursive-copy-metadata pymobiledevice3 \
    --collect-all pmd_pytcp \
    --collect-all pmd_net_addr \
    --collect-all zeroconf \
    --add-binary "$REPO_ROOT/zenlink/airplay/libplayfair.dylib:zenlink/airplay" \
    --exclude-module av \
    --exclude-module tkinter \
    --exclude-module matplotlib \
    --exclude-module IPython \
    --exclude-module webview \
    --exclude-module clr \
    --exclude-module clr_loader \
    --exclude-module pythonnet \
    --exclude-module bottle \
    --exclude-module proxy_tools \
    --exclude-module pystray \
    --exclude-module PIL \
    --exclude-module chardet \
    --exclude-module pydantic \
    --exclude-module pydantic_core \
    --exclude-module pefile \
    --distpath "$DIST_DIR/mac" \
    --workpath "$BUILD_DIR" >/dev/null

# Self-test frozen ZenLinkService
echo "  - Running frozen backend self-test..."
SELFTEST_REPORT="$BUILD_DIR/selftest.json"
"$DIST_DIR/mac/ZenLinkService/ZenLinkService" --selftest "$SELFTEST_REPORT"
if ! grep -q '"ok": true' "$SELFTEST_REPORT"; then
    echo "Error: Frozen ZenLinkService failed selftest:" >&2
    cat "$SELFTEST_REPORT" >&2
    exit 1
fi
echo "  - Frozen backend self-test OK."

# 5. Generate macOS AppIcon.icns
echo "[5/7] Generating macOS iconset & AppIcon.icns..."
ICONSET_DIR="$BUILD_DIR/AppIcon.iconset"
rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"
SRC_LOGO="$REPO_ROOT/assets/logo.png"

for s in 16 32 64 128 256 512; do
    sips -z "$s" "$s" "$SRC_LOGO" --out "$ICONSET_DIR/icon_${s}x${s}.png" >/dev/null 2>&1
    if (( s * 2 <= 1024 )); then
        sips -z "$((s * 2))" "$((s * 2))" "$SRC_LOGO" --out "$ICONSET_DIR/icon_${s}x${s}@2x.png" >/dev/null 2>&1
    fi
done

ICNS_FILE="$BUILD_DIR/AppIcon.icns"
iconutil -c icns "$ICONSET_DIR" -o "$ICNS_FILE"

# 6. Assemble ZenLink.app bundle
echo "[6/7] Assembling $APP_NAME.app bundle..."
rm -rf "$APP_BUNDLE"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

# Copy PyInstaller frozen backend files into MacOS
cp -R "$DIST_DIR/mac/ZenLinkService/"* "$MACOS_DIR/"

# Copy main Rust executable
cp "$RUST_BIN" "$MACOS_DIR/ZenLink"
chmod +x "$MACOS_DIR/ZenLink" "$MACOS_DIR/ZenLinkService"

# Copy third_party adb & tools into MacOS
mkdir -p "$MACOS_DIR/third_party/platform-tools" "$MACOS_DIR/third_party/scrcpy"
cp "$REPO_ROOT/third_party/platform-tools/adb" "$MACOS_DIR/third_party/platform-tools/"
cp "$REPO_ROOT/third_party/platform-tools/NOTICE.txt" "$MACOS_DIR/third_party/platform-tools/"
chmod +x "$MACOS_DIR/third_party/platform-tools/adb"
if [[ -f "$REPO_ROOT/third_party/scrcpy/LICENSE" ]]; then
    cp "$REPO_ROOT/third_party/scrcpy/LICENSE" "$MACOS_DIR/third_party/scrcpy/"
fi

# Copy icon and notices into Resources
cp "$ICNS_FILE" "$RESOURCES_DIR/AppIcon.icns"
cp "$REPO_ROOT/LICENSE" "$RESOURCES_DIR/"
cp "$REPO_ROOT/README.md" "$RESOURCES_DIR/"
cp "$REPO_ROOT/docs/THIRD_PARTY.md" "$RESOURCES_DIR/"

# Create Info.plist
cat <<EOF > "$CONTENTS_DIR/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>ZenLink</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.zenvy.zenlink</string>
    <key>CFBundleName</key>
    <string>ZenLink</string>
    <key>CFBundleDisplayName</key>
    <string>ZenLink</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
</dict>
</plist>
EOF

# Code sign bundle (ad-hoc)
codesign --force --deep -s - "$APP_BUNDLE" >/dev/null 2>&1 || true
echo "  - Bundle created: $APP_BUNDLE"

# 7. Create .dmg Disk Image
echo "[7/7] Generating DMG installer ($DMG_NAME)..."
DMG_STAGE="$BUILD_DIR/dmg_stage"
rm -rf "$DMG_STAGE" "$DMG_PATH"
mkdir -p "$DMG_STAGE"

cp -R "$APP_BUNDLE" "$DMG_STAGE/"
ln -s /Applications "$DMG_STAGE/Applications"
cp "$REPO_ROOT/README.md" "$DMG_STAGE/README.txt"

hdiutil create \
    -volname "ZenLink" \
    -srcfolder "$DMG_STAGE" \
    -ov \
    -format UDZO \
    "$DMG_PATH" >/dev/null

DMG_SIZE="$(du -h "$DMG_PATH" | awk '{print $1}')"
echo ""
echo "=================================================================="
echo " BUILD SUCCESSFUL!"
echo " DMG Asset: $DMG_PATH ($DMG_SIZE)"
echo " App Bundle: $APP_BUNDLE"
echo "=================================================================="
