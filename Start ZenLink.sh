#!/usr/bin/env bash
# ZenLink developer startup & launch script for macOS.
set -euo pipefail

cd "$(dirname "$0")"

echo "ZenLink (macOS Apple Silicon) - startup"
echo ""

ZL_ADB_REV="37.0.1"
ZL_ADB_SHA256="ee39ad5967e95c2a07f04dbcbde96b1a0c916ba376096db5d2f498b7727a5d1d"

VENV=".venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
STAMP="$VENV/.requirements"
STAMPLOCK="$VENV/.requirements-lock"

# Fast path: environment exists and requirements haven't changed
if [[ -f "$PY" && -f "$STAMP" && -f "$STAMPLOCK" ]]; then
    if cmp -s "requirements.txt" "$STAMP" && cmp -s "requirements.lock" "$STAMPLOCK"; then
        goto_launch=true
    fi
fi

if [[ "${goto_launch:-false}" != "true" ]]; then
    if [[ ! -f "$PY" ]]; then
        SYS_PY=""
        for v in python3.13 python3.12 python3.11; do
            if command -v "$v" >/dev/null 2>&1; then
                SYS_PY="$v"
                break
            fi
        done

        if [[ -z "$SYS_PY" ]] && command -v uv >/dev/null 2>&1; then
            for v in 3.13 3.12 3.11; do
                if uv_py="$(uv python find "$v" 2>/dev/null)" && [[ -n "$uv_py" && -x "$uv_py" ]]; then
                    SYS_PY="$uv_py"
                    break
                fi
            done
        fi

        if [[ -z "$SYS_PY" ]] && command -v python3 >/dev/null 2>&1; then
            if python3 -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)" 2>/dev/null; then
                SYS_PY="python3"
            fi
        fi

        if [[ -z "$SYS_PY" ]]; then
            echo "Python 3.11, 3.12 or 3.13 is required."
            echo "Install via Homebrew: brew install python@3.13"
            exit 1
        fi

        echo "[1/3] Creating Python environment (.venv) using $SYS_PY..."
        "$SYS_PY" -m venv "$VENV"
    fi

    echo "[2/3] Installing components..."
    "$PIP" install --disable-pip-version-check -q --upgrade pip >/dev/null 2>&1 || true
    "$PIP" install --disable-pip-version-check -q -r requirements.txt || {
        echo "Failed to install Python requirements." >&2
        exit 1
    }
    cp -f requirements.txt "$STAMP"
    cp -f requirements.lock "$STAMPLOCK"
    echo "[3/3] Python environment ready."
fi

# Check Android adb
check_adb() {
    if [[ -x "third_party/platform-tools/adb" ]] || [[ -f ".no-adb" ]]; then
        return 0
    fi
    if [[ -n "${ANDROID_HOME:-}" && -x "$ANDROID_HOME/platform-tools/adb" ]]; then
        return 0
    fi
    if [[ -n "${ANDROID_SDK_ROOT:-}" && -x "$ANDROID_SDK_ROOT/platform-tools/adb" ]]; then
        return 0
    fi
    if [[ -x "$HOME/Library/Android/sdk/platform-tools/adb" ]]; then
        return 0
    fi
    if command -v adb >/dev/null 2>&1; then
        return 0
    fi

    echo ""
    echo "  - Android phones and tablets need adb (Google platform-tools $ZL_ADB_REV, about 16 MB)."
    if [[ -t 0 ]]; then
        read -r -p "    Download it from Google now? iPhone and iPad work without it. [Y/n] " answer
        answer="${answer:-Y}"
    else
        answer="Y"
    fi
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        chmod +x tools/get-adb
        tools/get-adb "third_party/platform-tools" "$ZL_ADB_REV" "$ZL_ADB_SHA256" || {
            echo "    adb could not be downloaded. ZenLink still starts; Android needs adb."
        }
    else
        echo "Not downloaded. Delete .no-adb to be asked again." > .no-adb
    fi
}

check_adb

# Local overrides (machine-only settings)
if [[ -f "Start ZenLink.local.sh" ]]; then
    # shellcheck disable=SC1091
    source "Start ZenLink.local.sh"
fi

# Build Rust window if cargo is available
if command -v cargo >/dev/null 2>&1; then
    if [[ -x "rust/tools/build-window.sh" ]]; then
        rust/tools/build-window.sh "rust" || true
    else
        echo "Building ZenLink application (Rust)..."
        cargo build --release --manifest-path rust/Cargo.toml -p zenlink-app || true
    fi
fi

# Launch
for bin in "rust/target/aarch64-apple-darwin/release/ZenLink" "rust/target/release/ZenLink" "./ZenLink"; do
    if [[ -x "$bin" ]]; then
        exec "$bin" "$@"
    fi
done

echo "Launching Python backend (classic mode)..."
exec "$PY" -m zenlink "$@"
