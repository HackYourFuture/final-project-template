# OPTIONAL. Not part of the required pipeline, and nothing imports it where
# it sits. Copy it into src/ to use it. See data/optional/README.md.
"""Turn dbt's own record of a run into a table anyone can query.

dbt writes a full account of every model and test it ran to
`target/run_results.json`, and then that file sits on the machine that ran it.
Which means "are the tests passing?" can only be answered by whoever has SSH
access and a reason to look.

Landing it in the warehouse turns test results into data: something you can
query with SQL, chart, or join to anything else, without touching Airflow.

Nothing reads the table yet. The health page in optional/streamlit/ queries the
backend database only, so wiring it to show test results is work you would be
doing, not something that starts happening once you copy this file in.

Nothing here raises on a missing or broken file. dbt's own exit code already
decides whether the pipeline failed; losing the bookkeeping is annoying, but
failing a green run because the bookkeeping stumbled would be worse.
"""

import json
import logging
from pathlib import Path

from src.common.warehouse import Queryable

logger = logging.getLogger(__name__)


def sql_literal(value: str) -> str:
    """Quote a string for a SQL statement.

    Databricks treats the single quote and the backslash as special inside a
    literal, so both are doubled. A dbt node named with an apostrophe would
    otherwise end the statement in the middle of a word.
    """
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


TABLE = "dbt_test_runs"
SCHEMA = "ops"

# dbt's own words for "this went fine". Everything else is worth reading.
GOOD_STATUSES = ("success", "pass")


def parse_run_results(path: str | Path) -> list[dict]:
    """Read run_results.json into one dictionary per node.

    Returns an empty list when the file is missing or unreadable, which is the
    normal case the first time anyone runs this.
    """
    try:
        payload = json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        logger.warning("no dbt results to publish: %s", error)
        return []

    metadata = payload.get("metadata", {})
    invocation = metadata.get("invocation_id", "unknown")
    generated = (metadata.get("generated_at") or "")[:19].replace("T", " ")

    results = []
    for result in payload.get("results", []):
        node = result.get("unique_id", "")
        results.append(
            {
                "invocation_id": invocation,
                "node": node,
                # unique_id looks like test.project.name or model.project.name,
                # so the first segment is what kind of thing this was.
                "resource_type": node.split(".")[0],
                "status": result.get("status", ""),
                "execution_time": float(result.get("execution_time") or 0),
                "message": (result.get("message") or "")[:400],
                "run_at": generated,
            }
        )
    return results


def summarise(results: list[dict]) -> dict[str, int]:
    """Count nodes by status, for one readable log line."""
    counts: dict[str, int] = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    return counts


def publish_results(warehouse: Queryable, results: list[dict]) -> int:
    """Append one row per node to <catalog>.ops.dbt_test_runs."""
    if not results:
        return 0

    catalog = warehouse.catalog
    warehouse.run(f"create schema if not exists {catalog}.{SCHEMA}")
    warehouse.run(
        f"""
        create table if not exists {catalog}.{SCHEMA}.{TABLE} (
            invocation_id  string,
            node           string,
            resource_type  string,
            status         string,
            execution_time double,
            message        string,
            run_at         timestamp
        )
        """
    )
    values = ", ".join(
        "({}, {}, {}, {}, {}, {}, timestamp{})".format(
            sql_literal(result["invocation_id"]),
            sql_literal(result["node"]),
            sql_literal(result["resource_type"]),
            sql_literal(result["status"]),
            result["execution_time"],
            sql_literal(result["message"]),
            sql_literal(result["run_at"]),
        )
        for result in results
    )
    warehouse.run(f"insert into {catalog}.{SCHEMA}.{TABLE} values {values}")

    counts = summarise(results)
    logger.info(
        "published %d node results (%s)",
        len(results),
        ", ".join(f"{status}={count}" for status, count in sorted(counts.items())),
    )
    for result in results:
        if result["status"] not in GOOD_STATUSES:
            logger.warning("  %s %s %s", result["status"], result["node"], result["message"][:120])
    return len(results)
