-- mart_patient_cohort: all patients diagnosed with heart failure + qualifying encounter
-- This is the denominator for the HF GDMT quality measure.
-- Switch the ICD-10 code list to change disease area.

with hf_patients as (
    select distinct patient_id
    from {{ ref('int_patient_conditions') }}
    where icd10_code in (
        'I500',   -- Congestive heart failure
        'I501',   -- Left ventricular failure
        'I509',   -- Heart failure, unspecified
        'I5020',  -- Unspecified systolic (congestive) heart failure
        'I5030'   -- Unspecified diastolic (congestive) heart failure
    )
    and is_active = true
),

patients as (
    select * from {{ ref('stg_patients') }}
),

encounter_summary as (
    select * from {{ ref('int_encounter_summary') }}
)

select
    p.patient_id,
    p.birth_date,
    p.age,
    p.gender,
    p.race,
    p.ethnicity,
    p.city,
    p.state,
    p.zip,
    e.total_encounters,
    e.last_encounter_date,
    e.encounters_last_12m,
    e.has_qualifying_encounter,
    e.total_cost,
    true                    as has_hf_diagnosis,
    current_timestamp       as cohort_generated_at
from hf_patients hf
inner join patients p             on hf.patient_id = p.patient_id
left join  encounter_summary e    on hf.patient_id = e.patient_id
