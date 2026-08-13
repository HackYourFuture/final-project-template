"""The enrichment step: add to the mart what SQL expresses badly.

This is the table the sync publishes, so it is the last thing built before your
work leaves the warehouse.

It is a **dbt Python model**, which means it is a node in the dbt graph like any
`.sql` file: `dbt build` runs it in dependency order after `fct_postings`,
`ref()` works, and the tests in `_fct_postings_enriched.yml` run against its
output. It executes on Databricks **serverless**, so there is no cluster to
create, start, or forget to stop.

Why Python rather than SQL: the rules below are a dictionary you can read and
change. The same logic as SQL is a hundred-line `CASE` expression that nobody
dares touch, and it cannot be unit tested without a warehouse.

Why a dbt model rather than a container: dbt already knows this table depends on
`fct_postings`, so it cannot run in the wrong order or against yesterday's mart.
A separate container would need its own trigger, its own wait, and its own
answer to "did the thing I read finish building?".

`classify` is plain Python with no Spark and no dbt in it, so
`tests/dbt/test_fct_postings_enriched.py` covers it with no warehouse and no
credentials.

> Replace the rules with your own. This file is the one place in the pipeline
> where domain knowledge lives.
"""

import re

# A posting gets the first discipline whose keywords it matches, so the order of
# this dictionary is meaning, not decoration. Keep the list small and the
# keywords mutually exclusive: two disciplines matching the same title makes the
# result depend on dictionary order, which is not a rule anyone can explain.
DISCIPLINES: dict[str, tuple[str, ...]] = {
    "data": ("data engineer", "data scientist", "analytics", "machine learning", "bi"),
    # Before frontend, deliberately. "React Native Developer" matches `react`
    # too, so with frontend first every React Native role was labelled frontend
    # and the `react native` keyword below could never match anything.
    "mobile": ("android", "ios", "flutter", "react native", "mobile"),
    "backend": ("backend", "back-end", "java", "python developer", "golang", "api", "apis"),
    "frontend": ("frontend", "front-end", "react", "vue", "javascript", "ui"),
    "devops": ("devops", "sre", "platform engineer", "kubernetes", "cloud engineer"),
}
UNCLASSIFIED = "other"

# Whole words only, which is the whole game here. Plain substring matching
# looks fine until real titles arrive: `api` matched "Therapist" and "Capital
# Markets Analyst", `java` swallowed "JavaScript Developer", `ios` matched
# "BIOS", and `mobile` matched "Automobile". A word boundary handles every one
# of those, and still matches punctuation-joined titles like "React.js
# Developer" that space padding would miss.
_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    discipline: [re.compile(rf"\b{re.escape(keyword)}\b") for keyword in keywords]
    for discipline, keywords in DISCIPLINES.items()
}


def classify(title: str) -> str:
    """Decide which discipline a job title belongs to.

    The first discipline with a matching keyword wins, so the order of
    DISCIPLINES is meaning rather than decoration.
    """
    haystack = title.lower().strip()
    for discipline, patterns in _PATTERNS.items():
        if any(pattern.search(haystack) for pattern in patterns):
            return discipline
    return UNCLASSIFIED


def model(dbt, session):
    """One row per posting, with the discipline added."""
    dbt.config(
        materialized="table",
        # No cluster involved: dbt submits this as a serverless job run.
        submission_method="serverless_cluster",
    )

    from pyspark.sql.functions import coalesce, current_timestamp, lit

    postings = dbt.ref("fct_postings")

    # Classify distinct titles rather than rows. Thousands of postings are
    # hundreds of titles, and the answer for a title never depends on which
    # posting it came from. Rebuilt from scratch every run, so changing a rule
    # applies to the whole history instead of only to new rows.
    titles = [row["title"] for row in postings.select("title").distinct().collect()]
    mapping = session.createDataFrame(
        [(title, classify(title or "")) for title in titles],
        "title string, discipline string",
    )

    enriched = postings.join(mapping, on="title", how="left")
    # A posting whose title matched nothing lands as `other` rather than as a
    # null the backend has to handle.
    enriched = enriched.withColumn("discipline", coalesce("discipline", lit(UNCLASSIFIED)))
    return enriched.withColumn("enriched_at", current_timestamp())
