"""The publish step: type mapping, and the order of the swap.

The ordering test is the one that matters. Every other bug here shows up the
first time you run it; getting the swap wrong shows up as a backend reading a
table that is briefly missing, which nobody reproduces on demand.
"""

import pytest
from conftest import FakeWarehouse

from src.publishing import sync

COLUMNS = [
    ("posting_id", "STRING"),
    ("jobs_posted", "BIGINT"),
    ("remote_pct", "DECIMAL(5,1)"),
    ("is_remote", "BOOLEAN"),
    ("posted_at", "TIMESTAMP"),
    ("tags", "ARRAY<STRING>"),
]
ROWS = [["a1", 3, 66.7, True, "2026-08-12T00:00:00Z", '["sql"]']]


class FakeCursor:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def execute(self, statement, params=None):
        # Statements are psycopg SQL objects now, not strings. as_string()
        # renders one the way the server will see it, which is what the
        # ordering assertions below read.
        self.log.append(" ".join(statement.as_string().split()))

    def executemany(self, statement, rows):
        self.log.append(f"INSERT x{len(list(rows))}")

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.log: list[str] = []
        self.committed = False
        self.closed = False

    def cursor(self):
        return FakeCursor(self.log)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


@pytest.fixture
def connection(monkeypatch) -> FakeConnection:
    fake = FakeConnection()
    monkeypatch.setattr(sync.psycopg, "connect", lambda *a, **k: fake)
    return fake


def test_type_mapping():
    assert sync.postgres_type("BIGINT") == "bigint"
    assert sync.postgres_type("DECIMAL(5,1)") == "numeric"
    assert sync.postgres_type("TIMESTAMP") == "timestamptz"


def test_unknown_type_becomes_text():
    """Keeping the value beats guessing at it. A column nobody thought about
    should not fail the run."""
    assert sync.postgres_type("ARRAY<STRING>") == "text"
    assert sync.postgres_type("MAP<STRING,INT>") == "text"


def index_of(statements: list[str], fragment: str) -> int:
    """Position of the first statement containing `fragment`.

    A named failure rather than a bare `next()`, so a test that breaks tells
    you which statement went missing instead of raising StopIteration.
    """
    for position, statement in enumerate(statements):
        if fragment in statement:
            return position
    raise AssertionError(f"no statement contained {fragment!r}: {statements}")


def test_publish_swaps_in_the_right_order(connection):
    count = sync.publish("dsn", "analytics", "fct_postings", COLUMNS, ROWS)
    assert count == 1

    statements = connection.log
    staging_created = index_of(statements, "create table")
    inserted = index_of(statements, "INSERT")
    dropped = index_of(statements, 'drop table if exists "analytics"."fct_postings"')
    renamed = index_of(statements, "rename to")

    # Load first, swap last. Anything else means a reader can see a table that
    # is only half there.
    assert staging_created < inserted < dropped < renamed
    assert connection.committed


def test_first_publish_works_with_no_existing_table(connection):
    """The `if exists` subtlety. The obvious version of this pattern renames the
    current table out of the way first, which cannot work the very first time,
    on exactly the run you most want to succeed."""
    sync.publish("dsn", "analytics", "fct_postings", COLUMNS, ROWS)
    drop = connection.log[
        index_of(connection.log, 'drop table if exists "analytics"."fct_postings"')
    ]
    assert "if exists" in drop


def test_publishing_zero_rows_is_refused(connection):
    """An empty mart over a good table is a data loss incident."""
    with pytest.raises(ValueError, match="zero rows"):
        sync.publish("dsn", "analytics", "fct_postings", COLUMNS, [])
    assert connection.log == []


def test_reading_an_empty_mart_is_refused():
    warehouse = FakeWarehouse()
    with pytest.raises(ValueError, match="no rows"):
        sync.read_mart(warehouse, "main", "fct_postings_enriched")


def test_the_source_schema_is_stamped_on_the_table(connection):
    """One shared `analytics_dev` means the last publish wins, which is right for
    a place two tracks meet but leaves nobody able to say why the columns changed.
    The comment names the warehouse schema the rows came from."""
    sync.publish("dsn", "analytics_dev", "fct_postings", COLUMNS, ROWS, source="team_a.dev_alex")

    comment = connection.log[index_of(connection.log, "comment on table")]
    assert '"analytics_dev"."fct_postings"' in comment
    assert "from team_a.dev_alex at " in comment


def test_the_stamp_lands_after_the_swap(connection):
    """Comment the published table, not the staging one: the rename would carry
    the comment across, but only by accident of ordering."""
    sync.publish("dsn", "analytics_dev", "fct_postings", COLUMNS, ROWS, source="s")
    assert index_of(connection.log, "rename to") < index_of(connection.log, "comment on table")


def test_no_source_means_no_comment(connection):
    """Callers that do not know where the rows came from should not write a
    misleading stamp, and an unstamped table is better than a wrong one."""
    sync.publish("dsn", "analytics", "fct_postings", COLUMNS, ROWS)
    assert not any("comment on table" in statement for statement in connection.log)
