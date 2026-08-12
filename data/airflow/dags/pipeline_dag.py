"""Daily orchestration for the final project pipeline.

    ingest -> dbt_build -> enrich -> publish_to_backend

Each step is separate so that when dbt fails you re-run dbt, not the fetch, and
so the publish cannot run on a mart that failed its own tests.

Settings come from Airflow Variables (Admin -> Variables), read when the task
runs. Secrets never do: each is fetched from Key Vault inside the task that
needs it, using the machine's identity. See data/README.md, "What runs in
Airflow".
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import UTC, datetime, timedelta

from airflow.sdk import Variable, dag, task
from alerts import slack_alert

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "data-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    # Inherited by every task, including the one you add at 11pm on a Thursday.
    "on_failure_callback": slack_alert,
}

# Astro mounts the project under /usr/local/airflow; the team VM uses
# /opt/airflow. Neither is hardcoded.
DBT_PROJECT_DIR = os.environ.get("DBT_PROJECT_DIR", "/opt/airflow/include/dbt")

# Pinned exactly, and they have to be: dbt-databricks 1.10.11 requires
# dbt-core <1.10.10, so a wildcard stops resolving on the next patch release.
# Bump the two together. uvx, because the Airflow image ships a newer Python
# than stable dbt-core supports.
DBT_COMMAND = (
    "uvx --python 3.11 --from 'dbt-core==1.10.9' --with 'dbt-databricks==1.10.11' "
    f"dbt build --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}"
)


def setting(name: str, default: str | None = None) -> str:
    """One setting from Airflow Variables, environment as a local fallback.

    Called inside tasks, never at module scope: a DAG file is re-parsed every
    few seconds.
    """
    value = Variable.get(name, default=None) or os.environ.get(name) or default
    if value is None:
        raise RuntimeError(f"{name} is not set. Add it in the Airflow UI under Admin -> Variables.")
    return value


def keyvault(secret_name: str) -> str:
    """One secret, fetched at run time. Never logged, never written to disk."""
    from src.aca import imds_token

    token = imds_token("https://vault.azure.net")
    url = (
        f"https://{setting('KEY_VAULT', 'kv-hyf-data')}.vault.azure.net"
        f"/secrets/{secret_name}?api-version=7.4"
    )
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(request, timeout=20))["value"]


def databricks_environment() -> dict[str, str]:
    """Exactly what dbt/profiles.yml reads, plus the tenant for the token.

    One dictionary, so dbt and the Python steps cannot point at different
    places. Leave one out and dbt exits before it runs.
    """
    team = setting("TEAM")
    return {
        "DATABRICKS_HOST": setting("DATABRICKS_HOST"),
        "DATABRICKS_HTTP_PATH": setting("DATABRICKS_HTTP_PATH"),
        "DATABRICKS_CATALOG": setting("DATABRICKS_CATALOG"),
        "DBT_SCHEMA": setting("DBT_SCHEMA"),
        "AZURE_TENANT_ID": setting("AZURE_TENANT_ID"),
        "DATABRICKS_CLIENT_ID": keyvault(f"fp-databricks-client-id-{team}"),
        "DATABRICKS_CLIENT_SECRET": keyvault(f"fp-databricks-client-secret-{team}"),
    }


def start_job(job_name: str) -> str:
    """Start one Container Apps job and wait for it."""
    from src.aca import imds_token, start_and_wait

    return start_and_wait(
        subscription=setting("AZURE_SUBSCRIPTION"),
        resource_group=setting("AZURE_RESOURCE_GROUP"),
        job_name=job_name,
        token=imds_token("https://management.azure.com/"),
    )


@dag(
    dag_id="final_project_pipeline",
    description="Ingest to the lakehouse, build dbt models, enrich, publish to the backend",
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    schedule="0 6 * * *",
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["final-project"],
)
def final_project_pipeline():
    @task
    def ingest() -> str:
        """Fetch the source and land raw files in the team's storage account."""
        return start_job(setting("ACA_INGEST_JOB"))

    @task
    def dbt_build() -> str:
        """Build the models and run the tests."""
        import subprocess

        result = subprocess.run(
            DBT_COMMAND,
            shell=True,
            check=False,
            env={**os.environ, **databricks_environment()},
            text=True,
            capture_output=True,
            timeout=1800,
        )
        print(result.stdout[-8000:])
        if result.returncode != 0:
            print(result.stderr[-4000:])
            raise RuntimeError(f"dbt build exited {result.returncode}")

        summary = [line for line in result.stdout.splitlines() if "PASS=" in line]
        return summary[-1].strip() if summary else "dbt build finished"

    @task
    def enrich() -> str:
        """Add the column dbt cannot: see data/src/enrich.py for why."""
        return start_job(setting("ACA_ENRICH_JOB"))

    @task
    def publish_to_backend() -> int:
        """Copy the enriched mart into the backend's database, atomically."""
        from src.sync import publish, read_mart
        from src.warehouse import Warehouse

        os.environ.update(databricks_environment())
        columns, rows = read_mart(
            Warehouse.from_env(), setting("DBT_SCHEMA"), "fct_postings_enriched"
        )
        dsn = (
            f"host={setting('BACKEND_PG_HOST')} dbname={setting('BACKEND_PG_DB')} "
            f"user=analytics_writer "
            f"password={keyvault('fp-pg-analytics-writer-' + setting('TEAM'))} "
            "sslmode=require"
        )
        return publish(dsn, "analytics", "fct_postings", columns, rows)

    ingest() >> dbt_build() >> enrich() >> publish_to_backend()


final_project_pipeline()
