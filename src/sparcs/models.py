"""Steps 3-4: patient-level risk models, their calibration, and what drives them.

The model estimates each patient's chance of dying in hospital at an average
NY hospital. It is only a tool for expected deaths (E); nothing is predicted
at admission.

Feature rule: a variable is allowed if the hospital's care can't change it
(illness the patient arrived with), not because of when it is recorded.
- Hospital is NOT a feature: hospital differences show up later as O/E.
- Race is excluded here and used for the fairness check.
- Length of stay and cost are excluded: the hospital's care shapes them.
- Severity of illness and risk of mortality (ROM) are coded at discharge and
  can absorb complications, so `admission_only` is kept as the other extreme.
"""

import re

import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .config import SEED

# Known when the patient arrives; the hospital's care can't change them
ADMISSION_FEATURES = ["age_group", "gender", "type_of_admission",
                      "emergency_department_indicator"]
# Plus APR severity of illness, coded at discharge from all diagnoses
PATIENT_FEATURES = ADMISSION_FEATURES + ["apr_severity_of_illness_code"]

# First-pass sets, one per sensitivity question (not tuned for accuracy)
FEATURE_SETS = {
    # Main model: patient features + APR risk of mortality (ROM)
    "full": PATIENT_FEATURES + ["apr_risk_of_mortality"],
    # Without ROM: ROM can include complications that started in hospital
    "no_rom": PATIENT_FEATURES,
    # With payer: a rough proxy for socioeconomic status
    "full_plus_payer": PATIENT_FEATURES + ["apr_risk_of_mortality", "payment_typology_1"],
    # With principal diagnosis group: separates septicemia from rarer groups
    "full_plus_dx": PATIENT_FEATURES + ["apr_risk_of_mortality", "ccsr_diagnosis_description"],
    # Strictest: nothing coded at discharge. Weak model, but no complications leak in
    "admission_only": ADMISSION_FEATURES,
}

# Reference level for each feature's odds ratios: the lowest-risk or most common group
REFERENCE = {
    "age_group": "18 to 29", "gender": "F", "type_of_admission": "Emergency",
    "emergency_department_indicator": "N", "apr_severity_of_illness_code": "1",
    "apr_risk_of_mortality": "Minor", "payment_typology_1": "Medicare",
    "ccsr_diagnosis_description": "Septicemia",
}


def features(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    # All inputs are categories; a missing value becomes its own category
    return df[cols].fillna("Unknown").astype(str)


def oof_predict(make_model, X, y, groups, n_splits=5) -> np.ndarray:
    """Out-of-fold predictions split by hospital: each hospital is scored by a
    model that never saw any of its patients."""
    pred = np.zeros(len(X))
    for tr, te in GroupKFold(n_splits=n_splits).split(X, y, groups):
        m = make_model().fit(X.iloc[tr], y[tr])
        pred[te] = m.predict_proba(X.iloc[te])[:, 1]
    return pred


def logreg(cols, **lr_kwargs):
    """One-hot encode the categories, then logistic regression. Defaults to
    sklearn's mild L2 penalty; C=np.inf is unpenalized, l1_ratio=1 is L1."""
    lr_kwargs = {"max_iter": 2000, **lr_kwargs}
    pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), cols)])
    return lambda: Pipeline([("pre", pre), ("lr", LogisticRegression(**lr_kwargs))])


def lgbm():
    """Comparison model: can a flexible model beat logistic regression by finding
    interactions? Settings are hand-picked, not tuned (num_leaves 31 is the default)."""
    return lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=31,
                              min_child_samples=50, random_state=SEED, verbose=-1)


def predict(df: pd.DataFrame, feature_set: str = "full", outcome: str = "died") -> np.ndarray:
    """Out-of-fold logistic regression predictions for one feature set and outcome."""
    cols = FEATURE_SETS[feature_set]
    return oof_predict(logreg(cols), features(df, cols), df[outcome].to_numpy(),
                       df["permanent_facility_id"].to_numpy())


def fit_all(df: pd.DataFrame, outcome: str = "died") -> dict[str, np.ndarray]:
    """Logistic regression for every feature set, plus LightGBM on the full set only
    (the LightGBM check is about model flexibility, not about features)."""
    preds = {f"lr_{name}": predict(df, name, outcome) for name in FEATURE_SETS}
    cols = FEATURE_SETS["full"]
    preds["lgbm_full"] = oof_predict(lgbm, features(df, cols).astype("category"),
                                     df[outcome].to_numpy(), df["permanent_facility_id"].to_numpy())
    return preds


def calibration_stats(y, p) -> dict[str, float]:
    """Calibration as two numbers, from a logistic regression of the outcome on logit(p).
    - intercept (calibration-in-the-large): ~0 means not too high or low overall
    - slope: ~1 means not too extreme (<1) or too timid (>1)"""
    p = np.clip(p, 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p))
    slope = sm.GLM(y, sm.add_constant(logit), family=sm.families.Binomial()).fit().params[1]
    # Intercept with the slope fixed at 1 (logit(p) as an offset)
    intercept = sm.GLM(y, np.ones_like(logit), family=sm.families.Binomial(),
                       offset=logit).fit().params[0]
    return {"cal_intercept": intercept, "cal_slope": slope}


def metrics_table(y, preds: dict[str, np.ndarray]) -> pd.DataFrame:
    """Discrimination (AUROC, AUPRC), overall accuracy of the probabilities (Brier),
    and calibration. Calibration matters most here: E is a sum of probabilities."""
    rows = [{"model": name, "auroc": roc_auc_score(y, p),
             "auprc": average_precision_score(y, p), "brier": brier_score_loss(y, p),
             **calibration_stats(y, p)}
            for name, p in preds.items()]
    return pd.DataFrame(rows).round(4)


def plot_calibration(y, preds: dict[str, np.ndarray], path, models=("lr_full", "lgbm_full")) -> None:
    fig, ax = plt.subplots(figsize=(5, 5))
    # Bin patients into deciles of predicted risk; compare mean predicted vs observed
    for name in models:
        frac, mean = calibration_curve(y, preds[name], n_bins=10, strategy="quantile")
        ax.plot(mean, frac, marker="o", label=name)
    # Perfect calibration falls on the diagonal
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set(xlabel="Predicted mortality", ylabel="Observed mortality",
           title="Calibration (out-of-fold, deciles)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def odds_ratios(df: pd.DataFrame, cols: list[str], outcome: str = "died",
                min_count: int = 50) -> pd.DataFrame:
    """Unpenalized logistic regression with 95% CIs, as odds ratios against each
    feature's reference level. Correlated features (severity and ROM) share credit,
    so read their odds ratios together, not one at a time.

    Categories with fewer than min_count patients (e.g. gender "U", 2 patients) are
    dropped for this fit only: they can't be estimated and break the CIs."""
    data = features(df, cols).assign(**{outcome: df[outcome].to_numpy()})
    keep = np.ones(len(data), dtype=bool)
    for c in cols:
        counts = data[c].map(data[c].value_counts())
        keep &= (counts >= min_count).to_numpy()
    data = data[keep]

    terms = [f"C({c}, Treatment({REFERENCE[c]!r}))" for c in cols]
    fit = smf.logit(f"{outcome} ~ " + " + ".join(terms), data=data).fit(disp=False)
    ci = fit.conf_int()
    table = pd.DataFrame({"odds_ratio": np.exp(fit.params), "ci_low": np.exp(ci[0]),
                          "ci_high": np.exp(ci[1]), "p_value": fit.pvalues}).drop("Intercept")

    # "C(age_group, Treatment('18 to 29'))[T.70 or Older]" -> ("age_group", "70 or Older")
    parsed = [re.match(r"C\((\w+),.*\)\[T\.(.*)\]", t).groups() for t in table.index]
    table.index = pd.MultiIndex.from_tuples(parsed, names=["feature", "level"])
    table.attrs["rows_dropped"] = int((~keep).sum())
    return table.round(4)
