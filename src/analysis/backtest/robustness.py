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
from analysis.design import allocation, bond_options, profiles

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


def parameter_grid(layer: pd.DataFrame, base: pd.Series) -> pd.DataFrame:
    """Variants of the adopted allocation, each checked against every profile's limits."""
    layer = layer.assign(global_unhedged=_unhedged_global_bonds(layer)).dropna()
    rows = []
    for p in profiles.PROFILES:
        eq = float(base.get("equity", 0))
        variants = {"Base case": (base, engine.RULE, 1.0)}
        for shift in (-0.10, 0.10):
            e = min(max(eq + shift, 0.0), 1.0)
            variants[f"Equity {shift:+.0%}"] = (
                pd.Series({"equity": e, "bonds": 1 - e}),
                engine.RULE,
                1.0,
            )
        for band in (0.05, 0.15):
            variants[f"Band {band:.0%}"] = (base, {**engine.RULE, "band": band}, 1.0)
        variants["Calendar only"] = (base, {"type": "calendar", "months": 12}, 1.0)
        for sleeve, col in [
            ("Global hedged bonds", "global_bonds"),
            ("Global unhedged bonds", "global_unhedged"),
        ]:
            variants[sleeve] = (base.rename({"bonds": col}), engine.RULE, 1.0)
        for m in (2.0, 3.0):
            variants[f"Spreads x{m:.0f}"] = (base, engine.RULE, m)
        for label, (w, rule, mult) in variants.items():
            sim = engine.simulate(layer, w, rule, mult)
            s = engine.summarise(sim, layer)
            chk = engine.profile_check(sim, layer, p)
            rows.append(
                {
                    "profile": p.name,
                    "variant": label,
                    "real_annual_return": s["real_annual_return"],
                    "volatility": s["volatility"],
                    "max_drawdown": s["max_drawdown"],
                    "cost_per_year": s["cost_per_year"],
                    "worst_window_real": chk["worst_window_real"],
                    "meets_limits": chk["meets_limits"],
                }
            )
    return pd.DataFrame(rows).set_index(["profile", "variant"])


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
