-- stg_conditions: normalize ICD-10 diagnosis records from Synthea
-- Removes dots from ICD-10 codes so matching is consistent (I50.9 → I509).
-- Preserves both raw and normalized forms for flexibility.

with source as (
    select * from {{ source('synthea_raw', 'conditions') }}
),

cleaned as (
    select
        patient                                         as patient_id,
        encounter                                       as encounter_id,
        cast(start as date)                             as condition_start_date,
        cast(stop  as date)                             as condition_end_date,
        upper(trim(code))                               as icd10_code_raw,
        -- Normalized: strip dots for SQL IN-list matching
        upper(replace(trim(code), '.', ''))             as icd10_code,
        description                                     as condition_description,
        case
            when stop is null                           then true
            when cast(stop as date) > current_date      then true
            else false
        end                                             as is_active
    from source
    where patient  is not null
      and code     is not null
)

select * from cleaned
