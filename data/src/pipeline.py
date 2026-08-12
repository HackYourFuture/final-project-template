"""The ingestion job: fetch, validate, land. This is what the container runs.

    uv run python -m src.pipeline [--run-date YYYY-MM-DD]

Settings come from the environment: .env on your machine, the job definition in
Azure. Every one is a name or a URL. There is no secret here, because the job
authenticates as itself. See the README, "Settings".
"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from dotenv import load_dotenv

from .ingest import fetch_raw, parse_records
from .storage import blob_path, land_raw_json, volume_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("pipeline")


class MissingSetting(RuntimeError):
    """A required environment variable is not set."""


@dataclass(frozen=True)
class Config:
    """What the ingestion job needs. Names only, no credentials."""

    source_api_url: str
    source_name: str
    storage_account: str
    databricks_catalog: str


def load_config() -> Config:
    """Read settings, failing at startup rather than ten minutes in."""
    load_dotenv()

    def required(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise MissingSetting(f"{name} is not set. Copy .env.example to .env and fill it in.")
        return value

    return Config(
        source_api_url=required("SOURCE_API_URL"),
        source_name=os.getenv("SOURCE_NAME", "source"),
        storage_account=required("STORAGE_ACCOUNT"),
        databricks_catalog=os.getenv("DATABRICKS_CATALOG", "<your catalog>"),
    )


def run(run_date: str | None = None) -> int:
    """Run one execution and return the number of records landed."""
    config = load_config()
    run_date = run_date or datetime.now(tz=UTC).date().isoformat()

    records = fetch_raw(config.source_api_url)
    parsed, rejected = parse_records(records)

    # An empty batch is a failed extraction, not a quiet success: it would
    # leave yesterday's mart in place with every test still passing.
    if not parsed:
        raise RuntimeError(f"No valid records: {len(records)} received, {rejected} rejected")
    if rejected:
        logger.warning(
            "%d of %d records failed validation and are still being landed",
            rejected,
            len(records),
        )

    # Land what the source sent, not what validation produced. Parsing is a
    # gate, not a transformation. See the README, "Raw means raw".
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
