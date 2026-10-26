"""Core performance and risk metrics. Every function here should have a test."""

import numpy as np
import pandas as pd

from analysis.config import TRADING_DAYS


def simple_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Period-over-period simple returns; first row dropped."""
    return prices.pct_change().iloc[1:]


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


def max_drawdown(returns: pd.Series) -> float:
    """Largest peak-to-trough decline of the cumulative return path, as a negative decimal."""
    wealth = (1 + returns).cumprod()
    peak = wealth.cummax()
    return float((wealth / peak - 1).min())
