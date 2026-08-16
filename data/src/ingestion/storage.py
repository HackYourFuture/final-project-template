"""Land raw records as files in your team's landing zone.

See the README, "The landing zone", for why files and not tables, and how one
blob is readable from dbt as a volume path.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

# Two containers, and the split is a permission boundary rather than tidiness.
# The scheduled pipeline writes `prod`, which you can read and cannot write.
# Your own runs write `dev`, which is yours. Nothing you do while developing
# can overwrite the file the team's models read, even by accident.
PRODUCTION_CONTAINER = "prod"
PRODUCTION_PREFIX = "raw"
DEVELOPMENT_CONTAINER = "dev"

# Where `--local` writes when you do not name a directory yourself.
LOCAL_LANDING_DIR = Path("local-landing")


def _ndjson(records: list[dict]) -> bytes:
    """One JSON object per line, which is the format read_files expects.

    Shared by both destinations on purpose: a file you inspect on your laptop
    is byte-for-byte what would have gone to the landing zone, so deciding
    "this is the shape I want" locally means something.
    """
    if not records:
        raise ValueError("refusing to land an empty file: nothing to write")
    return "\n".join(json.dumps(record) for record in records).encode()


def blob_path(
    source_name: str, run_date: str | None = None, prefix: str = PRODUCTION_PREFIX
) -> str:
    """Where one run's file goes. One file per source per day.

    The date is a folder, `ingest_date=2026-08-12/`, not part of the filename.
    That layout is a convention every engine that reads files understands: a
    folder named `key=value` is a partition, so dbt gets an `ingest_date`
    column for free without anyone parsing a filename.

    What it buys you in practice is a bad day being one directory. When a
    source has an outage and sends you nonsense, deleting that day and running
    the pipeline again for it is one folder deleted and one command, and
    nothing else in the landing zone is touched.
    """
    run_date = run_date or datetime.now(tz=UTC).date().isoformat()
    return f"{prefix}/{source_name}/ingest_date={run_date}/data.json"


def land_raw_json(
    account: str, path: str, records: list[dict], container: str = PRODUCTION_CONTAINER
) -> int:
    """Write records as newline-delimited JSON, replacing that day's file."""
    payload = _ndjson(records)

    credential = DefaultAzureCredential()
    service = BlobServiceClient(f"https://{account}.blob.core.windows.net", credential)
    service.get_blob_client(container=container, blob=path).upload_blob(payload, overwrite=True)

    logger.info(
        "landed %d records, %d bytes, to %s/%s on %s",
        len(records),
        len(payload),
        container,
        path,
        account,
    )
    return len(records)


def land_local_json(directory: Path, path: str, records: list[dict]) -> int:
    """Write the same file to this machine instead of to the landing zone.

    For scoping out a new source. You want to see what an API actually returns,
    in an editor, before deciding which fields matter and what the staging model
    should rename them to. Doing that against ADLS means a round trip and a
    storage account you may not have been given yet.

    It is deliberately **not** a pipeline stage. The SQL warehouse cannot read
    your laptop, so dbt will never see this file, and there is no sequence where
    you land locally and then "upload it". When the shape looks right, drop the
    flag and the same command writes the dev container, which dbt can read.
    """
    payload = _ndjson(records)

    destination = directory / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)

    logger.info(
        "wrote %d records, %d bytes, to %s (local only: dbt cannot read this)",
        len(records),
        len(payload),
        destination,
    )
    return len(records)
