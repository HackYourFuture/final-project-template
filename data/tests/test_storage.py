"""Where files land, and what is in them."""

import json
from datetime import UTC, datetime

import pytest

from src import storage


def test_explicit_run_date_wins():
    assert storage.blob_path("postings", "2026-08-12") == "raw/postings/2026-08-12.json"


def test_default_run_date_is_todays_utc_date():
    """Not the local date. A run at 01:00 in Amsterdam is still yesterday in UTC,
    and the whole pipeline agrees on UTC or it agrees on nothing."""
    assert storage.blob_path("postings").endswith(f"{datetime.now(tz=UTC).date().isoformat()}.json")


def test_a_dev_prefix_keeps_your_runs_out_of_the_teams_files():
    """The isolation the whole local loop depends on: your ingestion writes
    somewhere the scheduled pipeline never reads."""
    assert storage.blob_path("postings", "2026-08-12", "alex") == "alex/postings/2026-08-12.json"


def test_the_two_containers_are_named_apart():
    """Not tidiness: `landing` is the one you are not allowed to write."""
    assert storage.PRODUCTION_CONTAINER == "landing"
    assert storage.DEVELOPMENT_CONTAINER == "dev"


def test_landing_nothing_raises():
    """An empty batch is a failed extraction. Writing it would leave yesterday's
    mart in place with every test still passing, and nobody would notice."""
    with pytest.raises(ValueError, match="empty"):
        storage.land_raw_json("account", "raw/x.json", [])


def test_payload_is_one_json_object_per_line(monkeypatch):
    """dbt's read_files expects newline-delimited JSON, not one big array."""
    captured = {}

    class FakeBlob:
        def upload_blob(self, payload, overwrite):
            captured["payload"] = payload
            captured["overwrite"] = overwrite

    class FakeService:
        def __init__(self, url, credential):
            captured["url"] = url

        def get_blob_client(self, container, blob):
            captured["container"] = container
            captured["blob"] = blob
            return FakeBlob()

    monkeypatch.setattr(storage, "BlobServiceClient", FakeService)
    monkeypatch.setattr(storage, "DefaultAzureCredential", lambda: "credential")

    records = [{"a": 1}, {"a": 2}]
    assert storage.land_raw_json("sthyffpteama", "raw/postings/x.json", records) == 2

    lines = captured["payload"].decode().splitlines()
    assert [json.loads(line) for line in lines] == records
    assert captured["container"] == "landing"
    assert captured["url"] == "https://sthyffpteama.blob.core.windows.net"
    # Re-running a day must replace that day's file, not fail or duplicate it.
    assert captured["overwrite"] is True


def test_the_container_is_chosen_by_the_caller(monkeypatch):
    """A local run must land in `dev`, which is the only one it can write."""
    captured = {}

    class FakeBlob:
        def upload_blob(self, payload, overwrite):
            pass

    class FakeService:
        def __init__(self, url, credential):
            pass

        def get_blob_client(self, container, blob):
            captured["container"] = container
            return FakeBlob()

    monkeypatch.setattr(storage, "BlobServiceClient", FakeService)
    monkeypatch.setattr(storage, "DefaultAzureCredential", lambda: "credential")

    storage.land_raw_json("sthyffpteama", "alex/postings/x.json", [{"a": 1}], container="dev")
    assert captured["container"] == "dev"
