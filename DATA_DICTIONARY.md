# Data Dictionary: SPARCS Hospital Inpatient Discharges 2023 (APR-DRG 720 cohort)

**Source:** NY SPARCS Hospital Inpatient Discharges (De-Identified) 2023, dataset `46xm-urtu` on health.data.ny.gov.
**Official descriptions:** copied word for word from the dataset's column metadata, `https://health.data.ny.gov/api/views/46xm-urtu/columns.json` (fetched 2026-10-01). Only extra whitespace and a stray leading period in `apr_mdc_code` were removed.
**Observed values:** taken from the cached file `data/sparcs_2023_drg720.parquet` (131,139 discharges, APR-DRG 720, before any cohort exclusions).

Every field comes from the Socrata API as text, including the numeric-looking ones. See the notes column for conversions.

## Facility

| Field (API name) | Official description | Observed in DRG 720 cohort / project notes |
|---|---|---|
| `hospital_service_area` | A description of the Health Service Area (HSA) in which the hospital is located. Blank for enhanced de-identification records. Capital/Adirondack, CentralNY, Finger Lakes, Hudson Valley, Long Island, New York City, Southern Tier, Western NY. | 8 values. NYC is the largest (50,875). "Capital/Adirondack" appears truncated as `Capital/Adirond`. 93 null (redacted records). |
| `hospital_county` | A description of the county in which the hospital is located. Blank for records with enhanced de-identification. | 56 counties. 93 null. |
| `operating_certificate_number` | The facility Operating Certificate Number assigned by NYS Department of Health. Blank for records with enhanced de-identification. | 153 values. Some certificates cover more than one facility, so use `permanent_facility_id` as the hospital key. 93 null. |
| `permanent_facility_id` | Permanent Facility Identifier. Blank for records with enhanced de-identification. | 187 hospitals. Keep it as a string, because the leading zeros matter (e.g. `001169`). 93 null. These are dropped at cohort step 2. **Hospital key for O/E. Never a model feature.** |
| `facility_name` | The name of the facility where services were performed based on the Permanent Facility Identifier (PFI), as maintained by the NYSDOH Division of Health Facility Planning. For records with enhanced de-identification, 'Redacted for Confidentiality' appears. | 188 values: 187 hospitals plus `Redacted for Confidentiality` (93 rows). |

## Patient demographics

| Field (API name) | Official description | Observed in DRG 720 cohort / project notes |
|---|---|---|
| `age_group` | Age in years at time of admission/visit. Grouped into the following age groups: 0 to 17, 18 to 29, 30 to 49, 50 to 69, and 70 or Older. | 70 or Older 68,921; 50 to 69 40,157; 30 to 49 15,191; 18 to 29 4,456; 0 to 17 2,414. `0 to 17` is dropped at cohort step 3. Ordinal risk-adjustment variable. |
| `zip_code_3_digits` | The first three digits of the patient's zip code. | 50 values. 1,300 null. Not used. |
| `gender` | Patient gender. | M 65,613; F 65,518; U 8. |
| `race` | Patient race. | White 78,423; Other Race 31,608; Black/African American 19,539; Multi-racial 1,569. **Not used for risk adjustment.** Used only in the calibration-by-group fairness check. |
| `ethnicity` | Patient ethnicity. | Not Span/Hispanic 99,819; Spanish/Hispanic 17,284; Unknown 13,764; Multi-ethnic 272. |

## Admission, stay and discharge

| Field (API name) | Official description | Observed in DRG 720 cohort / project notes |
|---|---|---|
| `type_of_admission` | A description of the manner in which the patient was admitted to the health care facility. | Emergency 125,490; Urgent 4,348; Elective 1,039; Trauma 154; Not Available 106; Newborn 2. |
| `emergency_department_indicator` | The Emergency Department Indicator is set based on the submitted revenue codes. | Y 124,538; N 6,601. |
| `length_of_stay` | The total number of patient days at an acute level and/or other than acute care level (excluding leave of absence days). | Text. Capped at `120 +` (65 rows); convert it to 120 before casting to int. Measured over the whole stay, so it reflects the outcome. Don't use it as a risk-adjustment feature. |
| `patient_disposition` | The patient's destination or status upon discharge. | 19 values. Home or Self Care 53,209; Skilled Nursing Home 25,085; Home w/ Home Health Services 22,135; **Expired 15,292**; Short-term Hospital 3,183; Left Against Medical Advice 3,145; Hospice - Medical Facility 2,669; Hospice - Home 2,101; plus 11 smaller categories. **Primary outcome:** `Expired`. **Sensitivity outcome:** `Expired` or either hospice value. `Short-term Hospital` (a transfer out) is dropped at cohort step 4. |
| `discharge_year` | The year (CCYY) of discharge. | All `2023`. |

## Diagnosis and procedure groupings

| Field (API name) | Official description | Observed in DRG 720 cohort / project notes |
|---|---|---|
| `ccsr_diagnosis_code` | AHRQ Clinical Classification Software Refined (CCSR) Diagnosis Category Code. | Category of the principal diagnosis. INF002 130,377; INJ037 524; PNL009 140; INF003 70; INF001 18; INF005 10. |
| `ccsr_diagnosis_description` | AHRQ Clinical Classification Software Refined (CCSR) Diagnosis Category Description. | Septicemia 130,377; Complication of other surgical or medical care, injury, initial encounter 524; Perinatal infections 140; Bacterial infections 70; Tuberculosis 18; Foodborne intoxications 10. |
| `ccsr_procedure_code` | AHRQ Clinical Classification Software Refined (CCSR) ICD-10 Procedure Category Code. | Category of the principal procedure. 191 values. 46,092 null (no procedure). |
| `ccsr_procedure_description` | AHRQ Clinical Classification Software Refined (CCSR) ICD-10 Procedure Category Description. | Examples: ADMINISTRATION OF ANTIBIOTICS, MECHANICAL VENTILATION, NON-INVASIVE VENTILATION. These are treatments given during the stay, so they reflect hospital practice. Don't use them for risk adjustment. |

## APR-DRG classification (3M All Patient Refined Diagnosis Related Groups)

| Field (API name) | Official description | Observed in DRG 720 cohort / project notes |
|---|---|---|
| `apr_drg_code` | The All Patients Refined Diagnosis Related Groups (APR-DRG) Classification Code. | All `720` (the cohort filter). |
| `apr_drg_description` | The APR-DRG Classification Code Description. | All `SEPTICEMIA AND DISSEMINATED INFECTIONS`. |
| `apr_mdc_code` | All Patient Refined Major Diagnostic Category (APR MDC) Code. | All `18`. |
| `apr_mdc_description` | All Patient Refined Major Diagnostic Category (APR MDC) Description. | All `INFECTIOUS & PARASITIC DISEASES, SYSTEMIC OR UNSPECIFIED SITES`. |
| `apr_severity_of_illness_code` | The APR-DRG Severity of Illness Code. | Text `1`–`4`. It maps one to one to the description below: 1 = Minor 4,639; 2 = Moderate 25,941; 3 = Major 45,355; 4 = Extreme 55,204. In-hospital death rate by code: 0.2%, 0.5%, 4.3%, 23.9%. |
| `apr_severity_of_illness` | All Patient Refined Severity of Illness (APR SOI) Description. | Minor / Moderate / Major / Extreme. |
| `apr_risk_of_mortality` | All Patient Refined Risk of Mortality (APR ROM) Description. | Extreme 58,303; Major 40,943; Moderate 19,016; Minor 12,877. Strongly correlated with SOI. |
| `apr_medical_surgical` | The APR-DRG specific classification of Medical, Surgical or Not Applicable. | All `Medical`. |

**Note on SOI and ROM:** the 3M grouper assigns both from every diagnosis coded on the discharge, and it doesn't consider whether a condition was present on admission. A complication picked up in the hospital can therefore raise a patient's SOI or ROM, which inflates expected deaths. Both scores also depend on how thoroughly the hospital codes. That is why the planned sensitivity analysis refits the model without ROM; SOI has the same weakness.

## Payer

| Field (API name) | Official description | Observed in DRG 720 cohort / project notes |
|---|---|---|
| `payment_typology_1` | A description of the type of payment for this occurrence. | Primary payer. Medicare 84,734; Medicaid 24,405; Private Health Insurance 10,697; Blue Cross/Blue Shield 7,179; Federal/State/Local/VA 1,332; Self-Pay 1,194; Managed Care, Unspecified 1,061; Miscellaneous/Other 454; Department of Corrections 83. Added only in the sensitivity model. |
| `payment_typology_2` | A description of the type of payment for this occurrence. | Secondary payer. 53,217 null. |
| `payment_typology_3` | A description of the type of payment for this occurrence. | Tertiary payer. 110,637 null. |

## Financial

| Field (API name) | Official description | Observed in DRG 720 cohort / project notes |
|---|---|---|
| `total_charges` | Total charges for the discharge. | Text with thousands separators (e.g. `76,210.47`). Remove the commas and cast to float. These are list-price charges, not payments. |
| `total_costs` | Total estimated cost for the discharge. | Same format. Estimated from charges using each hospital's cost-to-charge ratios. Use this column, not charges, for cost analyses. |

## Neonatal

| Field (API name) | Official description | Observed in DRG 720 cohort / project notes |
|---|---|---|
| `birth_weight` | The neonate birth weight in grams. | 130,946 null. Filled in only for newborns, zero-padded text (e.g. `02300`). Not relevant once adults are selected. |
