-- mart_gap_registry: one row per HF patient flagging whether they have a care gap
-- A "gap" = HF diagnosis confirmed + NO active GDMT in the last 12 months
-- This is the core output table — what drives outreach and clinical intervention.

with cohort as (
    select * from {{ ref('mart_patient_cohort') }}
    where has_qualifying_encounter = true   -- only patients with a recent visit
),

-- Patients on beta-blockers (any of: carvedilol, metoprolol succinate, bisoprolol)
on_beta_blocker as (
    select distinct patient_id
    from {{ ref('int_active_medications') }}
    where rxnorm_code in ('866511', '854901', '200031')
      and within_12_months = true
),

-- Patients on ACE inhibitor or ARB (lisinopril, enalapril, losartan, valsartan)
on_ace_arb as (
    select distinct patient_id
    from {{ ref('int_active_medications') }}
    where rxnorm_code in ('29046', '214354', '18867', '49276')
      and within_12_months = true
),

gap_registry as (
    select
        c.patient_id,
        c.birth_date,
        c.age,
        c.gender,
        c.race,
        c.ethnicity,
        c.state,
        c.zip,
        c.encounters_last_12m,
        c.last_encounter_date,
        c.total_cost,
        -- GDMT flags
        case when bb.patient_id is not null  then true else false end   as on_beta_blocker,
        case when aa.patient_id is not null  then true else false end   as on_ace_arb,
        case when bb.patient_id is not null
              and aa.patient_id is not null  then true else false end   as on_full_gdmt,
        -- Gap flags
        case when bb.patient_id is null      then true else false end   as missing_beta_blocker,
        case when aa.patient_id is null      then true else false end   as missing_ace_arb,
        case when bb.patient_id is null
              or aa.patient_id is null       then true else false end   as has_care_gap,
        -- Gap reason (human-readable for dashboard)
        case
            when bb.patient_id is null and aa.patient_id is null
                then 'Missing both beta-blocker and ACE/ARB'
            when bb.patient_id is null
                then 'Missing beta-blocker'
            when aa.patient_id is null
                then 'Missing ACE inhibitor or ARB'
            else 'On complete GDMT'
        end                                                             as gap_reason,
        current_timestamp                                               as gap_identified_at
    from cohort c
    left join on_beta_blocker bb on c.patient_id = bb.patient_id
    left join on_ace_arb      aa on c.patient_id = aa.patient_id
)

select * from gap_registry
