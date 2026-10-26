import pandas as pd
import pytest

from analysis import prices


def test_cross_check_flags_gaps_above_half_a_point():
    ours = pd.Series({2021: 0.100, 2022: -0.200, 2023: 0.050})
    reference = pd.DataFrame({"year": [2021, 2022, 2023], "total_return": [0.098, -0.190, 0.050]})
    out = prices.cross_check(ours, reference)
    # Gaps: +0.2 pp (ok), -1.0 pp (flag), 0 (ok).
    assert out["mismatch"].tolist() == [False, True, False]
    assert out.loc[2022, "gap"] == pytest.approx(-0.01)
