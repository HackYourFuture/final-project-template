"""Validation at the edge: what survives, what is rejected, what is counted."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.ingestion.ingest import parse_records
from src.ingestion.models import Posting

GOOD = {
    "slug": "data-engineer-acme",
    "title": "Data Engineer",
    "company_name": "Acme",
    "location": "Amsterdam",
    "remote": True,
    "tags": ["sql", "python"],
    "created_at": 1786481729,
}


def test_good_record_survives():
    parsed, rejected = parse_records([GOOD])
    assert rejected == 0
    assert parsed[0].slug == "data-engineer-acme"


def test_one_bad_record_does_not_lose_the_batch():
    """The whole point of counting rejections instead of raising."""
    parsed, rejected = parse_records([GOOD, {"slug": "missing-everything-else"}])
    assert len(parsed) == 1
    assert rejected == 1


def test_a_scalar_in_the_list_is_rejected_not_fatal():
    """A JSON list can hold a string. Calling .get on one would lose the batch."""
    parsed, rejected = parse_records([GOOD, "not-a-dict", 42])
    assert len(parsed) == 1
    assert rejected == 2


def test_epoch_seconds_become_an_aware_datetime():
    """The bug this prevents: a naive datetime reads as the machine's zone.

    The same integer would then mean a different instant on a laptop in
    Amsterdam and in a container running UTC, and `date(posted_at)` in dbt
    would put some postings on the wrong day.
    """
    posting = Posting.model_validate(GOOD)
    assert posting.created_at.tzinfo is not None
    assert posting.created_at == datetime(2026, 8, 11, 20, 55, 29, tzinfo=UTC)


def test_missing_required_field_is_rejected():
    with pytest.raises(ValidationError):
        Posting.model_validate({k: v for k, v in GOOD.items() if k != "title"})
