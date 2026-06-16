-- stg_medications: normalize medication records (RxNorm coded) from Synthea

with source as (
    select * from {{ source('synthea_raw', 'medications') }}
),

cleaned as (
    select
        patient                                                 as patient_id,
        encounter                                               as encounter_id,
        cast(start as date)                                     as med_start_date,
        cast(stop  as date)                                     as med_end_date,
        upper(trim(code))                                       as rxnorm_code,
        lower(trim(description))                                as medication_name,
        case
            when stop is null                                   then true
            when cast(stop as date) > current_date              then true
            else false
        end                                                     as is_active,
        datediff('day', cast(start as date), current_date)      as days_since_start
    from source
    where patient is not null
      and code    is not null
)

select * from cleaned
