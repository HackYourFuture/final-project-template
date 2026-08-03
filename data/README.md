# Final Project Data Pipeline

Starter code for the data half of the final project: fetch data from a source,
validate it, store it, shape it with dbt, and publish a mart the backend team
reads. It runs end to end the moment you clone it, against a local Postgres and
a public API that needs no key, so your first hour goes into your product
rather than into setup.

## Run it in five minutes

```bash
cd data
cp .env.example .env
docker compose up -d          # local Postgres on :5432

uv venv && uv pip install -e ".[dbt]"
uv run python -m src.pipeline # fetch, validate, store

cd dbt && uv run dbt build --profiles-dir .
```

You should see around 175 rows land in `raw.postings`, then `stg_postings` and
`fct_postings` build with all tests passing. Run the pipeline twice: the row
count stays the same, because writes are upserts.

## What is here

| Path | What it does |
|---|---|
| `src/config.py` | Reads every setting from environment variables and fails loudly when one is missing |
| `src/models.py` | Pydantic validation for incoming records |
| `src/ingest.py` | Calls the source API, validates, counts rejects |
| `src/storage.py` | Creates the raw schema and upserts rows |
| `src/pipeline.py` | Entry point, wires the three steps together |
| `dbt/models/staging/` | Cleans and renames. No business logic |
| `dbt/models/marts/fct_postings.sql` | **The contract with the backend team** |
| `dbt/tests/` | Two custom tests, including a zero-row check |
| `airflow/dags/pipeline_dag.py` | Daily schedule: ingest, then dbt build |
| `Dockerfile` | The image you push to Azure Container Registry |
| `optional/` | Bicep, Databricks, and Streamlit modules. None required |

## Making it yours

The template ships a job-postings example so it runs immediately. Swapping in
your team's data source is four edits:

1. `.env`: point `SOURCE_API_URL` at your source.
2. `src/models.py`: change the Pydantic model to match your records.
3. `src/storage.py`: change the table definition and upsert to match.
4. `dbt/models/`: rename the models and columns to your domain.

Do this in your first two days. Everything after that builds on the shape you
choose here.

> Verify your source before you commit to it: call it once, print a record, and
> confirm you can parse it. An idea you love with a source you cannot reach is
> worth less than a plain idea that works.

## The mart is a contract

`fct_postings` is what the backend reads to build endpoints. Adding a column is
safe. Renaming or removing one breaks the backend, so agree it with them first
and change it in both places at once.

Every column is documented in `dbt/models/marts/_fct_postings.yml`. Hand that
file to the backend trainees on day one and they can write endpoints before
your pipeline is finished. See `docs/mart_contract.md` for how to work on it
together.

## Secrets

No credentials live in this folder. `dbt/profiles.yml` is committed on purpose:
every value in it comes from `env_var(...)`, so it holds nothing secret. Real
values live in `.env`, which is git-ignored, and in your deployment environment.

Never commit `.env`, and never paste a connection string into a chat message or
an LLM prompt.
