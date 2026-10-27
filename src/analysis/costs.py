"""Trading cost per side, built from documented components in reference/trading_costs.csv.

cost = half the ETF's published median bid-ask spread + broker and regulatory fees at the
trade size. Rows marked to_verify are excluded unless include_unverified is set.
"""

import pandas as pd

from analysis.config import REFERENCE


def load_schedule(include_unverified: bool = False) -> pd.DataFrame:
    df = pd.read_csv(REFERENCE / "trading_costs.csv")
    return df if include_unverified else df[df["status"] == "verified"]


def fee_usd(rows: pd.DataFrame, trade_value: float, price: float, side: str) -> float:
    """Sum of fees for one order: per-share or percentage rates, each with its minimum."""
    shares = trade_value / price
    total = 0.0
    for row in rows.itertuples():
        if row.side not in ("both", side) or pd.isna(row.rate):
            continue
        base = shares if row.per == "share" else trade_value
        total += max(row.rate * base, 0 if pd.isna(row.minimum_usd) else row.minimum_usd)
    return total


def cost_per_side(
    trade_value: float, price: float, half_spread: float, fee_rows: pd.DataFrame, side: str
) -> float:
    """Cost of one order as a fraction of trade value."""
    return half_spread + fee_usd(fee_rows, trade_value, price, side) / trade_value
