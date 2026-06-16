"""
ClinIQ Gap Engine — YAML Config → SQL Generator
================================================
Reads a disease config YAML and generates parameterized gap-detection SQL.
This is ClinIQ's core innovation: same codebase, any disease.

Usage:
  python generate_gap_sql.py --config ../config/heart_failure.yaml
  python generate_gap_sql.py --config ../config/diabetes.yaml --output output/diabetes_gaps.sql
"""
import yaml
import argparse
from pathlib import Path
from datetime import datetime


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def generate_diagnosis_filter(codes: list, table_alias: str = "c") -> str:
    """Build the WHERE clause fragment for ICD-10 code matching.
    Strips dots so I50.9 → I509 matches our staging layer normalization.
    """
    normalized = [code.replace(".", "") for code in codes]
    quoted = ", ".join(f"'{c}'" for c in normalized)
    return f"{table_alias}.icd10_code in ({quoted})"


def generate_medication_codes(interventions: dict) -> list:
    """Collect all RxNorm codes across all medication groups in the config."""
    all_codes = []
    for group_name, group in interventions.get("medications", {}).items():
        all_codes.extend(group.get("rxnorm_codes", []))
    return all_codes


def generate_medication_filter(interventions: dict, table_alias: str = "m") -> str:
    codes = generate_medication_codes(interventions)
    if not codes:
        return "1=0  -- no medication codes defined"
    quoted = ", ".join(f"'{c}'" for c in codes)
    return f"{table_alias}.rxnorm_code in ({quoted})"


def generate_lab_filter(interventions: dict) -> str | None:
    """Generate a lab-value gap condition if lab_targets are defined (e.g., HbA1c, BP)."""
    lab_targets = interventions.get("lab_targets", {})
    if not lab_targets:
        return None

    clauses = []
    for key, lab in lab_targets.items():
        loinc = lab["loinc_code"]
        threshold = lab["threshold"]
        direction = lab["direction"]
        op = ">=" if direction == "less_than" else "<="
        clauses.append(
            f"(obs.loinc_code = '{loinc}' AND obs.observation_value_numeric {op} {threshold})"
        )
    return " OR ".join(clauses)


def generate_gap_sql(config: dict) -> str:
    condition_name = config["condition"]["name"]
    display_name = config["condition"]["display_name"]
    description = config["condition"]["description"]
    diag_codes = config["diagnosis_codes"]["icd10"]
    interventions = config["target_interventions"]
    lookback_days = config["gap_definition"]["lookback_days"]
    logic_desc = config["gap_definition"]["logic"]
    measure_name = config["quality_measure"]["name"]
    hedis_ref = config["quality_measure"].get("hedis_reference", "N/A")
    numerator = config["quality_measure"]["numerator"]
    denominator = config["quality_measure"]["denominator"]

    diag_filter = generate_diagnosis_filter(diag_codes)
    med_filter = generate_medication_filter(interventions)
    lab_filter = generate_lab_filter(interventions)
    med_codes = generate_medication_codes(interventions)

    # Build medication group documentation for the header comment
    med_groups = []
    for group_name, group in interventions.get("medications", {}).items():
        names = ", ".join(group.get("generic_names", []))
        med_groups.append(f"--     {group.get('display', group_name)}: {names}")
    med_group_doc = "\n".join(med_groups) if med_groups else "--     (none)"

    # Lab gap clause (only for conditions with lab targets like HbA1c)
    lab_gap_clause = ""
    if lab_filter:
        lab_gap_clause = f"""
-- Patients with out-of-range lab values (additional gap criterion)
lab_gaps as (
    select distinct obs.patient_id
    from stg_observations obs
    inner join qualifying_patients qp on obs.patient_id = qp.patient_id
    where ({lab_filter})
      and obs.observation_date >= dateadd('day', -{lookback_days}, current_date)
),
"""
        lab_join = "left join lab_gaps lg on q.patient_id = lg.patient_id"
        lab_gap_flag = "or lg.patient_id is not null"
        lab_gap_reason = """
        when i.patient_id is null and lg.patient_id is not null
            then 'Missing medication + out-of-range lab value'
        when lg.patient_id is not null
            then 'Out-of-range lab value'"""
    else:
        lab_join = ""
        lab_gap_flag = ""
        lab_gap_reason = ""

    sql = f"""-- =============================================================================
-- ClinIQ — Auto-Generated Gap Detection SQL
-- Condition  : {display_name}
-- Measure    : {measure_name} (HEDIS ref: {hedis_ref})
-- Description: {description}
-- Gap Logic  : {logic_desc}
-- Lookback   : {lookback_days} days
-- Target Medications:
{med_group_doc}
-- Generated  : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
-- =============================================================================

with qualifying_patients as (
    -- Step 1: Patients with the qualifying diagnosis (active)
    select distinct patient_id
    from stg_conditions c
    where {diag_filter}
      and c.is_active = true
),

active_interventions as (
    -- Step 2: Patients on target therapy within the lookback window
    select distinct m.patient_id
    from stg_medications m
    where {med_filter}
      and m.days_since_start <= {lookback_days}
),
{lab_gap_clause}
gap_registry as (
    -- Step 3: Identify gaps = qualifying diagnosis but no active intervention
    select
        q.patient_id,
        p.gender,
        p.race,
        p.age,
        p.state,
        p.zip,
        case when i.patient_id is not null then true  else false end as is_treated,
        case
            when i.patient_id is null {lab_gap_flag}  then true
            else false
        end                                                          as has_gap,
        '{condition_name}'                                           as condition,
        '{measure_name}'                                             as quality_measure,
        case{lab_gap_reason}
            when i.patient_id is null  then 'Not on guideline-directed therapy'
            else 'Receiving appropriate therapy'
        end                                                          as gap_reason,
        current_timestamp                                            as identified_at
    from qualifying_patients q
    left join active_interventions i on q.patient_id = i.patient_id
    {lab_join}
    left join stg_patients p          on q.patient_id = p.patient_id
)

select * from gap_registry
order by has_gap desc, patient_id;

-- =============================================================================
-- Quality Measure Summary (append to get aggregate KPIs)
-- Numerator : {numerator}
-- Denominator: {denominator}
-- =============================================================================
/*
select
    condition,
    quality_measure,
    count(*)                                               as denominator,
    countif(is_treated)                                   as numerator,
    countif(has_gap)                                      as gap_count,
    round(countif(has_gap) / count(*) * 100, 1)          as gap_rate_pct,
    round(countif(is_treated) / count(*) * 100, 1)       as adherence_pct,
    current_date                                          as as_of_date
from gap_registry
group by condition, quality_measure;
*/
"""
    return sql


def main():
    parser = argparse.ArgumentParser(
        description="ClinIQ: Generate gap-detection SQL from a disease YAML config."
    )
    parser.add_argument(
        "--config", required=True,
        help="Path to disease YAML config (e.g., ../config/heart_failure.yaml)"
    )
    parser.add_argument(
        "--output",
        help="Output SQL file path. If omitted, prints to stdout."
    )
    args = parser.parse_args()

    config = load_config(args.config)
    sql = generate_gap_sql(config)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(sql)
        print(f"✓ Gap SQL written to: {output_path}")
        print(f"  Condition : {config['condition']['display_name']}")
        print(f"  Measure   : {config['quality_measure']['name']}")
        print(f"  Lookback  : {config['gap_definition']['lookback_days']} days")
    else:
        print(sql)


if __name__ == "__main__":
    main()
