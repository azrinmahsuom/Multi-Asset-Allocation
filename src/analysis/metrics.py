"""Core performance and risk metrics. Every function here should have a test."""

import numpy as np
import pandas as pd

from analysis.config import TRADING_DAYS


def simple_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Period-over-period simple returns; first row dropped."""
    return prices.pct_change().iloc[1:]


def total_returns_from_distributions(close: pd.Series, dividend: pd.Series) -> pd.Series:
    """Period total returns from a split-adjusted close and cash distributions on ex-dates.

    r_t = (close_t + dividend_t) / close_{t-1} - 1, i.e. the distribution is reinvested at
    the ex-date close. First row dropped.
    """
    return ((close + dividend.fillna(0)) / close.shift(1) - 1).iloc[1:]


def annualised_return(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Geometric annualised return from periodic simple returns."""
    growth = (1 + returns).prod()
    years = len(returns) / periods_per_year
    return float(growth ** (1 / years) - 1)


def annualised_volatility(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Annualised standard deviation of periodic returns."""
    return float(returns.std(ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(
    returns: pd.Series, risk_free_annual: float = 0.0, periods_per_year: int = TRADING_DAYS
) -> float:
    """Annualised Sharpe ratio. risk_free_annual is a decimal (0.03 = 3%)."""
    rf_period = (1 + risk_free_annual) ** (1 / periods_per_year) - 1
    excess = returns - rf_period
    return float(excess.mean() / excess.std(ddof=1) * np.sqrt(periods_per_year))


def sortino_ratio(
    returns: pd.Series, risk_free_annual: float = 0.0, periods_per_year: int = TRADING_DAYS
) -> float:
    """Annualised Sortino ratio: mean excess return over downside deviation below risk-free.

    Downside deviation uses every period (non-negative excess counts as zero), so it is
    sqrt(mean(min(excess, 0)^2)). risk_free_annual is a decimal, converted as in sharpe_ratio.
    """
    rf_period = (1 + risk_free_annual) ** (1 / periods_per_year) - 1
    excess = returns - rf_period
    downside = np.sqrt((excess.clip(upper=0) ** 2).mean())
    return float(excess.mean() / downside * np.sqrt(periods_per_year))


def max_drawdown(returns: pd.Series) -> float:
    """Largest peak-to-trough decline of the cumulative return path, as a negative decimal."""
    wealth = (1 + returns).cumprod()
    peak = wealth.cummax()
    return float((wealth / peak - 1).min())


def recovery_periods(returns: pd.Series) -> int | None:
    """Periods from the trough of the maximum drawdown back to its previous peak.

    The starting wealth of 1 counts as a peak. Returns None if the peak is never regained.
    """
    wealth = pd.concat([pd.Series([1.0]), (1 + returns).cumprod()], ignore_index=True)
    drawdown = wealth / wealth.cummax() - 1
    trough = int(drawdown.idxmin())
    peak_level = wealth.iloc[: trough + 1].max()
    recovered = wealth.iloc[trough:][wealth.iloc[trough:] >= peak_level]
    return int(recovered.index[0] - trough) if len(recovered) else None


def rolling_annualised(returns: pd.Series, years: int, periods_per_year: int) -> pd.Series:
    """Annualised return over each rolling window of `years`, labelled by the window's end.

    A window containing any missing period is missing, so gaps are never bridged.
    """
    window = years * periods_per_year
    log_growth = np.log1p(returns).rolling(window, min_periods=window).sum()
    return np.expm1(log_growth / years).dropna()


def worst_rolling_return(returns: pd.Series, years: int, periods_per_year: int) -> float:
    """Worst annualised return over any rolling window of `years` (overlapping windows)."""
    window = years * periods_per_year
    if len(returns) < window:
        raise ValueError(f"Need at least {window} periods for a {years}-year window.")
    return float(rolling_annualised(returns, years, periods_per_year).min())


def par_bond_return(
    yield_start: pd.Series, yield_end: pd.Series, maturity_years: float, months: int = 1
) -> pd.Series:
    """Total return of a constant-maturity government bond built from yields (decimals).

    Buy a par bond at the start yield (coupon = that yield, paid semi-annually), hold it for
    `months`, then price it at the end yield with maturity shortened by the holding period.
    Return = end price + coupon accrued - 1. With unchanged yields this is exactly the coupon
    accrued (yield * months / 12).
    """
    coupon = yield_start
    periods = 2 * (maturity_years - months / 12)
    half = yield_end / 2
    discount = (1 + half) ** (-periods)
    price = coupon / yield_end * (1 - discount) + discount
    return price + coupon * months / 12 - 1


def real_returns(nominal: pd.Series, inflation: pd.Series) -> pd.Series:
    """Real returns from nominal returns and same-period inflation: (1 + r) / (1 + pi) - 1."""
    return (1 + nominal) / (1 + inflation) - 1


def to_base_currency(local: pd.Series, fx_change: pd.Series) -> pd.Series:
    """Unhedged return in the investor's currency.

    fx_change is the period change in the value of the asset's currency measured in the base
    currency (positive when the foreign currency appreciates): (1 + r_local)(1 + fx) - 1.
    """
    return (1 + local) * (1 + fx_change) - 1


def turnover(weights_before: pd.Series, weights_after: pd.Series) -> float:
    """One-way turnover of a rebalance: half the sum of absolute weight changes."""
    return float((weights_after - weights_before).abs().sum() / 2)
