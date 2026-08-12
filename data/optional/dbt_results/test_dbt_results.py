"""Recording what dbt did.

Run from the data folder once you have copied dbt_results.py into src/:
    uv run pytest optional/dbt_results

None of this may ever raise. dbt's exit code already decides whether the run
failed; losing the bookkeeping must not turn a green run red.
"""

import json

from dbt_results import parse_run_results, publish_results, summarise

from tests.conftest import FakeWarehouse

PAYLOAD = {
    "metadata": {"invocation_id": "abc-123", "generated_at": "2026-08-12T06:00:00.123Z"},
    "results": [
        {"unique_id": "model.fp.stg_postings", "status": "success", "execution_time": 1.5},
        {"unique_id": "model.fp.fct_postings", "status": "success", "execution_time": 2.0},
        {
            "unique_id": "test.fp.assert_postings_not_empty",
            "status": "fail",
            "execution_time": 0.4,
            "message": "Got 0 results, configured to fail if != 0",
        },
    ],
}


def test_missing_file_returns_nothing(tmp_path):
    """The normal case the first time anyone runs this."""
    assert parse_run_results(tmp_path / "nope.json") == []


def test_malformed_file_returns_nothing(tmp_path):
    broken = tmp_path / "run_results.json"
    broken.write_text("{not json")
    assert parse_run_results(broken) == []


def test_one_row_per_node(tmp_path):
    path = tmp_path / "run_results.json"
    path.write_text(json.dumps(PAYLOAD))
    results = parse_run_results(path)

    assert len(results) == 3
    assert results[0]["invocation_id"] == "abc-123"
    # The first segment of dbt's unique_id says what kind of node it was.
    assert results[0]["resource_type"] == "model"
    assert results[2]["resource_type"] == "test"
    assert results[2]["status"] == "fail"
    assert results[0]["run_at"] == "2026-08-12 06:00:00"


def test_summarise_counts_by_status(tmp_path):
    path = tmp_path / "run_results.json"
    path.write_text(json.dumps(PAYLOAD))
    assert summarise(parse_run_results(path)) == {"success": 2, "fail": 1}


def test_publishing_nothing_writes_nothing():
    warehouse = FakeWarehouse()
    assert publish_results(warehouse, []) == 0
    assert warehouse.statements == []


def test_publish_creates_the_table_and_inserts(tmp_path):
    path = tmp_path / "run_results.json"
    path.write_text(json.dumps(PAYLOAD))
    warehouse = FakeWarehouse()

    assert publish_results(warehouse, parse_run_results(path)) == 3
    assert warehouse.ran("create schema if not exists team_x.ops")
    assert warehouse.ran("create table if not exists team_x.ops.dbt_test_runs")
    assert warehouse.ran("insert into team_x.ops.dbt_test_runs")


def test_a_message_with_a_quote_does_not_break_the_insert(tmp_path):
    """dbt failure messages quote SQL back at you, apostrophes included."""
    payload = {
        "metadata": {"invocation_id": "x", "generated_at": "2026-08-12T06:00:00Z"},
        "results": [{"unique_id": "test.fp.t", "status": "fail", "message": "it's broken"}],
    }
    path = tmp_path / "run_results.json"
    path.write_text(json.dumps(payload))
    warehouse = FakeWarehouse()
    publish_results(warehouse, parse_run_results(path))

    insert = next(s for s in warehouse.statements if s.startswith("insert"))
    assert "'it''s broken'" in insert
