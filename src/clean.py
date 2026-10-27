"""Clean SPARCS discharges and build the adult sepsis cohort.

Column names are the Socrata API names (see DATA_DICTIONARY.md). Everything
arrives as text, so numeric fields are converted here.
"""

# Report findings from initial analysis of the dataset

# operating_certificate_number: change dtype
# permanent_facility_id: change dtype
# facility_name: check if the names need cleaning in anyway?
# age_group: change the way data is presented, 0 to 17 -> 0-17, 18 to 29 -> 18-29, ..., 70 or older -> 70+
# zip_code_3_digits: 1300+ missing
# length_of_stay: fix 65 "120 +" values to 120 and change dtype
# type_of_admission: 106 values are marked "Not Available", what to do?
# patient_disposition: Important col with lots of choices to make? found the "Cancer Center or Children's Hospital really weird?"
# ccsr_diagnosis_description: probably filter by "Septicemia"
# ccsr_procedure_code: create a new col to indicate if there was any procedure done instead? a binary 1/0
# apr_drg_code: evrything is 720 everything is septicemia
# apr_severity_of_illness_code: change dtype
# payment_typology_type_1: there is 3 diff types, we could technically get do a new col and just store the count of all insurances?
# birth_weight: change dtype
# total_charges: change dtype
# total_costs: change dtype

# can drop these - they are the same value overrall
# apr_drg_code, apr_drg_description, apr_mdc_code, apr_mdc_description, apr_medical_surgical,

import pandas as pd

# Columns the analysis relies on; fail early if the API renames any of them.
REQUIRED_COLS = [
    "permanent_facility_id", "facility_name", "age_group", "gender", "race",
    "type_of_admission", "emergency_department_indicator",
    "apr_severity_of_illness_code", "apr_risk_of_mortality",
    "payment_typology_1", "patient_disposition", "length_of_stay",
    "total_costs", "total_charges",
]

# Same value on every DRG 720 row, so they carry no information.
CONSTANT_COLS = [
    "apr_drg_code", "apr_drg_description", "apr_mdc_code",
    "apr_mdc_description", "apr_medical_surgical", "discharge_year",
]

HOSPICE = ["Hospice - Home", "Hospice - Medical Facility"]

# Discharged to another hospital that gives acute or ongoing hospital care.
# Post-acute settings (rehab, nursing homes, psych, swing beds) are not included.
TRANSFERS = [
    "Short-term Hospital", "Cancer Center or Children's Hospital",
    "Critical Access Hospital", "Medicare Cert Long Term Care Hospital",
    "Federal Health Care Facility",
]
LEFT_AMA = "Left Against Medical Advice"


def to_number(s: pd.Series) -> pd.Series:
    """Text like '76,210.47' -> 76210.47. Raises on anything unexpected."""
    return pd.to_numeric(s.str.replace(",", "", regex=False))


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Fix types and add the outcome columns. Does not drop any rows."""
    missing = [c for c in REQUIRED_COLS if c not in raw.columns]
    assert not missing, f"Columns missing from the download: {missing}"

    df = raw.drop(columns=CONSTANT_COLS).copy()
    df["patient_disposition"] = df["patient_disposition"].str.strip()

    # LOS is capped at "120 +"; treat those 65 stays as 120 days.
    df["length_of_stay"] = to_number(df["length_of_stay"].replace("120 +", "120"))
    df["total_costs"] = to_number(df["total_costs"])
    df["total_charges"] = to_number(df["total_charges"])
    df["apr_severity_of_illness_code"] = to_number(df["apr_severity_of_illness_code"])
    # permanent_facility_id stays text: leading zeros matter (e.g. "001169").

    disp = df["patient_disposition"]
    df["died"] = (disp == "Expired").astype(int)
    # Sensitivity outcome: hospitals differ in how often dying patients go to
    # hospice, which can make in-hospital mortality look better than it is.
    df["died_or_hospice"] = disp.isin(["Expired", *HOSPICE]).astype(int)
    return df


def build_cohort(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the cohort rules in order. Returns the cohort and a CONSORT-style count table."""
    steps = [("all sepsis discharges", len(df))]

    df = df[df["permanent_facility_id"].notna()]  # redacted records cannot be benchmarked
    steps.append(("facility identified", len(df)))

    df = df[df["age_group"] != "0 to 17"]
    steps.append(("adults", len(df)))

    # Transfers out to another hospital: their final outcome is unknown here,
    # and counting them as survivors would reward hospitals that transfer sick patients.
    df = df[~df["patient_disposition"].isin(TRANSFERS)]
    steps.append(("not transferred to another hospital", len(df)))

    # Left against medical advice: care was cut short, so the outcome is unknown too.
    df = df[df["patient_disposition"] != LEFT_AMA]
    steps.append(("did not leave against medical advice", len(df)))

    return df.copy(), pd.DataFrame(steps, columns=["step", "n"])
