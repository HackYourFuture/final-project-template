#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
. "$SCRIPT_DIR/common.sh"

require_cmd docker

print_step "Stopping local compose stack"
(
  cd "$REPO_ROOT"
  docker compose down
)

echo
echo "App stack is down."
