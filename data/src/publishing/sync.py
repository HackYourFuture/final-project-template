"""Publish a mart from Databricks into the backend's Postgres database.

Airflow runs this after dbt and the enrichment succeed. See the README, "The
two schemas" and "The write-then-swap", for why it works the way it does.
"""

import logging
from typing import LiteralString

import psycopg
from psycopg.sql import SQL, Identifier, Placeholder

from ..common.warehouse import Queryable

logger = logging.getLogger(__name__)

# What a Databricks column becomes in Postgres. Anything not listed becomes
# text: keeping the value beats guessing at it.
TYPE_MAP: dict[str, LiteralString] = {
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


def postgres_type(databricks_type: str) -> LiteralString:
    """Translate one column type. LiteralString because psycopg insists."""
    return TYPE_MAP.get(databricks_type.upper().split("(")[0], "text")


def read_mart(
    warehouse: Queryable, schema: str, table: str
) -> tuple[list[tuple[str, str]], list[list]]:
    """Read a whole published table out of the warehouse, with its columns."""
    qualified = f"{warehouse.catalog}.{schema}.{table}"
    columns, rows = warehouse.query(f"select * from {qualified}")
    logger.info("read %d rows and %d columns from %s", len(rows), len(columns), qualified)
    if not rows:
        raise ValueError(f"{qualified} returned no rows: refusing to publish an empty mart")
    return columns, rows


def read_backend_table(dsn: str, table: str, schema: str = "app") -> list[dict]:
    """Read one of the backend's own tables.

    `analytics_user` has read and nothing else on the `app` schema, so the
    worst a mistake here can do is return the wrong rows.
    """
    statement = SQL("select * from {}").format(Identifier(schema, table))
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(statement)
        names = [column.name for column in cursor.description or []]
        rows = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    logger.info("read %d rows from %s.%s", len(rows), schema, table)
    return rows


def publish(
    dsn: str, schema: str, table: str, columns: list[tuple[str, str]], rows: list[list]
) -> int:
    """Replace the backend's copy of the table, return the row count written.

    Load into staging, then swap inside one transaction, so a reader sees the
    whole old version or the whole new one and never a half-written table.
    """
    if not rows:
        raise ValueError("refusing to publish zero rows over an existing table")

    # Names are composed with psycopg's SQL objects, not pasted into an
    # f-string: a table name cannot be a query parameter.
    staging = Identifier(schema, f"{table}__staging")
    published = Identifier(schema, table)
    definition = SQL(", ").join(
        SQL("{} {}").format(Identifier(name), SQL(postgres_type(type_text)))
        for name, type_text in columns
    )

    connection = psycopg.connect(dsn, autocommit=False)
    try:
        with connection.cursor() as cursor:
            cursor.execute(SQL("drop table if exists {}").format(staging))
            cursor.execute(SQL("create table {} ({})").format(staging, definition))
            cursor.executemany(
                SQL("insert into {} ({}) values ({})").format(
                    staging,
                    SQL(", ").join(Identifier(name) for name, _ in columns),
                    SQL(", ").join([Placeholder()] * len(columns)),
                ),
                rows,
            )
            # The swap. `if exists` is what makes the very first publish work,
            # when there is nothing to replace yet.
            cursor.execute(SQL("drop table if exists {}").format(published))
            cursor.execute(SQL("alter table {} rename to {}").format(staging, Identifier(table)))
        connection.commit()
    finally:
        connection.close()

    logger.info("published %d rows to %s.%s", len(rows), schema, table)
    return len(rows)
