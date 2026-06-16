"""
ClinIQ — Run Gap Analysis Against Snowflake
============================================
Executes the generated gap SQL against your Snowflake instance
and outputs the results as a CSV for dashboard consumption.

Usage:
  python run_gap_analysis.py --config ../config/heart_failure.yaml
  python run_gap_analysis.py --config ../config/diabetes.yaml --output output/diabetes_results.csv
"""
import os
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
import snowflake.connector
from dotenv import load_dotenv

from generate_gap_sql import load_config, generate_gap_sql

load_dotenv(Path(__file__).parent.parent / ".env")


def get_snowflake_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.getenv("SNOWFLAKE_DATABASE", "CLINIQ"),
        schema=os.getenv("SNOWFLAKE_SCHEMA", "MARTS"),
        role=os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
    )


def run_gap_query(config: dict) -> pd.DataFrame:
    """Generate SQL from config and execute against Snowflake."""
    sql = generate_gap_sql(config)

    # Strip the commented summary block (Snowflake doesn't like /* */ in multi-statement)
    sql_clean = sql.split("/*")[0].strip().rstrip(";") + ";"

    print(f"Connecting to Snowflake...")
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    print(f"Running gap analysis for: {config['condition']['display_name']}")
    cursor.execute(sql_clean)

    columns = [desc[0].lower() for desc in cursor.description]
    rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=columns)

    cursor.close()
    conn.close()
    return df


def print_summary(df: pd.DataFrame, config: dict):
    total = len(df)
    gaps = df["has_gap"].sum() if "has_gap" in df.columns else 0
    treated = df["is_treated"].sum() if "is_treated" in df.columns else 0
    gap_rate = round(gaps / total * 100, 1) if total > 0 else 0

    print(f"\n{'='*60}")
    print(f"  ClinIQ Gap Analysis Summary")
    print(f"  Condition: {config['condition']['display_name']}")
    print(f"  Measure  : {config['quality_measure']['name']}")
    print(f"{'='*60}")
    print(f"  Total patients in cohort : {total:,}")
    print(f"  Receiving therapy        : {treated:,}")
    print(f"  Patients with care gap   : {gaps:,}")
    print(f"  Gap rate                 : {gap_rate}%")
    print(f"  Adherence rate           : {100 - gap_rate}%")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="ClinIQ: Execute gap analysis against Snowflake."
    )
    parser.add_argument("--config", required=True, help="Disease YAML config path")
    parser.add_argument(
        "--output",
        help="CSV output path. Defaults to output/<condition>_gaps_<date>.csv"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    df = run_gap_query(config)
    print_summary(df, config)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        condition_name = config["condition"]["name"]
        date_str = datetime.now().strftime("%Y%m%d")
        output_path = Path(f"output/{condition_name}_gaps_{date_str}.csv")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Results saved to: {output_path} ({len(df):,} rows)")


if __name__ == "__main__":
    main()
