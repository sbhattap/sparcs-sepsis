"""Step 5: roll patient risk up to hospitals, measure uncertainty, and flag outliers.

- Observed (O) = actual deaths; expected (E) = sum of patients' predicted risks.
- O/E above 1 means more deaths than the patient mix explains.
- Small hospitals vary a lot by chance, so flags use limits that widen as E shrinks.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

# Two-sided limits: 95% (warning) and 99.8% (alarm), the usual funnel-plot pair
LEVELS = {"95%": 0.95, "99.8%": 0.998}


def poisson_limits(expected, level: float):
    """Range of death counts a hospital with this many expected deaths would see
    by chance alone, if deaths were Poisson around E."""
    e = np.asarray(expected, dtype=float)
    tail = (1 - level) / 2
    return stats.poisson.ppf(tail, e), stats.poisson.ppf(1 - tail, e)


def oe_ci(observed, expected, level: float = 0.95):
    """Exact (Garwood) Poisson confidence interval for O/E: the range of true
    O/E values consistent with the observed death count."""
    o = np.asarray(observed, dtype=float)
    e = np.asarray(expected, dtype=float)
    tail = (1 - level) / 2
    low = np.where(o > 0, stats.chi2.ppf(tail, 2 * o) / 2, 0.0)
    high = stats.chi2.ppf(1 - tail, 2 * o + 2) / 2
    return low / e, high / e


def overdispersion(observed, expected, winsor: float = 0.1) -> dict[str, float]:
    """Do hospitals vary more than Poisson chance allows? (Spiegelhalter 2005)

    z = (O - E) / sqrt(E) is each hospital's Poisson z-score. Under pure chance
    the mean of z^2 (phi) is about 1. Winsorizing the extreme 10% on each side
    stops a few true outliers from inflating phi (it also pulls phi to ~0.7
    under pure chance, so the test is conservative). tau2 is the extra
    between-hospital variance on the O/E scale (0 if phi is consistent with chance)."""
    o = np.asarray(observed, dtype=float)
    e = np.asarray(expected, dtype=float)
    z = (o - e) / np.sqrt(e)
    lo, hi = np.quantile(z, [winsor, 1 - winsor])
    z = np.clip(z, lo, hi)

    n = len(z)
    phi = np.mean(z ** 2)
    # Weights are 1 / (Poisson variance of O/E) = E. One hospital has no
    # between-hospital variance to estimate.
    spread = e.sum() - (e ** 2).sum() / e.sum()
    tau2 = max(0.0, (n * phi - (n - 1)) / spread) if n > 1 else 0.0
    p_value = stats.chi2.sf(n * phi, n - 1)
    return {"phi": phi, "tau2": tau2, "p_value": p_value, "hospitals": n}


def adjusted_limits(expected, level: float, tau2: float):
    """Funnel limits on the O/E scale with the extra between-hospital variance
    added (normal approximation): 1 +/- z * sqrt(1/E + tau2).

    Extra variance can only widen the limits. With few expected deaths the normal
    approximation can fall inside the exact Poisson limits, so take the wider of the two."""
    e = np.asarray(expected, dtype=float)
    half = stats.norm.ppf(1 - (1 - level) / 2) * np.sqrt(1 / e + tau2)
    p_lo, p_hi = poisson_limits(e, level)
    return np.minimum(np.clip(1 - half, 0, None), p_lo / e), np.maximum(1 + half, p_hi / e)


def _flag(oe, limits: dict) -> np.ndarray:
    """Strongest limit crossed. limits maps each level to (low, high) on the O/E scale."""
    lo95, hi95 = limits["95%"]
    lo998, hi998 = limits["99.8%"]
    # Check the stricter limit first so each hospital gets its strongest flag
    return np.select(
        [oe > hi998, oe < lo998, oe > hi95, oe < lo95],
        ["high (99.8%)", "low (99.8%)", "high (95%)", "low (95%)"], default="within")


def expected_false_flags(n_hospitals: int) -> dict[str, float]:
    """Hospitals flagged by chance alone if none truly differ. At 95%, about 1 in
    20 crosses the limits; this is why the 99.8% limit is the one that counts."""
    return {label: n_hospitals * (1 - level) for label, level in LEVELS.items()}


def hospital_oe(df: pd.DataFrame, p, outcome: str = "died") -> pd.DataFrame:
    """Observed vs expected deaths per hospital, with a 95% CI and two flags:
    - flag: Poisson limits (chance only)
    - flag_adjusted: limits widened for overdispersion (chance + typical hospital variation)
    The overdispersion estimates are stored in .attrs["overdispersion"]."""
    h = (df.assign(p=p, o=df[outcome])
           .groupby(["permanent_facility_id", "facility_name"])
           .agg(n=("o", "size"), observed=("o", "sum"), expected=("p", "sum"))
           .reset_index())
    h["oe"] = h["observed"] / h["expected"]
    h["oe_ci_low"], h["oe_ci_high"] = oe_ci(h["observed"], h["expected"])

    # Poisson limits are on death counts; divide by E to put them on the O/E scale
    poisson = {label: tuple(lim / h["expected"] for lim in poisson_limits(h["expected"], level))
               for label, level in LEVELS.items()}
    h["flag"] = _flag(h["oe"], poisson)

    od = overdispersion(h["observed"], h["expected"])
    adjusted = {label: adjusted_limits(h["expected"], level, od["tau2"])
                for label, level in LEVELS.items()}
    h["flag_adjusted"] = _flag(h["oe"], adjusted)
    h.attrs["overdispersion"] = od
    return h


def plot_funnel(hosp: pd.DataFrame, path, title: str) -> None:
    """O/E against expected deaths, with Poisson limits (grey) and
    overdispersion-adjusted limits (red)."""
    tau2 = hosp.attrs["overdispersion"]["tau2"]
    e = np.linspace(max(hosp.expected.min(), 0.5), hosp.expected.max(), 300)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(hosp.expected, hosp.oe, s=14, alpha=0.7)
    for label, style in [("95%", "--"), ("99.8%", ":")]:
        level = LEVELS[label]
        lo, hi = poisson_limits(e, level)
        ax.plot(e, lo / e, "grey", ls=style, lw=1, label=f"Poisson {label}")
        ax.plot(e, hi / e, "grey", ls=style, lw=1)
        lo, hi = adjusted_limits(e, level, tau2)
        ax.plot(e, lo, "tab:red", ls=style, lw=1, label=f"Adjusted {label}")
        ax.plot(e, hi, "tab:red", ls=style, lw=1)
    ax.axhline(1, color="k", lw=0.8)  # O/E = 1: as expected
    ax.set_xscale("log")
    ax.set(xlabel="Expected deaths (log scale)", ylabel="Observed / expected", title=title)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
