# Sepsis mortality benchmarking: New York hospitals, 2023

Which New York hospitals have more in-hospital sepsis deaths than expected, given how sick their patients are, and do those conclusions hold up under reasonable changes to the method?

Using 120,995 adult sepsis discharges from 180 hospitals, I built a patient-level risk model, compared each hospital's observed deaths with its expected deaths (O/E), and tested how robust the hospital flags are to the choice of outcome, risk factors, and statistical limits.

## Key findings

1. **Raw death rates mostly reflect case mix.** Across hospitals with 300+ sepsis cases, raw mortality correlates 0.53 with the share of patients coded at Extreme risk of mortality. Ranking hospitals on raw rates would largely rank who they treat.
2. **A simple, well-calibrated model is enough.** Logistic regression on six patient factors reaches AUROC 0.81 with calibration slope 0.99 and intercept -0.003. LightGBM, EBM, and logistic regression with interactions are within 0.001 AUROC (bootstrap by hospital); the extra flexibility buys nothing here.
3. **Hospitals vary far more than chance allows.** The overdispersion factor is 4.9. With standard Poisson limits, 46 of 180 hospitals sit outside the 99.8% funnel limits; after allowing for the usual variation between hospitals, 5 do.
4. **Few flags are robust.** Requiring a flag to hold under both outcomes (in-hospital death; death or hospice discharge) and both risk-factor extremes (full model; admission factors only) leaves 7 high and 2 low hospitals at the adjusted 95% level, and 2 high at 99.8%: St Johns Episcopal Hospital South Shore (O/E 2.02, 95% CI 1.75 to 2.32) and Brookdale Hospital Medical Center (O/E 1.93, 1.60 to 2.32).
5. **The model under-predicts deaths for Black patients** (O/E 1.12, 95% CI 1.08 to 1.17) and slightly over-predicts for White patients (0.97, 0.95 to 0.99). Race is not a model input; this is a calibration gap worth understanding before using the expected deaths for any decision.

These are statistical signals worth a closer look, not verdicts on quality of care. The data are administrative billing records.

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
