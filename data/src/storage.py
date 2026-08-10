"""Land raw records as files in your team's Databricks volume.

This is the boundary between "getting data in" and "shaping data". The
ingestion job only lands files. Everything after that is dbt's job, which is
what lets two people work on the two halves at the same time.

Why files and not a table: a raw file is exactly what the source sent you. When
a column changes shape three weeks from now, you can re-read the file and find
out when it changed. A row that was already parsed into a table cannot tell you
that.

YOU IMPLEMENT THIS FILE. The signatures and the docstrings say what each
function has to do. The Databricks Files API is the simplest way in:

    PUT {host}/api/2.0/fs/files{path}?overwrite=true
    Authorization: Bearer {token}

Docs: https://docs.databricks.com/api/workspace/files/upload
"""

import logging

logger = logging.getLogger(__name__)


def landing_file_name(source_name: str, run_date: str) -> str:
    """Return the file name to write for one run.

    Put the date in the path. One file per run per day means a re-run overwrites
    its own file instead of doubling your data, and you can still see every day
    that ever ran.

    TODO: decide your naming. Something like `2026-08-10.json` under a folder
    per source is enough. Write down why you chose it in the README.
    """
    raise NotImplementedError


def land_raw_json(
    host: str,
    token: str,
    volume_path: str,
    file_name: str,
    records: list[dict],
) -> int:
    """Upload records as one JSON file into the volume, return how many.

    Args:
        host: your workspace URL, e.g. https://adb-....azuredatabricks.net
        token: a Databricks token with write access to your catalog
        volume_path: /Volumes/<catalog>/landing/raw/<source>
        file_name: what landing_file_name returned
        records: the parsed records to write

    Raise on a non-2xx response. A silent failure here is the worst kind: dbt
    then builds happily on yesterday's file and nobody notices for a week.

    TODO: implement with `requests.put`. Remember `overwrite=true`, or a re-run
    fails instead of replacing the file.
    """
    raise NotImplementedError
