"""Start an Azure Container Apps job and wait for it to finish.

Airflow uses this to run the two container steps. Plain HTTP against the
management API, because the Airflow image has no `az` and no Container Apps
provider. Authentication is the machine's own identity: no secret on the VM.
"""

import json
import logging
import time
import urllib.request

logger = logging.getLogger(__name__)

API_VERSION = "2024-03-01"
IMDS_URL = "http://169.254.169.254/metadata/identity/oauth2/token"

SUCCEEDED = "Succeeded"
FAILED_STATES = ("Failed", "Cancelled", "Degraded")


class JobFailed(RuntimeError):
    """The container job finished, and not well."""


def imds_token(resource: str, opener=urllib.request.urlopen) -> str:
    """A token for the machine's own identity."""
    request = urllib.request.Request(
        f"{IMDS_URL}?api-version=2018-02-01&resource={resource}",
        headers={"Metadata": "true"},
    )
    return json.load(opener(request, timeout=15))["access_token"]


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
