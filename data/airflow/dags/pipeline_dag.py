"""Daily orchestration for the final project pipeline.

Five steps, in this order:

    ingest ──┐
             ├─> dbt_build ──> enrich ──> publish_to_backend
    inbound ─┘

    ingest       Start the ingestion Container Apps job. It fetches the source
                 and lands raw JSON in your team's storage account, which the
                 warehouse reads as a volume.
    inbound      Copy the views the backend exposes in its `app` schema into
                 your catalog, so dbt can join application data with source
                 data. Skips cleanly until the backend has created one.
    dbt_build    Build staging and marts in your catalog, run the tests, and
                 record what happened in ops.dbt_test_runs.
    enrich       Start the enrichment job, which adds what SQL cannot express.
    publish      Copy the enriched mart into the backend's Postgres database.

Why separate tasks rather than one script: when dbt fails you re-run dbt, not
the fetch. And the publish must not run when dbt fails, or you hand the backend
a mart that failed its own tests. Airflow gives you both for free.

This pipeline runs end to end as it stands, against the default source. Change
the source, the models and the enrichment to your own domain; the wiring here
stays the same.

Settings
--------
Every value below comes from an Airflow Variable or an environment variable of
the same name, read at run time. They are names and hosts, not secrets:

    AZURE_SUBSCRIPTION, AZURE_RESOURCE_GROUP, ACA_INGEST_JOB, ACA_ENRICH_JOB,
    DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_CATALOG, DBT_SCHEMA,
    AZURE_TENANT_ID, BACKEND_PG_HOST, BACKEND_PG_DB, KEY_VAULT, TEAM

Every actual secret is fetched from Key Vault inside the task that needs it.
Your VM has an identity that may read your team's secrets and nobody else's,
so nothing is stored on the VM and a typo fails with a 403 rather than
reaching another team's data. Never type a secret into this file: it is
committed, and everyone can read it.

The pipeline code itself lives in `data/src` and is on the Python path as
`src`. One copy, used by the containers and by these tasks, and unit tested in
`data/tests`.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import UTC, datetime, timedelta

from airflow.sdk import Variable, dag, task
from airflow.sdk.exceptions import AirflowSkipException
from alerts import slack_alert

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    "owner": "data-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    # Every task inherits this, including ones you add later. Attaching it per
    # operator instead means the task you add at 11pm on a Thursday is the one
    # without alerting.
    "on_failure_callback": slack_alert,
}

# Where the dbt project is mounted. Local Astro puts it under
# /usr/local/airflow; the team VM runs plain Airflow at /opt/airflow.
DBT_PROJECT_DIR = os.environ.get("DBT_PROJECT_DIR", "/opt/airflow/include/dbt")


def setting(name: str, default: str | None = None) -> str:
    """Read one setting from Airflow Variables.

    The Airflow UI is where these live, under Admin -> Variables, and you are
    an admin on your team's instance. That is deliberate: you can change where
    the pipeline points without a deploy and without anyone with access to the
    machine, and the change is visible to your whole team rather than sitting
    in one person's shell.

    The environment is a fallback, for running a task on your own laptop where
    there is no Airflow database to read.

    Called inside tasks, never at module scope: a DAG file is re-parsed every
    few seconds, and a lookup up here would multiply by that.
    """
    value = Variable.get(name, default=None) or os.environ.get(name) or default
    if value is None:
        raise RuntimeError(
            f"{name} is not set. Add it in the Airflow UI under " "Admin -> Variables."
        )
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
    """Everything that talks to the warehouse, in one dictionary.

    This is exactly the set `dbt/profiles.yml` reads plus the tenant the token
    is minted at, so dbt and the Python steps cannot end up pointing at
    different places. Leave one out and dbt exits before it runs, with an
    error that names the variable and nothing else.

    Built inside a task so the two Key Vault reads happen once per run rather
    than once per parse.
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


def warehouse_client():
    """A Warehouse built from Key Vault, for the tasks that query directly."""
    from src.warehouse import Warehouse

    os.environ.update(databricks_environment())
    return Warehouse.from_env()


def backend_dsn(role: str, password: str) -> str:
    """A connection string for one specific role on the backend database.

    One role per direction, never a shared login: the credential that publishes
    marts cannot read the application's tables, and the credential that reads
    them cannot write anything.
    """
    return (
        f"host={setting('BACKEND_PG_HOST')} dbname={setting('BACKEND_PG_DB')} "
        f"user={role} password={password} sslmode=require"
    )


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
        """Fetch the source and land raw files in the team's storage account.

        The job itself decides which day it is writing, using the same UTC date
        this run belongs to. Re-running an old day overwrites that day's file
        rather than today's.
        """
        return start_job(setting("ACA_INGEST_JOB"))

    @task
    def inbound_sync() -> int:
        """Copy the backend's exposed views into the catalog.

        This is the direction people forget. The backend publishes views in its
        `app` schema, deliberately shaped and with anything personal already
        hashed, and your models can join them with source data.

        Skips until such a view exists, because a red DAG on day one teaches
        nothing. Set APP_INBOUND_TABLE when the backend has agreed one.
        """
        table = Variable.get("APP_INBOUND_TABLE", default=None) or os.environ.get(
            "APP_INBOUND_TABLE"
        )
        if not table:
            raise AirflowSkipException(
                "APP_INBOUND_TABLE is not set: the backend has not exposed a "
                "view in the app schema yet. Agree one, then set the variable."
            )

        from src.enrich import sql_literal
        from src.sync import read_app_table

        password = keyvault("fp-pg-app-reader-" + setting("TEAM"))
        rows = read_app_table(backend_dsn("app_reader", password), table)
        if not rows:
            logger.info("app.%s is empty, nothing to land", table)
            return 0

        warehouse = warehouse_client()
        catalog, schema = warehouse.catalog, setting("DBT_SCHEMA")
        columns = list(rows[0])
        target = f"{catalog}.{schema}_app.{table}"
        warehouse.run(f"create schema if not exists {catalog}.{schema}_app")
        warehouse.run(
            f"create or replace table {target} "
            f"({', '.join(f'{name} string' for name in columns)})"
        )
        values = ", ".join(
            "(" + ", ".join(sql_literal(str(row[name])) for name in columns) + ")" for row in rows
        )
        warehouse.run(f"insert into {target} values {values}")
        logger.info("landed %d rows in %s", len(rows), target)
        return len(rows)

    # none_failed, not the default all_success. inbound_sync skips by design
    # until the backend exposes a view, and under all_success a skipped
    # upstream skips everything after it: the pipeline would quietly do nothing
    # at all, with every task green-ish and no failure to investigate.
    @task(trigger_rule="none_failed")
    def dbt_build() -> str:
        """Build the models, run the tests, record the outcome.

        dbt runs through uvx on Python 3.11: the Airflow image ships a newer
        Python than stable dbt-core supports. Both versions are pinned exactly,
        and they have to be. A wildcard like 'dbt-core==1.10.*' picks the newest
        1.10 release, and dbt-databricks 1.10.11 refuses anything from 1.10.10
        up, so the pair stops resolving the moment dbt-core ships a patch. If
        you bump one, bump both.
        """
        import subprocess

        from src.dbt_results import parse_run_results, publish_results

        databricks = databricks_environment()
        command = (
            "uvx --python 3.11 --from 'dbt-core==1.10.9' "
            "--with 'dbt-databricks==1.10.11' "
            f"dbt build --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}"
        )
        result = subprocess.run(
            command,
            shell=True,
            check=False,
            env={**os.environ, **databricks},
            text=True,
            capture_output=True,
            timeout=1800,
        )
        print(result.stdout[-8000:])

        # Recorded before the task's fate is decided, so a failing test is
        # written down rather than lost. A failed run is when the record
        # matters most.
        os.environ.update(databricks)
        results = parse_run_results(f"{DBT_PROJECT_DIR}/target/run_results.json")
        try:
            from src.warehouse import Warehouse

            publish_results(Warehouse.from_env(), results)
        except Exception as error:  # noqa: BLE001
            logger.warning("could not publish dbt results: %s", error)

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
        """Copy the enriched mart into the backend's database, atomically.

        Runs only after everything upstream succeeded, which is what the
        dependency below buys you. The row count comes back so the log says how
        much was published.
        """
        from src.sync import publish, read_mart

        warehouse = warehouse_client()
        columns, rows = read_mart(warehouse, setting("DBT_SCHEMA"), "fct_postings_enriched")
        password = keyvault("fp-pg-analytics-writer-" + setting("TEAM"))
        dsn = backend_dsn("analytics_writer", password)
        return publish(dsn, "analytics", "fct_postings", columns, rows)

    transform = dbt_build()
    [ingest(), inbound_sync()] >> transform >> enrich() >> publish_to_backend()


final_project_pipeline()
