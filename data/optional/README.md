# Optional modules

Nothing in this folder is required. Week 15 asks for a working pipeline, not for
every tool you have seen. Add a module only when your team has the required
pipeline running and wants to go further.

| Folder | Adds | Data Track week |
|---|---|---|
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
