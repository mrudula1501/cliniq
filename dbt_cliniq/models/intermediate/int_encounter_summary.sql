-- int_encounter_summary: one row per patient summarizing their encounter history
-- Used to enforce the "qualifying encounter" requirement in gap logic.

with encounters as (
    select * from {{ ref('stg_encounters') }}
),

patients as (
    select patient_id from {{ ref('stg_patients') }}
),

summary as (
    select
        e.patient_id,
        count(*)                                                    as total_encounters,
        min(e.encounter_date)                                       as first_encounter_date,
        max(e.encounter_date)                                       as last_encounter_date,
        datediff('day', max(e.encounter_date), current_date)        as days_since_last_encounter,
        countif(e.encounter_class = 'outpatient')                   as outpatient_count,
        countif(e.encounter_class = 'inpatient')                    as inpatient_count,
        countif(e.encounter_class = 'emergency')                    as ed_count,
        countif(e.encounter_date >= dateadd('year', -1, current_date)) as encounters_last_12m,
        -- Qualifying encounter = at least one visit in the last 12 months
        case
            when countif(e.encounter_date >= dateadd('year', -1, current_date)) >= 1
            then true else false
        end                                                         as has_qualifying_encounter,
        sum(e.total_claim_cost)                                     as total_cost
    from encounters e
    inner join patients p on e.patient_id = p.patient_id
    group by e.patient_id
)

select * from summary
