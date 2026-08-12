"""The container job poll loop.

This is where a "starts the job and reports green" regression would hide, and
it would hide well: the pipeline stays green and only the numbers go wrong.
"""

import pytest
from conftest import RecordingOpener

from src.aca import JobFailed, start_and_wait

STARTED = {"name": "job-ingest-abc123"}


def execution(status: str, name: str = "job-ingest-abc123") -> dict:
    return {"value": [{"name": name, "properties": {"status": status}}]}


def run(answers: list[dict], **kwargs) -> str:
    opener = RecordingOpener(answers)
    return start_and_wait(
        subscription="sub",
        resource_group="rg-hyf-fp-team-a",
        job_name="job-ingest",
        token="token",
        opener=opener,
        sleep=lambda _seconds: None,
        **kwargs,
    )


def test_waits_through_pending_and_running():
    """The job is not finished when it starts, and the task must not be either."""
    name = run(
        [
            STARTED,
            execution("Pending"),
            execution("Running"),
            execution("Succeeded"),
        ]
    )
    assert name == "job-ingest-abc123"


def test_failed_execution_raises():
    with pytest.raises(JobFailed, match="Failed"):
        run([STARTED, execution("Failed")])


def test_cancelled_execution_raises():
    """Cancelled is not success. Treating any non-Failed state as fine is the
    easy mistake, and it turns a killed job into a green pipeline."""
    with pytest.raises(JobFailed, match="Cancelled"):
        run([STARTED, execution("Cancelled")])


def test_a_job_that_never_finishes_times_out():
    with pytest.raises(TimeoutError):
        run([STARTED] + [execution("Running")] * 5, timeout_seconds=0)


def test_watches_its_own_execution_not_the_newest():
    """Two runs of the same job can overlap. Taking executions[0] would report
    the status of somebody else's run."""
    answers = [
        STARTED,
        {
            "value": [
                {"name": "job-ingest-other", "properties": {"status": "Failed"}},
                {"name": "job-ingest-abc123", "properties": {"status": "Succeeded"}},
            ]
        },
    ]
    assert run(answers) == "job-ingest-abc123"


def test_start_is_a_post_to_the_right_url():
    opener = RecordingOpener([STARTED, execution("Succeeded")])
    start_and_wait(
        subscription="sub",
        resource_group="rg",
        job_name="job-ingest",
        token="token",
        opener=opener,
        sleep=lambda _seconds: None,
    )
    assert opener.requests[0].get_method() == "POST"
    assert "/providers/Microsoft.App/jobs/job-ingest/start" in opener.urls[0]
