"""ETF price history behind a swappable PriceSource interface.

Analysis code only calls PRICE_SOURCE.read() and the functions here, never yfinance directly,
so the provider can be replaced by writing another PriceSource. Raw pulls are cached in
data/raw/<source>/ and recorded in the manifest by analysis.sources, like every other file.
"""

from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd


class PriceSource(Protocol):
    """A provider of daily ETF history."""

    name: str  # folder under data/raw
    licence: str
    redistributable: bool
    adjustment: str  # how prices and distributions are treated, written to the manifest

    def download(self, ticker: str) -> bytes:
        """Full daily history for one ticker, serialised exactly as it will be cached."""
        ...

    def read(self, path: Path) -> pd.DataFrame:
        """Cached file -> DataFrame indexed by date with columns close, adj_close, dividend."""
        ...


class YFinanceSource:
    """Yahoo Finance via the yfinance package (version pinned in pyproject.toml)."""

    name = "yahoo"
    licence = "Yahoo Finance terms: personal use only. Not redistributable."
    redistributable = False
    adjustment = (
        "auto_adjust=False. close: split-adjusted, not dividend-adjusted. adj_close: Yahoo's "
        "dividend-adjusted close (kept only for cross-checks). dividend: cash per share on the "
        "ex-date. Total return is rebuilt from close + dividend, reinvested at the ex-date close."
    )

    def download(self, ticker: str) -> bytes:
        import yfinance as yf

        history = yf.Ticker(ticker).history(
            period="max", interval="1d", auto_adjust=False, actions=True
        )
        if history.empty:
            raise RuntimeError(f"Yahoo returned no history for {ticker}.")
        history.index = history.index.strftime("%Y-%m-%d")
        history.index.name = "date"
        out = history[["Close", "Adj Close", "Dividends", "Stock Splits"]]
        out.columns = ["close", "adj_close", "dividend", "split"]
        return out.to_csv().encode()

    def read(self, path: Path) -> pd.DataFrame:
        return pd.read_csv(path, index_col="date", parse_dates=True)


PRICE_SOURCE: PriceSource = YFinanceSource()


def describe(path: Path) -> tuple[int, str, str]:
    """Row count and date range of a cached price file, for the manifest."""
    df = pd.read_csv(path, usecols=["date"])
    return len(df), df["date"].iloc[0], df["date"].iloc[-1]


# Iglewicz and Hoaglin (1993), as given in the NIST/SEMATECH e-Handbook of Statistical
# Methods, section 1.3.5.17: flag modified z-scores with absolute value above 3.5.
OUTLIER_THRESHOLD = 3.5
# Issuers publish annual returns to 0.01%: gaps smaller than that cannot be told apart, so the
# MAD is floored at this precision (otherwise identical gaps give MAD = 0, which NIST notes
# leaves the score undefined).
PUBLISHED_PRECISION = 0.0001


def modified_z_scores(x: pd.Series, mad_floor: float = 0.0) -> pd.Series:
    """0.6745 (x - median) / max(MAD, mad_floor). Missing if that denominator is zero."""
    median = x.median()
    mad = max((x - median).abs().median(), mad_floor)
    if mad == 0:
        return pd.Series(np.nan, index=x.index)
    return 0.6745 * (x - median) / mad


def cross_check(ours: dict[str, pd.Series], reference: pd.DataFrame) -> pd.DataFrame:
    """Compare our calendar-year total returns with issuer-published market-price returns.

    ours maps ticker -> calendar-year total returns (index: year). reference has columns
    ticker, year, total_return and basis; only rows with basis 'market_price' are compared,
    because our returns use closing prices, not NAV. Gaps are pooled across all ETF-years and
    flagged as mismatches where |modified z-score| > OUTLIER_THRESHOLD.
    """
    ref = reference[reference["basis"] == "market_price"]
    rows = []
    for ticker, group in ref.groupby("ticker"):
        if ticker not in ours:
            continue
        mine = ours[ticker].rename("ours")
        mine.index = mine.index.astype(int)
        joined = group.set_index("year")[["total_return"]].join(mine, how="inner")
        joined["ticker"] = ticker
        rows.append(joined)
    out = pd.concat(rows).reset_index() if rows else pd.DataFrame()
    if out.empty:
        return out
    out["gap"] = out["ours"] - out["total_return"]
    out["modified_z"] = modified_z_scores(out["gap"], mad_floor=PUBLISHED_PRECISION)
    out["mismatch"] = out["modified_z"].abs() > OUTLIER_THRESHOLD
    return out


RETURN_CHECK_THRESHOLD = 0.005  # per year (owner rule, 2026-10-27)


def period_return_check(
    monthly: pd.DataFrame, issuer: pd.DataFrame, columns: dict[str, str]
) -> pd.DataFrame:
    """Our price-based total return over each issuer-published period (annualised for periods
    longer than a year) against the issuer's NAV return; a mismatch is a gap above
    RETURN_CHECK_THRESHOLD a year. Periods our data do not fully cover are skipped."""
    rows = []
    for r in issuer.to_dict("records"):
        series = monthly[columns[r["ticker"]]].dropna()
        end = r["period_end"]
        start = end - 12 * r["years"] + 1
        window = series.loc[start:end]
        if len(window) < 12 * r["years"] or series.index[0] > start:
            continue
        ours = float(np.prod(1 + window.to_numpy()) ** (1 / r["years"]) - 1)
        gap = ours - r["issuer_return"]
        rows.append(
            {
                **r,
                "ours": ours,
                "gap": gap,
                "mismatch": abs(gap) > RETURN_CHECK_THRESHOLD,
            }
        )
    return pd.DataFrame(rows)
