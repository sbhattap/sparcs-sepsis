"""Run every step in order: `uv run sparcs`. Figures go to figs/, tables to results/."""

import matplotlib

matplotlib.use("Agg")  # save figures without opening windows

import matplotlib.pyplot as plt  # noqa: E402

from . import benchmark, checks, data, eda, models  # noqa: E402
from .config import APR_DRG, FIGS, RESULTS  # noqa: E402


def main() -> None:
    FIGS.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)

    print("1. Data and cohort")
    df, cohort = data.build_cohort(data.clean(data.load_raw()))
    cohort.to_csv(RESULTS / "cohort.csv", index=False)
    print(cohort.to_string(index=False))

    print("\n2. EDA")
    eda.outcome_balance(df).to_csv(RESULTS / "outcome_balance.csv")
    eda.severity_table(df).to_csv(RESULTS / "severity_table.csv")
    eda.cramers_v_matrix(df, models.FEATURE_SETS["full"] + ["payment_typology_1"]).to_csv(
        RESULTS / "cramers_v.csv")
    eda.case_mix_table(df).to_csv(RESULTS / "case_mix.csv")
    eda.mild_sepsis_share(df).to_csv(RESULTS / "mild_sepsis_share.csv")
    eda.plot_eda(df, FIGS / "eda.png")

    print("\n3-4. Risk models and calibration")
    y = df["died"].to_numpy()
    preds = models.fit_all(df)
    metrics = models.metrics_table(y, preds)
    metrics.to_csv(RESULTS / "model_metrics.csv", index=False)
    print(metrics.to_string(index=False))
    models.odds_ratios(df, models.FEATURE_SETS["full"]).to_csv(RESULTS / "odds_ratios.csv")
    models.plot_calibration(y, preds, FIGS / "calibration.png")

    print("\n5. Hospital O/E and funnel plot")
    hosp = benchmark.hospital_oe(df, preds["lr_full"])
    hosp.sort_values("oe", ascending=False).to_csv(RESULTS / "hospital_oe.csv", index=False)
    benchmark.plot_funnel(hosp, FIGS / "funnel_plot.png",
                          f"Sepsis mortality O/E by hospital, NY 2023 (APR-DRG {APR_DRG})")
    od = hosp.attrs["overdispersion"]
    print(f"overdispersion phi = {od['phi']:.2f}, tau2 = {od['tau2']:.4f}")
    print(hosp["flag_adjusted"].value_counts().to_string())

    print("\n6. Robustness and fairness")
    variants = checks.variant_predictions(df)
    for level in ["95%", "99.8%"]:
        robust = checks.robust_flags(df, variants, level)
        robust.to_csv(RESULTS / f"robust_flags_{level.rstrip('%')}.csv")
        print(f"robust at adjusted {level}:", robust["robust"].value_counts().to_dict())
    checks.rank_agreement(df, preds, variants[("died_or_hospice", "full")]).to_csv(
        RESULTS / "rank_agreement.csv")
    checks.coding_intensity(df, variants[("died", "full")],
                            variants[("died", "admission_only")]).to_csv(RESULTS / "coding_intensity.csv")
    checks.los_vs_oe(df, hosp).to_csv(RESULTS / "los_vs_oe.csv")
    fair = checks.calibration_by_race(df, preds["lr_full"])
    fair.to_csv(RESULTS / "fairness_by_race.csv")
    print(fair.to_string())

    plt.close("all")
    print(f"\nFigures in {FIGS}/, tables in {RESULTS}/")
