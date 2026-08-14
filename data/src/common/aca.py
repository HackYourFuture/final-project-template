"""Start an Azure Container Apps job and wait for it to finish.

Airflow uses this to run the two container steps. Plain HTTP against the
management API, because the Airflow image has no `az` and no Container Apps
provider.
"""

import json
import logging
import time
import urllib.request

logger = logging.getLogger(__name__)

API_VERSION = "2024-03-01"
MANAGEMENT_SCOPE = "https://management.azure.com/.default"
VAULT_SCOPE = "https://vault.azure.net/.default"

SUCCEEDED = "Succeeded"
FAILED_STATES = ("Failed", "Cancelled", "Degraded")


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


def start_and_wait(
    subscription: str,
    resource_group: str,
    job_name: str,
    token: str,
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
    """
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
            return execution
        if status in FAILED_STATES:
            raise JobFailed(
                f"{job_name} execution {execution} ended as {status}. "
                "The reason is in the container's own output: read it under "
                "the job's execution history, or with "
                "`az containerapp job logs show`."
            )

    raise TimeoutError(f"{job_name} execution {execution} did not finish within {timeout_seconds}s")
