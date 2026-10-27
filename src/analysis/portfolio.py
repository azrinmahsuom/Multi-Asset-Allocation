"""Portfolio simulation with drift, rebalancing rules and trading costs.

Rebalancing rules (dicts):
- {"type": "never"}: buy and hold from the target weights.
- {"type": "calendar", "months": k}: rebalance at the end of every k-th calendar month
  (k = 1 monthly, 3 quarterly at Mar/Jun/Sep/Dec, 12 annually in December).
- {"type": "threshold", "band": b}: rebalance at a month-end when any weight is more than b
  (absolute, e.g. 0.05 = 5 percentage points) away from its target.
- {"type": "calendar_or_threshold", "months": k, "band": b}: either condition triggers.
Costs: each leg of a rebalance pays cost_fraction(asset, trade_value, side) on the traded value,
with trade values evaluated at a fixed portfolio value (the minimum allocation).
"""

from collections.abc import Callable

import numpy as np
import pandas as pd

CostFn = Callable[[str, float, str], float]


def _should_rebalance(
    rule: dict, month: pd.Period, weights: np.ndarray, target: np.ndarray
) -> bool:
    if rule["type"] == "never":
        return False
    if rule["type"] == "calendar":
        return month.month % rule["months"] == 0
    if rule["type"] == "threshold":
        return bool(np.max(np.abs(weights - target)) > rule["band"])
    if rule["type"] == "calendar_or_threshold":
        calendar = month.month % rule["months"] == 0
        return calendar or bool(np.max(np.abs(weights - target)) > rule["band"])
    raise ValueError(f"Unknown rule {rule}")


def simulate(
    returns: pd.DataFrame,
    target: pd.Series,
    rule: dict,
    cost_fraction: CostFn | None = None,
    portfolio_value: float = 25_000.0,
) -> pd.DataFrame:
    """Monthly portfolio returns, net of trading costs, with weights drifting between trades.

    returns: monthly simple returns, one column per asset (no missing values).
    target: target weights summing to 1, indexed like returns' columns.
    Initial purchase costs are ignored (they are the same for every rule).
    """
    assets = list(returns.columns)
    tgt = target.reindex(assets).to_numpy(dtype=float)
    w = tgt.copy()
    rows = []
    for month, r in zip(returns.index, returns.to_numpy(dtype=float), strict=True):
        gross = float(w @ r)
        drifted = w * (1 + r) / (1 + gross)
        cost = turnover = 0.0
        rebalanced = _should_rebalance(rule, month, drifted, tgt)
        if rebalanced:
            trades = tgt - drifted
            turnover = float(np.abs(trades).sum() / 2)
            if cost_fraction is not None:
                for asset, trade in zip(assets, trades, strict=True):
                    if trade != 0:
                        value = abs(trade) * portfolio_value
                        side = "buy" if trade > 0 else "sell"
                        cost += abs(trade) * cost_fraction(asset, value, side)
            w = tgt.copy()
        else:
            w = drifted
        rows.append(
            {
                "gross": gross,
                "cost": cost,
                "net": (1 + gross) * (1 - cost) - 1,
                "rebalanced": rebalanced,
                "turnover": turnover,
                **{f"w_{a}": wi for a, wi in zip(assets, drifted, strict=True)},
            }
        )
    return pd.DataFrame(rows, index=returns.index)


def cash_flow_split(values: np.ndarray, target: np.ndarray, flow: float) -> np.ndarray:
    """Split a contribution across sleeves: in proportion to each sleeve's shortfall from
    target (target x value after the flow, minus current value, floored at 0), capped at the
    shortfall; any remainder by target weights."""
    shortfall = np.maximum(target * (values.sum() + flow) - values, 0.0)
    total = shortfall.sum()
    if total >= flow:
        return flow * shortfall / total if total > 0 else flow * target
    return shortfall + (flow - total) * target


def simulate_cash_flows(
    returns: pd.DataFrame,
    target: pd.Series,
    rule: dict,
    cost_fraction: CostFn | None,
    start_value: float,
    contribution: float = 0.0,
    contribution_month: int = 12,
) -> pd.DataFrame:
    """Monthly time-weighted returns net of costs, tracking the portfolio's value.

    Each month-end: returns accrue; in contribution_month a contribution arrives. With
    rule {"type": "threshold", "band": b} the contribution is split by cash_flow_split and all
    sleeves trade back to target if any weight is then more than b from target. With any
    other rule the contribution is added and _should_rebalance decides a full rebalance (a
    contribution month with no rebalance invests the contribution at target weights). Orders
    are netted per sleeve and each pays cost_fraction at its actual size; costs are deducted
    pro rata. Net return = (value after costs - contribution) / value at the start - 1.
    """
    assets = list(returns.columns)
    tgt = target.reindex(assets).to_numpy(dtype=float)
    values = tgt * start_value
    rows = []
    for month, r in zip(returns.index, returns.to_numpy(dtype=float), strict=True):
        start = values.sum()
        values = values * (1 + r)
        pre = values.copy()
        flow = contribution if month.month == contribution_month else 0.0
        if rule["type"] == "threshold":
            after = pre + (cash_flow_split(pre, tgt, flow) if flow else 0.0)
            rebalance = bool(np.max(np.abs(after / after.sum() - tgt)) > rule["band"])
        else:
            after = pre + flow * tgt
            rebalance = _should_rebalance(rule, month, pre / pre.sum(), tgt)
        if rebalance:
            after = tgt * after.sum()
        orders = after - pre
        cost = 0.0
        if cost_fraction is not None:
            for asset, order in zip(assets, orders, strict=True):
                if abs(order) > 1e-9:
                    side = "buy" if order > 0 else "sell"
                    cost += abs(order) * cost_fraction(asset, abs(order), side)
        total = after.sum()
        values = after * (1 - cost / total)
        rows.append(
            {
                "net": (values.sum() - flow) / start - 1,
                "cost": cost / start,
                "turnover": float(np.abs(orders).sum() / 2 / pre.sum()),
                "orders": int((np.abs(orders) > 1e-9).sum()),
                "value": values.sum(),
            }
        )
    return pd.DataFrame(rows, index=returns.index)
