import pandas as pd
import pytest

from analysis import costs

ROWS = pd.DataFrame(
    {
        "rate": [0.0049, 0.005, 0.0000206],
        "per": ["share", "share", "trade_value"],
        "minimum_usd": [0.99, 1.00, 0.01],
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
