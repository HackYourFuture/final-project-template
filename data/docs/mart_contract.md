# The mart contract

This is the agreement between the data trainees and the backend trainees. It
exists because the frontend trainee cannot start until the API shape is known,
and the API shape cannot be known until the mart shape is.

Write it in week one, before anyone builds anything.

## What a contract is

A published dbt mart plus its `.yml` file. The `.yml` names every column and
says what it means. `dbt/models/marts/_fct_postings.yml` is a worked example.

That file is the whole contract. Once it exists, the backend can write
endpoints against columns that do not have data in them yet, and the frontend
can build screens against endpoints that return fixtures.

## How to agree it

1. **Data trainees** draft the mart columns from what the product needs, not
   from what the source happens to provide.
2. **Backend trainees** review it against the endpoints they plan to expose. A
   column nobody will serve is a column you do not need to build.
3. Both pairs sign off, then it goes in the repository.

## Changing it later

You will change it. That is fine, as long as it is deliberate.

| Change | Safe? | What to do |
|---|---|---|
| Add a column | Yes | Tell the backend it exists |
| Add a test | Yes | Just do it |
| Rename a column | No | Agree first, change both sides in the same day |
| Remove a column | No | Confirm no endpoint reads it, then remove |
| Change a type | No | Agree first. This breaks deserialisation quietly |

The rule of thumb: if the backend would have to change code, it is not a
unilateral change.

## Serving the mart

The backend reads the mart directly from Postgres. It does not re-implement
the transformations, and the data pipeline does not expose HTTP endpoints.
Each side does one job.

Three names, one table. dbt builds `fct_postings` in the warehouse, then the
`fct_postings_enriched` Python model adds the discipline next to it. Airflow
publishes that into the backend's database as `analytics.fct_postings`. The
backend only ever sees the last of the three, so the contract is the enriched
shape: `_fct_postings.yml` plus `_fct_postings_enriched.yml`.

If the backend needs a shape the mart does not have, the answer is a new mart
model, not a join written in Java. Business logic lives in dbt, where it is
tested and documented.

## Freshness

`ingested_at` tells you when the pipeline last saw a record. Surface it in the
UI, for example "updated 20 minutes ago". Users trust a number with a
timestamp far more than a number without one, and it makes a stale pipeline
visible during the demo instead of invisible.
