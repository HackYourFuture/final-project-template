"""Start an Azure Container Apps job and wait for it to finish.

Airflow uses this to run the two container steps. Plain HTTP against the
management API, because the Airflow image has no `az` and no Container Apps
provider.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

API_VERSION = "2024-03-01"
WORKSPACE_API_VERSION = "2022-10-01"
MANAGEMENT_SCOPE = "https://management.azure.com/.default"
LOG_ANALYTICS_SCOPE = "https://api.loganalytics.io/.default"
VAULT_SCOPE = "https://vault.azure.net/.default"

SUCCEEDED = "Succeeded"
FAILED_STATES = ("Failed", "Cancelled", "Degraded")

LOG_FETCH_MAX_WAIT_SECONDS = 180
LOG_FETCH_POLL_SECONDS = 5

# Container logging.basicConfig format in src.ingestion.pipeline.
_CONTAINER_LOG_LINE = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} "
    r"(?:DEBUG|INFO|WARNING|ERROR|CRITICAL) "
    r"(\S+)\s+"
)


def filter_application_log_lines(lines: list[str]) -> list[str]:
    """Keep pipeline application log lines; drop Azure SDK HTTP chatter."""
    kept: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line:
            continue
        match = _CONTAINER_LOG_LINE.match(line)
        if not match:
            continue
        logger_name = match.group(1)
        if logger_name == "pipeline" or logger_name.startswith("src."):
            kept.append(line)
    return kept


class JobFailed(RuntimeError):
    """The container job finished, and not well."""


def azure_token(scope: str = MANAGEMENT_SCOPE) -> str:
    """A management-API token for whoever is running.

    On the team VM that is the machine's own identity, which the credential
    chain finds through the instance metadata service. There is no such service
    on your laptop, so the chain falls through to the service principal in your
    `.env`, and the DAG you run in Astro starts the same job the VM does.

    The same rule `dbt_command()` and `databricks_environment()` follow: one
    code path, and where it runs decides who it runs as. Asking the metadata
    service directly is what used to make this VM-only, and the failure was a
    fifteen-second timeout rather than anything that named the cause.
    """
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential().get_token(scope).token


def log_analytics_customer_id(
    subscription: str,
    resource_group: str,
    team: str,
    token: str,
    opener=urllib.request.urlopen,
) -> str:
    """Return the Log Analytics workspace customer id for `log-fp-<team>`."""
    workspace_name = f"log-fp-{team}"
    url = (
        f"https://management.azure.com/subscriptions/{subscription}"
        f"/resourceGroups/{resource_group}/providers/Microsoft.OperationalInsights/workspaces/"
        f"{workspace_name}?api-version={WORKSPACE_API_VERSION}"
    )
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with opener(request, timeout=60) as response:
        payload = json.loads(response.read())
    customer_id = payload.get("properties", {}).get("customerId")
    if not customer_id:
        raise RuntimeError(f"workspace {workspace_name} has no customerId")
    return customer_id


def _console_log_query(execution: str) -> str:
    return (
        "ContainerAppConsoleLogs_CL\n"
        f"| where ContainerGroupName_s contains '{execution}'\n"
        "| order by TimeGenerated asc\n"
        "| project Log_s"
    )


def _query_log_analytics(
    workspace_id: str,
    query: str,
    timespan: str,
    token: str,
    opener=urllib.request.urlopen,
) -> list[str]:
    body = json.dumps({"query": query, "timespan": timespan}).encode()
    request = urllib.request.Request(
        f"https://api.loganalytics.io/v1/workspaces/{workspace_id}/query",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with opener(request, timeout=60) as response:
        payload = json.loads(response.read())
    table = (payload.get("tables") or [{}])[0]
    rows = table.get("rows") or []
    return [row[0] for row in rows if row and row[0]]


def fetch_console_logs(
    *,
    workspace_id: str,
    execution: str,
    started_at: datetime,
    token: str,
    opener=urllib.request.urlopen,
    sleep=time.sleep,
    max_wait_seconds: int = LOG_FETCH_MAX_WAIT_SECONDS,
    poll_seconds: int = LOG_FETCH_POLL_SECONDS,
) -> list[str]:
    """Read container stdout from Log Analytics and return the lines.

    Console output only exists in Log Analytics once the replica has finished
    and Azure has indexed it. That can lag a minute or two, longer the first
    time a workspace receives logs.
    """
    query = _console_log_query(execution)
    deadline = time.monotonic() + max_wait_seconds
    while time.monotonic() < deadline:
        end = datetime.now(UTC)
        start = started_at - timedelta(minutes=1)
        timespan = f"{start.isoformat().replace('+00:00', 'Z')}/{end.isoformat().replace('+00:00', 'Z')}"
        try:
            lines = _query_log_analytics(workspace_id, query, timespan, token, opener=opener)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Log Analytics query failed for %s: %s", execution, exc)
            lines = []
        if lines:
            return lines
        sleep(poll_seconds)
    return []


def emit_console_logs(lines: list[str], execution: str, workspace_id: str) -> None:
    """Write container stdout into the Airflow task log."""
    app_lines = filter_application_log_lines(lines)
    if not app_lines:
        if lines:
            logger.warning(
                "Console log for %s had %d line(s) in Log Analytics but none from "
                "application loggers (src.* / pipeline).",
                execution,
                len(lines),
            )
        else:
            logger.warning(
                "No console log in Log Analytics yet for %s. Query manually:\n"
                "  az monitor log-analytics query -w %s --analytics-query %r",
                execution,
                workspace_id,
                _console_log_query(execution).replace("\n", " "),
            )
        return
    logger.info("--- console log for %s ---", execution)
    for line in app_lines:
        logger.info("%s", line)


def start_and_wait(
    subscription: str,
    resource_group: str,
    job_name: str,
    token: str,
    team: str | None = None,
    opener=urllib.request.urlopen,
    timeout_seconds: int = 900,
    poll_seconds: int = 15,
    sleep=time.sleep,
) -> str:
    """Start one execution, wait for it, return its name.

    The waiting is the point. A task that starts a job and returns goes green
    while the container is still running, so the next step builds on data that
    has not landed. That only shows up when the job is slow, which is when the
    data is largest.

    When `team` is set (for example `team-a`), container stdout is pulled from
    the team's Log Analytics workspace (`log-fp-<team>`) into this task log.
    """
    started_at = datetime.now(UTC)
    base = (
        f"https://management.azure.com/subscriptions/{subscription}"
        f"/resourceGroups/{resource_group}/providers/Microsoft.App/jobs/{job_name}"
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    request = urllib.request.Request(
        f"{base}/start?api-version={API_VERSION}", data=b"{}", method="POST", headers=headers
    )
    with opener(request, timeout=60) as response:
        started = json.loads(response.read() or b"{}")
    execution = started.get("name", "")
    logger.info("started %s, execution %s", job_name, execution)

    workspace_id = None
    if team:
        try:
            workspace_id = log_analytics_customer_id(
                subscription, resource_group, team, token, opener=opener
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not resolve Log Analytics workspace for %s: %s", team, exc)

    def pull_console_logs() -> None:
        if not workspace_id:
            return
        la_token = azure_token(LOG_ANALYTICS_SCOPE)
        lines = fetch_console_logs(
            workspace_id=workspace_id,
            execution=execution,
            started_at=started_at,
            token=la_token,
            opener=opener,
            sleep=sleep,
        )
        emit_console_logs(lines, execution, workspace_id)

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        sleep(poll_seconds)
        request = urllib.request.Request(
            f"{base}/executions?api-version={API_VERSION}", headers=headers
        )
        executions = json.load(opener(request, timeout=60)).get("value", [])
        # Match by name rather than taking the newest: two runs of the same job
        # can overlap, and watching the wrong one reports the wrong answer.
        current = next((run for run in executions if run["name"] == execution), None)
        status = (current or {}).get("properties", {}).get("status")
        logger.info("  %s: %s", execution, status)
        if status == SUCCEEDED:
            pull_console_logs()
            return execution
        if status in FAILED_STATES:
            pull_console_logs()
            raise JobFailed(
                f"{job_name} execution {execution} ended as {status}. "
                "See the console log block above for container output."
            )

    raise TimeoutError(f"{job_name} execution {execution} did not finish within {timeout_seconds}s")
