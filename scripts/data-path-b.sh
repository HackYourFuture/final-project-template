#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
. "$SCRIPT_DIR/common.sh"

require_cmd astro

print_step "Restarting local Astro stack"
(
  cd "$REPO_ROOT/data/airflow"
  astro dev restart
)

echo
echo "Path B setup completed."
echo "Next: unpause and trigger final_project_pipeline in the Airflow UI."
