"""Talking to the SQL warehouse: the wait, and the failure."""

import pytest
from conftest import RecordingOpener

from src.warehouse import Warehouse, WarehouseError, warehouse_id


def build(answers: list[dict]) -> tuple[Warehouse, RecordingOpener]:
    opener = RecordingOpener(answers)
    warehouse = Warehouse(
        host="adb-123.7.azuredatabricks.net",
        http_path="/sql/1.0/warehouses/0aae52a375e34214",
        catalog="team_a",
        token="token",
        opener=opener,
        poll_seconds=0,
    )
    return warehouse, opener


def succeeded(rows: list[list] | None = None) -> dict:
    return {
        "status": {"state": "SUCCEEDED"},
        "manifest": {"schema": {"columns": [{"name": "n", "type_text": "BIGINT"}]}},
        "result": {"data_array": rows or []},
    }


def test_warehouse_id_comes_from_the_path_dbt_already_needs():
    """One warehouse setting rather than two that can disagree."""
    assert warehouse_id("/sql/1.0/warehouses/0aae52a375e34214") == "0aae52a375e34214"


def test_a_path_with_no_id_is_rejected():
    with pytest.raises(ValueError):
        warehouse_id("/")


def test_run_waits_for_a_pending_statement():
    """Returning while it is still RUNNING means the next step builds on a
    table that is half written."""
    warehouse, _ = build(
        [
            {"statement_id": "s1", "status": {"state": "PENDING"}},
            {"statement_id": "s1", "status": {"state": "RUNNING"}},
            succeeded([["7"]]),
        ]
    )
    assert warehouse.run("select count(*) from t") == [["7"]]


def test_a_failed_statement_raises():
    warehouse, _ = build([{"status": {"state": "FAILED", "error": {"message": "boom"}}}])
    with pytest.raises(WarehouseError, match="FAILED"):
        warehouse.run("select 1")


def test_query_returns_the_columns_the_warehouse_reported():
    """The publish step builds its Postgres table from these, so adding a
    column to the mart does not mean editing the sync too."""
    warehouse, _ = build([succeeded([["7"]])])
    columns, rows = warehouse.query("select count(*) as n from t")
    assert columns == [("n", "BIGINT")]
    assert rows == [["7"]]
