-- Test: no patient_id should appear more than once in stg_patients
-- Returns rows only if duplicates exist (dbt test fails on any rows returned)

select
    patient_id,
    count(*) as occurrence_count
from {{ ref('stg_patients') }}
group by patient_id
having count(*) > 1
