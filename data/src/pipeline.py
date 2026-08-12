"""Pipeline entry point: fetch, validate, land.

This module is what the container image runs, so what you test locally is what
Azure Container Apps executes in the deployed pipeline.

Run locally:
    cp .env.example .env      # then fill it in
    uv run python -m src.pipeline

Run it the way Azure will:
    docker compose run --rm pipeline

This file works as it stands, against the default source. What you change is
your source and your model, not this wiring.
"""

import argparse
import logging
import sys
from datetime import UTC, datetime

from .config import load_config
from .ingest import fetch_raw, parse_records
from .storage import blob_path, land_raw_json, volume_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("pipeline")


def run(run_date: str | None = None) -> int:
    """Run one execution and return the number of records landed.

    Args:
        run_date: the day this run belongs to, as YYYY-MM-DD. Airflow passes
            its logical date so a re-run of an old day overwrites that day's
            file rather than today's.
    """
    config = load_config()
    run_date = run_date or datetime.now(tz=UTC).date().isoformat()

    records = fetch_raw(config.source_api_url)
    parsed, rejected = parse_records(records)

    # An empty batch is a failed extraction, not a quiet success. Landing zero
    # rows leaves yesterday's mart in place and every test still passing, so
    # nobody finds out for a week.
    if not parsed:
        raise RuntimeError(f"No valid records: {len(records)} received, {rejected} rejected")
    if rejected:
        logger.warning(
            "%d of %d records failed validation and are still being landed",
            rejected,
            len(records),
        )

    # Land what the source sent, not what validation produced. Parsing here is
    # a gate, not a transformation: it decides whether this run is worth
    # landing at all. If you wrote the parsed objects instead, the "raw" file
    # would quietly carry your own type coercions, and re-reading it after a
    # source change would tell you about your bug rather than about theirs.
    landed = land_raw_json(
        account=config.storage_account,
        path=blob_path(config.source_name, run_date),
        records=records,
    )

    logger.info(
        "Pipeline finished: %d landed, %d rejected, readable at %s",
        landed,
        rejected,
        volume_path(config.databricks_catalog, config.source_name),
    )
    return landed


if __name__ == "__main__":
    # Airflow passes its logical date, so a backfill of an old day overwrites
    # that day's file. Without it, every re-run would write to today.
    parser = argparse.ArgumentParser(description="Run one ingestion.")
    parser.add_argument(
        "--run-date",
        default=None,
        help="the day this run belongs to, YYYY-MM-DD. Defaults to today.",
    )
    args = parser.parse_args()

    try:
        run(args.run_date)
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)
