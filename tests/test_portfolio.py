import pandas as pd
import pytest

from analysis import portfolio

MONTHS = pd.period_range("2024-01", periods=2, freq="M")
RETURNS = pd.DataFrame({"eq": [0.10, 0.0], "bd": [0.0, 0.0]}, index=MONTHS)
TARGET = pd.Series({"eq": 0.5, "bd": 0.5})


def test_never_rebalance_drifts():
    # 50/50, equity +10%: portfolio +5%, equity weight 0.55 / 1.05.
    out = portfolio.simulate(RETURNS, TARGET, {"type": "never"})
    assert out["gross"].iloc[0] == pytest.approx(0.05)
    assert out["w_eq"].iloc[0] == pytest.approx(0.55 / 1.05)
    assert not out["rebalanced"].any()


def test_monthly_rebalance_with_costs():
    # Rebalance after month 1: sell eq and buy bd by 0.55/1.05 - 0.5 each; 1% cost per side.
    trade = 0.55 / 1.05 - 0.5
    out = portfolio.simulate(
        RETURNS, TARGET, {"type": "calendar", "months": 1}, lambda a, v, s: 0.01
    )
    assert out["turnover"].iloc[0] == pytest.approx(trade)
    assert out["cost"].iloc[0] == pytest.approx(2 * trade * 0.01)
    assert out["net"].iloc[0] == pytest.approx(1.05 * (1 - 2 * trade * 0.01) - 1)


def test_threshold_rule_triggers_only_beyond_band():
    small = portfolio.simulate(RETURNS, TARGET, {"type": "threshold", "band": 0.05})
    large = portfolio.simulate(RETURNS, TARGET, {"type": "threshold", "band": 0.01})
    # Drift is 0.0238: beyond a 1-point band, within a 5-point band.
    assert not small["rebalanced"].iloc[0] and large["rebalanced"].iloc[0]


def test_calendar_or_threshold_triggers_on_either():
    months = pd.period_range("2024-11", periods=2, freq="M")  # November, December
    returns = pd.DataFrame({"eq": [0.0, 0.0], "bd": [0.0, 0.0]}, index=months)
    rule = {"type": "calendar_or_threshold", "months": 12, "band": 0.10}
    out = portfolio.simulate(returns, TARGET, rule)
    # No drift: November does not trigger, December does (calendar).
    assert out["rebalanced"].tolist() == [False, True]
    big = pd.DataFrame({"eq": [0.6, 0.0], "bd": [0.0, 0.0]}, index=months)
    # Equity +60% in November: weight 0.8/1.3 = 0.615, more than 10 points over 0.5 -> trigger.
    assert portfolio.simulate(big, TARGET, rule)["rebalanced"].iloc[0]
