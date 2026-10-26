import pandas as pd
import pytest

from analysis import metrics


def test_simple_returns():
    prices = pd.Series([100.0, 110.0, 99.0])
    assert metrics.simple_returns(prices).tolist() == pytest.approx([0.10, -0.10])


def test_annualised_return_one_year_of_monthly():
    # 12 months of 1% -> (1.01^12 - 1)
    rets = pd.Series([0.01] * 12)
    assert metrics.annualised_return(rets, periods_per_year=12) == pytest.approx(1.01**12 - 1)


def test_max_drawdown():
    # 100 -> 120 -> 90 -> 130: trough 90 from peak 120 = -25%
    rets = pd.Series([0.20, -0.25, 130 / 90 - 1])
    assert metrics.max_drawdown(rets) == pytest.approx(-0.25)


def test_sharpe_is_finite():
    rets = pd.Series([0.01, -0.005, 0.02, 0.0])
    assert pd.notna(metrics.sharpe_ratio(rets, periods_per_year=12))
