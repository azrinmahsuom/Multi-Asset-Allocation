"""Loading and cleaning data. Replace the stubs with your project's sources."""

import pandas as pd

from analysis.config import DATA_PROCESSED, DATA_RAW


def load_prices(filename: str = "prices.csv") -> pd.DataFrame:
    """Load a wide price table (index: date, columns: tickers) from data/raw."""
    path = DATA_RAW / filename
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run the download step first.")
    return pd.read_csv(path, index_col=0, parse_dates=True)


def save_processed(df: pd.DataFrame, filename: str) -> None:
    """Write an analysis-ready table to data/processed."""
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_PROCESSED / filename)
