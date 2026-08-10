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

Set these Airflow variables before the first run:
    AZURE_RESOURCE_GROUP, ACA_JOB_NAME,
    DATABRICKS_HOST, DATABRICKS_HTTP_PATH,
    DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET,
    DATABRICKS_CATALOG, DBT_SCHEMA,
    BACKEND_PG_HOST, BACKEND_PG_DB, BACKEND_PG_USER, BACKEND_PG_PASSWORD

Read the secret ones from Key Vault. Your VM has an identity that is allowed to
read your team's secrets and nobody else's, so the DAG fetches them at run time
and nothing is stored on the VM. Never type a secret into this file: it is
committed, and everyone on your team can read it.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task

DEFAULT_ARGS = {
    "owner": "data-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="final_project_pipeline",
    description="Ingest to the lakehouse, build dbt models, publish to the backend",
    start_date=datetime(2026, 1, 1),
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

        Two ways in, both fine:
          - `az containerapp job start` in a BashOperator, then poll with
            `az containerapp job execution show`
          - the azure-mgmt-appcontainers SDK from Python
        """
        raise NotImplementedError

    dbt_build = BashOperator(
        task_id="dbt_build",
        # dbt runs through uvx on Python 3.11: the Airflow image ships a newer
        # Python than stable dbt-core supports.
        #
        # TODO: point --project-dir at your dbt folder and pass your catalog in
        # --vars, then check that `dbt build` fails the DAG when a test fails.
        bash_command=(
            "uvx --python 3.11 --from 'dbt-core==1.10.*' "
            "--with 'dbt-databricks==1.10.*' "
            "dbt build --project-dir /opt/airflow/include/dbt --profiles-dir /opt/airflow/include/dbt"
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
