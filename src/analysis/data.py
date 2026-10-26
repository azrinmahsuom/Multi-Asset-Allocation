"""Load the analysis-ready tables written by analysis.clean to data/processed."""

import pandas as pd

from analysis.config import DATA_PROCESSED


def _path(name: str):
    path = DATA_PROCESSED / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run: uv run python -m analysis.pipeline clean")
    return path


def monthly(name: str) -> pd.DataFrame:
    """A monthly table, indexed by month period."""
    df = pd.read_csv(_path(name), index_col=0)
    df.index = pd.PeriodIndex(df.index, freq="M", name="month")
    return df


def daily(name: str) -> pd.DataFrame:
    """A daily table, indexed by date."""
    return pd.read_csv(_path(name), index_col=0, parse_dates=True)


def annual(name: str) -> pd.DataFrame:
    """An annual table, indexed by year."""
    return pd.read_csv(_path(name), index_col=0)


def jst() -> pd.DataFrame:
    """JST country-year panel, indexed by (country, year)."""
    return pd.read_csv(_path("jst_annual"), index_col=[0, 1])
