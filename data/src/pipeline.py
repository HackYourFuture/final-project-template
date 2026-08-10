"""Pipeline entry point: fetch, validate, land.

This module is what the container image runs, so what you test locally is what
Azure Container Apps executes in the deployed pipeline.

Run locally:
    cp .env.example .env      # then fill it in
    uv run python -m src.pipeline

The wiring below is done. The pieces it calls are not: `land_raw_json` in
storage.py raises NotImplementedError until you write it.

Your team's Databricks client id and secret come from Key Vault. Read them
with the identity of whatever is running this: your `az login` locally, the
Container Apps job's managed identity in Azure. Never put them in the image.
"""

import logging
import os
import sys
from datetime import date

from .config import load_config
from .ingest import fetch_raw, parse_records
from .storage import get_token, land_raw_json, volume_path

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
    run_date = run_date or date.today().isoformat()

    records = fetch_raw(config.source_api_url)
    parsed, rejected = parse_records(records)
    # An empty batch is a failed extraction, not a quiet success. Landing zero
    # rows leaves yesterday's mart in place and every test still passing, so
    # nobody finds out for a week.
    if not parsed:
        raise RuntimeError(
            f"No valid records: {len(records)} received, {rejected} rejected"
        )

    landed = land_raw_json(
        host=config.databricks_host,
        token=get_token(
            tenant_id=os.environ["AZURE_TENANT_ID"],
            client_id=os.environ["DATABRICKS_CLIENT_ID"],
            client_secret=os.environ["DATABRICKS_CLIENT_SECRET"],
        ),
        path=volume_path(config.databricks_catalog, config.source_name, run_date),
        records=[record.model_dump(mode="json") for record in parsed],
    )

    logger.info("Pipeline finished: %d landed, %d rejected", landed, rejected)
    return landed


if __name__ == "__main__":
    try:
        run()
    except Exception:
        logger.exception("Pipeline failed")
        sys.exit(1)
