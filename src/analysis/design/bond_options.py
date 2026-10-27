"""Bond sleeve for an SGD investor: SGS vs global government bonds hedged to SGD vs unhedged,
at matched duration, judged on portfolio-level metrics in SGD.

Rules (fixed before results were computed):
- Options: (1) Singapore government bonds (SGS); (2) global government bonds hedged to SGD;
  (3) global government bonds unhedged. Same rules for all three.
- Main layer (same fund, June 2019 onwards): global = iShares Global Govt Bond UCITS ETF,
  unhedged class IGLO.L and USD-hedged class SGLU.AS (Yahoo, close + distributions). Hedged to
  SGD = USD-hedged return + SGD one-month rate - USD one-month rate. Unhedged in SGD = USD
  return compounded with the month-end USD/SGD change.
- Long layer (robustness, 1998 onwards): global stand-in = constant-maturity US 10-year
  Treasury built from FRED yields, hedged and unhedged as above.
- SGS at matched duration: each month, the maturity whose par-bond modified duration (at the
  SGS curve's yield for that maturity, linearly interpolated between MAS benchmark tenors)
  equals the target; return = par bond bought at last month's yield, priced at this month's.
  Target: main layer, the fund's published effective duration (reference/bond_durations.csv);
  long layer, the US 10-year's duration that month.
- Portfolio: 60% global equities unhedged in SGD (main: ACWI; long: French developed markets)
  and 40% in the bond option, rebalanced monthly, before costs.
- Metrics, all in SGD: portfolio volatility, maximum drawdown, and mean monthly portfolio
  return in the worst 10% of equity months (by the SGD equity return).
- Decision: rank the options on each of the three metrics in the main layer; lowest average
  rank wins; ties are broken by the long layer's average rank. A moving-block bootstrap gives
  a 95% interval for the winner's volatility advantage over the runner-up.
- Sensitivity: the main layer is rerun with SGS matched at 5.0 and 7.5 years of duration.
"""

import numpy as np
import pandas as pd

from analysis import bootstrap, charts, data, metrics
from analysis.config import BOOTSTRAP_REPS, REFERENCE

EQUITY_WEIGHT = 0.6
OPTIONS = ["SGS", "Global hedged to SGD", "Global unhedged"]
SENSITIVITY_DURATIONS = [5.0, 7.5]


def target_duration() -> float:
    ref = pd.read_csv(REFERENCE / "bond_durations.csv")
    return float(ref["effective_duration_years"].iloc[0])


def _curve(row: pd.Series):
    """Linear interpolation of a month's SGS yields by maturity (flat beyond the ends)."""
    points = row.dropna()
    tenors = np.array([int(c.split("_")[1].rstrip("y")) for c in points.index], dtype=float)
    yields = points.to_numpy(dtype=float)
    order = np.argsort(tenors)
    return lambda m: float(np.interp(m, tenors[order], yields[order]))


def sgs_matched(targets: pd.Series) -> pd.DataFrame:
    """Monthly SGS returns at a target duration (targets indexed by month, set at month start)."""
    curves = data.monthly("sgs_month_end_yields")
    rows = {}
    months = curves.index
    for prev, now in zip(months[:-1], months[1:], strict=True):
        if now not in targets.index or pd.isna(targets.loc[now]):
            continue
        start, end = _curve(curves.loc[prev]), _curve(curves.loc[now])
        maturity = metrics.maturity_for_duration(float(targets.loc[now]), start)
        y0, y1 = start(maturity), end(maturity)
        ret = metrics.par_bond_return(pd.Series([y0]), pd.Series([y1]), maturity).iloc[0]
        rows[now] = {"sgs": float(ret), "sgs_maturity": maturity, "sgs_yield": y0}
    return pd.DataFrame(rows).T


def _common() -> dict[str, pd.Series]:
    return {
        "fx": data.monthly("usdsgd_month_end")["usd_vs_sgd_change"],
        "rf_sgd": data.monthly("sgd_rf_monthly")["sgd_rf_tr_nominal_sgd"],
        "rf_usd": data.monthly("us_monthly_french")["us_bill1m_tr_nominal_usd"],
        "sg_infl": data.monthly("sg_cpi_monthly")["sg_inflation_month"],
    }


def main_layer(duration: float | None = None) -> pd.DataFrame:
    c = _common()
    etf = data.monthly("etf_monthly")
    df = pd.DataFrame(
        {
            "equity": metrics.to_base_currency(etf["ACWI_tr_nominal_usd"], c["fx"]),
            "Global unhedged": metrics.to_base_currency(etf["IGLO.L_tr_nominal_usd"], c["fx"]),
            "Global hedged to SGD": metrics.hedged_return(
                etf["SGLU.AS_tr_nominal_usd"], c["rf_sgd"], c["rf_usd"]
            ),
            "inflation": c["sg_infl"],
        }
    ).dropna()
    target = pd.Series(duration or target_duration(), index=df.index)
    sgs = sgs_matched(target)
    return df.join(sgs.rename(columns={"sgs": "SGS"}), how="inner")


def long_layer() -> pd.DataFrame:
    c = _common()
    t = data.monthly("us_treasury_monthly")
    us10 = t["us_gov10_tr_nominal_usd"]
    duration = t["dgs10_yield"].shift(1).apply(lambda y: metrics.par_bond_duration(y, 10))
    dev = data.monthly("developed_monthly_french")["developed_eq_tr_nominal_usd"]
    df = pd.DataFrame(
        {
            "equity": metrics.to_base_currency(dev, c["fx"]),
            "Global unhedged": metrics.to_base_currency(us10, c["fx"]),
            "Global hedged to SGD": metrics.hedged_return(us10, c["rf_sgd"], c["rf_usd"]),
            "inflation": c["sg_infl"],
            "target_duration": duration,
        }
    ).dropna()
    sgs = sgs_matched(df["target_duration"])
    return df.join(sgs.rename(columns={"sgs": "SGS"}), how="inner")


def portfolio_metrics(df: pd.DataFrame) -> pd.DataFrame:
    worst = df["equity"] <= df["equity"].quantile(0.10)
    rows = {}
    for option in OPTIONS:
        port = EQUITY_WEIGHT * df["equity"] + (1 - EQUITY_WEIGHT) * df[option]
        rows[option] = {
            "portfolio_volatility": metrics.annualised_volatility(port, 12),
            "portfolio_max_drawdown": metrics.max_drawdown(port),
            "worst10_equity_months_return": float(port[worst].mean()),
            "portfolio_return": metrics.annualised_return(port, 12),
            "portfolio_real_return": metrics.annualised_return(
                metrics.real_returns(port, df["inflation"]), 12
            ),
            "bond_volatility": metrics.annualised_volatility(df[option], 12),
            "bond_equity_correlation": df[option].corr(df["equity"]),
        }
    table = pd.DataFrame(rows).T
    ranks = pd.DataFrame(
        {
            "portfolio_volatility": table["portfolio_volatility"].astype(float).rank(),
            "portfolio_max_drawdown": (-table["portfolio_max_drawdown"].astype(float)).rank(),
            "worst10_equity_months_return": (
                -table["worst10_equity_months_return"].astype(float)
            ).rank(),
        }
    )
    table["average_rank"] = ranks.mean(axis=1)
    return table


def vol_difference_ci(df: pd.DataFrame, a: str, b: str) -> tuple[float, float]:
    pa = (EQUITY_WEIGHT * df["equity"] + (1 - EQUITY_WEIGHT) * df[a]).to_numpy()
    pb = (EQUITY_WEIGHT * df["equity"] + (1 - EQUITY_WEIGHT) * df[b]).to_numpy()
    n = len(pa)
    block = bootstrap.block_length(n)
    generator = bootstrap.rng()
    diffs = np.empty(BOOTSTRAP_REPS)
    for i in range(BOOTSTRAP_REPS):
        idx = bootstrap.moving_block_indices(n, block, generator)
        diffs[i] = (pa[idx].std(ddof=1) - pb[idx].std(ddof=1)) * np.sqrt(12)
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def decide(main: pd.DataFrame, long: pd.DataFrame) -> str:
    ranks = main["average_rank"].astype(float)
    best = ranks[ranks == ranks.min()].index
    if len(best) == 1:
        return best[0]
    return long.loc[best, "average_rank"].astype(float).idxmin()


def _figure(main: pd.DataFrame, period: str, winner: str) -> "charts.Path":
    charts.style()
    fig, axes = charts.plt.subplots(1, 3, figsize=(charts.WIDTH_IN, 4.2))
    panels = [
        ("portfolio_volatility", "Portfolio volatility, %", 1),
        ("portfolio_max_drawdown", "Maximum drawdown, %", 1),
        ("worst10_equity_months_return", "Avg return, worst 10%\nequity months, %", 1),
    ]
    x = np.arange(len(OPTIONS))
    for ax, (col, label, _) in zip(axes, panels, strict=True):
        values = main.loc[OPTIONS, col].astype(float) * 100
        ax.bar(x, values, width=0.6, color=charts.SERIES[: len(OPTIONS)])
        ax.set_xticks(x, ["SGS", "Global\nhedged", "Global\nunhedged"], fontsize=8.5)
        ax.set_ylabel(label, fontsize=9)
        ax.axhline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
        ax.grid(axis="x", visible=False)
    charts.titles(
        fig,
        f"Bond sleeve: {winner} ranked best on portfolio-level risk in SGD",
        f"60% global equities (unhedged) + 40% bond option, monthly, SGD, {period}",
    )
    return charts.save(
        fig,
        "design_bond_options_sgd",
        "Source: MAS (SGS yields, SGD rates); Yahoo Finance (ACWI, IGLO.L, SGLU.AS); FRED "
        "(DEXSIUS); Kenneth French Data Library (T-bill). Calculations: this project.",
        {"mas", "yahoo", "fred", "french"},
    )


def run() -> dict:
    main_df, long_df = main_layer(), long_layer()
    main, long = portfolio_metrics(main_df), portfolio_metrics(long_df)
    winner = decide(main, long)
    others = main.drop(winner)["average_rank"].astype(float)
    runner_up = others.idxmin()
    lo, hi = vol_difference_ci(main_df, winner, runner_up)
    sensitivity = {d: decide(portfolio_metrics(main_layer(d)), long) for d in SENSITIVITY_DURATIONS}
    period = f"{main_df.index[0]} to {main_df.index[-1]}"
    return {
        "winner": winner,
        "runner_up": runner_up,
        "vol_diff_ci": (lo, hi),
        "main": main,
        "long": long,
        "main_period": period,
        "long_period": f"{long_df.index[0]} to {long_df.index[-1]}",
        "target_duration": target_duration(),
        "sgs_maturity_main": (
            float(main_df["sgs_maturity"].min()),
            float(main_df["sgs_maturity"].max()),
        ),
        "sensitivity": sensitivity,
        "figure": _figure(main, period, winner),
    }
