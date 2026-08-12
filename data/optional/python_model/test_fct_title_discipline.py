"""The parts of the LLM model worth testing: batching, parsing, and refusal.

No key and no network. `classify` takes the function that talks to the model,
so these tests hand it one that answers from a script. That is the whole
reason it is written that way.

Copy this next to the model file and run `uv run pytest optional/python_model`.
"""

import json
import urllib.error

import pytest
from fct_title_discipline import (
    BATCH_SIZE,
    ClassificationError,
    build_prompt,
    classify,
    openrouter,
    parse_response,
)


def answer_for(titles, disciplines):
    """One canned model answer, in the shape the prompt asks for."""
    return json.dumps({str(i): d for i, d in enumerate(disciplines)})


def test_every_title_gets_a_discipline():
    titles = ["Backend Engineer", "Data Engineer"]
    calls = []

    def call(prompt):
        calls.append(prompt)
        return answer_for(titles, ["backend", "data"])

    assert classify(titles, call) == {
        "Backend Engineer": "backend",
        "Data Engineer": "data",
    }
    assert len(calls) == 1, "two titles is one request, not two"


def test_titles_are_batched():
    """The cost control: one request per batch, not one per title."""
    titles = [f"Engineer {i}" for i in range(BATCH_SIZE * 2 + 1)]
    calls = []

    def call(prompt):
        calls.append(prompt)
        # The batch size is whatever the prompt actually listed.
        count = sum(1 for line in prompt.splitlines() if line[:1].isdigit())
        return answer_for(titles, ["other"] * count)

    classify(titles, call)
    assert len(calls) == 3


def test_a_discipline_outside_the_taxonomy_becomes_other():
    """The model does not get to invent categories.

    If `machine-learning` came through, every downstream `accepted_values`
    test would fail on a day when nothing about the data changed.
    """
    result = parse_response(json.dumps({"0": "machine-learning"}), ["ML Engineer"])
    assert result == {"ML Engineer": "other"}


def test_a_missing_answer_becomes_other():
    """A short answer must not shift every later title by one."""
    result = parse_response(json.dumps({"0": "backend"}), ["A", "B"])
    assert result == {"A": "backend", "B": "other"}


def test_json_wrapped_in_prose_is_still_read():
    """Models like to explain themselves. That is not a failure."""
    content = 'Sure! Here you go:\n```json\n{"0": "data"}\n```\nHope that helps.'
    assert parse_response(content, ["Analytics Engineer"]) == {"Analytics Engineer": "data"}


def test_an_answer_with_no_json_raises():
    """Better a failed run than a table of silent `other`."""
    with pytest.raises(ClassificationError, match="no JSON"):
        parse_response("I cannot help with that.", ["Backend Engineer"])


def test_being_rate_limited_says_so_in_words(monkeypatch):
    """429 is the failure teams will actually meet, on a shared daily quota.

    `HTTP Error 429: Too Many Requests` in an Airflow log sends someone
    looking for a bug in their own code, so the message names the real cause.
    """

    def refuse(*_args, **_kwargs):
        raise urllib.error.HTTPError(url="", code=429, msg="", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    with pytest.raises(ClassificationError, match="50 requests a day"):
        openrouter("not-a-real-key")("classify these")


def test_the_prompt_names_the_allowed_disciplines_and_the_titles():
    prompt = build_prompt(["Backend Engineer"])
    assert "backend, frontend, data, devops, other" in prompt
    assert "0. Backend Engineer" in prompt
