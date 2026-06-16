# ClinIQ — Clinical Intelligence & Quality Gap Analytics Platform

> A modular, disease-agnostic framework for identifying patients who qualify for evidence-based care interventions but aren't receiving them — across any clinical population.

---

## What this project does

Most clinical quality work is disease-specific. Someone builds a diabetes dashboard. Someone else builds a cardiac one. Each is hardcoded to one condition, one set of codes, one set of rules.

ClinIQ takes a different approach: **one architecture, any disease.**

You change a YAML config file — the condition, the ICD-10 codes, the target medications, the quality measure — and the same pipeline runs for heart failure, diabetes, hypertension, oncology screening, or anything else. The data layer, the gap detection logic, the AI abstraction agent, and the dashboard are all reusable.

The first demo use case is **heart failure GDMT gap detection**: finding patients diagnosed with heart failure who qualify for guideline-directed medical therapy (beta-blockers, ACE inhibitors/ARBs) but are not currently receiving it. This mirrors a real and unsolved problem across health systems — patients fall through the cracks not because the care doesn't exist, but because no one can identify them at scale.

---

## Architecture overview

```
Synthea (synthetic EHR data)
        │
        ▼
  Raw CSV ingestion
        │
        ▼
  dbt + Snowflake
  ├── staging models      (clean, normalize, deduplicate)
  ├── intermediate models  (encounter, medication, diagnosis joins)
  └── mart models         (patient_cohort, gap_registry, quality_summary)
        │
        ▼
  YAML-driven gap detection engine (SQL, parameterized by config)
        │
        ├──► Power BI dashboard  (care-gap registry, cohort view, gap rate trends)
        │
        └──► LangGraph AI agent  (reads clinical notes → abstracts quality measure → writes audit log)
```

---

## Repository structure

```
cliniq/
├── README.md
├── config/
│   ├── heart_failure.yaml          # Demo use case 1
│   ├── diabetes.yaml               # Demo use case 2
│   └── hypertension.yaml           # Demo use case 3
├── data/
│   └── synthea/                    # Generated synthetic patient data (gitignored if large)
├── ingestion/
│   └── load_to_snowflake.py        # Script to load Synthea CSVs into Snowflake raw schema
├── dbt_cliniq/
│   ├── dbt_project.yml
│   ├── profiles.yml.example
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_patients.sql
│   │   │   ├── stg_conditions.sql
│   │   │   ├── stg_medications.sql
│   │   │   ├── stg_encounters.sql
│   │   │   └── stg_observations.sql
│   │   ├── intermediate/
│   │   │   ├── int_patient_conditions.sql
│   │   │   ├── int_active_medications.sql
│   │   │   └── int_encounter_summary.sql
│   │   └── marts/
│   │       ├── mart_patient_cohort.sql
│   │       ├── mart_gap_registry.sql
│   │       └── mart_quality_summary.sql
│   ├── tests/
│   │   ├── assert_no_duplicate_patients.sql
│   │   ├── assert_valid_icd10_codes.sql
│   │   └── assert_gap_flag_logic.sql
│   └── macros/
│       └── gap_detection.sql       # Reusable macro driven by config
├── gap_engine/
│   ├── generate_gap_sql.py         # Reads YAML config → generates gap detection SQL
│   └── run_gap_analysis.py         # Executes gap SQL against Snowflake, outputs results
├── agent/
│   ├── cliniq_agent.py             # LangGraph agent: reads notes → abstracts measure
│   ├── audit_log.py                # Writes every abstraction to structured audit trail
│   └── prompts/
│       └── abstraction_prompt.txt  # System prompt for the abstraction agent
├── dashboard/
│   └── ClinIQ_PowerBI.pbix         # Power BI file (or export + instructions)
├── notebooks/
│   └── exploratory_analysis.ipynb  # EDA on synthetic cohort
├── tests/
│   └── test_gap_engine.py          # Unit tests for gap logic
├── .env.example
├── requirements.txt
└── .gitignore
```

---

## Config file design (the core innovation)

Each disease area is defined in a single YAML file. The gap engine reads this and generates all SQL automatically.

**Example: `config/heart_failure.yaml`**

```yaml
condition:
  name: heart_failure
  display_name: "Heart Failure"
  description: "Patients with HF diagnosis not receiving guideline-directed medical therapy (GDMT)"

diagnosis_codes:
  icd10:
    - I50.0   # Congestive heart failure
    - I50.1   # Left ventricular failure
    - I50.9   # Heart failure, unspecified
    - I50.20  # Unspecified systolic heart failure
    - I50.30  # Unspecified diastolic heart failure

target_interventions:
  medications:
    beta_blockers:
      display: "Beta-blocker therapy"
      rxnorm_codes: ["866511", "854901", "200031"]
      generic_names: ["carvedilol", "metoprolol succinate", "bisoprolol"]
    ace_arb:
      display: "ACE inhibitor or ARB therapy"
      rxnorm_codes: ["29046", "214354", "18867"]
      generic_names: ["lisinopril", "enalapril", "losartan", "valsartan"]

gap_definition:
  logic: "patient has qualifying diagnosis AND no active target medication in last 12 months"
  lookback_days: 365
  encounter_required: true
  min_encounters: 1

quality_measure:
  name: "HF_GDMT_GAP"
  hedis_reference: "CBP"   # Closest HEDIS analog
  numerator: "patients receiving GDMT"
  denominator: "patients with HF diagnosis + qualifying encounter"

output:
  cohort_table: "mart_patient_cohort"
  gap_table: "mart_gap_registry"
  summary_table: "mart_quality_summary"
```

**Example: `config/diabetes.yaml`**

```yaml
condition:
  name: diabetes_type2
  display_name: "Type 2 Diabetes"
  description: "Patients with T2DM not receiving statin therapy or with uncontrolled HbA1c"

diagnosis_codes:
  icd10:
    - E11.9   # Type 2 diabetes without complications
    - E11.65  # Type 2 diabetes with hyperglycemia
    - E11.0   # Type 2 diabetes with hyperosmolarity

target_interventions:
  medications:
    statins:
      display: "Statin therapy"
      rxnorm_codes: ["301542", "83367", "861634"]
      generic_names: ["atorvastatin", "rosuvastatin", "simvastatin"]
  lab_targets:
    hba1c:
      display: "HbA1c < 8%"
      loinc_code: "4548-4"
      threshold: 8.0
      direction: "less_than"

gap_definition:
  logic: "patient has T2DM diagnosis AND (no statin in last 12 months OR last HbA1c >= 8.0)"
  lookback_days: 365

quality_measure:
  name: "DM_CONTROL_GAP"
  hedis_reference: "CDC"
  numerator: "patients with controlled HbA1c + statin"
  denominator: "patients with T2DM diagnosis + qualifying encounter"
```

---

## Data layer — dbt models

### Staging models

**`stg_patients.sql`** — clean and normalize the Synthea patients table
```sql
with source as (
    select * from {{ source('synthea_raw', 'patients') }}
),
cleaned as (
    select
        id                                          as patient_id,
        upper(trim(birthdate))                      as birth_date,
        upper(trim(gender))                         as gender,
        upper(trim(race))                           as race,
        upper(trim(ethnicity))                      as ethnicity,
        city,
        state,
        zip,
        -- deduplicate: keep most recent record per patient
        row_number() over (
            partition by id
            order by birthdate desc
        )                                           as row_num
    from source
    where id is not null
)
select * from cleaned where row_num = 1
```

**`stg_conditions.sql`** — normalize diagnosis codes
```sql
with source as (
    select * from {{ source('synthea_raw', 'conditions') }}
),
cleaned as (
    select
        patient                                     as patient_id,
        encounter                                   as encounter_id,
        cast(start as date)                         as condition_start_date,
        cast(stop as date)                          as condition_end_date,
        upper(trim(code))                           as icd10_code,
        description                                 as condition_description,
        case
            when stop is null then true
            when cast(stop as date) > current_date then true
            else false
        end                                         as is_active
    from source
    where patient is not null
      and code is not null
)
select * from cleaned
```

**`stg_medications.sql`** — normalize medication records
```sql
with source as (
    select * from {{ source('synthea_raw', 'medications') }}
),
cleaned as (
    select
        patient                                     as patient_id,
        encounter                                   as encounter_id,
        cast(start as date)                         as med_start_date,
        cast(stop as date)                          as med_end_date,
        upper(trim(code))                           as rxnorm_code,
        lower(trim(description))                    as medication_name,
        case
            when stop is null then true
            when cast(stop as date) > current_date then true
            else false
        end                                         as is_active,
        datediff('day', cast(start as date), current_date) as days_since_start
    from source
    where patient is not null
      and code is not null
)
select * from cleaned
```

### Mart models

**`mart_gap_registry.sql`** — the core output table (parameterized by config via macro)
```sql
-- This model is generated dynamically by the gap engine from YAML config
-- Example output for heart failure use case:

with hf_patients as (
    select distinct patient_id
    from {{ ref('stg_conditions') }}
    where icd10_code in ('I50.0','I50.1','I50.9','I50.20','I50.30')
      and is_active = true
),
active_gdmt as (
    select distinct patient_id
    from {{ ref('stg_medications') }}
    where rxnorm_code in ('866511','854901','200031','29046','214354','18867')
      and is_active = true
      and days_since_start <= 365
),
gap_registry as (
    select
        p.patient_id,
        pt.gender,
        pt.race,
        pt.birth_date,
        datediff('year', pt.birth_date, current_date)   as age,
        true                                             as has_hf_diagnosis,
        case when g.patient_id is not null then true
             else false end                              as is_receiving_gdmt,
        case when g.patient_id is null then true
             else false end                              as has_care_gap,
        current_timestamp                                as gap_identified_at
    from hf_patients p
    left join {{ ref('stg_patients') }} pt on p.patient_id = pt.patient_id
    left join active_gdmt g on p.patient_id = g.patient_id
)
select * from gap_registry
```

**`mart_quality_summary.sql`** — aggregate gap rate for dashboard KPIs
```sql
select
    count(*)                                                    as total_patients,
    countif(has_hf_diagnosis)                                   as diagnosed_patients,
    countif(is_receiving_gdmt)                                  as patients_on_gdmt,
    countif(has_care_gap)                                       as patients_with_gap,
    round(countif(has_care_gap) / count(*) * 100, 1)           as gap_rate_pct,
    round(countif(is_receiving_gdmt) / count(*) * 100, 1)      as gdmt_adherence_pct,
    current_date                                                as as_of_date
from {{ ref('mart_gap_registry') }}
```

---

## Gap engine (Python)

**`gap_engine/generate_gap_sql.py`**
```python
"""
Reads a disease config YAML and generates the gap detection SQL.
This is the core of ClinIQ's modularity — same code, any disease.
"""
import yaml
import argparse
from pathlib import Path

def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)

def generate_diagnosis_filter(codes: list) -> str:
    quoted = ", ".join(f"'{c}'" for c in codes)
    return f"icd10_code in ({quoted})"

def generate_medication_filter(interventions: dict) -> str:
    all_codes = []
    for group in interventions.get("medications", {}).values():
        all_codes.extend(group.get("rxnorm_codes", []))
    quoted = ", ".join(f"'{c}'" for c in all_codes)
    return f"rxnorm_code in ({quoted})"

def generate_gap_sql(config: dict) -> str:
    condition_name = config["condition"]["name"]
    diag_codes = config["diagnosis_codes"]["icd10"]
    interventions = config["target_interventions"]
    lookback_days = config["gap_definition"]["lookback_days"]

    diag_filter = generate_diagnosis_filter(diag_codes)
    med_filter = generate_medication_filter(interventions)

    sql = f"""
-- Auto-generated by ClinIQ gap engine
-- Condition: {config['condition']['display_name']}
-- Generated: {{{{ run_started_at }}}}

with qualifying_patients as (
    select distinct patient_id
    from stg_conditions
    where {diag_filter}
      and is_active = true
),
active_interventions as (
    select distinct patient_id
    from stg_medications
    where {med_filter}
      and days_since_start <= {lookback_days}
),
gap_registry as (
    select
        q.patient_id,
        case when i.patient_id is not null then true else false end as is_treated,
        case when i.patient_id is null then true else false end     as has_gap,
        '{condition_name}'                                          as condition,
        current_timestamp                                           as identified_at
    from qualifying_patients q
    left join active_interventions i on q.patient_id = i.patient_id
)
select * from gap_registry;
"""
    return sql

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to disease YAML config")
    parser.add_argument("--output", help="Output SQL file path")
    args = parser.parse_args()

    config = load_config(args.config)
    sql = generate_gap_sql(config)

    if args.output:
        Path(args.output).write_text(sql)
        print(f"SQL written to {args.output}")
    else:
        print(sql)
```

---

## AI abstraction agent (LangGraph + Claude)

**`agent/cliniq_agent.py`**
```python
"""
ClinIQ AI Agent — reads unstructured clinical notes and abstracts
quality measure data, with full audit logging of every inference.
"""
from langgraph.graph import StateGraph, END
from anthropic import Anthropic
from typing import TypedDict
from audit_log import write_audit_entry
import json
from datetime import datetime

client = Anthropic()

class AgentState(TypedDict):
    patient_id: str
    clinical_note: str
    condition: str
    measure_name: str
    abstraction_result: dict
    audit_id: str

def abstract_note(state: AgentState) -> AgentState:
    """Call Claude to abstract the quality measure from the clinical note."""
    prompt = f"""
You are a clinical quality abstraction specialist.

Patient ID: {state['patient_id']}
Condition: {state['condition']}
Quality Measure: {state['measure_name']}

Clinical Note:
{state['clinical_note']}

Extract the following and return as JSON only:
{{
  "has_qualifying_diagnosis": true/false,
  "qualifying_icd10_codes_found": ["..."],
  "active_medications_mentioned": ["..."],
  "has_care_gap": true/false,
  "gap_reason": "...",
  "confidence_score": 0.0-1.0,
  "evidence_quote": "exact text supporting your conclusion"
}}
"""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    result = json.loads(response.content[0].text)
    state["abstraction_result"] = result
    return state

def log_abstraction(state: AgentState) -> AgentState:
    """Write every abstraction to the audit trail."""
    audit_entry = {
        "audit_id": state["audit_id"],
        "patient_id": state["patient_id"],
        "condition": state["condition"],
        "measure_name": state["measure_name"],
        "abstraction_result": state["abstraction_result"],
        "model_used": "claude-sonnet-4-6",
        "abstracted_at": datetime.utcnow().isoformat(),
        "note_length_chars": len(state["clinical_note"])
    }
    write_audit_entry(audit_entry)
    return state

# Build the LangGraph workflow
workflow = StateGraph(AgentState)
workflow.add_node("abstract", abstract_note)
workflow.add_node("log", log_abstraction)
workflow.set_entry_point("abstract")
workflow.add_edge("abstract", "log")
workflow.add_edge("log", END)

app = workflow.compile()

def run_abstraction(patient_id: str, note: str, condition: str, measure: str) -> dict:
    import uuid
    result = app.invoke({
        "patient_id": patient_id,
        "clinical_note": note,
        "condition": condition,
        "measure_name": measure,
        "abstraction_result": {},
        "audit_id": str(uuid.uuid4())
    })
    return result["abstraction_result"]
```

**`agent/audit_log.py`**
```python
"""
Audit logging for every AI abstraction.
Every inference ClinIQ makes is logged — who, what, when, why.
This is the governance layer.
"""
import json
import csv
from pathlib import Path
from datetime import datetime

AUDIT_LOG_PATH = Path("audit_log/abstractions.jsonl")
AUDIT_SUMMARY_PATH = Path("audit_log/summary.csv")

def write_audit_entry(entry: dict):
    """Append one abstraction event to the JSONL audit log."""
    AUDIT_LOG_PATH.parent.mkdir(exist_ok=True)
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

def get_audit_summary() -> list:
    """Read all audit entries and return as list of dicts."""
    if not AUDIT_LOG_PATH.exists():
        return []
    entries = []
    with open(AUDIT_LOG_PATH) as f:
        for line in f:
            entries.append(json.loads(line.strip()))
    return entries

def export_audit_csv():
    """Export audit log to CSV for dashboard consumption."""
    entries = get_audit_summary()
    if not entries:
        return
    keys = entries[0].keys()
    with open(AUDIT_SUMMARY_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(entries)
    print(f"Audit log exported: {len(entries)} entries → {AUDIT_SUMMARY_PATH}")
```

---

## Power BI dashboard

The dashboard connects directly to the Snowflake mart tables. Three pages:

**Page 1 — Care Gap Registry**
- KPI cards: Total patients, Gap rate %, Patients with gap, Patients on therapy
- Table: patient-level gap registry with filter by age, gender, gap type
- Bar chart: gap rate by demographic segment

**Page 2 — Cohort Trends**
- Line chart: gap rate over time (by `gap_identified_at` month)
- Funnel: diagnosed → qualifying encounter → on therapy → gap closed

**Page 3 — AI Abstraction Audit**
- Table of every agent abstraction with confidence score, evidence quote
- Accuracy rate: agent result vs rule-based SQL result (validation)
- Filter by condition, date range, confidence threshold

---

## How to run ClinIQ

### Prerequisites
- Python 3.11+
- Snowflake account (free trial: snowflake.com/try)
- dbt-snowflake (`pip install dbt-snowflake`)
- Anthropic API key
- Java 11+ (for Synthea)

### Step 1 — Generate synthetic data
```bash
# Download and run Synthea
git clone https://github.com/synthetichealth/synthea.git
cd synthea
./run_synthea -p 10000 --exporter.csv.export true Massachusetts
# This generates ~10K synthetic patients as CSV files
```

### Step 2 — Load to Snowflake
```bash
cd cliniq
pip install -r requirements.txt
cp .env.example .env
# Fill in your Snowflake credentials in .env
python ingestion/load_to_snowflake.py
```

### Step 3 — Run dbt models
```bash
cd dbt_cliniq
cp profiles.yml.example profiles.yml
# Fill in your Snowflake connection in profiles.yml
dbt deps
dbt run
dbt test
```

### Step 4 — Run gap analysis for a condition
```bash
# Generate SQL for heart failure
python gap_engine/generate_gap_sql.py \
  --config config/heart_failure.yaml \
  --output gap_engine/output/heart_failure_gaps.sql

# Run it
python gap_engine/run_gap_analysis.py \
  --config config/heart_failure.yaml

# Switch to diabetes — same command, different config
python gap_engine/generate_gap_sql.py \
  --config config/diabetes.yaml \
  --output gap_engine/output/diabetes_gaps.sql
```

### Step 5 — Run the AI abstraction agent
```bash
export ANTHROPIC_API_KEY=your_key_here
python agent/cliniq_agent.py \
  --patient_id P12345 \
  --note "Patient presents with history of heart failure. Currently on lisinopril. Beta blocker not prescribed due to bradycardia concern." \
  --condition heart_failure \
  --measure HF_GDMT_GAP
```

---

## What makes this different from a one-off dashboard

| Standard approach | ClinIQ |
|---|---|
| Hardcoded ICD-10 codes in SQL | Config-driven YAML, swap condition in seconds |
| One disease per project | Infinite diseases, one codebase |
| No audit trail | Every AI inference logged with evidence |
| Manual abstraction | LLM agent abstracts from unstructured notes |
| Static dashboard | Live Snowflake connection, refreshes with pipeline |
| No data quality layer | dbt tests enforce completeness + validity |

---

## Interview talking points

**"Why did you build this?"**
> Most clinical quality projects I saw were disease-specific — someone builds a diabetes dashboard, someone else builds a cardiac one. I wanted to build one architecture where you swap a config file and it runs for any population. The YAML-driven approach means a new disease area is a 10-minute config, not a month of SQL rewrites.

**"How does the AI layer work?"**
> The LangGraph agent reads unstructured clinical notes and extracts the same data points that a human abstractor would look for — qualifying diagnoses, active medications, gap reasoning. Every inference writes to an audit log with the evidence quote and confidence score. That governance layer was deliberate — in healthcare AI, you can't just run a model and trust the output. You need to know exactly why it said what it said.

**"What would it take to add a new disease?"**
> Write a YAML config with the ICD-10 codes, target medications or lab thresholds, and the gap logic definition. Then run `generate_gap_sql.py --config your_new_condition.yaml`. The dbt models, the agent, and the dashboard all pick it up automatically.

**"How did you handle data quality?"**
> dbt tests enforce no duplicate patients, valid ICD-10 code formats, and gap flag logic consistency. The staging layer also tracks record-level deduplication — same approach I used at Endeavor Health when cleaning ~500K patient records with ~44% duplication.

**"Why Synthea instead of real data?"**
> Synthea generates clinically realistic synthetic patients — realistic diagnoses, medication histories, encounter patterns — without any PHI concerns. It let me develop and test the full pipeline in a way I could share publicly, which a real EHR dataset never would.

---

## Tech stack

| Layer | Technology |
|---|---|
| Synthetic data | Synthea |
| Data warehouse | Snowflake |
| Transformation | dbt |
| Orchestration | Apache Airflow |
| Gap engine | Python + YAML |
| AI agent | LangGraph + Claude (Anthropic) |
| Dashboard | Power BI |
| Version control | GitHub |
| Testing | dbt tests + pytest |

---

## Author

**Mrudula (Mansi) Deshmukh**
MS Data Science, University at Buffalo
Healthcare Data Science | Clinical AI | EHR Analytics
[mrudula1501.github.io](https://mrudula1501.github.io) · [LinkedIn](https://www.linkedin.com/in/dmrudula/)


