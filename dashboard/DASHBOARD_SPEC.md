# ClinIQ — Power BI Dashboard Specification

Connect Power BI Desktop directly to Snowflake (DirectQuery mode):
- Server: `<your_account>.snowflakecomputing.com`
- Database: `CLINIQ`
- Schema: `MARTS`

## Page 1 — Care Gap Registry

**Data source**: `MART_GAP_REGISTRY`

| Visual | Type | Fields |
|---|---|---|
| Total Patients | KPI Card | COUNT(patient_id) |
| Gap Rate % | KPI Card | gap_rate_pct from MART_QUALITY_SUMMARY |
| Patients with Gap | KPI Card | COUNTIF(has_care_gap=TRUE) |
| Patients on GDMT | KPI Card | COUNTIF(has_care_gap=FALSE) |
| Patient-level table | Table | patient_id, age, gender, race, gap_reason, on_beta_blocker, on_ace_arb |
| Gap rate by reason | Bar chart | gap_reason (x), COUNT (y) |

**Filters (slicers)**: gender, age range, race, state, has_care_gap

---

## Page 2 — Cohort Trends

**Data source**: `MART_GAP_REGISTRY` + `MART_QUALITY_SUMMARY`

| Visual | Type | Fields |
|---|---|---|
| Gap rate over time | Line chart | gap_identified_at (month), gap_rate_pct |
| Cohort funnel | Funnel | Diagnosed → Qualifying Encounter → On Therapy → Gap Closed |
| Demographics breakdown | Stacked bar | gender/race vs. gap status |
| Age distribution | Histogram | age bins vs. gap/treated |

---

## Page 3 — AI Abstraction Audit

**Data source**: `audit_log/summary.csv` (exported by audit_log.py)

| Visual | Type | Fields |
|---|---|---|
| Total abstractions | KPI Card | COUNT(audit_id) |
| Avg confidence | KPI Card | AVG(confidence_score) |
| Low confidence flags | KPI Card | COUNTIF(confidence_score < 0.6) |
| Abstraction table | Table | patient_id, condition, has_care_gap, confidence_score, evidence_quote, abstracted_at |
| Confidence distribution | Histogram | confidence_score bins |
| Agent vs. SQL agreement | Donut | agreement / disagreement rate |

**Filters**: condition, date range, confidence threshold, has_care_gap

---

## Refresh schedule
Set Power BI Gateway to refresh daily after the dbt pipeline runs.
Recommended: dbt run → export audit CSV → Power BI refresh.
