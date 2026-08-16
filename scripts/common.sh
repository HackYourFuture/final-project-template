#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "error: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

load_data_env() {
  local env_file="$REPO_ROOT/data/.env"
  [[ -f "$env_file" ]] || fail "missing file: $env_file (copy data/.env.example first)"

  set -a
  # shellcheck source=/dev/null
  . "$env_file"
  set +a
}

assert_data_env_vars() {
  local required=(
    STORAGE_ACCOUNT
    LANDING_CONTAINER
    LANDING_PREFIX
    DATABRICKS_CATALOG
    DBT_SCHEMA
    LANDING_PATH
    BACKEND_PG_HOST
    BACKEND_PG_PORT
    BACKEND_PG_DB
    BACKEND_PG_USER
    BACKEND_PG_PASSWORD
  )

  local name
  for name in "${required[@]}"; do
    [[ -n "${!name:-}" ]] || fail "required env var is empty: $name"
  done
}

print_step() {
  echo
  echo "==> $*"
}
