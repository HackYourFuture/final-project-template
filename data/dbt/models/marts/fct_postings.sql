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
with
    postings as (select * from {{ ref("stg_postings") }}),

    tag_counts as (

        -- int_posting_tags has one row per posting and tag, so counting it
        -- gives tags per posting. Doing it here rather than `size(tags)` means
        -- this counts the same cleaned, de-duplicated tags that
        -- fct_tag_popularity counts, instead of raw array length.
        select posting_id, count(*) as tag_count
        from {{ ref("int_posting_tags") }}
        group by posting_id

    )

select
    postings.posting_id,
    postings.title,
    postings.company_name,
    postings.location,
    postings.is_remote,
    postings.tags,
    -- A posting with no tags has no rows in int_posting_tags, so the join
    -- finds nothing and the count has to be put back as zero. Without the
    -- coalesce it would be null, and "null tags" and "no tags" are different
    -- claims to make to the backend.
    coalesce(tag_counts.tag_count, 0) as tag_count,
    postings.posted_at,
    date(postings.posted_at) as posted_date,
    postings.ingested_at
from postings
left join tag_counts on postings.posting_id = tag_counts.posting_id
