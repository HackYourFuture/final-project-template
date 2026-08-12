# Optional modules

Nothing in this folder is required. Week 15 asks for a working pipeline, not for
every tool you have seen. Add a module only when your team has the required
pipeline running and wants to go further.

| Folder | Adds | Data Track week |
|---|---|---|
| `python_model/` | Classifies job titles with an LLM, as a dbt model | 13 |
| `streamlit/` | Freshness and row counts for the published mart | 11 |
| `dbt_results/` | Records every dbt run in `<catalog>.ops.dbt_test_runs` | 10 |

The Streamlit page reads the backend's database only, so it reports the end of
the pipeline and nothing before it. Adding `dbt_results` gives it test results
to show as well, which is the pair worth building if you want a health page
that answers more than "did anything arrive?".

Both write to the `ops` schema, which the scheduled run owns. Your own account
can read it and not write it, so run these through Airflow rather than from
your machine.

## dbt_results

dbt writes an account of every model and test to `target/run_results.json`,
which then sits on the machine that ran it. Landing it in the warehouse turns
"are the tests passing?" into a question anyone can answer with SQL.

Copy `dbt_results.py` into `src/`, then add these four lines to the `dbt_build`
task in the DAG, after dbt has run and before the exit code is checked:

```python
from src.dbt_results import parse_run_results, publish_results
from src.warehouse import Warehouse

results = parse_run_results(f"{DBT_PROJECT_DIR}/target/run_results.json")
publish_results(Warehouse.from_env(), results)
```

Publish before deciding the task's fate, so a failing test is recorded rather
than lost. Nothing in it raises: dbt's exit code already decides whether the
pipeline failed.


## python_model

`src/enrich.py` classifies titles with a dictionary, in a container. This does
the same job with an LLM, as a dbt model, and the interesting part is what
changes and what does not.

It runs on **serverless compute**. There is no cluster to create, and none to
forget to stop: dbt submits the model as a job, waits about a minute, and
writes the result. Verified on this workspace, as the team service principal
and as a trainee.

Because it is a dbt model rather than a container job, `dbt build` runs it in
order, `ref()` resolves it, and you can put tests on its output like any other
model. What you give up is speed while developing: a minute per run instead of
a few seconds, which is why the ingestion path stays a container.

### Switching it on

**1. Put your key in your team's secret scope.** It never goes in the
repository, in `.env`, or in a log. Every member of your team can write the
scope, and nobody outside it can read it.

```bash
databricks secrets put-secret team_<x> openrouter-api-key
```

**2. Copy the model into the project** and tell it which scope to read:

```bash
cp optional/python_model/fct_title_discipline.py dbt/models/marts/
```

```yaml
# dbt_project.yml
models:
  final_project:
    marts:
      fct_title_discipline:
        +secret_scope: team_<x>
```

**3. Join it in a SQL model,** the same way `src/enrich.py`'s output is joined
today:

```sql
select p.*, coalesce(d.discipline, 'other') as discipline
from {{ ref('fct_postings') }} as p
left join {{ ref('fct_title_discipline') }} as d on d.title = p.title
```

**4. Run the tests**, which need no key and no network:

```bash
uv run pytest optional/python_model
```

### Three decisions worth understanding before you copy it

**One row per distinct title, not per posting.** Thousands of postings are
hundreds of titles, and tomorrow's file repeats most of them.

**Incremental**, so a run only pays for titles it has never seen. The first run
classifies everything; the second usually classifies a handful.

**Batched**, so one request covers forty titles rather than one.

Drop any of the three and you are calling a paid API once per posting per day.
On the sample source that is cents; on a real one it is the difference between
a rounding error and a bill worth explaining.

### Where it gets awkward, honestly

An LLM is not deterministic, so `accepted_values` on the output can fail on a
day when your data did not change. Two things keep that in check, and both are
in the code: `temperature: 0`, and a fixed list of disciplines, with anything
outside it forced to `other`. The model does not get to extend your taxonomy.

Pin the model name too. `MODEL = "openai/gpt-4o-mini"` rather than a moving
alias, or your classification changes under you and the first you hear of it
is a failing test.
