-- One row per posting and tag. This is the layer between staging and the mart.
--
-- Why this is its own model rather than a CTE, which is the question worth
-- asking every time you add one.
--
-- It changes the grain. Staging is one row per posting; this is one row per
-- posting and tag. A model whose grain differs from its parent is almost
-- always worth naming.
--
-- And two models read it: fct_postings counts tags per posting, while
-- fct_tag_popularity counts postings per tag. Written as a CTE that logic
-- would exist twice, and the two copies would disagree the first time someone
-- fixed one of them.
--
-- If you only ever had one consumer, a CTE inside that model would be the
-- better answer. An intermediate model with a single reader is just a longer
-- way to write a CTE.
--
-- Change: if your source has no array column, this is the model to replace.
-- Anything that fans one row out into many (line items on an order, skills on
-- a profile, categories on an article) belongs here.
with
    postings as (select * from {{ ref("stg_postings") }}),

    exploded as (

        -- `explode` drops postings whose tag array is empty or null, which is
        -- correct: a posting with no tags has no rows at this grain. It also
        -- means fct_postings has to put the zero back with a coalesce, rather
        -- than losing the posting from the mart entirely.
        select posting_id, posted_at, tag
        from postings
        lateral view explode(tags) as tag

    ),

    cleaned as (

        select
            posting_id,
            -- Tags arrive as the source typed them, so "Python", "python" and
            -- " python" are three tags until you say otherwise. Normalising
            -- here means every consumer gets the same answer.
            lower(trim(tag)) as tag,
            posted_at
        from exploded
        where trim(tag) <> ''

    ),

    deduplicated as (

        -- A source that lists the same tag twice on one posting would otherwise
        -- double that posting's tag_count and its weight in the popularity
        -- mart.
        select *
        from cleaned
        qualify row_number() over (partition by posting_id, tag order by posted_at) = 1

    )

select *
from deduplicated
