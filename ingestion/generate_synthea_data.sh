#!/usr/bin/env bash
# =============================================================================
# ClinIQ — Synthea Synthetic Patient Data Generator
# Generates a realistic synthetic EHR population for pipeline development.
# No real patients. No PHI. Fully shareable.
# =============================================================================
set -euo pipefail

POPULATION=${1:-10000}
STATE=${2:-Massachusetts}
SYNTHEA_DIR="$(pwd)/synthea"
OUTPUT_DIR="$(pwd)/data/synthea"

echo "==> ClinIQ: Generating ${POPULATION} synthetic patients in ${STATE}"

# 1. Clone Synthea if not already present
if [ ! -d "$SYNTHEA_DIR" ]; then
  echo "==> Cloning Synthea..."
  git clone https://github.com/synthetichealth/synthea.git "$SYNTHEA_DIR"
fi

cd "$SYNTHEA_DIR"

# 2. Run Synthea — CSV export enabled
./run_synthea \
  -p "$POPULATION" \
  --exporter.csv.export true \
  --exporter.fhir.export false \
  "$STATE"

# 3. Copy CSVs to our data directory
mkdir -p "$OUTPUT_DIR"
cp output/csv/*.csv "$OUTPUT_DIR/"

echo "==> Done. CSV files written to $OUTPUT_DIR"
echo "==> Files:"
ls -lh "$OUTPUT_DIR"/*.csv
