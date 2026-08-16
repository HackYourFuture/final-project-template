#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/preflight.sh"
"$SCRIPT_DIR/data-path-a.sh"

echo
echo "run-all completed (preflight + path A)."
