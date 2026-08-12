-- One row per tag: how often it appears and when it was last seen.
--
-- The second reader of int_posting_tags, and the reason that model exists.
-- fct_postings asks "how many tags does this posting have?"; this asks "how
-- many postings does this tag have?". Same rows, counted along the other axis.
--
-- Not part of the backend contract. Airflow publishes fct_postings only, so
-- this mart is yours: query it in the warehouse, chart it, or add it to the
-- publish step if the product ends up needing it.
--
-- Change: delete it if your source has no tags, or point it at whatever your
-- fan-out model produces.
with tags as (select * from {{ ref("int_posting_tags") }})

select
    tag,
    count(*) as postings,
    -- Both dates, because "500 postings" means something different when the
    -- last one was yesterday than when the last one was in March.
    min(posted_at) as first_seen_at,
    max(posted_at) as last_seen_at
from tags
group by tag
