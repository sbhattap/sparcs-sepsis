# Sepsis mortality benchmarking: New York hospitals, 2023

Which New York hospitals have more in-hospital sepsis deaths than expected, given how sick their patients are, and do those conclusions hold up under reasonable changes to the method?

Using 120,995 adult sepsis discharges from 180 hospitals, I built a patient-level risk model, compared each hospital's observed deaths with its expected deaths (O/E), and tested how robust the hospital flags are to the choice of outcome, risk factors, and statistical limits.

## Answer

**Seven hospitals have consistently more in-hospital sepsis deaths than expected for their patients, and two have consistently fewer.** Each of these is flagged in the same direction under all four method variants: both outcomes (in-hospital death; death or discharge to hospice) and both risk-factor sets (full model; admission factors only), using funnel limits that allow for normal variation between hospitals.

| Hospital | Sepsis cases | Observed deaths | Expected deaths | O/E (95% CI) | Holds at 99.8%? |
|---|---|---|---|---|---|
| **More deaths than expected** | | | | | |
| St Johns Episcopal Hospital South Shore | 852 | 207 | 102 | 2.02 (1.75 to 2.32) | Yes |
| Brookdale Hospital Medical Center | 431 | 117 | 61 | 1.93 (1.60 to 2.32) | Yes |
| Brooklyn Hospital Center, Downtown Campus | 565 | 116 | 59 | 1.96 (1.62 to 2.35) | No |
| Westchester Medical Center | 537 | 115 | 67 | 1.70 (1.41 to 2.05) | No |
| Kenmore Mercy Hospital | 347 | 90 | 55 | 1.64 (1.32 to 2.01) | No |
| NYC Health + Hospitals/South Brooklyn Health | 1,064 | 232 | 144 | 1.61 (1.41 to 1.83) | No |
| Good Samaritan Hospital Medical Center | 1,081 | 208 | 135 | 1.54 (1.34 to 1.77) | No |
| **Fewer deaths than expected** | | | | | |
| NYU Langone Hospital-Long Island | 2,267 | 111 | 274 | 0.40 (0.33 to 0.49) | No |
| A.O. Fox Memorial Hospital | 208 | 6 | 19 | 0.31 (0.11 to 0.68) | No |

O/E and CIs are from the main model (in-hospital death, full risk factors). "Holds at 99.8%" means the flag survives all four variants at the stricter limit.

**Do the conclusions hold up? The ranking does; most of the flags don't.** Hospitals keep a similar order across method variants (Spearman rank correlation of O/E: 0.89 when hospice counts as death, 0.80 with admission factors only, 0.99 or more across the other risk-factor sets). But how many hospitals stand out from the rest depends heavily on method:

| Method | Hospitals flagged (of 180) |
|---|---|
| Poisson funnel limits, 99.8% (the textbook approach) | 46 |
| Limits adjusted for overdispersion, 95% | 29 |
| Adjusted 95%, and flagged under all four variants | **9** (table above) |
| Adjusted 99.8%, and flagged under all four variants | **2** |

These are statistical signals worth a closer look, not verdicts on quality of care. The data are administrative billing records; see [What this measures](#what-this-measures-and-what-it-doesnt).

## Supporting findings

1. **Raw death rates mostly reflect case mix.** Across hospitals with 300+ sepsis cases, raw mortality correlates 0.53 with the share of patients coded at Extreme risk of mortality. Ranking hospitals on raw rates would largely rank who they treat.
2. **A simple, well-calibrated model is enough.** Logistic regression on six patient factors reaches AUROC 0.81 with calibration slope 0.99 and intercept -0.003. LightGBM, EBM, and logistic regression with interactions are within 0.001 AUROC (bootstrap by hospital).
3. **Hospitals vary far more than chance allows.** The overdispersion factor is 4.9, so Poisson limits flag far too many hospitals. Allowing for the usual variation between hospitals cuts the 99.8% flags from 46 to 5.
4. **Black patients die more often than predicted, because of where they are treated.** Overall O/E is 1.12 (95% CI 1.08 to 1.17) for Black patients and 0.97 for White patients. Within the same hospital the gap disappears (O/E 1.02; odds ratio vs White patients 1.02, 0.96 to 1.09, down from 1.22 when hospital is ignored). So the model is not miscalibrated by race; Black patients are more often treated at hospitals with higher-than-expected mortality (5.5% at the 7 robust-high hospitals vs 2.9% of White patients). Race is not a model input.

## Data

- NY SPARCS Hospital Inpatient Discharges (De-Identified), 2023: dataset `46xm-urtu` on [health.data.ny.gov](https://health.data.ny.gov). Public, no patient identifiers.
- Cohort: APR-DRG 720, septicemia and disseminated infections. Sepsis is therefore defined by billing codes.
- Columns and observed values: [DATA_DICTIONARY.md](DATA_DICTIONARY.md).

| Step | Discharges |
|---|---|
| All APR-DRG 720 discharges | 131,139 |
| Facility identified | 131,046 |
| Adults (18+) | 128,637 |
| Not transferred to another hospital (final outcome unknown) | 124,939 |
| Did not leave against medical advice (outcome unknown) | 121,801 |
| Hospital treats acute sepsis: under 90% elective admissions (drops palliative and rehab hospitals) | 121,728 |
| Hospital reports deaths plausibly: not 0 deaths among 100+ cases (drops one reporting anomaly) | **120,995** |

In-hospital mortality is 12.6%; death or discharge to hospice is 16.5%.

## Method

1. **Risk model.** Logistic regression predicting in-hospital death from age group, sex, admission type, ED admission, APR severity of illness, and APR risk of mortality. The hospital is never a feature: the model estimates risk at an average NY hospital, and hospital differences show up as O/E. Race is excluded and used for the fairness check.
2. **Out-of-fold expected deaths.** Predictions come from 5-fold cross-validation grouped by hospital, so every hospital is scored by a model that never saw its patients.
3. **Calibration first.** Expected deaths are sums of predicted probabilities, so calibration (slope, intercept, decile plot) matters more than AUROC.
4. **O/E with uncertainty.** Exact Poisson 95% CIs per hospital; funnel plot with Poisson limits and with overdispersion-adjusted limits (Spiegelhalter, 2005).
5. **Robustness.** Rank agreement across feature sets; robust flags across 2 outcomes x 2 risk-factor sets; checks for coding intensity and length of stay.

**Choosing risk factors.** A variable belongs in the model if the hospital's care can't change it. APR severity and risk of mortality fail that test partly: they are assigned at discharge from all coded diagnoses, so they can absorb complications that began in hospital, and they depend on how thoroughly a hospital codes. They are kept because leaving them out is worse (admission factors alone give AUROC 0.60, so expected deaths would ignore how sick patients were), and the admission-only model is run as the other extreme. Hospitals flagged under both are the robust signals.

## What this measures, and what it doesn't

- **In-hospital deaths only.** SPARCS is not linked to death records, so a patient who dies at home or in a nursing home after discharge counts as a survivor. Hospitals that discharge dying patients look better. The death-or-hospice outcome captures the most common route; the gold standard, 30-day mortality from admission, needs linked data.
- **Sepsis as billed.** Hospitals that code sepsis liberally add milder patients and lower their mortality without any change in care. The share of mild (severity 1-2) sepsis ranges from 4% to 38% across hospitals.
- **Severity coded at discharge.** No present-on-admission flags are in the public file. Including severity can hide hospitals whose care causes complications (so high flags may understate problems), while coding habits can push O/E either way. The coding-intensity check found no strong link (Spearman 0.09 between coded-vs-admission expected deaths and O/E), but it can't separate thorough coding from genuinely sicker patients.
- **Discharge practice.** Hospitals with longer median stays have slightly higher O/E (Spearman 0.20), consistent with more time for deaths to happen in hospital.

## Limitations

- Administrative data: no labs, vitals, or medications; ages come in four bands.
- Transfers *into* a hospital aren't identified, so receiving centers get sicker patients than the model can see.
- No patient identifier: repeat admissions count as separate patients.
- Hospital type isn't recorded in SPARCS or the NY facility registry, so out-of-scope hospitals are identified from the data (admission mix).
- One year; a single bad year and a persistent problem look the same.

## Next steps

- Hierarchical model with a random intercept per hospital, to shrink small hospitals toward the average; compare with the funnel-plot flags.
- Repeat for 2022 to see which flags persist.
- Link CMS hospital type to restrict to general acute-care hospitals.
- Volume vs outcome, and cost per case with the same risk adjustment.

## Reproduce

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run sparcs       # downloads the data once, runs every step, writes figs/ and results/
uv run pytest       # checks the O/E, limits, CI and overdispersion math
```

- `notebooks/sparcs_sepsis_2023.ipynb`: the full analysis, step by step
- `notebooks/modeling_lab.ipynb`: model comparison, bootstrap, and explainability

## Repository layout

```
src/sparcs/
  config.py      dataset, paths, seed
  data.py        1. download, clean, cohort rules
  eda.py         2. descriptive tables and figure
  models.py      3-4. feature sets, out-of-fold predictions, metrics, calibration, odds ratios
  benchmark.py   5. O/E, CIs, Poisson and overdispersion-adjusted limits, funnel plot
  checks.py      6-7. robustness and fairness
  __init__.py    main(): runs every step
notebooks/
  sparcs_sepsis_2023.ipynb   full analysis, calling src/sparcs
  modeling_lab.ipynb         model experiments
tests/           math checks on small hand-made and simulated data
```
