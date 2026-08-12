"""Start an Azure Container Apps job and wait for it to finish.

Airflow uses this to run the two container steps. It talks to Azure's
management API directly over HTTP, because the Airflow image has no `az`
command and no Container Apps provider, and adding either to get two API calls
is not worth it.

The waiting is the important part. A task that starts a job and returns
immediately goes green while the container is still running, so the next step
builds on data that has not landed yet. That failure is intermittent, which
makes it one of the worst kinds to debug: it only shows up when the job is
slow, which is when the data is largest.

Authentication is the VM's own managed identity, read from the instance
metadata service at a link-local address only reachable from inside the
machine. There is no secret on the VM. The identity holds Container Apps Jobs
Operator on your team's resource group, which is enough to start a job and read
how it went, and not enough to change one.
"""

import json
import logging
import time
import urllib.request

logger = logging.getLogger(__name__)

API_VERSION = "2024-03-01"
IMDS_URL = "http://169.254.169.254/metadata/identity/oauth2/token"

# Terminal states, and what each one means for the task.
SUCCEEDED = "Succeeded"
FAILED_STATES = ("Failed", "Cancelled", "Degraded")


class JobFailed(RuntimeError):
    """The container job finished, and not well."""


def imds_token(resource: str, opener=urllib.request.urlopen) -> str:
    """A token for the machine's own identity.

    This is what Managed Identity looks like in practice: no client secret
    anywhere, the machine asks Azure who it is and Azure answers.
    """
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
    """Start one job execution, wait for it, return the execution name.

    Raises `JobFailed` if the execution ends badly and `TimeoutError` if it
    never ends at all. Both matter: an Airflow task that cannot fail is
    decoration.
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
        # Match by name rather than taking the newest. Two runs of the same job
        # can overlap, and watching the wrong one reports the wrong answer.
        current = next((run for run in executions if run["name"] == execution), None)
        status = (current or {}).get("properties", {}).get("status")
        logger.info("  %s: %s", execution, status)
        if status == SUCCEEDED:
            return execution
        if status in FAILED_STATES:
            raise JobFailed(
                f"{job_name} execution {execution} ended as {status}. "
                "The reason is in the container's own output, not in this "
                "status: read it in the portal under the job's execution "
                "history, or with `az containerapp job logs show`."
            )

    raise TimeoutError(
        f"{job_name} execution {execution} did not finish within "
        f"{timeout_seconds}s"
    )
