"""Fetch records from the source API and validate them.

The default source is the Arbeitnow job board, which needs no API key. Point
SOURCE_API_URL at your team's source and rewrite `parse_records` to match it.
"""

import logging
from typing import Any

import requests
from pydantic import ValidationError

from .models import Posting

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30


def fetch_raw(url: str) -> list[Any]:
    """Call the source API and return its raw records. Non-2xx raises."""
    logger.info("Fetching %s", url)
    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    # Some sources wrap their rows in {"data": [...]}, others return the list.
    records = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise TypeError(f"Expected a list of records, got {type(records).__name__}")
    logger.info("Received %d record(s)", len(records))
    return records


def parse_records(records: list[Any]) -> tuple[list[Posting], int]:
    """Validate raw records, returning the good ones and a rejected count.

    One malformed record must not lose the whole batch, so invalid rows are
    counted and skipped. `Any` is deliberate: this is the boundary, and the
    source can send anything.
    """
    parsed: list[Posting] = []
    rejected = 0
    for record in records:
        try:
            parsed.append(Posting.model_validate(record))
        except ValidationError as exc:
            rejected += 1
            # A JSON list can hold a scalar, and .get on one would raise here
            # and lose the batch this loop exists to save.
            identifier = (
                record.get("slug", "<no slug>") if isinstance(record, dict) else repr(record)[:40]
            )
            logger.warning("Rejected record %s: %s", identifier, exc.error_count())
    logger.info("Parsed %d record(s), rejected %d", len(parsed), rejected)
    return parsed, rejected
