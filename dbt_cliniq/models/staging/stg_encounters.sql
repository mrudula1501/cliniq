-- stg_encounters: normalize clinical encounter records from Synthea

with source as (
    select * from {{ source('synthea_raw', 'encounters') }}
),

cleaned as (
    select
        id                          as encounter_id,
        patient                     as patient_id,
        cast(start as timestamp)    as encounter_start_ts,
        cast(stop  as timestamp)    as encounter_end_ts,
        cast(start as date)         as encounter_date,
        lower(trim(encounterclass)) as encounter_class,   -- inpatient, outpatient, emergency, etc.
        lower(trim(description))    as encounter_description,
        upper(trim(reasoncode))     as reason_icd10_code,
        lower(trim(reasondescription)) as reason_description,
        payer,
        base_encounter_cost,
        total_claim_cost,
        payer_coverage
    from source
    where id      is not null
      and patient is not null
)

select * from cleaned
