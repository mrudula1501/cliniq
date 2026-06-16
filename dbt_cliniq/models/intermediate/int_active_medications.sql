-- int_active_medications: active medications per patient with recency window flags
-- Used by mart models to check GDMT adherence, statin coverage, etc.

with medications as (
    select * from {{ ref('stg_medications') }}
),

patients as (
    select patient_id from {{ ref('stg_patients') }}
),

enriched as (
    select
        m.patient_id,
        m.encounter_id,
        m.rxnorm_code,
        m.medication_name,
        m.med_start_date,
        m.med_end_date,
        m.is_active,
        m.days_since_start,
        -- Convenience flags for common lookback windows
        case when m.days_since_start <= 365  then true else false end as within_12_months,
        case when m.days_since_start <= 180  then true else false end as within_6_months,
        case when m.days_since_start <= 90   then true else false end as within_90_days,
        -- Rank medications per patient by recency
        row_number() over (
            partition by m.patient_id, m.rxnorm_code
            order by m.med_start_date desc
        )                                                              as med_recency_rank
    from medications m
    inner join patients p on m.patient_id = p.patient_id
)

select * from enriched
