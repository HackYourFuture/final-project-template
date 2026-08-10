"""Publish a mart from Databricks into the backend's Postgres database.

This is the outbound sync, and it is the step that turns your pipeline into a
data product. The backend trainees do not query Databricks: they query their
own database, the way they always have. Your job is to put a fresh copy of the
mart there, on a schedule, without ever leaving them a half-written table.

Airflow runs this after dbt succeeds. Never before: publishing a mart that
failed its tests is worse than publishing nothing.

YOU IMPLEMENT THIS FILE.

Read side:  databricks-sql-connector, against your SQL warehouse.
Write side: psycopg, against the backend database.

The pattern that avoids a half-written table is write-then-swap:

    1. create <table>_new
    2. insert every row into it
    3. rename <table> -> <table>_old, <table>_new -> <table>, drop <table>_old
       (all three inside one transaction)

Readers see the old table until the swap, then the new one. They never see an
empty or partial table.
"""

import logging

logger = logging.getLogger(__name__)


def read_mart(http_path: str, host: str, token: str, table: str) -> list[dict]:
    """Read every row of a published mart from Databricks.

    Args:
        table: fully qualified, e.g. team_a.analytics.fct_postings

    TODO: implement with databricks.sql.connect. Return plain dicts, so the
    write side does not need to know where the rows came from.
    """
    raise NotImplementedError


def publish(dsn: str, schema: str, table: str, rows: list[dict]) -> int:
    """Replace the backend's copy of the table, return the row count written.

    TODO: implement the write-then-swap above. Decide what happens when `rows`
    is empty: publishing zero rows over a good table is a data loss incident,
    so most teams raise instead.
    """
    raise NotImplementedError
