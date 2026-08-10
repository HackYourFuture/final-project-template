"""Land raw records as files in your team's ADLS container.

This is the boundary between "getting data in" and "shaping data". The
ingestion job only lands files. Everything after that is dbt's job, which is
what lets two people work on the two halves at the same time.

Why files and not a table: a raw file is exactly what the source sent you. When
a column changes shape three weeks from now, you can re-read the file and find
out when it changed. A row that was already parsed into a table cannot tell you
that.

Why ADLS and not a database: your storage account holds the raw layer, and
Databricks reads it through a volume your teachers pointed at this container.
Nothing here needs a Databricks token. The container authenticates as itself.

YOU IMPLEMENT THIS FILE.

Authentication is `DefaultAzureCredential`, which is the whole point of the
setup: locally it uses your `az login`, and in Azure it uses the Container Apps
job's managed identity. There is no key, no connection string, and nothing to
put in .env.

    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    client = BlobServiceClient(
        f"https://{account}.blob.core.windows.net",
        credential=DefaultAzureCredential(),
    )

Docs: https://learn.microsoft.com/azure/storage/blobs/storage-quickstart-blobs-python
"""

import logging

logger = logging.getLogger(__name__)


def blob_name(source_name: str, run_date: str) -> str:
    """Return the blob path to write for one run.

    Put the date in the path. One file per run per day means a re-run
    overwrites its own file instead of doubling your data, and you can still
    see every day that ever ran.

    TODO: decide your layout. Something like `postings/2026-08-10.json` is
    enough. Write down why you chose it in the README, because dbt reads
    whatever you choose here.
    """
    raise NotImplementedError


def land_raw_json(
    account: str,
    container: str,
    blob_path: str,
    records: list[dict],
) -> int:
    """Upload records as one JSON file, and return how many were written.

    Args:
        account: storage account name, e.g. stteamaa1b2c3d4
        container: the container raw files land in, normally `raw`
        blob_path: what blob_name returned
        records: the parsed records to write

    Overwrite an existing blob rather than failing: Airflow re-runs tasks, and
    a re-run of the same day must replace that day's file.

    Let failures raise. A silent failure here is the worst kind: dbt then
    builds happily on yesterday's file and nobody notices for a week.

    TODO: implement with BlobServiceClient, then check the file really is in
    the container before you move on. The portal shows it under
    Storage account > Containers > raw.
    """
    raise NotImplementedError
