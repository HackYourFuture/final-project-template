"""Land raw records as files in your team's landing zone.

See the README, "The landing zone", for why files and not tables, and how one
blob is readable from dbt as a volume path.
"""

import json
import logging
from datetime import UTC, datetime

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

CONTAINER = "landing"


def blob_path(source_name: str, run_date: str | None = None) -> str:
    """Where one run's file goes. One file per source per day."""
    run_date = run_date or datetime.now(tz=UTC).date().isoformat()
    return f"raw/{source_name}/{run_date}.json"


def volume_path(catalog: str, source_name: str) -> str:
    """The same location as dbt sees it. Put this in dbt_project.yml."""
    return f"/Volumes/{catalog}/landing/raw/{source_name}"


def land_raw_json(account: str, path: str, records: list[dict]) -> int:
    """Write records as newline-delimited JSON, replacing that day's file."""
    if not records:
        raise ValueError("refusing to land an empty file: nothing to write")

    payload = "\n".join(json.dumps(record) for record in records).encode()

    credential = DefaultAzureCredential()
    service = BlobServiceClient(f"https://{account}.blob.core.windows.net", credential)
    service.get_blob_client(container=CONTAINER, blob=path).upload_blob(payload, overwrite=True)

    logger.info(
        "landed %d records, %d bytes, to %s/%s on %s",
        len(records),
        len(payload),
        CONTAINER,
        path,
        account,
    )
    return len(records)
