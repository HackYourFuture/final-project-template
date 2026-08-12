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
forget to stop: dbt submits the model as a job, waits, and writes the result.
Measured on this workspace at 125 seconds for a first run and 85 for the next,
as the team service principal and as a trainee.

Because it is a dbt model rather than a container job, `dbt build` runs it in
order, `ref()` resolves it, and you can put tests on its output like any other
model. What you give up is speed while developing: a minute per run instead of
a few seconds, which is why the ingestion path stays a container.

### What it costs: nothing

The model it calls, `openai/gpt-oss-20b:free`, is free. Not "a few cents", not
"free trial": OpenRouter charges 0 for every model whose ID ends in `:free`,
and you do not need a card to use one.

Be precise about what is free, though. The *model* costs nothing. The
*serverless compute* that runs the dbt model is ordinary Databricks usage, the
same as any other model in your project, and it bills for the two minutes the
run takes. That is small, and it is not zero.

What you pay for the free model is in speed and in a shared daily allowance,
both further down. If your team ever wants a paid model, `gpt-4.1-mini` is
about $0.40 per million input tokens, so a few hundred job titles is a fraction
of a cent. Ask your teacher before switching: a paid model should have a key
with a spending limit on it.

### Getting an API key

Ask your teacher first, because the class may already have a key. If you are
making your own:

**Step 1:** Sign up at [openrouter.ai](https://openrouter.ai). An email address
is enough. You do not need to add a payment method to use free models.

**Step 2:** Open **Keys** in the account menu and choose **Create Key**. Name it
after your team, for example `hyf-team-a`, so you can tell later which one to
revoke.

**Step 3:** Copy the key immediately. It is shown once, and if you lose it the
only option is to create another one. It starts with `sk-or-`.

**Step 4:** Leave the credit limit empty. It caps spending on paid models, and
you are using a free one.

> ⚠️ Treat the key like a password. Anyone holding it can spend on your account.
> If it ever lands in a commit, a screenshot or a Slack message, delete it in
> the OpenRouter UI and make a new one. Deleting it is a ten-second job and
> costs you nothing.

### Where the key lives

In your team's Databricks secret scope, and nowhere else. Not in the repository,
not in `data/.env`, not in the dbt project, not in a notebook cell.

```bash
databricks secrets put-secret team_<x> openrouter-api-key
```

That opens an editor; paste the key, save, close. To check it without printing
it, `databricks secrets list-secrets team_<x>` shows the name and the time it
was updated, never the value. Databricks also redacts secrets from job output,
so a stray `print()` shows `[REDACTED]` rather than your key.

Every member of your team can write this scope and nobody outside it can read
it, which is why the key goes here rather than into a file somebody has to
remember not to commit.

### Switching it on

**1. Copy the model into the project** and tell it which scope to read:

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
        # Optional. Leave it out and the model uses the free one it ships with.
        +llm_model: openai/gpt-oss-20b:free
```

**2. Run the tests**, which need no key and no network, so they tell you the
file arrived intact before you spend a request:

```bash
uv run pytest optional/python_model
```

**3. Build it once, by hand,** and read what it wrote:

```bash
uv run dbt build --select fct_title_discipline
```

Expect roughly two minutes: most of it is serverless starting up, not the
model thinking. Then look at the output before you build anything on it:

```sql
select discipline, count(*) from fct_title_discipline group by discipline
```

If everything came back `other`, the model did not answer in the shape the
code expects. Check the run's log in Databricks rather than changing the
prompt: the error names the cause.

**4. Join it in a SQL model,** the same way `src/enrich.py`'s output is joined
today:

```sql
select p.*, coalesce(d.discipline, 'other') as discipline
from {{ ref('fct_postings') }} as p
left join {{ ref('fct_title_discipline') }} as d on d.title = p.title
```

The `coalesce` matters: a posting whose title arrived after the last run has
no row here yet, and you want it in your mart as `other` rather than missing.

### Three decisions worth understanding before you copy it

**One row per distinct title, not per posting.** Thousands of postings are
hundreds of titles, and tomorrow's file repeats most of them.

**Incremental**, so a run only pays for titles it has never seen. The first run
classifies everything; the second usually classifies a handful.

**Batched**, so one request covers forty titles rather than one.

Drop any of the three and you are calling a paid API once per posting per day.
On the sample source that is cents; on a real one it is the difference between
a rounding error and a bill worth explaining.

### The limits, measured

Free models are rate limited, not quality limited. Numbers from actual runs
against `openai/gpt-oss-20b:free`:

| Titles in one request | Answered | Agreed with the expected discipline | Time |
|---|---|---|---|
| 40 | 40 | 100% | 43s |
| 100 | 100 | 100% | 434s |

The accuracy did not drop as the batch grew. The waiting did, steeply, which is
why `BATCH_SIZE` is 40: big enough that one request does real work, small
enough that a request comes back in under a minute.

The other limits worth knowing:

- **50 requests a day for the whole OpenRouter account**, or 1,000 once the
  account has bought 10 credits. Not per team and not per key.
- **20 requests a minute**, which batching keeps you far below.
- **A request has no real time limit.** The `read_timeout` in the code guards
  against a server that never answers, not one that is slow: Python applies it
  per socket read, so a 434-second request completed under a 300-second
  setting. What bounds a run is the dbt task timeout in the DAG.

### The daily allowance is shared, and that shapes your first run

The model ships pointing at a free one, and free on OpenRouter means **50
requests a day for the whole account**, not per team and not per key. All three
teams draw on the same allowance. At forty titles per request that is up to
2,000 titles a day, far more than this pipeline needs, but only if nobody
wastes it.

Two habits keep you out of trouble:

**Run the first backfill by hand, once.** The scheduled task retries twice, and
because the model is incremental a failed run writes nothing, so every batch
gets paid for again on the retry. Run `dbt build --select fct_title_discipline`
yourself, watch it finish, and let the schedule pick up from there, when there
are only a few new titles a day.

**Read the error before you change anything.** A rate limit comes back as a
message naming the daily allowance, not as a mystery. If it says that, the
answer is to wait or to ask your teacher, not to edit the code.

### Where it gets awkward, honestly

An LLM is not deterministic, so `accepted_values` on the output can fail on a
day when your data did not change. Two things keep that in check, and both are
in the code: `temperature: 0`, and a fixed list of disciplines, with anything
outside it forced to `other`. The model does not get to extend your taxonomy.

Pin the model name too. `openai/gpt-oss-20b:free` rather than a moving alias,
or your classification changes under you and the first you hear of it is a
failing test. Free model IDs do get retired, so if a run suddenly reports an
unknown model, set `+llm_model` to the current one rather than editing the
file you copied.

One more, said plainly: this classifier has been tested for its batching and
its parsing, not for the quality of its answers. Nobody has checked how well
this particular model labels your titles. Read a sample of the output before
you build anything on top of it.
