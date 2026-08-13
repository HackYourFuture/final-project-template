"""The enrichment job: add to the mart what SQL cannot express well.

    uv run python -m src.enrichment.enrich

Here that is a classifier over job titles. Replace it with your own logic: this
file is the one place in the pipeline where domain rules live. See the README,
"Why there is a second container".
"""

import logging
import os
import sys

from ..common.warehouse import Queryable, Warehouse, WarehouseError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("enrich")

# A posting gets the first discipline whose keywords it matches, so order is
# meaning. Keep the list small and mutually exclusive.
DISCIPLINES: dict[str, tuple[str, ...]] = {
    "data": ("data engineer", "data scientist", "analytics", "machine learning", "bi "),
    "backend": ("backend", "back-end", "java", "python developer", "golang", "api"),
    "frontend": ("frontend", "front-end", "react", "vue", "javascript", "ui "),
    "devops": ("devops", "sre", "platform engineer", "kubernetes", "cloud engineer"),
    "mobile": ("android", "ios", "flutter", "react native", "mobile"),
}
UNCLASSIFIED = "other"


def classify(title: str) -> str:
    """Decide which discipline a job title belongs to."""
    haystack = f" {title.lower().strip()} "
    for discipline, keywords in DISCIPLINES.items():
        if any(keyword in haystack for keyword in keywords):
            return discipline
    return UNCLASSIFIED


def sql_literal(value: str) -> str:
    """Quote a string for a SQL statement.

    Databricks treats the single quote and the backslash as special inside a
    literal, so both are doubled. A company called O'Neill would otherwise end
    your statement in the middle of a word.
    """
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def enrich(warehouse: Queryable, schema: str, batch_size: int = 500) -> int:
    """Classify every posting and rebuild the enriched table.

    Writes only what it produced, the id and the discipline, into a mapping
    table and joins that back in SQL: the warehouse is better at joins than a
    string of INSERTs, and less source text is pasted into a statement.

    Rebuilt from scratch each run, so a change to `classify` applies to the
    whole history rather than only to new rows.
    """
    catalog = warehouse.catalog
    source = f"{catalog}.{schema}.fct_postings"
    mapping = f"{catalog}.{schema}.postings_discipline"
    target = f"{catalog}.{schema}.fct_postings_enriched"

    rows = warehouse.run(f"select posting_id, title from {source}")
    logger.info("read %d postings from %s", len(rows), source)
    if not rows:
        raise WarehouseError(f"{source} is empty: there is nothing to enrich")

    classified = [(str(row[0]), classify(str(row[1] or ""))) for row in rows]
    counts: dict[str, int] = {}
    for _, discipline in classified:
        counts[discipline] = counts.get(discipline, 0) + 1
    logger.info("classified: %s", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    warehouse.run(f"create or replace table {mapping} (posting_id string, discipline string)")
    # In batches: one statement holding every row eventually exceeds what the
    # API accepts, on the day your source gets popular rather than today.
    for start in range(0, len(classified), batch_size):
        values = ", ".join(
            f"({sql_literal(posting_id)}, {sql_literal(discipline)})"
            for posting_id, discipline in classified[start : start + batch_size]
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
        # Built first: it is what loads .env, so DBT_SCHEMA is read from the
        # same place as everything else.
        warehouse = Warehouse.from_env()
        enrich(warehouse, os.getenv("DBT_SCHEMA", "main"))
    except Exception:
        logger.exception("Enrichment failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
