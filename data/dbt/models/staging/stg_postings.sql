-- Staging does one job: read the raw files and clean them. No business logic.
--
-- `read_files` reads every file in the landing volume, so a new day's file is
-- picked up without you changing anything here. `_metadata.file_path` tells you
-- which file a row came from, which is the first thing you want when one day
-- looks wrong.
--
-- Change: rename this model and its columns to your own domain. The folder it
-- reads comes from LANDING_PATH in your .env, not from anything in here.
--
-- This model is a table, not a view, and that is a deliberate choice. A view
-- would re-read every file in the landing folder for each model and each test
-- that selects from it, which is more than a dozen full reads per `dbt build`.
-- As a table the files are read once and everything downstream reads the
-- result. See dbt_project.yml.
with
    source as (

        -- `schemaHints` names the type of every field this model uses. Without
        -- it, JSON types are guessed from the files, and the guess can change:
        -- the day your source sends "1" instead of 1, a column that was a
        -- number becomes a string and something downstream breaks for a reason
        -- that has nothing to do with the model that broke. Naming the types
        -- means the guess cannot drift.
        --
        -- Change: list your own fields here, using the names the source sends,
        -- not the names you rename them to below.
        select
            *,
            _metadata.file_path as source_file,
            _metadata.file_modification_time as ingested_at
        from
            read_files(
                '{{ var("landing_path") }}',
                format => 'json',
                schemahints
                => 'slug string, title string, company_name string, location string, remote boolean, tags array<string>, created_at bigint'
            )

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
