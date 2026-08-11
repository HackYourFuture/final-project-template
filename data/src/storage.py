"""Land raw records as files in your team's landing zone.

This is the boundary between "getting data in" and "shaping data". The
ingestion job only lands files. Everything after that is dbt's job, which is
what lets two people work on the two halves at the same time.

Why files and not a table: a raw file is exactly what the source sent you. When
a column changes shape three weeks from now, you can re-read the file and find
out when it changed. A row that was already parsed into a table cannot tell you
that.

Where the bytes go, and why you see them in two places
------------------------------------------------------
Your team has its own Azure storage account with a `landing` container. This
module writes blobs into it. That same container is registered in Unity Catalog
as an external volume, so the file you write as

    landing/raw/postings/2026-08-12.json

is readable from dbt as

    /Volumes/<your catalog>/landing/raw/postings/2026-08-12.json

One copy of the bytes, two ways to reach them: Azure tooling on one side, SQL
on the other. `volume_path()` below returns the second form, which is what you
put in `dbt_project.yml`.

Authentication: there is no secret here
---------------------------------------
`DefaultAzureCredential` asks the environment who it is. On your laptop that is
your `az login`. In Azure it is the Container Apps job's managed identity,
which holds Storage Blob Data Contributor on your team's account and nothing
else. The same code runs in both places, and no password exists to leak,
rotate, or accidentally commit.

Shared key access is switched off on the account, so an identity is the only
way in. If you find a tutorial that tells you to paste a connection string,
that is the thing this design removes.
"""

import json
import logging
from datetime import UTC, datetime

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

CONTAINER = "landing"


def blob_path(source_name: str, run_date: str | None = None) -> str:
    """Where one run's file goes inside the landing container.

    The date is in the path on purpose. One file per source per day means a
    re-run overwrites its own file instead of doubling your data, and you can
    still see every day that ever ran.

    You can change this layout, but change `landing_path` in dbt_project.yml to
    match and write down why in the README, because dbt reads whatever you
    choose here.
    """
    run_date = run_date or datetime.now(tz=UTC).date().isoformat()
    return f"raw/{source_name}/{run_date}.json"


def volume_path(catalog: str, source_name: str) -> str:
    """The same location, as dbt sees it. Put this in dbt_project.yml."""
    return f"/Volumes/{catalog}/landing/raw/{source_name}"


def land_raw_json(account: str, path: str, records: list[dict]) -> int:
    """Write records as one JSON file and return how many were written.

    Args:
        account: your team's storage account name, no https:// and no suffix
        path: what `blob_path()` returned
        records: the raw records, exactly as the source sent them

    One JSON object per line, not one big array. dbt's `read_files` reads that
    shape directly, and a half-written file costs you one line rather than the
    whole run.

    Overwrites an existing file rather than failing, because Airflow re-runs
    tasks and a re-run of the same day must replace that day's file.

    Anything that goes wrong here raises. A silent failure is the worst kind:
    dbt would then build happily on yesterday's file and nobody would notice
    for a week.
    """
    if not records:
        raise ValueError("refusing to land an empty file: nothing to write")

    payload = "\n".join(json.dumps(record) for record in records).encode()

    credential = DefaultAzureCredential()
    service = BlobServiceClient(f"https://{account}.blob.core.windows.net", credential)
    blob = service.get_blob_client(container=CONTAINER, blob=path)
    blob.upload_blob(payload, overwrite=True)

    logger.info(
        "landed %d records, %d bytes, to %s/%s on %s",
        len(records), len(payload), CONTAINER, path, account,
    )
    return len(records)
