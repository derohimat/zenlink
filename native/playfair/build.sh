#!/usr/bin/env bash
# Builds libplayfair.dylib on macOS using clang (AirPlay FairPlay key decryption).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="$ROOT_DIR/zenlink/airplay"

mkdir -p "$OUT_DIR"
cd "$SCRIPT_DIR"

clang -O2 -dynamiclib -Wall \
    -D"__declspec(x)=__attribute__((visibility(\"default\")))" \
    -o "$OUT_DIR/libplayfair.dylib" \
    export.c playfair.c omg_hax.c hand_garble.c modified_md5.c sap_hash.c

echo "Built $OUT_DIR/libplayfair.dylib"
