-- Test: logical consistency of gap flags
-- has_care_gap must be TRUE when EITHER missing_beta_blocker OR missing_ace_arb is TRUE
-- Returns rows only if the logic is violated

select
    patient_id,
    has_care_gap,
    missing_beta_blocker,
    missing_ace_arb,
    gap_reason
from {{ ref('mart_gap_registry') }}
where
    -- Violation: gap flagged true but neither drug is missing
    (has_care_gap = true  and missing_beta_blocker = false and missing_ace_arb = false)
    or
    -- Violation: gap flagged false but at least one drug is missing
    (has_care_gap = false and (missing_beta_blocker = true or missing_ace_arb = true))
