#!/usr/bin/env bash
# Builds ZenLink binary on macOS and shows elapsed time and estimate.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUST_DIR="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"

STAMP="$RUST_DIR/target/last-build-seconds.txt"
LAST=0
if [[ -f "$STAMP" ]]; then
    LAST="$(cat "$STAMP" 2>/dev/null || echo 0)"
    LAST="${LAST//[^0-9]/}"
    LAST="${LAST:-0}"
fi

format_time() {
    local s="$1"
    local m=$((s / 60))
    local sec=$((s % 60))
    printf "%d:%02d" "$m" "$sec"
}

if [[ "$LAST" -gt 0 ]]; then
    EST="~$(format_time "$LAST")"
else
    EST="a few minutes"
fi

echo "Expected time: $EST. The last step (ZenLink(bin)) optimises the whole app"
echo "and shows no progress; it takes the longest. Keep this terminal open."

START_TIME="$(date +%s)"

cargo build --release --manifest-path "$RUST_DIR/Cargo.toml" -p zenlink-app
STATUS=$?

END_TIME="$(date +%s)"
TOOK=$((END_TIME - START_TIME))

if [[ $STATUS -eq 0 ]]; then
    echo "Built in $(format_time "$TOOK")."
    if [[ $TOOK -ge 20 ]]; then
        mkdir -p "$RUST_DIR/target"
        echo "$TOOK" > "$STAMP"
    fi
fi

exit $STATUS
