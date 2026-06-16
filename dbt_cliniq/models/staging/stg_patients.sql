-- stg_patients: clean and normalize Synthea patient demographics
-- Deduplicates on patient_id, keeping the most recently updated record.

with source as (
    select * from {{ source('synthea_raw', 'patients') }}
),

cleaned as (
    select
        id                                              as patient_id,
        cast(birthdate as date)                         as birth_date,
        datediff('year', cast(birthdate as date), current_date) as age,
        upper(trim(gender))                             as gender,
        upper(trim(race))                               as race,
        upper(trim(ethnicity))                          as ethnicity,
        city,
        state,
        zip,
        -- flag duplicates; only row_num = 1 passes through
        row_number() over (
            partition by id
            order by birthdate desc nulls last
        )                                               as row_num
    from source
    where id is not null
)

select
    patient_id,
    birth_date,
    age,
    gender,
    race,
    ethnicity,
    city,
    state,
    zip
from cleaned
where row_num = 1
