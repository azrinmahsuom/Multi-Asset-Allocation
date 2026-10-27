"""Trading cost per side, built from documented components in reference/.

cost = half the bid-ask spread (reference/spread_snapshot.csv) + broker and exchange fees at
the trade size (reference/trading_costs.csv), with Singapore GST on rows marked gst=yes.
Fee minimums and thresholds are converted to USD with reference/fx_rates.csv. Fee rows marked
to_verify are excluded unless include_unverified is set; spread rows are used whatever their
status, and reports name the ones still to_verify.
"""

import pandas as pd

from analysis.config import REFERENCE


def load_schedule(include_unverified: bool = False) -> pd.DataFrame:
    df = pd.read_csv(REFERENCE / "trading_costs.csv")
    return df if include_unverified else df[df["status"] == "verified"]


def fee_rows(provider: str, market: str, schedule: pd.DataFrame | None = None) -> pd.DataFrame:
    """Broker rows for one provider in one market, plus that market's exchange and regulatory
    rows (every row in the market whose provider is not a broker)."""
    s = load_schedule() if schedule is None else schedule
    fees = s[(s["market"] == market) & s["rate"].notna()]
    broker = fees["provider_or_instrument"].str.startswith(provider)
    shared = fees["provider_or_instrument"].str.contains("exchange fees|levies|regulatory")
    return fees[broker | shared]


def gst_rate(schedule: pd.DataFrame | None = None) -> float:
    s = load_schedule() if schedule is None else schedule
    return float(s.loc[s["component"] == "gst", "rate"].iloc[0])


def usd_per_unit(currency: str) -> float:
    fx = pd.read_csv(REFERENCE / "fx_rates.csv").set_index("currency")
    return float(fx.loc[currency, "usd_per_unit"])


def spread_snapshot() -> pd.DataFrame:
    return pd.read_csv(REFERENCE / "spread_snapshot.csv").set_index("ticker")


def half_spread(ticker: str) -> float:
    """Half the quoted spread relative to the mid price, or half the published median spread."""
    r = spread_snapshot().loc[ticker]
    if pd.notna(r["median_spread"]):
        return float(r["median_spread"]) / 2
    mid = (r["bid"] + r["ask"]) / 2
    return float((r["ask"] - r["bid"]) / mid / 2)


def mid_price_usd(ticker: str) -> float:
    r = spread_snapshot().loc[ticker]
    return float((r["bid"] + r["ask"]) / 2 * usd_per_unit(r["currency"]))


def reference_price(ticker: str) -> float:
    prices = pd.read_csv(REFERENCE / "etf_reference_prices.csv")
    return float(prices.loc[prices["ticker"] == ticker, "price_usd"].iloc[0])


def fee_usd(
    rows: pd.DataFrame, trade_value: float, price: float, side: str, gst: float = 0.0
) -> float:
    """Sum of fees for one order in USD: per-share, per-order or percentage rates, each with its
    minimum (in the row's currency) and, where set, a minimum order size before it applies."""
    shares = trade_value / price
    total = 0.0
    for row in rows.to_dict("records"):
        if row["side"] not in ("both", side) or pd.isna(row["rate"]):
            continue
        fx = usd_per_unit(row.get("currency", "USD"))
        threshold = row.get("min_trade_value")
        if pd.notna(threshold) and trade_value < float(threshold) * fx:
            continue
        minimum = 0.0 if pd.isna(row.get("minimum")) else float(row["minimum"]) * fx
        if row["per"] == "order":
            fee = float(row["rate"]) * fx
        else:
            base = shares if row["per"] == "share" else trade_value
            fee = max(float(row["rate"]) * base, minimum)
        total += fee * (1 + gst if row.get("gst") == "yes" else 1)
    return total


def cost_per_side(
    trade_value: float,
    price: float,
    half_spread: float,
    fee_rows: pd.DataFrame,
    side: str,
    gst: float = 0.0,
) -> float:
    """Cost of one order as a fraction of trade value."""
    return half_spread + fee_usd(fee_rows, trade_value, price, side, gst) / trade_value
