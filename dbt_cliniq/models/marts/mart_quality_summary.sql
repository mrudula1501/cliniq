-- mart_quality_summary: aggregate KPIs for the Power BI dashboard
-- One row per run — tracks gap rate over time as the pipeline refreshes.

select
    count(*)                                                        as total_patients_in_cohort,
    countif(has_care_gap = false)                                   as patients_on_full_gdmt,
    countif(has_care_gap = true)                                    as patients_with_gap,
    countif(missing_beta_blocker = true)                            as missing_beta_blocker_count,
    countif(missing_ace_arb = true)                                 as missing_ace_arb_count,
    countif(on_beta_blocker = true)                                 as on_beta_blocker_count,
    countif(on_ace_arb = true)                                      as on_ace_arb_count,

    -- Rates
    round(countif(has_care_gap)     / nullif(count(*), 0) * 100, 1) as gap_rate_pct,
    round(countif(on_full_gdmt)     / nullif(count(*), 0) * 100, 1) as gdmt_adherence_pct,
    round(countif(on_beta_blocker)  / nullif(count(*), 0) * 100, 1) as beta_blocker_rate_pct,
    round(countif(on_ace_arb)       / nullif(count(*), 0) * 100, 1) as ace_arb_rate_pct,

    -- Demographics breakdown
    countif(gender = 'M')                                           as male_patients,
    countif(gender = 'F')                                           as female_patients,
    avg(age)                                                        as avg_patient_age,

    current_date                                                    as as_of_date,
    current_timestamp                                               as summary_generated_at
from {{ ref('mart_gap_registry') }}
