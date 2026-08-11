"""Daily orchestration for the final project pipeline.

Three steps, in this order:

    1. ingest   Start the Container Apps job. It fetches the source and lands
                raw files in your team's Databricks volume.
    2. dbt      Build staging and marts in your catalog, and run the tests.
    3. publish  Copy the published mart into the backend's Postgres database.

Why three separate tasks rather than one script: when step 2 fails you re-run
step 2, not the fetch. And step 3 must not run when step 2 fails, or you
publish a mart that failed its own tests. Airflow gives you both for free.

This file is a skeleton. Each task says what it has to do; you write the body.

Set these as Airflow variables before the first run. They are names and hosts,
not secrets:
    AZURE_SUBSCRIPTION, AZURE_RESOURCE_GROUP, ACA_JOB_NAME,
    DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_CATALOG, DBT_SCHEMA,
    BACKEND_PG_HOST, BACKEND_PG_DB

Every actual secret comes from Key Vault at run time, through `keyvault()`
below. Your VM has an identity that is allowed to read your team's secrets and
nobody else's, so nothing is stored on the VM and a typo in a secret name fails
with a 403 rather than reaching someone else's data. Never type a secret into
this file: it is committed, and everyone on your team can read it.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import UTC, datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task
from alerts import slack_alert

DEFAULT_ARGS = {
    "owner": "data-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    # Every task inherits this, including ones you add later. Attaching it per
    # operator instead means the task you add at 11pm on a Thursday is the one
    # without alerting.
    "on_failure_callback": slack_alert,
}

# Where the dbt project is mounted. Local Astro puts the project under
# /usr/local/airflow; the team VM runs plain Airflow at /opt/airflow. The
# override file sets this for local runs, so neither path is hardcoded here.
DBT_PROJECT_DIR = os.environ.get("DBT_PROJECT_DIR", "/opt/airflow/include/dbt")

VAULT = "kv-hyf-data"


def azure_token(resource: str) -> str:
    """A token for the VM's own identity, from the instance metadata service.

    This is what Managed Identity looks like in practice. There is no client
    secret anywhere: the VM asks Azure who it is, and Azure answers.

    Pass "https://management.azure.com/" to talk to Azure itself, or
    "https://vault.azure.net" to open Key Vault.
    """
    url = ("http://169.254.169.254/metadata/identity/oauth2/token"
           f"?api-version=2018-02-01&resource={resource}")
    request = urllib.request.Request(url, headers={"Metadata": "true"})
    return json.load(urllib.request.urlopen(request, timeout=15))["access_token"]


def keyvault(secret_name: str) -> str:
    """One secret, fetched at run time. Never logged, never written to disk."""
    token = azure_token("https://vault.azure.net")
    url = f"https://{VAULT}.vault.azure.net/secrets/{secret_name}?api-version=7.4"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(request, timeout=20))["value"]


@dag(
    dag_id="final_project_pipeline",
    description="Ingest to the lakehouse, build dbt models, publish to the backend",
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    schedule="0 6 * * *",
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["final-project"],
)
def final_project_pipeline():
    @task
    def ingest(**context) -> str:
        """Start the Container Apps job and wait for it to finish.

        Pass the logical date through, so a re-run of an old day overwrites
        that day's file instead of today's:
            context["logical_date"].date().isoformat()

        TODO: start the job, then poll its execution until it is Succeeded or
        Failed. Raise on Failed. A task that starts a job and returns
        immediately reports green while the job is still running, which makes
        the dbt step build on data that is not there yet.

        Your Airflow image has no `az` command and no Container Apps provider,
        so this is an HTTP call. Use `azure_token()` below, then:

            base = (f"https://management.azure.com/subscriptions/{SUBSCRIPTION}"
                    f"/resourceGroups/{RESOURCE_GROUP}"
                    f"/providers/Microsoft.App/jobs/{JOB_NAME}")

            POST {base}/start?api-version=2024-03-01       to start it
            GET  {base}/executions?api-version=2024-03-01  to poll status

        Match the execution by the `name` the start call returns, and treat
        anything other than Succeeded, Running or Pending as a failure.
        """
        raise NotImplementedError

    dbt_build = BashOperator(
        task_id="dbt_build",
        # dbt runs through uvx on Python 3.11: the Airflow image ships a newer
        # Python than stable dbt-core supports.
        #
        # Both versions are pinned exactly, and they have to be. A wildcard like
        # 'dbt-core==1.10.*' picks the newest 1.10 release, and dbt-databricks
        # 1.10.11 refuses anything from 1.10.10 up, so the pair stops resolving
        # the moment dbt-core ships a patch. If you bump one, bump both.
        #
        # TODO: pass your catalog in --vars, then check that `dbt build` fails
        # the DAG when a test fails.
        bash_command=(
            "uvx --python 3.11 --from 'dbt-core==1.10.9' "
            "--with 'dbt-databricks==1.10.11' "
            f"dbt build --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROJECT_DIR}"
        ),
    )

    @task
    def publish_to_backend() -> int:
        """Copy the published mart into the backend's database.

        Runs only after dbt succeeds, which is what the dependency below buys
        you. Use src/sync.py, and return the row count so the log says how much
        was published.

        TODO: implement, then answer one question in your README: what does the
        backend see while this task is halfway through?
        """
        raise NotImplementedError

    ingest() >> dbt_build >> publish_to_backend()


final_project_pipeline()
