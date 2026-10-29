"""Flag direction and the robust-flag rule on hand-made flags."""

import pandas as pd

from sparcs.checks import direction


def test_direction_counts_99_8_as_95():
    flags = pd.Series(["high (99.8%)", "high (95%)", "low (95%)", "within"])
    assert direction(flags, "95%").tolist() == ["high", "high", "low", "within"]
    assert direction(flags, "99.8%").tolist() == ["high", "within", "within", "within"]
