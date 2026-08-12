"""Enrichment job: add something to the mart that SQL cannot express well.

This is the second container, and the first question to answer is why it is a
container at all. dbt already runs SQL against the warehouse. Anything you can
write as SQL belongs in a dbt model, where it is tested, documented and
rebuilt with everything else.

This step exists for the work that is not SQL. Here it is a classifier: it
reads each job title and decides which discipline the posting belongs to. In
SQL that is a hundred-line CASE expression that nobody dares change. In Python
it is a dictionary, and the day your team replaces it with a real model or a
call to an external API, only this file changes.

That is the seam to keep. Rules of thumb for what belongs here rather than in
dbt: calling another service, anything with a library behind it (language
detection, geocoding, a model), and anything you want to unit test with
`pytest` rather than with a dbt test.

How it writes back, and why in two steps
----------------------------------------
It could build one enormous statement containing every row. Instead it writes
only what it produced itself, the posting id and the discipline, into a small
mapping table, and then joins that back to the mart in SQL.

Two reasons. The join is the warehouse's job and it is better at it than a
string of INSERTs. And the only values this job sends back over the wire are a
key and a word from a list we control, so the amount of source text being
pasted into SQL stays as small as it can be.

Run:
    uv run python -m src.enrich

In Azure this is a second Container Apps job using the same image, with the
command overridden. One image, two jobs, one thing to build and push.
"""

import logging
import os
import sys

from .warehouse import Queryable, Warehouse, WarehouseError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("enrich")

# The vocabulary. Keep it small and mutually exclusive: a posting gets the
# first discipline whose keywords it matches, so order is meaning.
DISCIPLINES: dict[str, tuple[str, ...]] = {
    "data": ("data engineer", "data scientist", "analytics", "machine learning", "bi "),
    "backend": ("backend", "back-end", "java", "python developer", "golang", "api"),
    "frontend": ("frontend", "front-end", "react", "vue", "javascript", "ui "),
    "devops": ("devops", "sre", "platform engineer", "kubernetes", "cloud engineer"),
    "mobile": ("android", "ios", "flutter", "react native", "mobile"),
}
UNCLASSIFIED = "other"


def classify(title: str) -> str:
    """Decide which discipline a job title belongs to.

    Lowercased substring matching, deliberately. It is easy to read, easy to
    extend, and easy to test, which matters more here than being clever: this
    function is the one piece of business logic in the whole pipeline that a
    non-programmer on your team will have an opinion about.
    """
    haystack = f" {title.lower().strip()} "
    for discipline, keywords in DISCIPLINES.items():
        if any(keyword in haystack for keyword in keywords):
            return discipline
    return UNCLASSIFIED


def sql_literal(value: str) -> str:
    """Quote a string for a SQL statement.

    Databricks treats both the single quote and the backslash as special
    inside a string literal, so both are doubled. Anything you send to a
    warehouse as text needs this: a company called O'Neill will otherwise end
    your statement in the middle of a word, and the error will point at a line
    that looks fine.

    Values that came from your own code, like the discipline names above, do
    not strictly need it. Applying it to everything is the habit worth having.
    """
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def enrich(warehouse: Queryable, schema: str, batch_size: int = 500) -> int:
    """Classify every posting in the mart and rebuild the enriched table.

    Returns the number of postings classified. Rebuilding from scratch each
    run, rather than updating in place, means a change to `classify` applies to
    the whole history on the next run instead of only to new rows.
    """
    catalog = warehouse.catalog
    source = f"{catalog}.{schema}.fct_postings"
    mapping = f"{catalog}.{schema}.postings_discipline"
    target = f"{catalog}.{schema}.fct_postings_enriched"

    rows = warehouse.run(f"select posting_id, title from {source}")
    logger.info("read %d postings from %s", len(rows), source)
    if not rows:
        # Nothing to classify means the mart is empty, which means dbt built
        # nothing, which is a broken run rather than a quiet one.
        raise WarehouseError(f"{source} is empty: there is nothing to enrich")

    classified = [(str(row[0]), classify(str(row[1] or ""))) for row in rows]
    counts: dict[str, int] = {}
    for _, discipline in classified:
        counts[discipline] = counts.get(discipline, 0) + 1
    logger.info("classified: %s", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    warehouse.run(f"create or replace table {mapping} " "(posting_id string, discipline string)")
    # In batches, because one statement holding every row eventually exceeds
    # what the API accepts, and it does so on the day your source gets popular
    # rather than today.
    for start in range(0, len(classified), batch_size):
        batch = classified[start : start + batch_size]
        values = ", ".join(
            f"({sql_literal(posting_id)}, {sql_literal(discipline)})"
            for posting_id, discipline in batch
        )
        warehouse.run(f"insert into {mapping} values {values}")

    warehouse.run(
        f"""
        create or replace table {target} as
        select
            postings.*,
            coalesce(mapping.discipline, '{UNCLASSIFIED}') as discipline,
            current_timestamp()                            as enriched_at
        from {source} as postings
        left join {mapping} as mapping using (posting_id)
        """
    )
    landed = int(warehouse.run(f"select count(*) from {target}")[0][0])
    logger.info("wrote %d rows to %s", landed, target)
    if landed != len(rows):
        raise WarehouseError(f"read {len(rows)} postings but {target} has {landed} rows")
    return landed


def main() -> int:
    try:
        # Built first: it is what loads .env, so DBT_SCHEMA below is read from
        # the same place as everything else.
        warehouse = Warehouse.from_env()
        enrich(warehouse, os.getenv("DBT_SCHEMA", "main"))
    except Exception:
        logger.exception("Enrichment failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
