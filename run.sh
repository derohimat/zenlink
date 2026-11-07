#!/usr/bin/env bash
# Runs ZenLink in console (diagnostic) mode on macOS.
set -euo pipefail
cd "$(dirname "$0")"

if [[ -x "ZenLinkService" ]]; then
    exec "./ZenLinkService" "$@"
fi

if [[ ! -f ".venv/bin/python" ]]; then
    echo "First run ./Start\\ ZenLink.sh once to set up the Python environment."
    exit 1
fi

exec .venv/bin/python -X dev -m zenlink "$@"
