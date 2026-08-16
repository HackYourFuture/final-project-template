# OPTIONAL, and disabled. `enabled: false` in dbt_project.yml keeps it out of
# every build until your team turns it on, because it calls an LLM and needs an
# API key first. It does the same job as src/enrichment/enrich.py.
# See ../../../optional/README.md.
"""Classify job titles with an LLM, as a dbt model rather than a container.

Enable it in `dbt_project.yml` and it becomes a normal node in the graph:
`dbt build` runs it in order, `ref()` works, and you can test its output. See
`optional/README.md` for the two settings it needs.

Its tests are in `tests/dbt/test_fct_title_discipline.py`, not next to this file:
dbt reads every `.py` under `models/` as a model and refuses one that defines
no `model()`, so a test file here stops the whole project from parsing.

It runs on **serverless compute**, so there is no cluster to create, start or
forget to stop. dbt submits the model as a job, waits, and writes the result.
Expect about a minute per run of that: fine daily, noticeable when you are
iterating, which is one reason the ingestion path stays a container.

The shape here is the whole point, and it is not "call the model for every
row":

  1. One row per distinct title, not per posting. Thousands of postings are
     hundreds of titles, and the same title tomorrow is already answered.
  2. Incremental, so a run only pays for titles it has never seen.
  3. Batched, so one request classifies many titles instead of one.

Skip any of the three and the bill is per posting per day, which on a real
source is the difference between cents and tens of euros. The functions above
`model()` are plain Python with no Spark and no dbt in them, so they are unit
tested in `test_fct_title_discipline.py` without a key or a network.
"""

import json
import urllib.error
import urllib.request

# Keep this list short and closed. An open-ended prompt ("what discipline is
# this?") returns a different taxonomy every week, and nothing downstream can
# depend on it.
DISCIPLINES = ("backend", "frontend", "data", "devops", "other")

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
# Pin the model. "latest" means your classification changes under you, and the
# first you hear of it is a dbt test failing on data that did not change.
#
# The `:free` suffix costs nothing and is capped at 50 requests a day across
# the whole OpenRouter account, which at BATCH_SIZE titles per request is far
# more than this pipeline needs. That cap is shared, not per team, so read
# optional/README.md before the first backfill. Override it per model with
# `+llm_model:` rather than editing this line.
MODEL = "openai/gpt-oss-20b:free"
# Titles per request, chosen from measurements rather than taste. Against
# gpt-oss-20b:free, 200 and 400 titles both came back complete and correct;
# 800 was cut off mid-JSON after six minutes. 200 leaves room below that and
# keeps a 500-title backfill down to 3 requests out of the 50 a day the
# account gets. Raise it and you save requests but risk a truncated answer,
# which fails the whole batch rather than part of it.
BATCH_SIZE = 200


class ClassificationError(RuntimeError):
    """The model answered, but not with something usable."""


def build_prompt(titles: list[str]) -> str:
    """One request covering many titles, answered as JSON we can parse."""
    allowed = ", ".join(DISCIPLINES)
    numbered = "\n".join(f"{i}. {title}" for i, title in enumerate(titles))
    return (
        "Classify each job title into exactly one of these disciplines: "
        f"{allowed}.\n"
        'Answer with JSON only, of the form {"0": "backend", "1": "data"}, '
        "using the numbers below as keys. Use `other` when unsure.\n\n"
        f"{numbered}"
    )


def parse_response(content: str, titles: list[str]) -> dict[str, str]:
    """Turn one answer into {title: discipline}, refusing anything odd.

    An LLM will occasionally wrap JSON in prose or invent a discipline. Both
    are caught here rather than becoming rows nobody notices.
    """
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        raise ClassificationError(f"no JSON in the answer: {content[:120]!r}")
    try:
        answer = json.loads(content[start : end + 1])
    except json.JSONDecodeError as error:
        raise ClassificationError(f"answer is not JSON: {error}") from error

    result = {}
    for index, title in enumerate(titles):
        discipline = str(answer.get(str(index), "other")).strip().lower()
        # An unknown label becomes `other` rather than a new category. Your
        # taxonomy is a contract; the model does not get to extend it.
        result[title] = discipline if discipline in DISCIPLINES else "other"
    return result


def classify(titles: list[str], call) -> dict[str, str]:
    """Classify every title, one request per batch.

    `call` takes a prompt and returns the model's text. Passing it in is what
    makes this testable: the tests hand it a function that returns a canned
    answer, so the logic is covered without a key or a network.
    """
    result: dict[str, str] = {}
    for start in range(0, len(titles), BATCH_SIZE):
        batch = titles[start : start + BATCH_SIZE]
        result.update(parse_response(call(build_prompt(batch)), batch))
    return result


def openrouter(api_key: str, model: str = MODEL, read_timeout: int = 120):
    """Build the `call` function that talks to OpenRouter.

    Kept to one small function on purpose: swapping OpenRouter for Azure
    OpenAI, or for a model you host, is a change to this and nothing else.

    `read_timeout` is not a budget for the whole request. Python applies it to
    each socket read, so a server that answers and then sends its body slowly
    can take far longer: a measured 100-title request took 434 seconds under a
    300-second setting. It protects you from a server that never replies, not
    from one that is slow. The cap that actually bounds the run is the dbt task
    timeout in the DAG.
    """

    def call(prompt: str) -> str:
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(
                {
                    "model": model,
                    # Deterministic, so two runs over the same titles agree and
                    # your dbt tests are testing the data rather than the dice.
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=read_timeout) as response:
                body = json.load(response)
        except urllib.error.HTTPError as error:
            # 429 is the one you will actually meet, and it has two very
            # different causes that "HTTP Error 429" hides. Either the account
            # spent its 50 free requests for the day, or the free model is
            # throttled upstream, which happens without you doing anything and
            # can clear in minutes. The body says which, so pass it through
            # instead of guessing.
            if error.code == 429:
                raise ClassificationError(
                    f"OpenRouter refused the request (429). Either the account's "
                    f"50 free requests for today are gone, or the model is "
                    f"temporarily throttled upstream, which is not your doing and "
                    f"usually clears. OpenRouter said: {error.read().decode()[:300]}"
                ) from error
            raise ClassificationError(f"OpenRouter returned {error.code}") from error
        return body["choices"][0]["message"]["content"]

    return call


def model(dbt, session):
    """One row per distinct title, classified once and remembered."""
    dbt.config(
        materialized="incremental",
        unique_key="title",
        # No cluster involved. dbt submits this as a serverless job run.
        submission_method="serverless_cluster",
    )

    postings = dbt.ref("fct_postings").select("title").distinct()

    # The saving that makes this affordable: on every run after the first,
    # only titles that are not in the table already reach the model.
    if dbt.is_incremental:
        seen = session.table(f"{dbt.this}").select("title")
        postings = postings.join(seen, on="title", how="left_anti")

    titles = [row["title"] for row in postings.collect() if row["title"]]
    if not titles:
        # Nothing new today. Return the empty frame with the right shape:
        # returning None fails the run, and a run that found no new work is a
        # success, not a failure.
        return session.createDataFrame([], "title string, discipline string")

    # The key never appears in this file, in the repository, or in a log. It
    # lives in your team's Databricks secret scope, which only your team can
    # read. See optional/README.md.
    scope = dbt.config.get("secret_scope")
    if not scope:
        raise ClassificationError(
            "secret_scope is not set. Add `secret_scope: team_a` (or your catalog) to this "
            "model's config, so it knows which scope holds the API key."
        )
    # `dbutils` exists inside Databricks and nowhere else, which is why the
    # tests only cover the functions above.
    api_key = dbutils.secrets.get(scope=scope, key="openrouter-api-key")  # noqa: F821

    # A config rather than a constant: free model IDs get retired, and changing
    # one should not mean editing a file you copied.
    classified = classify(titles, openrouter(api_key, dbt.config.get("llm_model") or MODEL))
    return session.createDataFrame(list(classified.items()), "title string, discipline string")
