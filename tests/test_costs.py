import pandas as pd
import pytest

from analysis import costs

ROWS = pd.DataFrame(
    {
        "rate": [0.0049, 0.005, 0.0000206],
        "per": ["share", "share", "trade_value"],
        "minimum": [0.99, 1.00, 0.01],
        "currency": ["USD", "USD", "USD"],
        "min_trade_value": [None, None, None],
        "gst": ["no", "no", "no"],
        "side": ["both", "both", "sell"],
    }
)


def test_fee_usd_applies_minimums_and_sides():
    # 100 shares at $100 = $10,000. Commission 0.49 -> min 0.99; platform 0.50 -> min 1.00.
    assert costs.fee_usd(ROWS, 10_000, 100, "buy") == pytest.approx(1.99)
    # Sell adds the SEC fee: 0.206 (above its 0.01 minimum).
    assert costs.fee_usd(ROWS, 10_000, 100, "sell") == pytest.approx(1.99 + 0.206)


def test_cost_per_side_adds_half_spread():
    # Half spread 0.5 bp plus $1.99 on $10,000 (1.99 bp) = 2.49 bp.
    out = costs.cost_per_side(10_000, 100, 0.00005, ROWS, "buy")
    assert out == pytest.approx(0.00005 + 1.99 / 10_000)


def test_fee_usd_gst_currency_and_order_threshold(monkeypatch):
    monkeypatch.setattr(costs, "usd_per_unit", lambda c: {"USD": 1.0, "GBP": 1.25}[c])
    rows = pd.DataFrame(
        {
            "rate": [0.003, 1.50],
            "per": ["trade_value", "order"],
            "minimum": [40.0, 0.0],
            "currency": ["GBP", "GBP"],
            "min_trade_value": [None, 10_000.0],
            "gst": ["yes", "no"],
            "side": ["both", "both"],
        }
    )
    # $10,000: 0.3% = $30, below the GBP 40 = $50 minimum; +10% GST = $55. Levy needs
    # GBP 10,000 = $12,500, so it does not apply.
    assert costs.fee_usd(rows, 10_000, 100, "buy", gst=0.10) == pytest.approx(55.0)
    # $20,000: 0.3% = $60 (+GST = $66) plus the GBP 1.50 = $1.875 levy.
    assert costs.fee_usd(rows, 20_000, 100, "buy", gst=0.10) == pytest.approx(66.0 + 1.875)


def test_half_spread_from_quote_and_median(monkeypatch):
    snap = pd.DataFrame(
        {"bid": [99.0, None], "ask": [101.0, None], "median_spread": [None, 0.0002]},
        index=["Q", "M"],
    )
    monkeypatch.setattr(costs, "spread_snapshot", lambda: snap)
    assert costs.half_spread("Q") == pytest.approx(0.01)  # (101-99)/100/2
    assert costs.half_spread("M") == pytest.approx(0.0001)
