#!/bin/bash
# =============================================================================
# ClinIQ — Full Pipeline Runner
# Double-click this file in Finder to run the complete pipeline:
#   1. Install Python dependencies
#   2. Create Snowflake database + schema
#   3. Load synthetic patient data
#   4. Run dbt models (staging → intermediate → marts)
#   5. Run gap analysis → output gap registry CSV
# =============================================================================

# Change to the project directory (same folder as this script)
cd "$(dirname "$0")"

echo ""
echo "============================================="
echo "  ClinIQ Pipeline — Starting"
echo "============================================="
echo ""

# ── Step 1: Install dependencies ─────────────────────────────────────────
echo "[1/5] Installing Python dependencies..."
pip3 install "snowflake-connector-python[pandas]" pandas python-dotenv "dbt-core" "dbt-snowflake" pyyaml --quiet --break-system-packages 2>/dev/null || \
pip3 install "snowflake-connector-python[pandas]" pandas python-dotenv "dbt-core" "dbt-snowflake" pyyaml --quiet

# Add Python bin to PATH so dbt command is found
export PATH="$PATH:$(python3 -c "import sys, os; print(os.path.dirname(sys.executable))")"
echo "  ✓ Dependencies ready"
echo ""

# ── Step 2: Generate synthetic data (already done, but run if missing) ───
if [ ! -f "data/synthea/patients.csv" ]; then
  echo "[2/5] Generating synthetic patient data..."
  python3 ingestion/generate_synthetic_data.py
else
  echo "[2/5] Synthetic data already present — skipping generation"
  echo "  ✓ $(wc -l < data/synthea/patients.csv) patient rows found"
fi
echo ""

# ── Step 3: Load data to Snowflake ────────────────────────────────────────
echo "[3/5] Loading CSV data to Snowflake (CLINIQ.SYNTHEA_RAW)..."
python3 - << 'PYEOF'
import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('.env')

import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
import pandas as pd

TABLES = {
    "patients.csv":     "PATIENTS",
    "conditions.csv":   "CONDITIONS",
    "medications.csv":  "MEDICATIONS",
    "encounters.csv":   "ENCOUNTERS",
    "observations.csv": "OBSERVATIONS",
}

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    role=os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
)
cur = conn.cursor()

# Create database and schema
cur.execute("CREATE DATABASE IF NOT EXISTS CLINIQ")
cur.execute("USE DATABASE CLINIQ")
cur.execute("CREATE SCHEMA IF NOT EXISTS SYNTHEA_RAW")
cur.execute("USE SCHEMA SYNTHEA_RAW")
print("  ✓ CLINIQ.SYNTHEA_RAW schema ready")

data_dir = Path("data/synthea")
for filename, table in TABLES.items():
    path = data_dir / filename
    if not path.exists():
        print(f"  SKIP: {filename} not found")
        continue
    df = pd.read_csv(path, dtype=str, low_memory=False)
    df.columns = [c.upper().replace(" ","_").replace("-","_") for c in df.columns]
    success, _, nrows, _ = write_pandas(conn, df, table_name=table,
                                        auto_create_table=True, overwrite=True)
    print(f"  ✓ {table}: {nrows:,} rows loaded")

conn.close()
PYEOF

echo ""

# ── Step 4: Run dbt models ────────────────────────────────────────────────
echo "[4/5] Creating Snowflake views (staging → intermediate → marts)..."
python3 - << 'PYEOF'
import os
from dotenv import load_dotenv
load_dotenv('.env')
import snowflake.connector

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE","COMPUTE_WH"),
    database="CLINIQ",
    role=os.getenv("SNOWFLAKE_ROLE","SYSADMIN"),
)
cur = conn.cursor()

cur.execute("USE DATABASE CLINIQ")
cur.execute("CREATE SCHEMA IF NOT EXISTS DBT_DEV")
cur.execute("USE SCHEMA DBT_DEV")

views = {
    "STG_PATIENTS": """
        SELECT
            id                                                          AS patient_id,
            first || ' ' || last                                        AS full_name,
            gender,
            race,
            ethnicity,
            state,
            zip,
            birthdate,
            datediff('year', try_to_date(birthdate), current_date)     AS age
        FROM (
            SELECT *, row_number() OVER (PARTITION BY id ORDER BY birthdate) AS rn
            FROM CLINIQ.SYNTHEA_RAW.PATIENTS
        ) WHERE rn = 1
    """,
    "STG_CONDITIONS": """
        SELECT
            patient                                                    AS patient_id,
            encounter                                                  AS encounter_id,
            upper(replace(trim(code), '.', ''))                       AS icd10_code,
            description                                               AS condition_name,
            try_to_date("START")                                      AS onset_date,
            try_to_date("STOP")                                       AS resolved_date,
            CASE WHEN "STOP" IS NULL OR "STOP" = '' THEN true ELSE false END AS is_active,
            datediff('day', try_to_date("START"), current_date)      AS days_since_onset
        FROM CLINIQ.SYNTHEA_RAW.CONDITIONS
        WHERE code IS NOT NULL
    """,
    "STG_MEDICATIONS": """
        SELECT
            patient                                                    AS patient_id,
            encounter                                                  AS encounter_id,
            code                                                       AS rxnorm_code,
            description                                               AS medication_name,
            try_to_date("START")                                      AS start_date,
            try_to_date("STOP")                                       AS stop_date,
            CASE WHEN "STOP" IS NULL OR "STOP" = '' THEN true ELSE false END AS is_active,
            datediff('day', try_to_date("START"), current_date)      AS days_since_start
        FROM CLINIQ.SYNTHEA_RAW.MEDICATIONS
        WHERE code IS NOT NULL
    """,
    "STG_ENCOUNTERS": """
        SELECT
            id                                                         AS encounter_id,
            patient                                                    AS patient_id,
            encounterclass                                            AS encounter_class,
            try_to_date("START")                                      AS encounter_date,
            description
        FROM CLINIQ.SYNTHEA_RAW.ENCOUNTERS
        WHERE id IS NOT NULL
    """,
    "STG_OBSERVATIONS": """
        SELECT
            patient                                                    AS patient_id,
            encounter                                                  AS encounter_id,
            code                                                       AS loinc_code,
            description                                               AS observation_name,
            try_to_number(value::varchar, 10, 2)                      AS numeric_value,
            units,
            try_to_date("DATE")                                       AS observation_date
        FROM CLINIQ.SYNTHEA_RAW.OBSERVATIONS
        WHERE code IS NOT NULL
    """,
}

for name, sql in views.items():
    cur.execute(f"CREATE OR REPLACE VIEW {name} AS {sql}")
    print(f"  ✓ View {name} created")

# Mart table: gap registry
cur.execute("""
CREATE OR REPLACE TABLE MART_GAP_REGISTRY AS
WITH qualifying_patients AS (
    SELECT DISTINCT patient_id
    FROM STG_CONDITIONS
    WHERE icd10_code IN ('I500','I501','I509','I5020','I5030')
      AND is_active = true
),
has_beta_blocker AS (
    SELECT DISTINCT patient_id
    FROM STG_MEDICATIONS
    WHERE rxnorm_code IN ('866511','854901','200031')
      AND days_since_start <= 365
),
has_ace_arb AS (
    SELECT DISTINCT patient_id
    FROM STG_MEDICATIONS
    WHERE rxnorm_code IN ('29046','214354','18867','49276')
      AND days_since_start <= 365
),
has_encounter AS (
    SELECT DISTINCT patient_id
    FROM STG_ENCOUNTERS
    WHERE datediff('day', encounter_date, current_date) <= 365
)
SELECT
    q.patient_id,
    p.full_name,
    p.gender,
    p.race,
    p.ethnicity,
    p.age,
    p.state,
    p.zip,
    CASE WHEN bb.patient_id IS NOT NULL THEN true ELSE false END AS on_beta_blocker,
    CASE WHEN aa.patient_id IS NOT NULL THEN true ELSE false END AS on_ace_arb,
    CASE WHEN e.patient_id IS NOT NULL  THEN true ELSE false END AS has_qualifying_encounter,
    CASE WHEN bb.patient_id IS NULL OR aa.patient_id IS NULL THEN true ELSE false END AS has_care_gap,
    CASE
        WHEN bb.patient_id IS NULL AND aa.patient_id IS NULL THEN 'Missing both beta-blocker and ACE/ARB'
        WHEN bb.patient_id IS NULL THEN 'Missing beta-blocker therapy'
        WHEN aa.patient_id IS NULL THEN 'Missing ACE inhibitor or ARB therapy'
        ELSE 'Receiving full GDMT'
    END AS gap_reason,
    'HF_GDMT_GAP' AS quality_measure,
    'heart_failure' AS condition,
    current_timestamp AS gap_identified_at
FROM qualifying_patients q
LEFT JOIN STG_PATIENTS       p  ON q.patient_id = p.patient_id
LEFT JOIN has_beta_blocker   bb ON q.patient_id = bb.patient_id
LEFT JOIN has_ace_arb        aa ON q.patient_id = aa.patient_id
LEFT JOIN has_encounter      e  ON q.patient_id = e.patient_id
ORDER BY has_care_gap DESC, patient_id
""")
print("  ✓ Table MART_GAP_REGISTRY created")

cur.execute("""
CREATE OR REPLACE TABLE MART_QUALITY_SUMMARY AS
SELECT
    quality_measure,
    condition,
    COUNT(*)                                                          AS total_patients,
    SUM(CASE WHEN has_care_gap THEN 1 ELSE 0 END)                   AS patients_with_gap,
    SUM(CASE WHEN NOT has_care_gap THEN 1 ELSE 0 END)               AS patients_on_gdmt,
    ROUND(100.0 * SUM(CASE WHEN has_care_gap THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 1) AS gap_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN NOT has_care_gap THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 1) AS gdmt_adherence_pct
FROM MART_GAP_REGISTRY
GROUP BY quality_measure, condition
""")
print("  ✓ Table MART_QUALITY_SUMMARY created")

conn.close()
PYEOF
echo ""

# ── Step 5: Run gap analysis ──────────────────────────────────────────────
echo "[5/5] Running gap analysis..."
python3 - << 'PYEOF'
import os, csv
from pathlib import Path
from dotenv import load_dotenv
load_dotenv('.env')

import snowflake.connector

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE","COMPUTE_WH"),
    database="CLINIQ",
    schema="DBT_DEV",
    role=os.getenv("SNOWFLAKE_ROLE","SYSADMIN"),
)
cur = conn.cursor()

output_dir = Path("gap_engine/output")
output_dir.mkdir(exist_ok=True)

# Fetch gap registry
cur.execute("SELECT * FROM MART_GAP_REGISTRY")
cols = [c[0] for c in cur.description]
rows = cur.fetchall()

with open(output_dir / "heart_failure_gap_registry.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(cols)
    w.writerows(rows)

# Fetch summary
cur.execute("SELECT * FROM MART_QUALITY_SUMMARY")
scols = [c[0] for c in cur.description]
srows = cur.fetchall()
with open(output_dir / "quality_summary.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(scols)
    w.writerows(srows)

conn.close()

# Print stats
total = len(rows)
hcg_idx = cols.index("HAS_CARE_GAP") if "HAS_CARE_GAP" in cols else None
gaps = sum(1 for r in rows if hcg_idx is not None and r[hcg_idx]) if hcg_idx else 0
gap_rate = round(gaps/total*100,1) if total > 0 else 0

print("")
print("=====================================================")
print("  ClinIQ — Gap Analysis Results")
print("=====================================================")
print(f"  Total HF patients in cohort : {total:,}")
print(f"  Receiving full GDMT         : {total-gaps:,}")
print(f"  Patients with care gap      : {gaps:,}")
print(f"  Gap rate                    : {gap_rate}%")
print("=====================================================")
print(f"  Saved to gap_engine/output/")
print("=====================================================")
PYEOF

echo ""
echo "============================================="
echo "  ClinIQ Pipeline — COMPLETE ✓"
echo "============================================="
echo ""
echo "  Gap registry CSV: gap_engine/output/heart_failure_gap_registry.csv"
echo "  Summary CSV:      gap_engine/output/quality_summary.csv"
echo ""
echo "  Connect Power BI to Snowflake > CLINIQ.DBT_DEV for live dashboard."
echo ""
read -p "Press Enter to close..."
