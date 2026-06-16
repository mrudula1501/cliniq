-- stg_observations: normalize lab results and clinical observations (LOINC coded)
-- Used for lab-target gap detection (HbA1c, BP, etc.)

with source as (
    select * from {{ source('synthea_raw', 'observations') }}
),

cleaned as (
    select
        patient                         as patient_id,
        encounter                       as encounter_id,
        cast(date as date)              as observation_date,
        upper(trim(code))               as loinc_code,
        lower(trim(description))        as observation_name,
        value                           as observation_value_raw,
        -- Cast numeric value for lab comparisons
        try_to_number(value, 10, 4)     as observation_value_numeric,
        lower(trim(units))              as units,
        lower(trim(type))               as observation_type    -- numeric, text, etc.
    from source
    where patient is not null
      and code    is not null
)

select * from cleaned
