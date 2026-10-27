import pandas as pd
import pytest

from analysis import stats


def test_block_annualised_drops_incomplete_block():
    # Annual data, 2-year blocks: (1.1 * 1.2)^(1/2) - 1 and (0.9 * 1.0)^(1/2) - 1; 5th year dropped.
    r = pd.Series([0.1, 0.2, -0.1, 0.0, 0.5], index=[2000, 2001, 2002, 2003, 2004])
    out = stats.block_annualised(r, years=2, periods_per_year=1)
    assert list(out.index) == ["2000–2001", "2002–2003"]
    assert out.tolist() == pytest.approx([(1.1 * 1.2) ** 0.5 - 1, 0.9**0.5 - 1])


def test_hac_mean_test_mean_and_sign():
    r = pd.Series([0.01, 0.02, 0.03, 0.02] * 10)
    out = stats.hac_mean_test(r)
    assert out["mean"] == pytest.approx(0.02) and out["t_stat"] > 0


def test_newey_west_lags():
    assert stats.newey_west_lags(100) == 4
