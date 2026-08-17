#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./common.sh
. "$SCRIPT_DIR/common.sh"

require_cmd az
require_cmd curl
require_cmd uv
require_cmd psql

load_data_env

print_step "Checking LANDING_PREFIX and LANDING_PATH consistency"
[[ -n "${LANDING_PREFIX:-}" ]] || fail "LANDING_PREFIX is empty in data/.env"
[[ -n "${LANDING_PATH:-}" ]] || fail "LANDING_PATH is empty in data/.env"

# LANDING_PATH is /Volumes/<catalog>/landing/<volume>/<prefix>/<source>, where
# `landing` is the schema holding every volume and <volume> is the container:
# `dev` for your runs, `prod` for the scheduled one. Pull both out, because a
# path can disagree with LANDING_CONTAINER as easily as with LANDING_PREFIX.
path_volume="$(echo "$LANDING_PATH" | sed -n 's#^.*/landing/\([^/]*\)/.*#\1#p')"
path_prefix="$(echo "$LANDING_PATH" | sed -n 's#^.*/landing/[^/]*/\([^/]*\)/.*#\1#p')"

if [[ -z "$path_volume" ]]; then
  echo "warning: could not read a volume out of LANDING_PATH: $LANDING_PATH" >&2
elif [[ "$path_volume" != "$LANDING_CONTAINER" ]]; then
  echo "warning: LANDING_PATH reads the '$path_volume' volume while LANDING_CONTAINER writes '$LANDING_CONTAINER'. dbt will build from files this run did not write." >&2
else
  echo "LANDING_CONTAINER and LANDING_PATH name the same container."
fi

if [[ -z "$path_prefix" ]]; then
  echo "warning: could not infer prefix from LANDING_PATH: $LANDING_PATH" >&2
elif [[ "$path_prefix" == "$LANDING_PREFIX" ]]; then
  echo "LANDING_PREFIX and LANDING_PATH are aligned."
else
  echo "warning: LANDING_PATH uses '$path_prefix' while LANDING_PREFIX is '$LANDING_PREFIX' (this is expected for Path B using aca-dev)." >&2
fi

print_step "Checking Azure login"
az account show --query "{user:user.name,subscription:id,tenant:tenantId}" -o table

if [[ -n "${AZURE_TENANT_ID:-}" ]]; then
  current_tenant="$(az account show --query tenantId -o tsv)"
  if [[ "$current_tenant" != "$AZURE_TENANT_ID" ]]; then
    fail "Azure tenant mismatch. Current tenant is '$current_tenant' but AZURE_TENANT_ID is '$AZURE_TENANT_ID'. Run: az login --tenant $AZURE_TENANT_ID"
  fi
  echo "Azure tenant matches AZURE_TENANT_ID."
fi

if [[ -n "${AZURE_SUBSCRIPTION:-}" ]]; then
  current_subscription="$(az account show --query id -o tsv)"
  if [[ "$current_subscription" != "$AZURE_SUBSCRIPTION" ]]; then
    fail "Azure subscription mismatch. Current subscription is '$current_subscription' but AZURE_SUBSCRIPTION is '$AZURE_SUBSCRIPTION'. Run: az account set --subscription $AZURE_SUBSCRIPTION"
  fi
  echo "Azure subscription matches AZURE_SUBSCRIPTION."
fi

print_step "Checking Databricks token"
[[ -n "${DATABRICKS_TOKEN:-}" ]] || fail "DATABRICKS_TOKEN is empty in data/.env"
[[ -n "${DATABRICKS_HOST:-}" ]] || fail "DATABRICKS_HOST is empty in data/.env"

http_code="$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $DATABRICKS_TOKEN" \
  "$DATABRICKS_HOST/api/2.0/sql/warehouses")"

[[ "$http_code" == "200" ]] || fail "Databricks token check failed (HTTP $http_code)"
echo "Databricks token check passed (HTTP 200)."

print_step "Checking dbt connectivity"
(
  cd "$REPO_ROOT/data/dbt"
  uv run --project .. --extra dbt dbt debug
)

print_step "Checking $LANDING_CONTAINER/$LANDING_PREFIX prefix visibility"
az storage blob list \
  --account-name "$STORAGE_ACCOUNT" \
  --container-name "$LANDING_CONTAINER" \
  --prefix "$LANDING_PREFIX" \
  --auth-mode login \
  --query "[].{name:name,modified:properties.lastModified,bytes:properties.contentLength}" \
  -o table

print_step "Checking Postgres schemas"
PGPASSWORD="$BACKEND_PG_PASSWORD" psql \
  -h "$BACKEND_PG_HOST" \
  -p "$BACKEND_PG_PORT" \
  -U "$BACKEND_PG_USER" \
  -d "$BACKEND_PG_DB" \
  -c '\dn'

echo
echo "Preflight completed."
