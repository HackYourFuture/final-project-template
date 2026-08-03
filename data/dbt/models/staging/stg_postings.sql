-- Staging does one job: clean and rename. No business logic lives here.
with source as (

    select * from {{ source('raw', 'postings') }}

),

renamed as (

    select
        slug                                as posting_id,
        trim(title)                         as title,
        trim(company_name)                  as company_name,
        nullif(trim(location), '')          as location,
        remote                              as is_remote,
        tags                                as tags,
        created_at                          as posted_at,
        ingested_at                         as ingested_at
    from source

)

select * from renamed
