-- Staging does one job: read the raw files and clean them. No business logic.
--
-- `read_files` reads every file in the landing volume, so a new day's file is
-- picked up without you changing anything here. `_metadata.file_path` tells you
-- which file a row came from, which is the first thing you want when one day
-- looks wrong.
--
-- TODO: rename this model and its columns to your own domain, and set
-- landing_path in dbt_project.yml to your team's volume.
with source as (

    select
        *,
        _metadata.file_path as source_file,
        _metadata.file_modification_time as ingested_at
    from read_files(
        '{{ var("landing_path") }}',
        format => 'json'
    )

),

renamed as (

    select
        -- TODO: replace these with your source's fields. Keep the pattern:
        -- rename to your own names here, so nothing downstream depends on
        -- what the API happened to call things.
        slug                        as posting_id,
        trim(title)                 as title,
        trim(company_name)          as company_name,
        nullif(trim(location), '')  as location,
        remote                      as is_remote,
        tags                        as tags,
        created_at                  as posted_at,
        source_file,
        ingested_at
    from source

)

select * from renamed
