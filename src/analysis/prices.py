"""ETF price history behind a swappable PriceSource interface.

Analysis code only calls PRICE_SOURCE.read() and the functions here, never yfinance directly,
so the provider can be replaced by writing another PriceSource. Raw pulls are cached in
data/raw/<source>/ and recorded in the manifest by analysis.sources, like every other file.
"""

from pathlib import Path
from typing import Protocol

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


def cross_check(
    annual_total_return: pd.Series, reference: pd.DataFrame, tolerance: float = 0.005
) -> pd.DataFrame:
    """Compare our calendar-year total returns with issuer-published ones.

    reference has columns year and total_return (decimals) for one ETF. Returns every
    compared year with the gap and a flag where |gap| > tolerance (0.005 = 0.5 pp).
    """
    ours = annual_total_return.rename("ours")
    ours.index = ours.index.astype(int)
    joined = reference.set_index("year")[["total_return"]].join(ours, how="inner")
    joined["gap"] = joined["ours"] - joined["total_return"]
    joined["mismatch"] = joined["gap"].abs() > tolerance
    return joined
