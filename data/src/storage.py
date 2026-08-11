"""Land raw records as files in your team's Databricks volume.

This is the boundary between "getting data in" and "shaping data". The
ingestion job only lands files. Everything after that is dbt's job, which is
what lets two people work on the two halves at the same time.

Why files and not a table: a raw file is exactly what the source sent you. When
a column changes shape three weeks from now, you can re-read the file and find
out when it changed. A row that was already parsed into a table cannot tell you
that.

Why a volume and not your own storage account: the volume already lives inside
your catalog, so the same permissions that protect your tables protect your raw
files, and dbt reads them with `read_files()` without knowing where the bytes
physically sit. Your path is `/Volumes/<your catalog>/landing/raw/...`.

YOU IMPLEMENT THIS FILE.

Authentication is your team's service principal, the same client id and secret
dbt uses. Both come from Key Vault at run time. Two calls:

    # 1. Entra token for Databricks
    POST https://login.microsoftonline.com/<tenant>/oauth2/v2.0/token
         grant_type=client_credentials, client_id, client_secret,
         scope=2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default

    # 2. Upload, one PUT per file
    PUT https://<host>/api/2.0/fs/files/Volumes/<catalog>/landing/raw/<path>
        ?overwrite=true
        Authorization: Bearer <token>

Both are plain HTTP, so `requests` is all you need. A 204 means it landed.

Docs: https://docs.databricks.com/api/azure/workspace/files/upload
"""

import logging

logger = logging.getLogger(__name__)


def volume_path(catalog: str, source_name: str, run_date: str) -> str:
    """Return the volume path to write for one run.

    Put the date in the path. One file per run per day means a re-run
    overwrites its own file instead of doubling your data, and you can still
    see every day that ever ran.

    TODO: decide your layout. Something like
    `/Volumes/team_a/landing/raw/postings/2026-08-10.json` is enough. Write
    down why you chose it in the README, because dbt reads whatever you choose
    here.
    """
    raise NotImplementedError


def land_raw_json(
    host: str,
    token: str,
    path: str,
    records: list[dict],
) -> int:
    """Upload records as one JSON file, and return how many were written.

    Args:
        host: your workspace host, without https://
        token: the Entra access token from get_token
        path: what volume_path returned
        records: the parsed records to write

    Write one JSON object per line rather than one big array. dbt reads that
    shape directly, and a half-written file costs you one line instead of the
    whole run.

    Overwrite an existing file rather than failing: Airflow re-runs tasks, and
    a re-run of the same day must replace that day's file.

    Let failures raise. A silent failure here is the worst kind: dbt then
    builds happily on yesterday's file and nobody notices for a week.

    TODO: implement, then check the file really is there before you move on:

        SELECT * FROM read_files('/Volumes/<catalog>/landing/raw/postings',
                                 format => 'json')
    """
    raise NotImplementedError


def get_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """Exchange your team's client id and secret for a Databricks token.

    The token is short-lived on purpose. Fetch one per run and keep it in
    memory: never write it to a file, a log line, or an Airflow Variable.

    TODO: implement the client-credentials POST above and return
    `access_token`.
    """
    raise NotImplementedError
