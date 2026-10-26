"""Claim 4: the minimum-risk stock/bond mix shifts towards equities as the horizon lengthens.

Rules:
- Data: JST annual real (CPI-deflated) total returns for equities, government bonds and bills,
  each country's longest run of consecutive years with all three.
- Portfolio: equity weight w from 0% to 100% in 1-point steps, the rest in bonds, rebalanced
  every year. For horizon k, every overlapping k-year window gives an annualised real return.
- Minimum-variance mix: the w with the lowest standard deviation of k-year annualised real
  returns. Maximum-Sharpe mix: the w with the highest mean / std of k-year annualised
  returns in excess of bills.
- Claim test per country (descriptive, as the usual tables are): the minimum-variance equity
  weight at 20 years exceeds the weight at 1 year. verdict_from_share over countries.
- Statistical check: the 1-to-20-year shift is compared with 2,000 i.i.d. resamples of whole
  years (stock, bond and bill returns kept together), which remove any horizon effect.
"""

import numpy as np
import pandas as pd

from analysis import bootstrap, charts, data, metrics
from analysis.config import BOOTSTRAP_REPS, JST_CREDIT
from analysis.evidence import ClaimResult, verdict_from_share

WEIGHTS = np.linspace(0, 1, 101)
HORIZONS = [1, 5, 10, 20, 30]
SHORT, LONG = 1, 20


def _annualised_windows(log_returns: np.ndarray, k: int) -> np.ndarray:
    """(T, W) log returns -> (T - k + 1, W) annualised simple returns over k-year windows."""
    csum = np.vstack([np.zeros(log_returns.shape[1]), np.cumsum(log_returns, axis=0)])
    return np.expm1((csum[k:] - csum[:-k]) / k)


def optimal_weights(stocks: np.ndarray, bonds: np.ndarray, bills: np.ndarray, k: int) -> dict:
    """Minimum-variance and maximum-Sharpe equity weights for horizon k (annual data)."""
    port = np.log1p(np.outer(stocks, WEIGHTS) + np.outer(bonds, 1 - WEIGHTS))
    ann = _annualised_windows(port, k)
    bill_ann = _annualised_windows(np.log1p(bills)[:, None], k)
    excess = ann - bill_ann
    std = ann.std(axis=0, ddof=1)
    sharpe = excess.mean(axis=0) / excess.std(axis=0, ddof=1)
    return {"min_variance": WEIGHTS[np.argmin(std)], "max_sharpe": WEIGHTS[np.argmax(sharpe)]}


def iid_shift(stocks, bonds, bills, reps: int = BOOTSTRAP_REPS) -> np.ndarray:
    """Distribution of the min-variance weight shift (LONG minus SHORT) under i.i.d. years."""
    generator = bootstrap.rng()
    n = len(stocks)
    shifts = np.empty(reps)
    for i in range(reps):
        idx = generator.integers(0, n, n)
        s, b, r = stocks[idx], bonds[idx], bills[idx]
        shifts[i] = (
            optimal_weights(s, b, r, LONG)["min_variance"]
            - optimal_weights(s, b, r, SHORT)["min_variance"]
        )
    return shifts


def country_inputs(jst: pd.DataFrame) -> dict[str, pd.DataFrame]:
    real = pd.DataFrame(
        {
            "stocks": metrics.real_returns(jst["eq_tr"], jst["inflation"]),
            "bonds": metrics.real_returns(jst["bond_tr"], jst["inflation"]),
            "bills": metrics.real_returns(jst["bill_rate"], jst["inflation"]),
        }
    )
    out = {}
    for country, group in real.groupby(level="country"):
        g = group.droplevel("country").dropna()
        if g.empty:
            continue
        years = g.index.to_numpy()
        breaks = np.flatnonzero(np.diff(years) != 1)
        starts, ends = np.r_[0, breaks + 1], np.r_[breaks + 1, len(g)]
        i = int(np.argmax(ends - starts))
        run_ = g.iloc[starts[i] : ends[i]]
        if len(run_) >= 3 * LONG:
            out[country] = run_
    return out


def _figure(us_weights: pd.DataFrame, period: str) -> "charts.Path":
    fig, ax = charts.figure(height_in=5.0)
    labels = {"min_variance": "Minimum variance", "max_sharpe": "Maximum Sharpe ratio"}
    for i, column in enumerate(["min_variance", "max_sharpe"]):
        ax.plot(
            us_weights.index,
            us_weights[column] * 100,
            marker="o",
            markersize=7,
            color=charts.SERIES[i],
            label=labels[column],
        )
        ax.annotate(
            labels[column],
            (us_weights.index[-1], us_weights[column].iloc[-1] * 100),
            xytext=(-6, 8),
            textcoords="offset points",
            ha="right",
            color=charts.TEXT,
        )
    ax.set_ylim(-5, 105)
    ax.set_xticks(us_weights.index)
    ax.set_xlabel("Holding period, years")
    ax.set_ylabel("Equity weight in stock/bond mix, %")
    ax.legend(loc="lower right")
    mv = us_weights["min_variance"]
    charts.titles(
        fig,
        f"US: lowest-risk equity weight rises from {mv.loc[SHORT]:.0%} at 1 year to "
        f"{mv.loc[LONG]:.0%} at 20 years",
        f"Optimal equity weight by holding period, real returns, annual rebalancing, {period}",
    )
    return charts.save(fig, "claim04_horizon_mix_us", JST_CREDIT, {"jst"})


def run() -> ClaimResult:
    inputs = country_inputs(data.jst())
    rows, us_weights = {}, None
    for country, g in inputs.items():
        s, b, r = (g[c].to_numpy() for c in ("stocks", "bonds", "bills"))
        by_h = pd.DataFrame({k: optimal_weights(s, b, r, k) for k in HORIZONS if len(g) >= 3 * k}).T
        shifts = iid_shift(s, b, r)
        observed = by_h.loc[LONG, "min_variance"] - by_h.loc[SHORT, "min_variance"]
        rows[country] = {
            "start": int(g.index[0]),
            "end": int(g.index[-1]),
            "mv_1y": by_h.loc[SHORT, "min_variance"],
            "mv_20y": by_h.loc[LONG, "min_variance"],
            "ms_1y": by_h.loc[SHORT, "max_sharpe"],
            "ms_20y": by_h.loc[LONG, "max_sharpe"],
            "shift": observed,
            "iid_shift_p95": float(np.percentile(shifts, 95)),
            "shift_beyond_iid": bool(observed > np.percentile(shifts, 95)),
        }
        if country == "USA":
            us_weights = by_h
            us_period = f"{int(g.index[0])}–{int(g.index[-1])}"
    table = pd.DataFrame(rows).T.sort_values("shift", ascending=False)
    n = len(table)
    n_up = int((table["shift"] > 0).sum())
    n_sig = int(table["shift_beyond_iid"].sum())
    us = table.loc["USA"]

    figure = _figure(us_weights, us_period)
    return ClaimResult(
        number=4,
        claim=("A minimum-risk stock/bond mix shifts towards equities as the horizon lengthens."),
        verdict=verdict_from_share(n_up, n),
        headline=(
            f"The minimum-variance equity weight was higher at 20 years than at 1 year in "
            f"{n_up} of {n} countries; in {n_sig} the shift exceeded the 95th percentile of "
            f"i.i.d. resamples. US: {us['mv_1y']:.0%} → {us['mv_20y']:.0%}."
        ),
        data=(
            "JST Macrohistory Database R6, annual real total returns on equities, government "
            "bonds and bills, each country's longest run of consecutive years with all three "
            "(at least 60 years). Local currency."
        ),
        method=(
            "Stock/bond mixes from 0% to 100% equity in 1-point steps, rebalanced annually. For "
            "each holding period, the standard deviation of overlapping annualised real "
            "returns (minimum variance) and the Sharpe ratio over bills (maximum Sharpe) pick "
            f"the optimal weight. The 1→20-year shift is compared with {BOOTSTRAP_REPS:,} "
            "i.i.d. resamples of whole years."
        ),
        findings=[
            f"US {us_period}: minimum-variance equity weight {us['mv_1y']:.0%} at 1 year and "
            f"{us['mv_20y']:.0%} at 20 years; maximum-Sharpe weight {us['ms_1y']:.0%} and "
            f"{us['ms_20y']:.0%}.",
            f"Shift beyond the i.i.d. 95th percentile in {n_sig} of {n} countries: "
            + (", ".join(table.index[table["shift_beyond_iid"]]) or "none")
            + ".",
            "The two definitions answer different questions: minimum variance ignores return, "
            "while maximum Sharpe trades return against risk. A rising minimum-variance weight "
            "says equities became relatively less risky over long windows in real terms, not "
            "that they are riskless.",
            "Tables in popular books (e.g. Siegel, Stocks for the Long Run) report the "
            "minimum-standard-deviation mix by holding period; cited, not independently "
            "verified.",
        ],
        caveats=[
            "Long horizons rest on few independent periods: 20-year windows in about 120–150 "
            "years give 6–7 non-overlapping observations, so the 20-year weights are imprecise.",
            "Real returns in local currency: bonds look riskier in real terms in countries with "
            "high inflation episodes, which pushes the result towards equities there.",
            "Survivorship and missing years as in claim 1.",
            "No costs, taxes or currency effects for an SGD investor.",
        ],
        tables={"countries": table, "us_by_horizon": us_weights},
        figures=[figure],
    )
