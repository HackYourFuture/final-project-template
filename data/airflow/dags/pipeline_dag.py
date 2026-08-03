"""Daily orchestration for the final project pipeline.

Two tasks in sequence: ingest raw data, then let dbt shape it. Keeping them
separate means a dbt failure does not force you to re-fetch from the API, and
you can see at a glance which half broke.

Set these Airflow variables (or environment variables) before the first run:
    SOURCE_API_URL, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_SCHEMA_RAW, DBT_SCHEMA
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

DEFAULT_ARGS = {
    "owner": "data-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="final_project_pipeline",
    description="Ingest source data, then build dbt models",
    start_date=datetime(2026, 1, 1),
    schedule="0 6 * * *",
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["final-project"],
)
def final_project_pipeline():
    @task
    def ingest() -> int:
        """Fetch, validate, and store raw records."""
        from src.pipeline import run

        return run()

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="cd /usr/local/airflow/include/dbt && dbt build --profiles-dir .",
    )

    ingest() >> dbt_build


final_project_pipeline()
