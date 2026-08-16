"""Daily orchestration for the final project pipeline.

    ingest -> dbt_build -> publish_to_backend

Each step is separate so that when dbt fails you re-run dbt, not the fetch, and
so the publish cannot run on a mart that failed its own tests. Enrichment is
not a task here: it is a dbt Python model, so `dbt_build` already runs it in
the right order. See data/dbt/models/marts/fct_postings_enriched.py.

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
DBT_RUNNER = "uvx --python 3.11 --from 'dbt-core==1.10.9' --with 'dbt-databricks==1.10.11' dbt"


def dbt_command() -> str:
    """The dbt command, aimed at whoever is running it.

    The same rule as databricks_environment(), and it has to be the same rule
    or the two disagree: a token in the environment is you on your machine, so
    target `dev`; no token is the VM, so target `prod` and the team's service
    principal. Hardcoding `--target prod` made the documented local run fail
    with "Env var required but not provided: 'DATABRICKS_CLIENT_ID'", asking a
    laptop for a credential it is deliberately not allowed to have.
    """
    target = "dev" if os.environ.get("DATABRICKS_TOKEN") else "prod"
    return (
        f"{DBT_RUNNER} build --target {target} "
        f"--project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}"
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


def secret(env_name: str, secret_name: str) -> str:
    """One secret: the environment first, then your team's Key Vault.

    On the VM nothing is in the environment, so every secret comes from Key
    Vault through the machine's own identity. On your laptop there is no such
    identity, so the same task reads what you put in `data/.env`. That is what
    lets you run a task locally without a copy of the DAG that skips the
    security.

    Never logged, never written to disk, and fetched inside the task rather
    than at parse time.
    """
    from_env = os.environ.get(env_name)
    if from_env:
        return from_env

    from src.common.aca import imds_token

    token = imds_token("https://vault.azure.net")
    url = (
        f"https://{setting('KEY_VAULT', 'kv-hyf-data')}.vault.azure.net"
        f"/secrets/{secret_name}?api-version=7.4"
    )
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(request, timeout=20))["value"]


def databricks_environment() -> dict[str, str]:
    """Exactly what dbt/profiles.yml reads, plus what it needs to sign in.

    One dictionary, so dbt and the Python steps cannot point at different
    places. Leave one out and dbt exits before it runs.

    Who it signs in as depends on where it runs, and the rule is the same one
    profiles.yml uses. On your machine `data/.env` has your own token, so that
    is you, and the team's service principal is neither needed nor available.
    On the VM there is no token, so it fetches the service principal from Key
    Vault with the machine's identity.

    Getting this wrong is not theoretical: asking for the service principal
    unconditionally made `airflow tasks test publish_to_backend` fail on a
    laptop with "TEAM is not set", which is the documented way to try the
    publish step locally.
    """
    where = {
        "DATABRICKS_HOST": setting("DATABRICKS_HOST"),
        "DATABRICKS_HTTP_PATH": setting("DATABRICKS_HTTP_PATH"),
        "DATABRICKS_CATALOG": setting("DATABRICKS_CATALOG"),
        "DBT_SCHEMA": setting("DBT_SCHEMA"),
    }
    if os.environ.get("DATABRICKS_TOKEN"):
        return where

    team = setting("TEAM")
    return {
        **where,
        "AZURE_TENANT_ID": setting("AZURE_TENANT_ID"),
        "DATABRICKS_CLIENT_ID": secret("DATABRICKS_CLIENT_ID", f"fp-databricks-client-id-{team}"),
        "DATABRICKS_CLIENT_SECRET": secret(
            "DATABRICKS_CLIENT_SECRET", f"fp-databricks-client-secret-{team}"
        ),
    }


def start_job(job_name: str) -> str:
    """Start one Container Apps job and wait for it."""
    from src.common.aca import imds_token, start_and_wait

    return start_and_wait(
        subscription=setting("AZURE_SUBSCRIPTION"),
        resource_group=setting("AZURE_RESOURCE_GROUP"),
        job_name=job_name,
        token=imds_token("https://management.azure.com/"),
    )


@dag(
    dag_id="final_project_pipeline",
    description="Ingest to the lakehouse, build and enrich dbt models, publish to the backend",
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    schedule="0 6 * * *",
    catchup=False,
    # One run at a time. Airflow allows sixteen by default, and two runs would
    # build into the same dbt schema and both publish through the same
    # `fct_postings__staging` table, so whichever finished second would win and
    # the loser's rows would vanish. Triggering by hand while the scheduled run
    # is going is the normal way to meet this.
    max_active_runs=1,
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
            dbt_command(),
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
    def publish_to_backend() -> int:
        """Copy the enriched mart into the backend's database, atomically."""
        from src.common.warehouse import Warehouse
        from src.publishing.sync import publish, read_mart

        os.environ.update(databricks_environment())
        columns, rows = read_mart(
            Warehouse.from_env(), setting("DBT_SCHEMA"), "fct_postings_enriched"
        )
        # Both are settings, because the role and the secret holding its
        # password are named when the database is created. `scripts/db-setup.py`
        # makes `analytics_user`; the defaults below are what the rehearsal
        # database uses until the real one exists.
        # `scripts/db-setup.py` creates this role, so the default matches the
        # database you get by following the README. The rehearsal databases use
        # `analytics_writer` instead: set the Variable there.
        user = setting("BACKEND_PG_USER", "analytics_user")
        # Two steps rather than one nested call, and deliberately. Written as
        # one, the default secret name interpolates the team eagerly, so a
        # local run with the password already in .env still failed with "TEAM
        # is not set" while fetching a secret it was never going to use.
        password = os.environ.get("BACKEND_PG_PASSWORD")
        if not password:
            secret_name = setting("BACKEND_PG_SECRET", "") or (
                f"fp-pg-analytics-writer-{setting('TEAM')}"
            )
            password = secret("BACKEND_PG_PASSWORD", secret_name)
        # sslmode=require in Azure; the local container has no certificate, so
        # `prefer` keeps one DSN working in both places.
        sslmode = setting("BACKEND_PG_SSLMODE", "require")
        dsn = (
            f"host={setting('BACKEND_PG_HOST')} port={setting('BACKEND_PG_PORT', '5432')} "
            f"dbname={setting('BACKEND_PG_DB')} user={user} password={password} "
            f"sslmode={sslmode}"
        )
        return publish(
            dsn,
            # Your own runs publish to `analytics_dev`, which you may write and
            # the scheduled run cannot even read. The default is production,
            # because on the VM there is no .env to say otherwise.
            setting("BACKEND_PG_PUBLISH_SCHEMA", "analytics"),
            # The same table name in both schemas, so promotion changes where
            # the table lives and never what the backend selects.
            "fct_postings",
            columns,
            rows,
            source=f"{Warehouse.from_env().catalog}.{setting('DBT_SCHEMA')}",
        )

    ingest() >> dbt_build() >> publish_to_backend()


final_project_pipeline()
