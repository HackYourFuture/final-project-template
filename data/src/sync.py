"""Publish a mart from Databricks into the backend's Postgres database.

This is the outbound sync, and it is the step that turns your pipeline into a
data product. The backend trainees do not query Databricks: they query their
own database, the way they always have. Your job is to put a fresh copy of the
mart there, on a schedule, without ever leaving them a half-written table.

Airflow runs this after dbt and the enrichment succeed. Never before:
publishing a mart that failed its tests is worse than publishing nothing.

Which schema, and why there are two
-----------------------------------
The two tracks meet through two schemas, and each side owns the one it writes:

    analytics   you write, the backend reads. Your published marts.
    app         the backend writes, you read. Views it chooses to expose.

Neither side reads the other's internal tables. That is what stops a backend
migration from silently breaking your DAG at 6am, and it is why any hashing or
dropping of personal data happens in the backend's view rather than here: the
data never has to leave their database in the first place.

This module writes to `analytics`. `read_app_table` below reads `app`, which is
the other half of the same idea.

The write-then-swap
-------------------
Readers must never see a half-loaded table, so the load and the switch are
separated:

    1. create <table>__staging, empty
    2. insert every row into it
    3. inside one transaction:
           drop table if exists <table>
           alter table <table>__staging rename to <table>

Note the `if exists` on step 3. The obvious version of this pattern renames the
current table out of the way first, which cannot work the very first time you
publish, because there is nothing to rename. Getting that wrong means the sync
fails once, on the run you most want to see succeed.

Readers see the old table until the transaction commits, then the new one.
They never see an empty or partial table.
"""

import logging

import psycopg

from .warehouse import Warehouse

logger = logging.getLogger(__name__)

# What a Databricks column becomes in Postgres. Anything not listed here is
# stored as text, which is the honest default: it keeps the value rather than
# guessing at it, and a column you did not think about does not fail the run.
TYPE_MAP = {
    "BIGINT": "bigint",
    "INT": "integer",
    "SMALLINT": "smallint",
    "DOUBLE": "double precision",
    "FLOAT": "double precision",
    "DECIMAL": "numeric",
    "BOOLEAN": "boolean",
    "DATE": "date",
    "TIMESTAMP": "timestamptz",
    "TIMESTAMP_NTZ": "timestamp",
}


def postgres_type(databricks_type: str) -> str:
    """Translate one column type. Unknown types become text on purpose."""
    return TYPE_MAP.get(databricks_type.upper().split("(")[0], "text")


def read_mart(
    warehouse: Warehouse, schema: str, table: str
) -> tuple[list[tuple[str, str]], list[list]]:
    """Read a whole published table out of the warehouse.

    Returns its columns and its rows. Reading everything is right at this size
    and wrong at a hundred million: at that point you publish a window rather
    than the whole table, and the shape of this function changes.
    """
    qualified = f"{warehouse.catalog}.{schema}.{table}"
    columns, rows = warehouse.query(f"select * from {qualified}")
    logger.info("read %d rows and %d columns from %s", len(rows), len(columns), qualified)
    if not rows:
        # Publishing nothing over a good table is a data loss incident. It is
        # also exactly what a broken upstream looks like, so it fails here.
        raise ValueError(f"{qualified} returned no rows: refusing to publish an empty mart")
    return columns, rows


def read_app_table(dsn: str, table: str) -> list[dict]:
    """Read one of the backend's exposed views, the inbound direction.

    `table` is unqualified and lives in the `app` schema, which is the only
    schema this credential can see. That is deliberate: a typo reaches nothing
    rather than reaching something private.
    """
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(f'select * from app."{table}"')
        names = [column.name for column in cursor.description]
        rows = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    logger.info("read %d rows from app.%s", len(rows), table)
    return rows


def publish(
    dsn: str, schema: str, table: str, columns: list[tuple[str, str]], rows: list[list]
) -> int:
    """Replace the backend's copy of the table, return the row count written.

    `schema` is `analytics`. This is the schema you own on their database, and
    the only one this credential can write to.
    """
    if not rows:
        raise ValueError("refusing to publish zero rows over an existing table")

    staging = f"{table}__staging"
    definition = ", ".join(
        f'"{name}" {postgres_type(type_text)}' for name, type_text in columns
    )
    placeholders = ", ".join(["%s"] * len(columns))
    column_list = ", ".join(f'"{name}"' for name, _ in columns)

    connection = psycopg.connect(dsn, autocommit=False)
    try:
        with connection.cursor() as cursor:
            # Rebuilt every run rather than reused, so a column added to the
            # mart does not need anyone to remember to drop the old staging
            # table by hand.
            cursor.execute(f'drop table if exists "{schema}"."{staging}"')
            cursor.execute(f'create table "{schema}"."{staging}" ({definition})')
            cursor.executemany(
                f'insert into "{schema}"."{staging}" ({column_list}) values ({placeholders})',
                rows,
            )
            # The swap. Both statements land together or neither does, so a
            # reader is never looking at a table that does not exist.
            cursor.execute(f'drop table if exists "{schema}"."{table}"')
            cursor.execute(
                f'alter table "{schema}"."{staging}" rename to "{table}"'
            )
        connection.commit()
    finally:
        connection.close()

    logger.info("published %d rows to %s.%s", len(rows), schema, table)
    return len(rows)
