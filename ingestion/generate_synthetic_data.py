"""
ClinIQ — Synthetic EHR Data Generator (Synthea-compatible CSV format)
=====================================================================
Generates realistic synthetic patient data WITHOUT needing Java/Synthea.
Produces CSVs in the exact same schema as Synthea exports.

Seeded for the heart failure GDMT demo:
  - 2000 total patients
  - ~400 with heart failure diagnosis
  - ~220 HF patients with NO active GDMT (the care gaps we detect)
  - Realistic demographics, ICD-10 codes, RxNorm codes, encounters

Run: python ingestion/generate_synthetic_data.py
"""
import random
import uuid
import csv
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "synthea"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TODAY = date.today()

# ── Demographics pools ─────────────────────────────────────────────────────
FIRST_NAMES_M = ["James","John","Robert","Michael","William","David","Richard","Joseph","Thomas","Charles","Daniel","Matthew","Anthony","Mark","Donald","Steven","Paul","Andrew","Kenneth","George"]
FIRST_NAMES_F = ["Mary","Patricia","Jennifer","Linda","Barbara","Elizabeth","Susan","Jessica","Sarah","Karen","Lisa","Nancy","Betty","Sandra","Dorothy","Ashley","Kimberly","Emily","Donna","Carol"]
LAST_NAMES    = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin"]
RACES         = ["White","Black or African American","Asian","American Indian or Alaska Native","Other"]
RACE_WEIGHTS  = [0.60, 0.13, 0.06, 0.01, 0.20]
ETHNICITIES   = ["Non-Hispanic","Hispanic"]
STATES        = ["MA","NY","CA","TX","FL","IL","PA","OH","GA","NC"]
CITIES = {
    "MA": ["Boston","Worcester","Springfield"],
    "NY": ["New York","Buffalo","Rochester"],
    "CA": ["Los Angeles","San Francisco","San Diego"],
    "TX": ["Houston","Dallas","Austin"],
    "FL": ["Jacksonville","Miami","Tampa"],
    "IL": ["Chicago","Aurora","Naperville"],
    "PA": ["Philadelphia","Pittsburgh","Allentown"],
    "OH": ["Columbus","Cleveland","Cincinnati"],
    "GA": ["Atlanta","Augusta","Savannah"],
    "NC": ["Charlotte","Raleigh","Greensboro"],
}

# ── ICD-10 codes ───────────────────────────────────────────────────────────
HF_CODES = [
    ("I50.0",  "Congestive heart failure"),
    ("I50.1",  "Left ventricular failure, unspecified"),
    ("I50.9",  "Heart failure, unspecified"),
    ("I50.20", "Unspecified systolic (congestive) heart failure"),
    ("I50.30", "Unspecified diastolic (congestive) heart failure"),
]
OTHER_CODES = [
    ("I10",   "Essential (primary) hypertension"),
    ("E11.9", "Type 2 diabetes mellitus without complications"),
    ("J18.9", "Pneumonia, unspecified organism"),
    ("M79.3", "Panniculitis, unspecified"),
    ("Z87.39","Personal history of other musculoskeletal disorders"),
    ("I25.10","Atherosclerotic heart disease of native coronary artery without angina pectoris"),
    ("N18.3", "Chronic kidney disease, stage 3"),
    ("F32.9", "Major depressive disorder, single episode, unspecified"),
    ("J44.1", "Chronic obstructive pulmonary disease with acute exacerbation"),
    ("K21.0", "Gastro-esophageal reflux disease with esophagitis"),
]

# ── RxNorm codes ───────────────────────────────────────────────────────────
BETA_BLOCKERS = [
    ("866511", "carvedilol 25 mg oral tablet"),
    ("854901", "metoprolol succinate 50 mg oral tablet"),
    ("200031", "bisoprolol fumarate 5 mg oral tablet"),
]
ACE_ARBS = [
    ("29046",  "lisinopril 10 mg oral tablet"),
    ("214354", "enalapril maleate 5 mg oral tablet"),
    ("18867",  "losartan potassium 50 mg oral tablet"),
    ("49276",  "valsartan 80 mg oral tablet"),
]
OTHER_MEDS = [
    ("310798", "hydrochlorothiazide 25 mg oral tablet"),
    ("83367",  "atorvastatin 40 mg oral tablet"),
    ("308460", "metformin hydrochloride 500 mg oral tablet"),
    ("197361", "amlodipine 5 mg oral tablet"),
    ("198369", "furosemide 40 mg oral tablet"),
    ("309362", "aspirin 81 mg oral tablet"),
    ("1049502","acetaminophen 500 mg oral tablet"),
]

ENCOUNTER_CLASSES = ["outpatient","ambulatory","wellness","urgentcare","emergency"]
ENCOUNTER_DESCRIPTIONS = [
    "Encounter for symptom","General examination","Follow-up visit",
    "Routine visit","Preventive care visit","Chronic condition management",
]


def rand_date(years_back_min=0, years_back_max=2) -> date:
    days_back = random.randint(years_back_min * 365, years_back_max * 365)
    return TODAY - timedelta(days=days_back)


def rand_birth_date(age_min=40, age_max=85) -> date:
    age = random.randint(age_min, age_max)
    return TODAY - timedelta(days=age * 365 + random.randint(0, 364))


def make_id() -> str:
    return str(uuid.uuid4())


# ── Generators ────────────────────────────────────────────────────────────

def generate_patients(n=2000):
    patients = []
    for _ in range(n):
        gender = random.choice(["M", "F"])
        first = random.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F)
        last  = random.choice(LAST_NAMES)
        birth = rand_birth_date()
        state = random.choice(STATES)
        race  = random.choices(RACES, weights=RACE_WEIGHTS)[0]
        patients.append({
            "id":          make_id(),
            "birthdate":   birth.isoformat(),
            "deathdate":   "",
            "ssn":         f"999-{random.randint(10,99)}-{random.randint(1000,9999)}",
            "drivers":     "",
            "passport":    "",
            "prefix":      "Mr." if gender=="M" else "Ms.",
            "first":       first,
            "last":        last,
            "suffix":      "",
            "maiden":      "",
            "marital":     random.choice(["M","S","D","W"]),
            "race":        race,
            "ethnicity":   random.choices(ETHNICITIES, weights=[0.82,0.18])[0],
            "gender":      gender,
            "birthplace":  f"{random.choice(CITIES[state])} {state} US",
            "address":     f"{random.randint(1,999)} Main St",
            "city":        random.choice(CITIES[state]),
            "state":       state,
            "county":      "",
            "fips":        "",
            "zip":         f"{random.randint(10000,99999)}",
            "lat":         round(random.uniform(25.0, 48.0), 4),
            "lon":         round(random.uniform(-122.0, -70.0), 4),
            "healthcare_expenses": round(random.uniform(1000, 50000), 2),
            "healthcare_coverage": round(random.uniform(500, 40000), 2),
            "income":      random.randint(20000, 120000),
        })
    return patients


def generate_encounters(patients):
    encounters = []
    patient_encounters = {}  # patient_id -> list of encounter ids

    for p in patients:
        n_enc = random.randint(1, 8)
        pid = p["id"]
        patient_encounters[pid] = []
        for _ in range(n_enc):
            enc_date = rand_date(0, 3)
            enc_id = make_id()
            enc_class = random.choice(ENCOUNTER_CLASSES)
            encounters.append({
                "id":               enc_id,
                "start":            f"{enc_date}T08:{random.randint(0,59):02d}:00Z",
                "stop":             f"{enc_date}T09:{random.randint(0,59):02d}:00Z",
                "patient":          pid,
                "organization":     make_id(),
                "provider":         make_id(),
                "payer":            make_id(),
                "encounterclass":   enc_class,
                "code":             "185349003",
                "description":      random.choice(ENCOUNTER_DESCRIPTIONS),
                "base_encounter_cost": round(random.uniform(50, 500), 2),
                "total_claim_cost": round(random.uniform(100, 2000), 2),
                "payer_coverage":   round(random.uniform(50, 1500), 2),
                "reasoncode":       "",
                "reasondescription":"",
            })
            patient_encounters[pid].append((enc_id, enc_date))

    return encounters, patient_encounters


def generate_conditions(patients, patient_encounters, hf_patient_ids):
    conditions = []
    for p in patients:
        pid = p["id"]
        encs = patient_encounters.get(pid, [])
        if not encs:
            continue
        enc_id, enc_date = random.choice(encs)

        # Heart failure patients get an HF diagnosis
        if pid in hf_patient_ids:
            code, desc = random.choice(HF_CODES)
            onset = rand_date(1, 5)
            conditions.append({
                "start":       onset.isoformat(),
                "stop":        "",  # active
                "patient":     pid,
                "encounter":   enc_id,
                "code":        code,
                "description": desc,
            })

        # All patients get 1-3 other comorbidities
        n_other = random.randint(1, 3)
        for code, desc in random.sample(OTHER_CODES, min(n_other, len(OTHER_CODES))):
            onset = rand_date(0, 4)
            conditions.append({
                "start":       onset.isoformat(),
                "stop":        "" if random.random() > 0.3 else (onset + timedelta(days=random.randint(30,365))).isoformat(),
                "patient":     pid,
                "encounter":   enc_id,
                "code":        code,
                "description": desc,
            })

    return conditions


def generate_medications(patients, patient_encounters, hf_patient_ids, hf_on_gdmt):
    medications = []

    for p in patients:
        pid = p["id"]
        encs = patient_encounters.get(pid, [])
        if not encs:
            continue
        enc_id, enc_date = random.choice(encs)
        start = rand_date(0, 2)

        # HF patients on GDMT get their meds
        if pid in hf_on_gdmt:
            bb_code, bb_name = random.choice(BETA_BLOCKERS)
            aa_code, aa_name = random.choice(ACE_ARBS)
            for code, name in [(bb_code, bb_name), (aa_code, aa_name)]:
                medications.append({
                    "start":       start.isoformat(),
                    "stop":        "",  # active
                    "patient":     pid,
                    "payer":       make_id(),
                    "encounter":   enc_id,
                    "code":        code,
                    "description": name,
                    "base_cost":   round(random.uniform(10, 80), 2),
                    "payer_coverage": round(random.uniform(5, 60), 2),
                    "dispenses":   random.randint(1, 12),
                    "totalcost":   round(random.uniform(20, 500), 2),
                    "reasoncode":  "",
                    "reasondescription": "",
                })

        # All patients get some background meds
        n_other = random.randint(0, 3)
        for code, name in random.sample(OTHER_MEDS, min(n_other, len(OTHER_MEDS))):
            med_start = rand_date(0, 3)
            medications.append({
                "start":       med_start.isoformat(),
                "stop":        "" if random.random() > 0.4 else (med_start + timedelta(days=random.randint(30, 180))).isoformat(),
                "patient":     pid,
                "payer":       make_id(),
                "encounter":   enc_id,
                "code":        code,
                "description": name,
                "base_cost":   round(random.uniform(5, 50), 2),
                "payer_coverage": round(random.uniform(2, 40), 2),
                "dispenses":   random.randint(1, 6),
                "totalcost":   round(random.uniform(10, 200), 2),
                "reasoncode":  "",
                "reasondescription": "",
            })

    return medications


def generate_observations(patients, patient_encounters):
    observations = []
    for p in patients:
        pid = p["id"]
        encs = patient_encounters.get(pid, [])
        if not encs:
            continue

        for enc_id, enc_date in random.sample(encs, min(2, len(encs))):
            # Blood pressure
            observations.append({
                "date":        enc_date.isoformat(),
                "patient":     pid,
                "encounter":   enc_id,
                "category":    "vital-signs",
                "code":        "8480-6",
                "description": "Systolic Blood Pressure",
                "value":       random.randint(110, 165),
                "units":       "mmHg",
                "type":        "numeric",
            })
            # HbA1c for some patients
            if random.random() < 0.3:
                observations.append({
                    "date":        enc_date.isoformat(),
                    "patient":     pid,
                    "encounter":   enc_id,
                    "category":    "laboratory",
                    "code":        "4548-4",
                    "description": "Hemoglobin A1c/Hemoglobin.total in Blood",
                    "value":       round(random.uniform(5.5, 11.0), 1),
                    "units":       "%",
                    "type":        "numeric",
                })

    return observations


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✓ {path.name}: {len(rows):,} rows")


def main():
    print("ClinIQ Synthetic Data Generator")
    print("="*45)

    print("Generating 2,000 synthetic patients...")
    patients = generate_patients(2000)

    # Select HF patients (~20% of total)
    n_hf = int(len(patients) * 0.20)
    hf_patients = random.sample(patients, n_hf)
    hf_patient_ids = {p["id"] for p in hf_patients}

    # ~45% of HF patients are on full GDMT (no gap), ~55% have a gap
    n_on_gdmt = int(n_hf * 0.45)
    hf_on_gdmt = {p["id"] for p in random.sample(hf_patients, n_on_gdmt)}

    print(f"  HF patients total      : {n_hf}")
    print(f"  HF patients on GDMT    : {n_on_gdmt} ({round(n_on_gdmt/n_hf*100)}%)")
    print(f"  HF patients with gap   : {n_hf - n_on_gdmt} ({round((n_hf-n_on_gdmt)/n_hf*100)}%)")

    print("\nGenerating encounters...")
    encounters, patient_encounters = generate_encounters(patients)

    print("Generating conditions...")
    conditions = generate_conditions(patients, patient_encounters, hf_patient_ids)

    print("Generating medications...")
    medications = generate_medications(patients, patient_encounters, hf_patient_ids, hf_on_gdmt)

    print("Generating observations...")
    observations = generate_observations(patients, patient_encounters)

    print(f"\nWriting CSV files to {OUTPUT_DIR}/")
    write_csv(OUTPUT_DIR / "patients.csv", patients, [
        "id","birthdate","deathdate","ssn","drivers","passport","prefix","first","last","suffix",
        "maiden","marital","race","ethnicity","gender","birthplace","address","city","state",
        "county","fips","zip","lat","lon","healthcare_expenses","healthcare_coverage","income"
    ])
    write_csv(OUTPUT_DIR / "encounters.csv", encounters, [
        "id","start","stop","patient","organization","provider","payer","encounterclass",
        "code","description","base_encounter_cost","total_claim_cost","payer_coverage",
        "reasoncode","reasondescription"
    ])
    write_csv(OUTPUT_DIR / "conditions.csv", conditions, [
        "start","stop","patient","encounter","code","description"
    ])
    write_csv(OUTPUT_DIR / "medications.csv", medications, [
        "start","stop","patient","payer","encounter","code","description",
        "base_cost","payer_coverage","dispenses","totalcost","reasoncode","reasondescription"
    ])
    write_csv(OUTPUT_DIR / "observations.csv", observations, [
        "date","patient","encounter","category","code","description","value","units","type"
    ])

    print(f"\n✓ Done. {len(patients):,} patients, {len(encounters):,} encounters,")
    print(f"  {len(conditions):,} conditions, {len(medications):,} medications, {len(observations):,} observations")
    print(f"\nExpected gap rate: ~{round((n_hf-n_on_gdmt)/n_hf*100)}% of HF cohort")
    print(f"Next: python ingestion/load_to_snowflake.py")


if __name__ == "__main__":
    main()
