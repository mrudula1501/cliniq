-- Test: ICD-10 codes must match expected pattern (letter + digits, 3-7 chars)
-- Catches malformed codes that would silently break gap detection logic.

select
    patient_id,
    icd10_code,
    condition_description
from {{ ref('stg_conditions') }}
where icd10_code is not null
  and not regexp_like(icd10_code, '^[A-Z][0-9]{2}[0-9A-Z]{0,4}$')
