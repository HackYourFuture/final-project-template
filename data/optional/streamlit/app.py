"""Operations dashboard for the pipeline.

This is for your team, not for end users. The product UI is the frontend
trainee's job. This page answers one question: is the pipeline healthy?

streamlit and pandas are not installed by default. Install the extra first:

    uv sync --extra dashboard
    uv run streamlit run optional/streamlit/app.py

It reads the same `.env` as everything else: point BACKEND_PG_* at the
database you want to look at.
"""

import os

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

# The same .env the pipeline reads, so the dashboard needs no settings of its
# own. In Azure there is no file and the values come from the container's
# environment instead.
load_dotenv()

st.set_page_config(page_title="Pipeline health", page_icon="📊")
st.title("Pipeline health")

# The same BACKEND_PG_* names the sync uses. One database, one set of
# settings: a dashboard with its own names is a dashboard that quietly points
# at the wrong server.
DSN = (
    f"host={os.environ['BACKEND_PG_HOST']} "
    f"port={os.getenv('BACKEND_PG_PORT', '5432')} "
    f"dbname={os.environ['BACKEND_PG_DB']} user={os.environ['BACKEND_PG_USER']} "
    f"password={os.environ['BACKEND_PG_PASSWORD']}"
)
# Where the pipeline publishes, which is not the schema dbt builds into.
SCHEMA = os.getenv("BACKEND_PG_PUBLISH_SCHEMA", "analytics")


@st.cache_data(ttl=60)
def load_freshness() -> pd.DataFrame:
    query = f"""
        select
            max(ingested_at) as last_ingested,
            count(*)         as row_count,
            count(distinct posted_date) as days_covered
        from {SCHEMA}.fct_postings
    """
    # Read with a cursor rather than pd.read_sql. pandas only recognises
    # SQLAlchemy and sqlite connections, so handing it a psycopg one works but
    # prints a warning telling you to install SQLAlchemy, which you do not need
    # for three numbers.
    with psycopg.connect(DSN) as conn, conn.cursor() as cursor:
        cursor.execute(query)
        columns = [column.name for column in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=columns)


stats = load_freshness()
col1, col2, col3 = st.columns(3)
col1.metric("Rows", int(stats["row_count"][0]))
col2.metric("Days covered", int(stats["days_covered"][0]))
col3.metric("Last ingest", str(stats["last_ingested"][0]))

st.caption("Add a chart per metric your team cares about. Keep it to what you would check at 9am.")
