# OPTIONAL to configure, not optional to keep. pipeline_dag.py imports this
# file, so deleting it stops the DAG from loading. Leave it alone and nothing
# breaks: without a Slack webhook it writes the alert to the task log instead
# of posting it. To make it post, put a webhook in Key Vault. See the README,
# "Alerting".
"""Tell a human when a task fails, by posting to Slack.

The webhook is a credential, so it lives in Key Vault and is read inside the
callback: nothing is fetched until something has already gone wrong. See the
README, "Alerting".
"""

from __future__ import annotations

import json
import os
import urllib.request

VAULT = os.environ.get("KEY_VAULT_NAME", "kv-hyf-data")
WEBHOOK_SECRET = os.environ.get("SLACK_WEBHOOK_SECRET", "fp-slack-webhook")


def _webhook_url() -> str:
    # The VM's own identity, or whatever your .env says when you run this in
    # Astro on your machine. src/common/aca.py explains the chain.
    from src.common.aca import VAULT_SCOPE, azure_token

    token = azure_token(VAULT_SCOPE)
    url = f"https://{VAULT}.vault.azure.net/secrets/{WEBHOOK_SECRET}?api-version=7.4"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(request, timeout=20))["value"]


def post(text: str) -> None:
    """Post one message. Useful for your own notifications too."""
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

    Swallows its own errors on purpose: a bug in the alerting must never turn
    one failed task into two.
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
