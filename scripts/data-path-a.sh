#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
. "$SCRIPT_DIR/common.sh"

require_cmd uv
require_cmd az

load_data_env
assert_data_env_vars

print_step "Step 1: ingest source data"
(
  cd "$REPO_ROOT/data"
  uv run python -m src.ingestion.pipeline
)

print_step "Step 2: verify landed blob metadata"
az storage blob list \
  --account-name "$STORAGE_ACCOUNT" \
  --container-name "$LANDING_CONTAINER" \
  --prefix "$LANDING_PREFIX" \
  --auth-mode login \
  --query "[].{name:name,modified:properties.lastModified,bytes:properties.contentLength}" \
  -o table

print_step "Step 3: dbt build"
(
  cd "$REPO_ROOT/data/dbt"
  uv run --project .. dbt build
)

print_step "Step 4: publish mart to backend"
(
  cd "$REPO_ROOT/data"
  uv run --extra sync python -m src.publishing.sync
)

echo
echo "Path A completed."
