"""
ClinIQ — Unit Tests for the Gap Engine
Run: pytest tests/test_gap_engine.py -v
"""
import sys
from pathlib import Path
import pytest
import yaml

# Add gap_engine to path
sys.path.insert(0, str(Path(__file__).parent.parent / "gap_engine"))
from generate_gap_sql import (
    load_config,
    generate_diagnosis_filter,
    generate_medication_filter,
    generate_medication_codes,
    generate_gap_sql,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
CONFIG_DIR = Path(__file__).parent.parent / "config"


@pytest.fixture
def heart_failure_config():
    return load_config(CONFIG_DIR / "heart_failure.yaml")


@pytest.fixture
def diabetes_config():
    return load_config(CONFIG_DIR / "diabetes.yaml")


@pytest.fixture
def hypertension_config():
    return load_config(CONFIG_DIR / "hypertension.yaml")


# ---------------------------------------------------------------------------
# Tests: Config loading
# ---------------------------------------------------------------------------
class TestConfigLoading:
    def test_hf_config_has_required_keys(self, heart_failure_config):
        cfg = heart_failure_config
        assert "condition" in cfg
        assert "diagnosis_codes" in cfg
        assert "target_interventions" in cfg
        assert "gap_definition" in cfg
        assert "quality_measure" in cfg

    def test_hf_config_condition_name(self, heart_failure_config):
        assert heart_failure_config["condition"]["name"] == "heart_failure"

    def test_diabetes_icd10_codes_present(self, diabetes_config):
        codes = diabetes_config["diagnosis_codes"]["icd10"]
        assert len(codes) > 0
        assert "E11.9" in codes

    def test_hypertension_has_lab_targets(self, hypertension_config):
        assert "lab_targets" in hypertension_config["target_interventions"]


# ---------------------------------------------------------------------------
# Tests: Diagnosis filter generation
# ---------------------------------------------------------------------------
class TestDiagnosisFilter:
    def test_dots_stripped_from_codes(self):
        codes = ["I50.9", "I50.20", "E11.65"]
        result = generate_diagnosis_filter(codes)
        assert "I509" in result
        assert "I5020" in result
        assert "E1165" in result
        # Original dotted forms should NOT appear
        assert "I50.9" not in result

    def test_filter_uses_in_clause(self):
        result = generate_diagnosis_filter(["I50.0"])
        assert "in (" in result.lower()

    def test_single_code(self):
        result = generate_diagnosis_filter(["I10"])
        assert "'I10'" in result

    def test_multiple_codes_comma_separated(self):
        result = generate_diagnosis_filter(["I10", "I119"])
        assert "," in result


# ---------------------------------------------------------------------------
# Tests: Medication filter generation
# ---------------------------------------------------------------------------
class TestMedicationFilter:
    def test_hf_medication_codes_present(self, heart_failure_config):
        codes = generate_medication_codes(heart_failure_config["target_interventions"])
        # Should include beta-blocker and ACE/ARB codes
        assert "866511" in codes  # carvedilol
        assert "29046" in codes   # lisinopril

    def test_filter_includes_all_groups(self, heart_failure_config):
        fil = generate_medication_filter(heart_failure_config["target_interventions"])
        assert "866511" in fil
        assert "29046" in fil

    def test_empty_medications_returns_false_clause(self):
        result = generate_medication_filter({"medications": {}})
        assert "1=0" in result

    def test_diabetes_statin_codes(self, diabetes_config):
        codes = generate_medication_codes(diabetes_config["target_interventions"])
        assert "301542" in codes  # atorvastatin


# ---------------------------------------------------------------------------
# Tests: SQL generation
# ---------------------------------------------------------------------------
class TestGapSqlGeneration:
    def test_sql_is_string(self, heart_failure_config):
        sql = generate_gap_sql(heart_failure_config)
        assert isinstance(sql, str)
        assert len(sql) > 100

    def test_sql_contains_cte_structure(self, heart_failure_config):
        sql = generate_gap_sql(heart_failure_config)
        assert "with qualifying_patients as" in sql.lower()
        assert "active_interventions as" in sql.lower()
        assert "gap_registry as" in sql.lower()

    def test_sql_contains_hf_icd10_codes(self, heart_failure_config):
        sql = generate_gap_sql(heart_failure_config)
        assert "I500" in sql  # I50.0 normalized
        assert "I509" in sql  # I50.9 normalized

    def test_sql_contains_lookback_days(self, heart_failure_config):
        sql = generate_gap_sql(heart_failure_config)
        lookback = heart_failure_config["gap_definition"]["lookback_days"]
        assert str(lookback) in sql

    def test_sql_contains_has_gap_flag(self, heart_failure_config):
        sql = generate_gap_sql(heart_failure_config)
        assert "has_gap" in sql

    def test_sql_contains_condition_name(self, heart_failure_config):
        sql = generate_gap_sql(heart_failure_config)
        assert "heart_failure" in sql

    def test_diabetes_sql_has_lab_gap_clause(self, diabetes_config):
        sql = generate_gap_sql(diabetes_config)
        # Diabetes config has HbA1c lab target
        assert "4548-4" in sql or "lab_gaps" in sql

    def test_hypertension_sql_generated(self, hypertension_config):
        sql = generate_gap_sql(hypertension_config)
        assert "hypertension" in sql
        assert "qualifying_patients" in sql.lower()

    def test_sql_switches_between_configs(self, heart_failure_config, diabetes_config):
        sql_hf = generate_gap_sql(heart_failure_config)
        sql_dm = generate_gap_sql(diabetes_config)
        # Different conditions → different SQL
        assert sql_hf != sql_dm
        assert "heart_failure" in sql_hf
        assert "diabetes_type2" in sql_dm


# ---------------------------------------------------------------------------
# Tests: Lookback window
# ---------------------------------------------------------------------------
class TestLookbackWindow:
    def test_default_lookback_is_365(self, heart_failure_config):
        assert heart_failure_config["gap_definition"]["lookback_days"] == 365

    def test_lookback_reflected_in_sql(self, heart_failure_config):
        sql = generate_gap_sql(heart_failure_config)
        assert "<= 365" in sql
