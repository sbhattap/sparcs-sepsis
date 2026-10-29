"""O/E, limits, CIs and overdispersion on tiny hand-made or simulated data."""

import numpy as np
import pandas as pd
from scipy import stats

from sparcs.benchmark import adjusted_limits, hospital_oe, oe_ci, overdispersion, poisson_limits


def one_hospital(deaths: int, n: int = 100):
    df = pd.DataFrame({"permanent_facility_id": ["H"] * n, "facility_name": ["H"] * n,
                       "died": [1] * deaths + [0] * (n - deaths)})
    return df, np.full(n, 0.1)  # 100 patients at 10% risk -> E = 10


def test_observed_expected_sums():
    # Hospital A: 2 deaths, E = 4 x 0.5 = 2 -> O/E 1. Hospital B: 0 deaths, E = 0.5 -> O/E 0
    df = pd.DataFrame({"permanent_facility_id": ["A"] * 4 + ["B"] * 2,
                       "facility_name": ["Alpha"] * 4 + ["Beta"] * 2,
                       "died": [1, 1, 0, 0, 0, 0]})
    h = hospital_oe(df, [0.5] * 4 + [0.25] * 2).set_index("permanent_facility_id")
    assert h.loc["A", ["n", "observed", "expected", "oe"]].tolist() == [4, 2, 2.0, 1.0]
    assert h.loc["B", "expected"] == 0.5 and h.loc["B", "oe"] == 0.0


def test_poisson_limits_match_scipy():
    lo, hi = poisson_limits([10.0], 0.95)
    assert lo[0] == stats.poisson.ppf(0.025, 10) and hi[0] == stats.poisson.ppf(0.975, 10)


def test_flags():
    # E = 10: 30 deaths is far above the 99.8% limit, 10 deaths is exactly as expected
    assert hospital_oe(*one_hospital(30)).loc[0, "flag"] == "high (99.8%)"
    assert hospital_oe(*one_hospital(10)).loc[0, "flag"] == "within"


def test_adjusted_limits_never_narrower_than_poisson():
    # Tiny E (0.08 expected deaths) is where the normal approximation breaks down
    e = np.array([0.08, 1.0, 10.0, 100.0])
    p_lo, p_hi = poisson_limits(e, 0.998)
    a_lo, a_hi = adjusted_limits(e, 0.998, tau2=0.05)
    assert np.all(a_lo <= p_lo / e) and np.all(a_hi >= p_hi / e)


def test_oe_ci():
    # 10 observed, 10 expected: exact 95% CI for O/E is about 0.48 to 1.84
    lo, hi = oe_ci([10], [10])
    assert np.allclose([lo[0], hi[0]], [0.4795, 1.8390], atol=1e-3)
    # No deaths: the lower limit is 0
    assert oe_ci([0], [5])[0][0] == 0


def test_overdispersion():
    rng = np.random.default_rng(0)
    e = rng.uniform(5, 100, size=2000)
    # Pure Poisson chance: winsorized phi stays below 1, so no extra variance
    od = overdispersion(rng.poisson(e), e)
    assert od["phi"] < 1 and od["tau2"] == 0
    # Hospitals truly differ (true O/E spread with sd 0.3): tau2 clearly above 0
    od = overdispersion(rng.poisson(e * rng.lognormal(0, 0.3, size=e.size)), e)
    assert od["tau2"] > 0.02
