"""
ClinIQ — Synthea CSV → Snowflake Loader
Loads all Synthea CSV exports into the SYNTHEA_RAW schema in Snowflake.
Run after generate_synthea_data.sh has produced the CSV files.
"""
import os
import glob
from pathlib import Path
from dotenv import load_dotenv
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
import pandas as pd

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SNOWFLAKE_CONN = {
    "account":   os.getenv("SNOWFLAKE_ACCOUNT"),
    "user":      os.getenv("SNOWFLAKE_USER"),
    "password":  os.getenv("SNOWFLAKE_PASSWORD"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    "database":  os.getenv("SNOWFLAKE_DATABASE", "CLINIQ"),
    "schema":    "SYNTHEA_RAW",
    "role":      os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
}

DATA_DIR = Path(__file__).parent.parent / "data" / "synthea"

# The Synthea CSV files we care about (maps filename → Snowflake table name)
TABLES = {
    "patients.csv":     "PATIENTS",
    "conditions.csv":   "CONDITIONS",
    "medications.csv":  "MEDICATIONS",
    "encounters.csv":   "ENCOUNTERS",
    "observations.csv": "OBSERVATIONS",
    "procedures.csv":   "PROCEDURES",
    "allergies.csv":    "ALLERGIES",
    "careplans.csv":    "CAREPLANS",
}


def get_connection():
    return snowflake.connector.connect(**SNOWFLAKE_CONN)


def ensure_schema(cursor):
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {SNOWFLAKE_CONN['database']}")
    cursor.execute(f"USE DATABASE {SNOWFLAKE_CONN['database']}")
    cursor.execute("CREATE SCHEMA IF NOT EXISTS SYNTHEA_RAW")
    cursor.execute("USE SCHEMA SYNTHEA_RAW")
    print("Schema SYNTHEA_RAW ready.")


def load_csv(conn, csv_path: Path, table_name: str):
    print(f"Loading {csv_path.name} → {table_name} ...", end=" ", flush=True)
    df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    # Normalize column names: uppercase, replace spaces with underscores
    df.columns = [c.upper().replace(" ", "_").replace("-", "_") for c in df.columns]

    success, nchunks, nrows, _ = write_pandas(
        conn,
        df,
        table_name=table_name,
        auto_create_table=True,
        overwrite=True,
    )
    print(f"{nrows:,} rows loaded." if success else "FAILED.")


def main():
    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Data directory not found: {DATA_DIR}\n"
            "Run ingestion/generate_synthea_data.sh first."
        )

    conn = get_connection()
    cursor = conn.cursor()
    ensure_schema(cursor)
    cursor.close()

    for filename, table in TABLES.items():
        csv_path = DATA_DIR / filename
        if csv_path.exists():
            load_csv(conn, csv_path, table)
        else:
            print(f"SKIP: {filename} not found in {DATA_DIR}")

    conn.close()
    print("\nAll done. Verify in Snowflake: SELECT * FROM SYNTHEA_RAW.PATIENTS LIMIT 5;")


if __name__ == "__main__":
    main()
