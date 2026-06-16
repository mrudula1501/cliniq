-- int_patient_conditions: one row per patient per active condition
-- Adds encounter context and recency flags for cohort building.

with conditions as (
    select * from {{ ref('stg_conditions') }}
),

patients as (
    select patient_id from {{ ref('stg_patients') }}
),

enriched as (
    select
        c.patient_id,
        c.encounter_id,
        c.icd10_code,
        c.icd10_code_raw,
        c.condition_description,
        c.condition_start_date,
        c.condition_end_date,
        c.is_active,
        -- How many days since the condition was first diagnosed?
        datediff('day', c.condition_start_date, current_date) as days_since_diagnosis,
        -- How many distinct conditions does this patient have?
        count(*) over (partition by c.patient_id)             as total_conditions_count,
        -- Rank conditions by recency (most recent = 1)
        row_number() over (
            partition by c.patient_id, c.icd10_code
            order by c.condition_start_date desc
        )                                                      as condition_recency_rank
    from conditions c
    inner join patients p on c.patient_id = p.patient_id
)

select * from enriched
where condition_recency_rank = 1  -- deduplicate: one row per patient-condition pair
