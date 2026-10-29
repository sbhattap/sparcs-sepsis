"""Step 6: do the hospital conclusions hold up, and is the model fair?

Two choices could drive the flags rather than real differences in care:
- Outcome: in-hospital death misses patients discharged to die elsewhere, so
  died_or_hospice is reported as a co-primary outcome.
- Features: severity and risk of mortality are coded at discharge and can absorb
  complications, so admission_only is the other extreme.
A flag that holds under all four combinations is a robust signal.
"""

import numpy as np
import pandas as pd

from . import models
from .benchmark import hospital_oe, oe_ci

OUTCOMES = ["died", "died_or_hospice"]
FEATURE_EXTREMES = ["full", "admission_only"]


def direction(flags: pd.Series, level: str = "95%") -> pd.Series:
    """'high', 'low' or 'within' at a given level. A 99.8% flag also counts at 95%."""
    levels = ["99.8%"] if level == "99.8%" else ["95%", "99.8%"]
    high = flags.isin([f"high ({lv})" for lv in levels])
    low = flags.isin([f"low ({lv})" for lv in levels])
    return pd.Series(np.select([high, low], ["high", "low"], "within"), index=flags.index)


def variant_predictions(df: pd.DataFrame) -> dict[tuple[str, str], np.ndarray]:
    """Out-of-fold predictions for every outcome x feature-extreme combination."""
    return {(outcome, fs): models.predict(df, fs, outcome)
            for outcome in OUTCOMES for fs in FEATURE_EXTREMES}


def robust_flags(df: pd.DataFrame, variant_preds: dict, level: str = "95%") -> pd.DataFrame:
    """O/E and adjusted flag under each of the four variants, plus a robust flag:
    'high' or 'low' only if every variant agrees on that direction."""
    oe, flags = {}, {}
    for (outcome, fs), p in variant_preds.items():
        h = hospital_oe(df, p, outcome).set_index(["permanent_facility_id", "facility_name"])
        name = f"{outcome} / {fs}"
        oe[name] = h["oe"]
        flags[name] = direction(h["flag_adjusted"], level)
    table = pd.concat({"oe": pd.DataFrame(oe), "flag": pd.DataFrame(flags)}, axis=1)
    f = table["flag"]
    table[("robust", "")] = np.select([f.eq("high").all(axis=1), f.eq("low").all(axis=1)],
                                      ["high", "low"], "not robust or within")
    return table


def rank_agreement(df: pd.DataFrame, preds: dict, p_hospice) -> pd.DataFrame:
    """Spearman correlation of hospital O/E across feature sets and the hospice outcome.
    Near 1 means hospitals keep roughly the same order."""
    oe = {name: hospital_oe(df, preds[f"lr_{name}"]).set_index("permanent_facility_id")["oe"]
          for name in models.FEATURE_SETS}
    oe["died_or_hospice"] = (hospital_oe(df, p_hospice, "died_or_hospice")
                             .set_index("permanent_facility_id")["oe"])
    return pd.DataFrame(oe).corr(method="spearman").round(3)


def coding_intensity(df: pd.DataFrame, p_full, p_admission) -> pd.DataFrame:
    """Expected deaths with discharge-coded severity vs from admission factors alone.

    A ratio above 1 means the hospital's coded severity raises its expected deaths
    beyond what age, sex and admission type predict: sicker patients, or more
    thorough coding (the data can't tell which). If heavy coding drove the flags,
    low-O/E hospitals would have high ratios."""
    t = (df.assign(p_full=p_full, p_adm=p_admission)
           .groupby(["permanent_facility_id", "facility_name"])
           .agg(observed=("died", "sum"), e_full=("p_full", "sum"), e_adm=("p_adm", "sum")))
    t["coding_ratio"] = t["e_full"] / t["e_adm"]
    t["oe"] = t["observed"] / t["e_full"]
    return t


def los_vs_oe(df: pd.DataFrame, hosp: pd.DataFrame) -> pd.DataFrame:
    """Median length of stay per hospital next to its O/E. Shorter stays leave less
    time for deaths to happen in hospital, so if short-stay hospitals had low O/E,
    discharge practice (not care) could explain part of their result."""
    los = df.groupby("permanent_facility_id")["length_of_stay"].median().rename("median_los")
    return hosp.set_index("permanent_facility_id")[["facility_name", "n", "oe"]].join(los)


def calibration_by_race(df: pd.DataFrame, p) -> pd.DataFrame:
    """Observed vs expected deaths within each race group, with an exact 95% CI.
    O/E near 1 means the model isn't systematically over- or under-predicting
    risk for that group. Race is never a model input."""
    t = (df.assign(p=p).groupby("race")
           .agg(n=("died", "size"), observed=("died", "sum"), expected=("p", "sum")))
    t["oe"] = t["observed"] / t["expected"]
    t["oe_ci_low"], t["oe_ci_high"] = oe_ci(t["observed"], t["expected"])
    return t.round(3)
