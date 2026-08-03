"""Write validated records into Postgres.

The pipeline owns the raw layer only. Everything downstream of `raw` is dbt's
job, which keeps the boundary between "getting data in" and "shaping data"
clear enough that two people can work on them at once.
"""

import json
import logging

import psycopg

from .models import Posting

logger = logging.getLogger(__name__)

CREATE_SCHEMA = "CREATE SCHEMA IF NOT EXISTS {schema}"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS {schema}.postings (
    slug          TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    company_name  TEXT NOT NULL,
    location      TEXT,
    remote        BOOLEAN NOT NULL DEFAULT FALSE,
    tags          JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at    TIMESTAMP NOT NULL,
    ingested_at   TIMESTAMP NOT NULL DEFAULT NOW()
)
"""

UPSERT = """
INSERT INTO {schema}.postings
    (slug, title, company_name, location, remote, tags, created_at)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (slug) DO UPDATE SET
    title        = EXCLUDED.title,
    company_name = EXCLUDED.company_name,
    location     = EXCLUDED.location,
    remote       = EXCLUDED.remote,
    tags         = EXCLUDED.tags,
    created_at   = EXCLUDED.created_at,
    ingested_at  = NOW()
"""


def ensure_schema(dsn: str, schema: str) -> None:
    """Create the raw schema and table when they do not exist yet."""
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(CREATE_SCHEMA.format(schema=schema))
        cur.execute(CREATE_TABLE.format(schema=schema))
        conn.commit()
    logger.info("Ensured %s.postings exists", schema)


def write_postings(dsn: str, schema: str, postings: list[Posting]) -> int:
    """Upsert postings and return how many rows were written.

    Upserting rather than inserting makes the pipeline safe to re-run. Running
    it twice on the same day must not double your row count, and Airflow will
    re-run tasks whenever one fails.
    """
    if not postings:
        logger.warning("Nothing to write")
        return 0

    rows = [
        (
            p.slug,
            p.title,
            p.company_name,
            p.location,
            p.remote,
            json.dumps(p.tags),
            p.created_at,
        )
        for p in postings
    ]
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.executemany(UPSERT.format(schema=schema), rows)
        conn.commit()
    logger.info("Wrote %d row(s) into %s.postings", len(rows), schema)
    return len(rows)
