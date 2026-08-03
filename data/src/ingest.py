"""Fetch records from the source API and validate them.

The default source is the Arbeitnow job board, which needs no API key so the
template runs the moment you clone it. Point SOURCE_API_URL at your team's
source and rewrite `parse_records` to match its shape.
"""

import logging

import requests
from pydantic import ValidationError

from .models import Posting

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30


def fetch_raw(url: str) -> list[dict]:
    """Call the source API and return its raw records.

    Any non-2xx response raises, so a broken source fails the pipeline run
    instead of silently writing zero rows.
    """
    logger.info("Fetching %s", url)
    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    records = payload.get("data", payload)
    logger.info("Received %d record(s)", len(records))
    return records


def parse_records(records: list[dict]) -> tuple[list[Posting], int]:
    """Validate raw records, returning the good ones and a rejected count.

    One malformed record should not lose you the whole batch, so invalid rows
    are counted and skipped rather than raised.
    """
    parsed: list[Posting] = []
    rejected = 0
    for record in records:
        try:
            parsed.append(Posting.model_validate(record))
        except ValidationError as exc:
            rejected += 1
            logger.warning("Rejected record %s: %s", record.get("slug", "<no slug>"), exc.error_count())
    logger.info("Parsed %d record(s), rejected %d", len(parsed), rejected)
    return parsed, rejected
