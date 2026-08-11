"""Publish a mart from Databricks into the backend's Postgres database.

This is the outbound sync, and it is the step that turns your pipeline into a
data product. The backend trainees do not query Databricks: they query their
own database, the way they always have. Your job is to put a fresh copy of the
mart there, on a schedule, without ever leaving them a half-written table.

Airflow runs this after dbt succeeds. Never before: publishing a mart that
failed its tests is worse than publishing nothing.

Which schema, and why there are two
-----------------------------------
The two tracks meet through two schemas, and each side owns the one it writes:

    analytics   you write, the backend reads. Your published marts.
    app         the backend writes, you read. Views it chooses to expose.

Neither side reads the other's internal tables. That is what stops a backend
migration from silently breaking your DAG at 6am, and it is why any hashing or
dropping of personal data happens in the backend's view rather than here: the
data never has to leave their database in the first place.

This module writes to `analytics`. The inbound direction, reading `app`, is the
other half of the same idea.

YOU IMPLEMENT THIS FILE.

Read side:  databricks-sql-connector, against your SQL warehouse.
Write side: psycopg, against the backend database.

The pattern that avoids a half-written table is write-then-swap:

    1. create <table>__staging, or truncate it if it is already there
    2. insert every row into it
    3. inside one transaction:
           drop table if exists <table>
           alter table <table>__staging rename to <table>

Note the `if exists` on step 3. The obvious version of this pattern renames the
current table out of the way first, which cannot work the very first time you
publish, because there is nothing to rename. Getting that wrong means the sync
fails once, on the run you most want to see succeed.

Readers see the old table until the transaction commits, then the new one. They
never see an empty or partial table.
"""

import logging

logger = logging.getLogger(__name__)


def read_mart(host: str, http_path: str, client_id: str, client_secret: str, table: str) -> list[dict]:
    """Read every row of a published mart from Databricks.

    Args:
        table: fully qualified, e.g. team_a.analytics.fct_postings

    TODO: implement with databricks.sql.connect, using your team's client id
    and secret (OAuth), not a personal token. Return plain dicts, so the write
    side does not need to know where the rows came from.
    """
    raise NotImplementedError


def publish(dsn: str, schema: str, table: str, rows: list[dict]) -> int:
    """Replace the backend's copy of the table, return the row count written.

    Args:
        schema: `analytics`. This is the schema you own on their database.

    TODO: implement the write-then-swap above, including the `if exists` that
    makes the first publish work. Decide what happens when `rows` is empty:
    publishing zero rows over a good table is a data loss incident, so most
    teams raise instead.
    """
    raise NotImplementedError
