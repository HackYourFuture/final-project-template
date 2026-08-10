"""Operations dashboard for the pipeline.

This is for your team, not for end users. The product UI is the frontend
trainee's job. This page answers one question: is the pipeline healthy?

streamlit and pandas are not installed by default. Install the extra first:

    uv sync --extra dashboard
    uv run streamlit run optional/streamlit/app.py
"""

import os

import pandas as pd
import psycopg
import streamlit as st

st.set_page_config(page_title="Pipeline health", page_icon="📊")
st.title("Pipeline health")

DSN = (
    f"host={os.environ['POSTGRES_HOST']} port={os.getenv('POSTGRES_PORT', '5432')} "
    f"dbname={os.environ['POSTGRES_DB']} user={os.environ['POSTGRES_USER']} "
    f"password={os.environ['POSTGRES_PASSWORD']}"
)
SCHEMA = os.getenv("DBT_SCHEMA", "analytics")


@st.cache_data(ttl=60)
def load_freshness() -> pd.DataFrame:
    query = f"""
        select
            max(ingested_at) as last_ingested,
            count(*)         as row_count,
            count(distinct posted_date) as days_covered
        from {SCHEMA}.fct_postings
    """
    with psycopg.connect(DSN) as conn:
        return pd.read_sql(query, conn)


stats = load_freshness()
col1, col2, col3 = st.columns(3)
col1.metric("Rows", int(stats["row_count"][0]))
col2.metric("Days covered", int(stats["days_covered"][0]))
col3.metric("Last ingest", str(stats["last_ingested"][0]))

st.caption("Add a chart per metric your team cares about. Keep it to what you would check at 9am.")
