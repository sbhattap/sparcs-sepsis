"""Flag direction and the within-hospital fairness check on hand-made data."""

import numpy as np
import pandas as pd

from sparcs.checks import calibration_by_race, direction


def test_direction_counts_99_8_as_95():
    flags = pd.Series(["high (99.8%)", "high (95%)", "low (95%)", "within"])
    assert direction(flags, "95%").tolist() == ["high", "high", "low", "within"]
    assert direction(flags, "99.8%").tolist() == ["high", "within", "within", "within"]


def test_race_gap_explained_by_hospital():
    # Hospital A has twice the expected deaths for everyone; hospital B is as expected.
    # Group X is mostly treated at A, so its overall O/E is high, but within each
    # hospital it does exactly as well as group Y.
    rows = []
    for hospital, deaths_per_10, n_x, n_y in [("A", 2, 80, 20), ("B", 1, 20, 80)]:
        for race, n in [("X", n_x), ("Y", n_y)]:
            died = ([1] * deaths_per_10 + [0] * (10 - deaths_per_10)) * (n // 10)
            rows += [(hospital, hospital, race, d) for d in died]
    df = pd.DataFrame(rows, columns=["permanent_facility_id", "facility_name", "race", "died"])
    p = np.full(len(df), 0.1)

    t = calibration_by_race(df, p)
    assert t.loc["X", "oe"] > t.loc["Y", "oe"]
    assert np.allclose(t["oe_within_hospital"], 1.0)
