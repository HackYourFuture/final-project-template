# Optional modules

Nothing in this folder is required. Week 15 asks for a working pipeline, not for
every tool you have seen. Add a module only when your team has the required
pipeline running and wants to go further.

| Folder | Adds | Data Track week |
|---|---|---|
| `streamlit/` | An operations dashboard showing pipeline health | 11 |
| `dbt_results/` | Records every dbt run in `<catalog>.ops.dbt_test_runs` | 10 |

## dbt_results

dbt writes an account of every model and test to `target/run_results.json`,
which then sits on the machine that ran it. Landing it in the warehouse turns
"are the tests passing?" into a question anyone can answer with SQL.

Copy `dbt_results.py` into `src/`, then add three lines to the `dbt_build` task
in the DAG, after dbt has run and before the exit code is checked:

```python
from src.dbt_results import parse_run_results, publish_results

results = parse_run_results(f"{DBT_PROJECT_DIR}/target/run_results.json")
publish_results(Warehouse.from_env(), results)
```

Publish before deciding the task's fate, so a failing test is recorded rather
than lost. Nothing in it raises: dbt's exit code already decides whether the
pipeline failed.
