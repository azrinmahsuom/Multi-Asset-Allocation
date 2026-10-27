"""Robustness checks for the backtest (rules fixed before results were computed).

- Subperiods (index layer): Feb 1998-Dec 2007, the 2008-2009 crisis, 2010-2019, 2020, 2022,
  and 2023 to latest: annualised return and maximum drawdown per strategy and benchmark.
- Rising-rate era: the GDP-weighted global JST portfolio (annual, real USD, bonds hedged),
  1950-1981, the post-war period when US long-term yields rose to their 1981 peak (the end
  year follows claim 6's yield peak), and 1871-2020 for reference.
- Forward outcomes: 2,000 moving-block bootstrap paths (block = n^(1/5) months) of 10 years
  of each strategy's monthly real index-layer returns: 5th, 50th and 95th percentile of the
  annualised real return and the share of paths below zero.
- Parameter grid (index layer, adopted allocation against each profile's limits): equity
  weight -10/+10 points, rebalancing
  band 5/15 points or calendar-only, bond sleeve global hedged or global unhedged instead of
  SGS, trading-cost spreads x2 and x3. Reported against each profile's limits.
- Attribution: each sleeve's contribution to the strategy's return (weight x annualised
  sleeve return) and the change in the 10-year SGS yield over the sample.
"""

import numpy as np
import pandas as pd

from analysis import bootstrap, data, metrics
from analysis.backtest import engine
from analysis.config import BOOTSTRAP_REPS
from analysis.design import allocation, bond_options, holdout

SUBPERIODS = {
    "1998–2007": ("1998-02", "2007-12"),
    "2008–2009": ("2008-01", "2009-12"),
    "2010–2019": ("2010-01", "2019-12"),
    "2020": ("2020-01", "2020-12"),
    "2022": ("2022-01", "2022-12"),
    "2023 to latest": ("2023-01", None),
}
RISING_RATES = (1950, 1981)
HORIZON_YEARS = 10


def subperiods(sims: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Annualised return (cumulative if under a year) and maximum drawdown per subperiod."""
    returns, drawdowns = {}, {}
    for name, sim in sims.items():
        returns[name], drawdowns[name] = {}, {}
        for label, (start, end) in SUBPERIODS.items():
            net = sim["net"].loc[start:end]
            years = len(net) / 12
            growth = float((1 + net).prod())
            returns[name][label] = growth ** (1 / years) - 1 if years >= 1 else growth - 1
            drawdowns[name][f"{label} drawdown"] = metrics.max_drawdown(net)
    return pd.DataFrame(returns).T.join(pd.DataFrame(drawdowns).T)


def rising_rate_era(weights: dict[str, pd.Series]) -> pd.DataFrame:
    glob = allocation.global_portfolio_real()
    rows = {}
    for name, w in weights.items():
        if "global_bonds" in w.index:
            w = w.rename({"global_bonds": "bonds"})
        vec = w.reindex(["equity", "bonds", "cash"]).fillna(0).to_numpy()
        for label, (a, b) in {"1950–1981": RISING_RATES, "1871–2020": (1871, 2020)}.items():
            r = pd.Series(glob.loc[a:b].to_numpy() @ vec, index=glob.loc[a:b].index)
            rows[(name, label)] = {
                "real_annual_return": float(np.expm1(np.log1p(r).mean())),
                "max_drawdown": metrics.max_drawdown(r),
            }
    return pd.DataFrame(rows).T


def forward_outcomes(sims: dict[str, pd.DataFrame], layer: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    months = HORIZON_YEARS * 12
    for name, sim in sims.items():
        real = metrics.real_returns(sim["net"], layer.loc[sim.index, "inflation"]).to_numpy()
        n = len(real)
        block = bootstrap.block_length(n)
        generator = bootstrap.rng()
        outcomes = np.empty(BOOTSTRAP_REPS)
        for i in range(BOOTSTRAP_REPS):
            idx = bootstrap.moving_block_indices(n, block, generator)[:months]
            if len(idx) < months:
                idx = np.resize(idx, months)
            outcomes[i] = np.prod(1 + real[idx]) ** (1 / HORIZON_YEARS) - 1
        p5, p50, p95 = np.percentile(outcomes, [5, 50, 95])
        rows[name] = {
            "p5": p5,
            "median": p50,
            "p95": p95,
            "share_below_zero": float((outcomes < 0).mean()),
        }
    return pd.DataFrame(rows).T


def _unhedged_global_bonds(layer: pd.DataFrame) -> pd.Series:
    c = bond_options._common()
    us10 = data.monthly("us_treasury_monthly")["us_gov10_tr_nominal_usd"]
    return metrics.to_base_currency(us10, c["fx"]).reindex(layer.index)


def parameter_grid(
    layer: pd.DataFrame, base: pd.Series, name: str, tolerance: float
) -> pd.DataFrame:
    """Variants of a menu mix, each checked against the mix's drawdown tolerance."""
    layer = layer.assign(global_unhedged=_unhedged_global_bonds(layer)).dropna()
    base = base.reindex(["equity", "bonds"]).fillna(0.0)
    rows = []
    eq = float(base.get("equity", 0))
    variants = {"Base case": (base, engine.RULE, None)}
    for shift in (-0.10, 0.10):
        e = min(max(eq + shift, 0.0), 1.0)
        variants[f"Equity {shift:+.0%}"] = (
            pd.Series({"equity": e, "bonds": 1 - e}),
            engine.RULE,
            None,
        )
    for band in (0.05, 0.15):
        variants[f"Band {band:.0%}"] = (base, {**engine.RULE, "band": band}, None)
    variants["Calendar only"] = (base, {"type": "calendar", "months": 12}, None)
    for sleeve, col in [
        ("Global hedged bonds", "global_bonds"),
        ("Global unhedged bonds", "global_unhedged"),
    ]:
        variants[sleeve] = (base.rename({"bonds": col}), engine.RULE, None)
    for bps in engine.SPREAD_SENSITIVITY:
        variants[f"Spread {bps * 1e4:.0f} bps per side"] = (base, engine.RULE, bps)
    for label, (w, rule, spread) in variants.items():
        sim = engine.simulate(layer, w, rule, spread)
        s = engine.summarise(sim, layer)
        chk = engine.menu_check(sim, layer, tolerance)
        rows.append(
            {
                "mix": name,
                "variant": label,
                "real_annual_return": s["real_annual_return"],
                "volatility": s["volatility"],
                "max_drawdown": s["max_drawdown"],
                "cost_per_year": s["cost_per_year"],
                "max_drawdown_real": chk["max_drawdown_real"],
                "meets_tolerance": chk["meets_tolerance"],
            }
        )
    return pd.DataFrame(rows).set_index(["mix", "variant"])


def attribution(layer: pd.DataFrame, weights: dict[str, pd.Series]) -> dict:
    sleeves = {
        c: metrics.annualised_return(layer[c], 12)
        for c in ("equity", "bonds", "global_bonds", "cash")
    }
    contrib = {
        name: {k: float(w.get(k, 0)) * sleeves[k] for k in sleeves} for name, w in weights.items()
    }
    sgs = data.monthly("sgs_month_end_yields")["sgs_10y"].loc[layer.index[0] : layer.index[-1]]
    return {
        "sleeve_returns": sleeves,
        "contributions": pd.DataFrame(contrib).T,
        "sgs10_start": float(sgs.dropna().iloc[0]),
        "sgs10_min": float(sgs.min()),
        "sgs10_min_month": str(sgs.idxmin()),
        "sgs10_end": float(sgs.dropna().iloc[-1]),
    }


def cost_ranking(layer: pd.DataFrame, frontier: pd.DataFrame) -> dict:
    """Does the cost model change the frontier ranking? For each portfolio size and LSE broker:
    cost per year of every equity/SGS mix (1-point steps, index layer), the expected real
    return net of that cost, whether mixes keep their order, and whether any menu pick changes
    when the menu ranks by net instead of gross expected return."""
    f = frontier[frontier["profile"] == frontier["profile"].iloc[0]].set_index("equity_share")
    gross = f["expected_real_return"]
    order = gross.rank(method="first")
    rows, costs_by_case = [], {}
    for broker in engine.lse_brokers():
        for size in engine.PORTFOLIO_SIZES:
            cost = pd.Series(
                {
                    e: engine.summarise(
                        engine.simulate(
                            layer,
                            pd.Series({"equity": e, "bonds": 1 - e}),
                            portfolio_value=size,
                            lse_broker=broker,
                        ),
                        layer,
                    )["cost_per_year"]
                    for e in gross.index
                }
            )
            net = gross - cost
            changed = []
            for tol in holdout.DRAWDOWN_TOLERANCES:
                ok = f[f["max_drawdown"] >= tol]
                if len(ok) and gross[ok.index].idxmax() != net[ok.index].idxmax():
                    changed.append(f"{tol:.0%}")
            costs_by_case[(broker, size)] = cost
            rows.append(
                {
                    "lse_broker": broker,
                    "portfolio_usd": size,
                    "max_cost_per_year": float(cost.max()),
                    "order_unchanged": bool((net.rank(method="first") == order).all()),
                    "mixes_changing_rank": int((net.rank(method="first") != order).sum()),
                    "net_return_peak_equity": float(net.idxmax()),
                    "menu_picks_changed": ", ".join(changed) or "none",
                }
            )
    return {
        "table": pd.DataFrame(rows).set_index(["lse_broker", "portfolio_usd"]),
        "costs": pd.DataFrame(costs_by_case),
    }
