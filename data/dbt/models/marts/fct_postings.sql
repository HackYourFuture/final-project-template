-- This mart is the contract with the backend team.
--
-- Its columns are what backend/ reads to build API endpoints, so treat a
-- change here the way you would treat changing a public API: agree it with
-- the backend trainees first, then change it in both places.
with postings as (

    select * from {{ ref('stg_postings') }}

)

select
    posting_id,
    title,
    company_name,
    location,
    is_remote,
    tags,
    posted_at,
    ingested_at,
    date(posted_at) as posted_date
from postings
