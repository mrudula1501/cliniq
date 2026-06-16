-- ClinIQ reusable gap detection macro
-- Generates the core gap detection SQL for any disease config loaded from YAML.
-- Usage in a mart model: {{ gap_detection(icd10_codes, rxnorm_codes, lookback_days) }}

{% macro gap_detection(icd10_codes, rxnorm_codes, lookback_days=365) %}

with qualifying_patients as (
    select distinct patient_id
    from {{ ref('stg_conditions') }}
    where icd10_code in (
        {{ "'" + "','".join(icd10_codes) + "'" }}
    )
    and is_active = true
),

active_interventions as (
    select distinct patient_id
    from {{ ref('int_active_medications') }}
    where rxnorm_code in (
        {{ "'" + "','".join(rxnorm_codes) + "'" }}
    )
    and days_since_start <= {{ lookback_days }}
),

gap_result as (
    select
        q.patient_id,
        case when i.patient_id is not null then true  else false end as is_treated,
        case when i.patient_id is null     then true  else false end as has_gap,
        current_timestamp                                            as identified_at
    from qualifying_patients q
    left join active_interventions i on q.patient_id = i.patient_id
)

select * from gap_result

{% endmacro %}
