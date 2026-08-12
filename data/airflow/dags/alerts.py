"""Tell a human when a task fails.

Airflow's behaviour on failure is to colour a square red and wait for somebody
to look. Nobody looks at 6am, which is exactly when your pipeline runs. This
posts to your team's Slack channel instead.

This is not optional polish. "When the pipeline fails, somebody has to find out
without opening Airflow" is one of the things your project is assessed on, and
a failure you were told about is the difference between fixing yesterday's run
this morning and discovering on demo day that the numbers stopped updating a
week ago.

Why this file sits in the dags folder
-------------------------------------
Airflow puts the dags folder on sys.path, so `from alerts import slack_alert`
works with no PYTHONPATH configuration. Airflow will parse this file looking
for DAGs, find none, and move on. No DAGs are defined here.

Why the webhook is not in this file
-----------------------------------
A Slack webhook URL is a credential: anyone holding it can post to your
channel. So it lives in Key Vault, and your Airflow VM's managed identity is
allowed to read that one secret. The lookup happens inside the callback, which
means it costs nothing until something has already gone wrong. Putting it in
module scope would fetch it every few seconds, because Airflow re-parses every
DAG file continuously.
"""

from __future__ import annotations

import json
import os
import urllib.request

VAULT = os.environ.get("KEY_VAULT_NAME", "kv-hyf-data")
WEBHOOK_SECRET = os.environ.get("SLACK_WEBHOOK_SECRET", "fp-slack-webhook")


def _imds_token(resource: str) -> str:
    """A token for the VM's own identity. No secret involved."""
    url = (
        "http://169.254.169.254/metadata/identity/oauth2/token"
        f"?api-version=2018-02-01&resource={resource}"
    )
    request = urllib.request.Request(url, headers={"Metadata": "true"})
    return json.load(urllib.request.urlopen(request, timeout=15))["access_token"]


def _webhook_url() -> str:
    token = _imds_token("https://vault.azure.net")
    url = f"https://{VAULT}.vault.azure.net/secrets/{WEBHOOK_SECRET}?api-version=7.4"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(request, timeout=20))["value"]


def post(text: str) -> None:
    """Post one message. Use it for your own notifications too, not just failures."""
    url = _webhook_url()
    if not url.startswith("https://hooks.slack.com/"):
        # The secret exists but has not been filled in. Say so in the task log
        # rather than raising, so half-configured alerting never masks the real
        # failure that triggered it.
        print(f"alerts: {WEBHOOK_SECRET} is not a Slack webhook yet, not posting")
        print(f"alerts: would have posted:\n{text}")
        return
    request = urllib.request.Request(
        url,
        data=json.dumps({"text": text}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        print(f"alerts: posted to Slack ({response.status})")


def slack_alert(context) -> None:
    """Airflow calls this with the failed task's context.

    Attach it once in `default_args` and every task in the DAG inherits it,
    including tasks you add later. That is the point of putting it there rather
    than on each operator: alerting you have to remember is alerting you will
    forget.

    It deliberately swallows its own errors. A bug in the alerting must never
    turn one failed task into two, and the traceback still reaches the task log.
    """
    try:
        instance = context.get("task_instance")
        dag_id = getattr(instance, "dag_id", "?")
        task_id = getattr(instance, "task_id", "?")
        run_id = getattr(instance, "run_id", "") or str(context.get("run_id", ""))
        attempt = getattr(instance, "try_number", "?")

        reason = str(context.get("exception") or "no exception recorded").strip()
        # The last line of a traceback is the part that names what went wrong.
        reason = reason.splitlines()[-1][:300] if reason else "no exception recorded"

        base = os.environ.get("AIRFLOW_BASE_URL", "").rstrip("/")
        link = (
            f"\n<{base}/dags/{dag_id}/runs/{run_id}/tasks/{task_id}|Open the task log>"
            if base
            else ""
        )

        post(
            f":rotating_light: *{dag_id}* failed\n"
            f"*task* `{task_id}`  *attempt* {attempt}\n"
            f"*why* `{reason}`{link}"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"alerts: could not post the failure alert: {type(exc).__name__} {exc}")
