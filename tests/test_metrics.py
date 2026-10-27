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


def test_hedged_return_adds_rate_differential():
    # 1% foreign return, SGD rate 0.3%/month, USD rate 0.4%/month -> 0.9% hedged.
    out = metrics.hedged_return(pd.Series([0.01]), pd.Series([0.003]), pd.Series([0.004]))
    assert out.tolist() == pytest.approx([0.009])


def test_par_bond_return_handles_zero_end_yield():
    # Coupon 1%, 2 years, held 6 months, yield falls to 0: remaining 3 half-year coupons of
    # 0.5 plus 100 principal, undiscounted -> price 101.5; return = 1.015 + 0.005 - 1.
    out = metrics.par_bond_return(pd.Series([0.01]), pd.Series([0.0]), 2, months=6)
    assert out.iloc[0] == pytest.approx(1.015 + 0.005 - 1)


def test_par_bond_duration_closed_form():
    # 2-year par bond, 4% coupon: cash flows 2,2,2,102 at 2% per half-year.
    times = [0.5, 1.0, 1.5, 2.0]
    pv = [2 / 1.02, 2 / 1.02**2, 2 / 1.02**3, 102 / 1.02**4]
    macaulay = sum(t * v for t, v in zip(times, pv, strict=True)) / sum(pv)
    assert metrics.par_bond_duration(0.04, 2) == pytest.approx(macaulay / 1.02)
    assert metrics.par_bond_duration(0.0, 7) == 7


def test_maturity_for_duration_on_flat_curve():
    m = metrics.maturity_for_duration(5.0, lambda _m: 0.03)
    assert metrics.par_bond_duration(0.03, m) == pytest.approx(5.0)


def test_cvar_mean_of_worst_tail():
    x = np.arange(1, 21) / 100  # 0.01 ... 0.20
    # 5% of 20 = 1 outcome: the worst, 0.01. 10% of 20 = 2: mean(0.01, 0.02) = 0.015.
    assert metrics.cvar(x, 0.05) == pytest.approx(0.01)
    assert metrics.cvar(x, 0.10) == pytest.approx(0.015)
    # 5% of 30 rounds up to 2 outcomes.
    assert metrics.cvar(np.arange(30.0), 0.05) == pytest.approx(0.5)


def test_constant_duration_returns_flat_yields_earn_coupon():
    idx = pd.period_range("2000-01", periods=3, freq="M")
    out = metrics.constant_duration_returns(pd.Series([0.06, 0.06, 0.06], index=idx), 5.0)
    assert list(out.index) == list(idx[1:])
    assert out.to_numpy() == pytest.approx([0.005, 0.005])  # 6% / 12


def test_constant_duration_returns_caps_at_30_years():
    idx = pd.period_range("2000-01", periods=2, freq="M")
    # At 20%, a 30-year par bond's duration is about 5, below the 8-year target: use 30 years.
    out = metrics.constant_duration_returns(pd.Series([0.20, 0.20], index=idx), 8.0)
    assert metrics.par_bond_duration(0.20, 30.0) < 8.0
    assert out.iloc[0] == pytest.approx(0.20 / 12)
