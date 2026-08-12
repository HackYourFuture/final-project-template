-- This mart is the contract with the backend team.
--
-- Its columns are what backend/ reads to build API endpoints, so treat a change
-- here the way you would treat changing a public API: agree it with the backend
-- trainees first, then change it in both places.
--
-- Airflow copies this table into the backend's database after dbt succeeds, so
-- whatever you select here is what they get.
--
-- Change: rename to your domain and decide the grain. Write one sentence in
-- _fct_postings.yml saying what one row means. If you cannot write that
-- sentence, the mart is not ready.
with postings as (select * from {{ ref("stg_postings") }})

select
    posting_id,
    title,
    company_name,
    location,
    is_remote,
    tags,
    posted_at,
    date(posted_at) as posted_date,
    ingested_at
from postings
