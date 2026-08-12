-- Staging does one job: read the raw files and clean them. No business logic.
--
-- `read_files` reads every file in the landing volume, so a new day's file is
-- picked up without you changing anything here. `_metadata.file_path` tells you
-- which file a row came from, which is the first thing you want when one day
-- looks wrong.
--
-- Change: rename this model and its columns to your own domain, and set
-- landing_path in dbt_project.yml to your team's volume.
with
    source as (

        select
            *,
            _metadata.file_path as source_file,
            _metadata.file_modification_time as ingested_at
        from read_files('{{ var("landing_path") }}', format => 'json')

    ),

    renamed as (

        select
            -- Change: replace these with your source's fields. Keep the pattern:
            -- rename to your own names here, so nothing downstream depends on
            -- what the API happened to call things.
            slug as posting_id,
            trim(title) as title,
            trim(company_name) as company_name,
            nullif(trim(location), '') as location,
            remote as is_remote,
            tags as tags,
            -- The raw file holds exactly what the source sent, and Arbeitnow
            -- sends Unix seconds. Converting here rather than during ingestion is
            -- deliberate: the landed file stays a faithful copy, and the moment a
            -- source changes its date format you can see it in this one line
            -- instead of re-reading three weeks of files. If your source sends an
            -- ISO string, cast it instead.
            timestamp_seconds(created_at) as posted_at,
            source_file,
            ingested_at
        from source

    ),

    deduplicated as (

        -- One row per posting, keeping the most recently ingested version.
        --
        -- This is not optional tidying. `read_files` reads every file in the
        -- landing folder, and most sources still list the same record tomorrow, so
        -- on day two a posting that is still open appears twice. The `unique` test
        -- on posting_id then fails, the DAG goes red, and nothing is actually
        -- wrong with the data.
        --
        -- Keeping the newest version also means a posting that changed (a title
        -- edit, a closing date) reflects what the source says today rather than
        -- what it said the first time you saw it.
        select *
        from renamed
        qualify
            row_number() over (partition by posting_id order by ingested_at desc) = 1

    )

select *
from deduplicated
