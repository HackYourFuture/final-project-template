"""The classifier, the quoting, and the rebuild.

`classify` is the one piece of business logic in the pipeline that someone
non-technical on your team will have an opinion about. That is exactly the kind
of thing to pin down in tests, so changing it is a conversation about rules
rather than a gamble.
"""

import pytest
from conftest import FakeWarehouse

from src.common.warehouse import WarehouseError
from src.enrichment.enrich import UNCLASSIFIED, classify, enrich, sql_literal


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior Data Engineer", "data"),
        ("Backend Developer (Java)", "backend"),
        ("Site Reliability Engineer / SRE", "devops"),
        ("Sales Manager", UNCLASSIFIED),
        ("", UNCLASSIFIED),
    ],
)
def test_classify(title, expected):
    assert classify(title) == expected


def test_quoting_survives_an_apostrophe():
    """A company called O'Neill would otherwise end the statement mid-word, and
    the error points at a line that looks fine."""
    assert sql_literal("O'Neill") == "'O''Neill'"


def test_quoting_survives_a_backslash():
    assert sql_literal("back\\slash") == "'back\\\\slash'"


def test_enrich_rebuilds_the_table_and_checks_the_count():
    warehouse = FakeWarehouse(
        {
            "select posting_id, title": [["a1", "Data Engineer"], ["b2", "Sales Rep"]],
            "count(*)": [["2"]],
        }
    )
    assert enrich(warehouse, "main") == 2

    # Mapping table first, then the join back. The other order would join
    # against last run's classifications.
    assert (
        warehouse.index_of("create or replace table team_x.main.postings_discipline")
        < warehouse.index_of("insert into team_x.main.postings_discipline")
        < warehouse.index_of("create or replace table team_x.main.fct_postings_enriched")
    )


def test_enrich_batches_large_inputs():
    rows = [[f"id{n}", "Data Engineer"] for n in range(1200)]
    warehouse = FakeWarehouse({"select posting_id, title": rows, "count(*)": [["1200"]]})
    enrich(warehouse, "main", batch_size=500)
    inserts = [s for s in warehouse.statements if s.startswith("insert into")]
    assert len(inserts) == 3


def test_enrich_refuses_an_empty_mart():
    """Nothing to classify means dbt built nothing, which is a broken run."""
    with pytest.raises(WarehouseError, match="empty"):
        enrich(FakeWarehouse(), "main")


def test_enrich_notices_a_row_count_that_does_not_match():
    """The join dropped rows. Silently publishing fewer is worse than failing."""
    warehouse = FakeWarehouse(
        {"select posting_id, title": [["a1", "Data Engineer"]], "count(*)": [["0"]]}
    )
    with pytest.raises(WarehouseError, match="but"):
        enrich(warehouse, "main")
