import numpy as np
import pandas as pd
import pytest

from analysis import metrics


def test_simple_returns():
    prices = pd.Series([100.0, 110.0, 99.0])
    assert metrics.simple_returns(prices).tolist() == pytest.approx([0.10, -0.10])


def test_total_returns_from_distributions():
    # 100 -> 98 with a 3.00 distribution on the ex-date: (98 + 3) / 100 - 1 = 1%.
    # Then 98 -> 99 with no distribution: 99 / 98 - 1.
    close = pd.Series([100.0, 98.0, 99.0])
    dividend = pd.Series([0.0, 3.0, 0.0])
    out = metrics.total_returns_from_distributions(close, dividend)
    assert out.tolist() == pytest.approx([0.01, 99 / 98 - 1])


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


def test_sharpe_reconciles_with_inputs():
    # rf 12.6825% p.a. -> exactly 1% per month (1.01^12 - 1).
    # Excess returns: 0.02, 0.00, 0.03, -0.01 -> mean 0.01, sample sd = sqrt(0.001/3).
    rf = 1.01**12 - 1
    rets = pd.Series([0.03, 0.01, 0.04, 0.0])
    expected = 0.01 / (0.001 / 3) ** 0.5 * 12**0.5
    assert metrics.sharpe_ratio(rets, risk_free_annual=rf, periods_per_year=12) == pytest.approx(
        expected
    )


def test_sortino_by_hand():
    # Zero rf. Downside: only -0.02 below 0 -> sqrt(0.0004 / 4) = 0.01. Mean 0.01.
    rets = pd.Series([0.02, -0.02, 0.03, 0.01])
    assert metrics.sortino_ratio(rets, periods_per_year=12) == pytest.approx(0.01 / 0.01 * 12**0.5)


def test_recovery_periods():
    # Wealth 1 -> 1.2 -> 0.9 -> 1.0 -> 1.2: trough at 0.9, back to 1.2 two periods later.
    rets = pd.Series([0.20, -0.25, 1.0 / 0.9 - 1, 0.20])
    assert metrics.recovery_periods(rets) == 2


def test_recovery_periods_never_recovered():
    rets = pd.Series([0.10, -0.50, 0.10])
    assert metrics.recovery_periods(rets) is None


def test_worst_rolling_return():
    # Annual returns; 2-year windows: 1.1*0.8=0.88, 0.8*1.25=1.0. Worst = 0.88^(1/2) - 1.
    rets = pd.Series([0.10, -0.20, 0.25])
    assert metrics.worst_rolling_return(rets, years=2, periods_per_year=1) == pytest.approx(
        0.88**0.5 - 1
    )


def test_rolling_annualised_skips_windows_with_gaps():
    # 2-year windows on annual data: (1.1*0.8)^(1/2)-1 ends 2001; 2002 is missing, so the
    # windows ending 2002 and 2003 are missing; 2003-2004: (1.25*1.0)^(1/2)-1.
    rets = pd.Series([0.10, -0.20, np.nan, 0.25, 0.0], index=[2000, 2001, 2002, 2003, 2004])
    out = metrics.rolling_annualised(rets, years=2, periods_per_year=1)
    assert list(out.index) == [2001, 2004]
    assert out.tolist() == pytest.approx([0.88**0.5 - 1, 1.25**0.5 - 1])


def test_par_bond_return_unchanged_yield_earns_the_coupon():
    out = metrics.par_bond_return(pd.Series([0.05]), pd.Series([0.05]), maturity_years=10)
    assert out.iloc[0] == pytest.approx(0.05 / 12)


def test_par_bond_return_matches_hand_price():
    # 2-year bond, coupon 4% (semi-annual 2%), held 6 months, yield rises to 6%:
    # 3 coupons of 2 left, discounted at 3% per half-year, plus principal.
    # Price = 2/1.03 + 2/1.03^2 + 102/1.03^3; return = price/100 + 0.02 - 1.
    price = (2 / 1.03 + 2 / 1.03**2 + 102 / 1.03**3) / 100
    out = metrics.par_bond_return(pd.Series([0.04]), pd.Series([0.06]), 2, months=6)
    assert out.iloc[0] == pytest.approx(price + 0.02 - 1)


def test_real_returns():
    # 10% nominal with 10% inflation is 0% real; 5% with 0% inflation stays 5%.
    out = metrics.real_returns(pd.Series([0.10, 0.05]), pd.Series([0.10, 0.0]))
    assert out.tolist() == pytest.approx([0.0, 0.05])


def test_to_base_currency():
    # 10% local return, foreign currency falls 10% vs SGD: 1.1 * 0.9 - 1 = -1%.
    out = metrics.to_base_currency(pd.Series([0.10]), pd.Series([-0.10]))
    assert out.tolist() == pytest.approx([-0.01])


def test_turnover():
    # 60/40 drifted to 70/30, rebalanced back: 10% one-way.
    before = pd.Series({"eq": 0.7, "bd": 0.3})
    after = pd.Series({"eq": 0.6, "bd": 0.4})
    assert metrics.turnover(before, after) == pytest.approx(0.10)
