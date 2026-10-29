"""Step 2: describe the cohort before modelling it.

Each function returns a table (or saves a figure) so the notebook can show it
and the pipeline can save it.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency


def outcome_balance(df: pd.DataFrame) -> pd.DataFrame:
    """How rare are the outcomes? About 1 in 8 patients die: imbalanced, but not
    rare enough to need resampling, which would distort predicted probabilities."""
    outcomes = df[["died", "died_or_hospice"]]
    return pd.DataFrame({"n": outcomes.sum(), "rate": outcomes.mean().round(3)})


def missing_table(df: pd.DataFrame) -> pd.DataFrame:
    """Missing values per column, worst first; columns with none are left out."""
    n = df.isna().sum()
    n = n[n > 0].sort_values(ascending=False)
    return pd.DataFrame({"missing": n, "percent": (n / len(df) * 100).round(1)})


def mortality_by(df: pd.DataFrame, col: str, outcome: str = "died") -> pd.DataFrame:
    """Patients and mortality for each value of one column."""
    return (df.groupby(col, dropna=False)[outcome]
              .agg(n="size", mortality="mean")
              .round(3))


def severity_table(df: pd.DataFrame) -> pd.DataFrame:
    """Mortality, cost and length of stay by APR severity of illness (1 = minor, 4 = extreme)."""
    return df.groupby("apr_severity_of_illness_code").agg(
        n=("died", "size"), mortality=("died", "mean"),
        median_cost=("total_costs", "median"), median_los=("length_of_stay", "median"),
    ).round(3)


def cramers_v(a: pd.Series, b: pd.Series) -> float:
    """Association between two categorical columns: 0 = unrelated, 1 = one
    fully determines the other. The categorical counterpart of a correlation."""
    table = pd.crosstab(a, b)
    chi2 = chi2_contingency(table, correction=False)[0]
    return np.sqrt(chi2 / table.values.sum() / (min(table.shape) - 1))


def cramers_v_matrix(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Pairwise Cramér's V. Strongly related features don't hurt prediction,
    but they share credit, which makes their individual odds ratios less stable."""
    return pd.DataFrame([[cramers_v(df[a], df[b]) for b in cols] for a in cols],
                        index=cols, columns=cols).round(2)


def hospital_sizes(df: pd.DataFrame, cutoffs=(50, 100, 300)) -> pd.Series:
    """How many hospitals fall below each case count. Small hospitals have noisy
    death rates, which the funnel plot accounts for."""
    n = df.groupby("permanent_facility_id").size()
    sizes = {f"under {c} cases": int((n < c).sum()) for c in cutoffs}
    return pd.Series({"hospitals": len(n), **sizes, "median cases": int(n.median())})


def case_mix_table(df: pd.DataFrame, min_n: int = 300) -> pd.DataFrame:
    """Raw mortality vs share of Extreme-risk patients, for hospitals with at
    least min_n cases. If these move together, raw death rates mostly measure
    which patients a hospital sees, not how well it treats them."""
    t = (df.assign(extreme=df["apr_risk_of_mortality"].eq("Extreme"))
           .groupby(["permanent_facility_id", "facility_name"])
           .agg(n=("died", "size"), raw_mortality=("died", "mean"),
                share_extreme=("extreme", "mean")))
    return t[t["n"] >= min_n].sort_values("share_extreme")


def mild_sepsis_share(df: pd.DataFrame, min_n: int = 100) -> pd.DataFrame:
    """Share of each hospital's sepsis patients coded as mild (severity 1-2).

    Sepsis here is defined by billing codes. A hospital that codes sepsis more
    liberally adds milder patients, which lowers its raw mortality without any
    change in care. An unusually high mild share is a hint of that, not proof:
    some hospitals really do see milder sepsis."""
    t = (df.assign(mild=df["apr_severity_of_illness_code"] <= 2)
           .groupby(["permanent_facility_id", "facility_name"])
           .agg(n=("died", "size"), share_mild=("mild", "mean"),
                raw_mortality=("died", "mean")))
    return t[t["n"] >= min_n].sort_values("share_mild", ascending=False)


def plot_eda(df: pd.DataFrame, path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    # Mortality rises steeply with APR risk of mortality
    df.groupby("apr_risk_of_mortality")["died"].mean().sort_values().plot.bar(
        ax=axes[0], title="Mortality by APR risk of mortality", ylabel="In-hospital mortality")

    # Length of stay is right-skewed; clip the long tail so the shape is visible
    df["length_of_stay"].clip(upper=40).plot.hist(
        bins=40, ax=axes[1], title="Length of stay (clipped at 40)", xlabel="Days")

    # Hospital size: many small hospitals, whose O/E will be noisy
    df.groupby("permanent_facility_id").size().plot.hist(
        bins=40, ax=axes[2], title="Sepsis discharges per hospital", xlabel="Discharges")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
