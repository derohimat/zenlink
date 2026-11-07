#!/usr/bin/env bash
# ==============================================================================
# ZenLink macOS E2E Test Runner
#
# Runs comprehensive 4-tier E2E tests for ZenLink on macOS (Apple Silicon arm64).
# Supports running individual tiers or the entire test suite.
#
# Usage:
#   tests/e2e/runner.sh [options]
#
# Options:
#   --tier <1|2|3|4>   Run only tests from the specified tier
#   -v, --verbose      Enable verbose test output
#   -h, --help         Display this help message
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

TIER_ARG=""
VERBOSE_ARG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tier)
            if [[ -n "${2:-}" && "$2" =~ ^[1-4]$ ]]; then
                TIER_ARG="--tier $2"
                shift 2
            else
                echo "Error: --tier requires an argument between 1 and 4." >&2
                exit 1
            fi
            ;;
        -v|--verbose)
            VERBOSE_ARG="-v"
            shift
            ;;
        -h|--help)
            echo "ZenLink macOS E2E Test Suite Runner"
            echo "Usage: $0 [--tier <1|2|3|4>] [-v|--verbose] [-h|--help]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--tier <1|2|3|4>] [-v|--verbose] [-h|--help]" >&2
            exit 1
            ;;
    esac
done

# Select Python runtime: prefer virtualenv if available, else python3
PYTHON_BIN="python3"
if [[ -f "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
elif command -v /opt/homebrew/bin/python3.11 &>/dev/null; then
    PYTHON_BIN="/opt/homebrew/bin/python3.11"
elif command -v /Users/denirohimat/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/bin/python3.11 &>/dev/null; then
    PYTHON_BIN="/Users/denirohimat/.local/share/uv/python/cpython-3.11.14-macos-aarch64-none/bin/python3.11"
fi

echo "=================================================================="
echo " ZenLink macOS E2E Test Suite Runner (Apple Silicon arm64)"
echo "=================================================================="
echo " Repository Root: $REPO_ROOT"
echo " Python Runtime : $PYTHON_BIN ($($PYTHON_BIN --version 2>&1))"
echo " Platform       : $(uname -s) $(uname -m)"
echo " Selected Tier  : ${TIER_ARG:-All Tiers (1-4)}"
echo "=================================================================="
echo ""

START_TIME=$(date +%s)

# Execute test suite
set +e
"$PYTHON_BIN" "$REPO_ROOT/tests/test_macos_e2e.py" $TIER_ARG $VERBOSE_ARG
EXIT_CODE=$?
set -e

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "=================================================================="
if [[ $EXIT_CODE -eq 0 ]]; then
    echo " RESULT: ALL TESTS PASSED (${ELAPSED}s)"
else
    echo " RESULT: TEST SUITE FAILED (exit code: $EXIT_CODE, ${ELAPSED}s)"
fi
echo "=================================================================="

exit $EXIT_CODE
