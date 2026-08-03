# Databricks module

Use this only if your team has a reason to move transformations off Postgres,
for example a dataset too large to model comfortably in it.

## Switching dbt to Databricks

Add a second output to `../../dbt/profiles.yml`:

```yaml
    databricks:
      type: databricks
      catalog: "{{ env_var('DATABRICKS_CATALOG') }}"
      schema: "{{ env_var('DBT_SCHEMA') }}"
      host: "{{ env_var('DATABRICKS_HOST') }}"
      http_path: "{{ env_var('DATABRICKS_HTTP_PATH') }}"
      token: "{{ env_var('DATABRICKS_TOKEN') }}"
      threads: 4
```

Then run `dbt build --target databricks`. Your models stay the same, which is
the point of keeping business logic in dbt rather than in notebooks.

Install the adapter with `uv pip install dbt-databricks`.
