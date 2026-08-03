"""Pipeline entry point: fetch, validate, store.

Run locally:
    docker compose up -d
    uv run python -m src.pipeline

The same module is what the container image runs, so what you test locally is
what Airflow and Azure execute.
"""

import logging
import sys

from .config import load_config
from .ingest import fetch_raw, parse_records
from .storage import ensure_schema, write_postings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("pipeline")


def run() -> int:
    """Run one pipeline execution and return the number of rows written."""
    config = load_config()

    records = fetch_raw(config.source_api_url)
    postings, rejected = parse_records(records)
    if rejected and not postings:
        raise RuntimeError("Every record failed validation: check the source shape")

    ensure_schema(config.postgres_dsn, config.raw_schema)
    written = write_postings(config.postgres_dsn, config.raw_schema, postings)

    logger.info("Pipeline finished: %d row(s) written, %d rejected", written, rejected)
    return written


if __name__ == "__main__":
    try:
        run()
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)
