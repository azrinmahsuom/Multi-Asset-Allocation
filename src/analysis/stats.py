"""Small statistical tests shared by the evidence modules."""

import numpy as np
import pandas as pd
import statsmodels.api as sm


def newey_west_lags(n: int) -> int:
    """Rule-of-thumb lag length floor(4 (n/100)^(2/9)) for HAC standard errors."""
    return int(np.floor(4 * (n / 100) ** (2 / 9)))


def hac_mean_test(series: pd.Series) -> dict:
    """Mean of a series with a HAC (Newey-West) t-statistic and two-sided p-value."""
    y = series.dropna().to_numpy()
    fit = sm.OLS(y, np.ones(len(y))).fit(
        cov_type="HAC", cov_kwds={"maxlags": newey_west_lags(len(y))}
    )
    return {
        "mean": float(fit.params[0]),
        "t_stat": float(fit.tvalues[0]),
        "p_value": float(fit.pvalues[0]),
    }


def block_annualised(returns: pd.Series, years: int, periods_per_year: int) -> pd.Series:
    """Annualised return in consecutive non-overlapping blocks of `years`, from the first period.

    An incomplete final block is dropped. Labelled 'start–end'.
    """
    r = returns.dropna()
    size = years * periods_per_year
    out = {}
    for b in range(len(r) // size):
        part = r.iloc[b * size : (b + 1) * size]
        out[f"{part.index[0]}–{part.index[-1]}"] = float((1 + part).prod() ** (1 / years) - 1)
    return pd.Series(out)
