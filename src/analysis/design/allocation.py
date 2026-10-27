"""Allocation methods compared under each profile's risk-capacity limits.

Rules (fixed before results were computed; gold removed on 2026-10-27 when the universe rule
gained its return-source condition, before any allocation result was seen):
- Assets: global equities, government bonds (the SGS sleeve) and cash (design/universe.py).
- Moments for the estimated methods: monthly SGD excess returns over SGD cash of global
  equities (ACWI, unhedged) and SGS (matched duration), June 2008 onwards.
- Methods, each giving risky weights over equities and bonds:
  1. Glide path: equity weight = median across JST countries of the minimum-variance equity
     weight at the profile's horizon (claim 4 method); the rest in bonds.
  2. Market cap: reference/market_cap_weights.csv, equities and bonds (SIFMA, end-2025).
  3. Minimum variance, Ledoit-Wolf covariance.
  4. Mean-variance with shrinkage: Bayes-Stein means, Ledoit-Wolf covariance, maximum Sharpe.
  5. Risk parity: equal risk contributions, Ledoit-Wolf covariance.
- Profile allocation: a x risky weights + (1 - a) x cash, with a the largest value (1% steps)
  that meets all of the profile's limits.
- Limit tests (binding; owner decisions 2026-10-27): real SGD monthly returns from February
  1998: developed-market equities (French, unhedged in SGD), SGS at the global fund's
  duration, SGD cash; Singapore CPI; rolling windows of the profile's length and the
  maximum drawdown.
- Stress scenario (not binding): a GDP-weighted global portfolio of the JST countries,
  annual, real USD, 1871-2020: equities unhedged, government bonds hedged to USD, cash = US
  bills (global_portfolio_real). Single-country tests were dropped at the owner's direction.
- Expected real return: the global JST portfolio's real annualised return.
- Selection per profile: highest expected real return among the five methods' allocations;
  ties go to lower monthly SGD volatility.
- Sensitivity: methods 3-5 re-estimated on 2,000 moving-block bootstrap resamples (5th-95th
  percentile weights); glide path interquartile range across countries.
"""

import numpy as np
import pandas as pd

from analysis import bootstrap, charts, data, metrics, optimise
from analysis.config import BOOTSTRAP_REPS, JST_CREDIT, REFERENCE
from analysis.design import bond_options, profiles, universe
from analysis.evidence import claim04_horizon_mix as c4

RISKY = ["equity", "bonds"]
ASSETS = [*RISKY, "cash"]
METHODS = ["Glide path", "Market cap", "Minimum variance", "Mean-variance (shrunk)", "Risk parity"]


# --- data -----------------------------------------------------------------------------


def monthly() -> pd.DataFrame:
    """Monthly SGD nominal returns of the three assets plus Singapore inflation."""
    df = universe.monthly_sgd()
    out = pd.DataFrame({"equity": df["equity"], "bonds": df["sgs"], "cash": df["rf"]})
    infl = data.monthly("sg_cpi_monthly")["sg_inflation_month"]
    return out.join(infl.rename("inflation"), how="inner")


def global_portfolio_real() -> pd.DataFrame:
    """Annual real USD returns of a GDP-weighted global portfolio of the JST countries.

    Weights each year are the previous year's GDP in USD (known at the start of the year),
    across countries with data for that asset. Equities: local total return converted to USD
    (unhedged). Government bonds: hedged to USD, local return + US bill rate - local bill rate
    (covered interest parity, annual). Cash: hedged bills, which equals the US bill rate.
    Deflated by US CPI inflation.
    """
    jst = data.jst()
    fx = jst.groupby(level="country")["xrusd"].pct_change()  # change in local per USD
    us = jst.xs("USA", level="country")
    us_bill = us["bill_rate"].reindex(jst.index.get_level_values("year")).to_numpy()
    weight = (jst["gdp"] / jst["xrusd"]).groupby(level="country").shift(1)
    panel = pd.DataFrame(
        {
            "equity": (1 + jst["eq_tr"]) / (1 + fx) - 1,
            "bonds": jst["bond_tr"] + us_bill - jst["bill_rate"],
            "weight": weight,
        }
    )
    out = {}
    for asset in ["equity", "bonds"]:
        sub = panel[[asset, "weight"]].dropna()
        out[asset] = sub.groupby(level="year").apply(
            lambda g, a=asset: float(np.average(g[a], weights=g["weight"]))
        )
    df = pd.DataFrame(out)
    df["cash"] = us["bill_rate"]
    real = df.apply(lambda col: metrics.real_returns(col, us["inflation"])).dropna()
    real.index.name = "year"
    return real[ASSETS]


# --- methods --------------------------------------------------------------------------


def market_cap_weights() -> np.ndarray:
    ref = pd.read_csv(REFERENCE / "market_cap_weights.csv").set_index("maps_to")
    w = ref["value_usd_trillion"].astype(float).reindex(RISKY).to_numpy()
    return w / w.sum()


def glide_path_equity(horizon: int) -> tuple[float, float, float]:
    """Median and interquartile range across countries of the min-variance equity weight."""
    weights = []
    for g in c4.country_inputs(data.jst()).values():
        if len(g) < 3 * horizon:
            continue
        s, b, r = (g[c].to_numpy() for c in ("stocks", "bonds", "bills"))
        weights.append(c4.optimal_weights(s, b, r, horizon)["min_variance"])
    q = np.percentile(weights, [25, 50, 75])
    return float(q[1]), float(q[0]), float(q[2])


def estimated_weights(excess: np.ndarray) -> dict[str, np.ndarray]:
    cov, _ = optimise.ledoit_wolf(excess)
    means, _ = optimise.bayes_stein_means(excess, cov)
    return {
        "Minimum variance": optimise.min_variance(cov),
        "Mean-variance (shrunk)": optimise.max_sharpe(means, cov),
        "Risk parity": optimise.risk_parity(cov),
    }


# --- limits ---------------------------------------------------------------------------


def sgd_history() -> pd.DataFrame:
    """Monthly SGD returns for the limit tests: developed-market equities (French, unhedged),
    SGS at the global fund's duration, SGD cash, and Singapore inflation; from February 1998."""
    c = bond_options._common()
    dev = data.monthly("developed_monthly_french")["developed_eq_tr_nominal_usd"]
    df = pd.DataFrame(
        {
            "equity": metrics.to_base_currency(dev, c["fx"]),
            "cash": c["rf_sgd"],
            "inflation": c["sg_infl"],
        }
    ).dropna()
    sgs = bond_options.sgs_matched(pd.Series(bond_options.target_duration(), index=df.index))
    df = df.join(sgs["sgs"].rename("bonds"), how="inner").dropna()
    return df[[*ASSETS, "inflation"]]


def _worst_window(series: pd.Series, years: int, periods: int, annualised: bool) -> float:
    ann = metrics.rolling_annualised(series, years, periods)
    if not len(ann):
        return np.nan
    stat = ann if annualised else (1 + ann) ** years - 1
    return float(stat.min())


def _profile_test(real: pd.Series, periods: int, p: profiles.Profile) -> dict:
    worst = _worst_window(real, p.window_years, periods, p.floor_is_annualised)
    dd = metrics.max_drawdown(real)
    ok = worst >= p.worst_window_floor
    if p.max_drawdown_cap is not None:
        ok = ok and dd >= p.max_drawdown_cap
    return {"worst_window": worst, "max_drawdown": dd, "ok": bool(ok)}


def evaluate(w: np.ndarray, glob: pd.DataFrame, sgd: pd.DataFrame, p: profiles.Profile) -> dict:
    """Limits bind on real SGD history (monthly). The global JST portfolio (annual, real USD,
    1871-2020) is a stress scenario and gives the expected real return (its real annualised
    return)."""
    sgd_real = metrics.real_returns(
        pd.Series(sgd[ASSETS].to_numpy() @ w, index=sgd.index), sgd["inflation"]
    )
    glob_real = pd.Series(glob[ASSETS].to_numpy() @ w, index=glob.index)
    s_test, g_test = _profile_test(sgd_real, 12, p), _profile_test(glob_real, 1, p)
    return {
        "expected_real_return": float(np.expm1(np.log1p(glob_real).mean())),
        "worst_window_global": g_test["worst_window"],
        "max_drawdown_global": g_test["max_drawdown"],
        "worst_window_sgd": s_test["worst_window"],
        "max_drawdown_sgd": s_test["max_drawdown"],
        "sgd_real_return": metrics.annualised_return(sgd_real, 12),
        "sgd_volatility": metrics.annualised_volatility(sgd_real, 12),
        "global_stress_passes": g_test["ok"],
        "meets_limits": s_test["ok"],
    }


def scale_to_limits(risky: np.ndarray, glob, sgd, p) -> tuple[float, np.ndarray, dict]:
    """Largest share a (1% steps) in the risky mix, rest cash, that meets the limits."""
    for a in np.round(np.arange(1.0, -0.001, -0.01), 2):
        w = np.append(a * risky, 1 - a)
        result = evaluate(w, glob, sgd, p)
        if result["meets_limits"]:
            return float(a), w, result
    cash_only = np.append(np.zeros(len(risky)), 1.0)
    return np.nan, cash_only, evaluate(cash_only, glob, sgd, p)


# --- sensitivity ----------------------------------------------------------------------


def bootstrap_weights(excess: np.ndarray) -> pd.DataFrame:
    n = len(excess)
    block = bootstrap.block_length(n)
    generator = bootstrap.rng()
    rows = []
    for _ in range(BOOTSTRAP_REPS):
        idx = bootstrap.moving_block_indices(n, block, generator)
        for method, w in estimated_weights(excess[idx]).items():
            rows.append({"method": method, **dict(zip(RISKY, w, strict=True))})
    df = pd.DataFrame(rows)
    grouped = df.groupby("method")[RISKY]
    return pd.concat(
        [grouped.quantile(0.05).add_suffix("_p5"), grouped.quantile(0.95).add_suffix("_p95")],
        axis=1,
    )


# --- figure ---------------------------------------------------------------------------


def _figure(table: pd.DataFrame, selected: dict) -> "charts.Path":
    charts.style()
    fig, axes = charts.plt.subplots(1, 3, figsize=(charts.WIDTH_IN, 4.6), sharey=True)
    labels = {"equity": "Equities", "bonds": "SGS", "cash": "Cash"}
    for ax, p in zip(axes, profiles.PROFILES, strict=True):
        rows = table[table["profile"] == p.name].set_index("method").loc[METHODS]
        y = np.arange(len(METHODS))[::-1]
        ok = rows["meets_limits"].astype(bool).to_numpy()
        left = np.zeros(len(METHODS))
        for i, asset in enumerate(ASSETS):
            vals = np.where(ok, rows[f"w_{asset}"].astype(float).to_numpy() * 100, 0)
            ax.barh(
                y,
                vals,
                left=left,
                height=0.6,
                color=charts.SERIES[i],
                edgecolor=charts.SURFACE,
                linewidth=1,
                label=labels[asset],
            )
            left += vals
        for yi, passed in zip(y, ok, strict=True):
            if not passed:
                ax.text(
                    2,
                    yi,
                    "no mix meets the limits",
                    va="center",
                    fontsize=7.5,
                    color=charts.TEXT_SECONDARY,
                )
        ax.set_title(f"{p.name}: selected {selected[p.name]}", fontsize=9)
        ax.set_xlim(0, 100)
        ax.set_xlabel("Weight, %")
        ax.grid(axis="y", visible=False)
        ax.set_yticks(y, METHODS, fontsize=8)
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        names,
        loc="upper right",
        bbox_to_anchor=(0.99, 0.935),
        ncols=3,
        fontsize=8,
        frameon=False,
    )
    charts.titles(
        fig,
        "Allocations by method after scaling with cash to each profile's limits",
        "Risk limits tested on real SGD returns, monthly, from February 1998",
    )
    return charts.save(
        fig,
        "design_allocation_methods",
        JST_CREDIT + " MAS; Yahoo Finance; FRED; SingStat. Calculations: this project.",
        {"jst", "mas", "yahoo", "fred", "singstat"},
    )


# --- run ------------------------------------------------------------------------------


def compare() -> dict:
    """Run the method comparison and selection (no bootstrap, no figure)."""
    mon = monthly()
    glob = global_portfolio_real()
    sgd = sgd_history()
    excess = mon[RISKY].sub(mon["cash"], axis=0).to_numpy()
    estimated = estimated_weights(excess)
    rows, risky_rows, selected = [], {}, {}
    for p in profiles.PROFILES:
        glide, g_lo, g_hi = glide_path_equity(p.window_years)
        risky = {
            "Glide path": np.array([glide, 1 - glide]),
            "Market cap": market_cap_weights(),
            **estimated,
        }
        for method in METHODS:
            risky_rows[(p.name, method)] = dict(zip(RISKY, risky[method], strict=True))
            a, w, res = scale_to_limits(risky[method], glob, sgd, p)
            rows.append(
                {
                    "profile": p.name,
                    "method": method,
                    "share_in_risky_mix": a,
                    **{f"w_{k}": v for k, v in zip(ASSETS, w, strict=True)},
                    **res,
                }
            )
        prof = pd.DataFrame([r for r in rows if r["profile"] == p.name])
        feasible = prof[prof["meets_limits"]]
        if feasible.empty:
            selected[p.name] = "none feasible"
        else:
            best = feasible.sort_values(
                ["expected_real_return", "sgd_volatility"], ascending=[False, True]
            ).iloc[0]
            selected[p.name] = best["method"]
        risky_rows[(p.name, "Glide path IQR")] = {"equity": f"{g_lo:.0%}–{g_hi:.0%}"}
    return {
        "table": pd.DataFrame(rows),
        "risky_weights": pd.DataFrame(risky_rows).T,
        "selected": selected,
        "excess": excess,
        "monthly_period": f"{mon.index[0]} to {mon.index[-1]}",
        "sgd_period": f"{sgd.index[0]} to {sgd.index[-1]}",
        "global_years": f"{int(glob.index.min())}–{int(glob.index.max())}",
    }


def selected_weights() -> dict[str, pd.Series]:
    """Selected allocation per profile: weights over equity, bonds and cash."""
    c = compare()
    t = c["table"].set_index(["profile", "method"])
    return {
        profile: t.loc[(profile, method), [f"w_{a}" for a in ASSETS]]
        .astype(float)
        .rename(lambda k: k[2:])
        for profile, method in c["selected"].items()
    }


def run() -> dict:
    c = compare()
    c["bootstrap_ranges"] = bootstrap_weights(c.pop("excess"))
    c["figure"] = _figure(c["table"], c["selected"])
    return c


FINAL_METHOD = "Risk parity"  # owner decision 2026-10-27 after the holdout (docs/decisions.md)


def final_allocation() -> pd.Series:
    """The single allocation adopted after the holdout: risk-parity weights over equities and
    SGS, no cash (the three profiles coincided on the holdout and were merged)."""
    excess = monthly()
    x = excess[RISKY].sub(excess["cash"], axis=0).to_numpy()
    w = estimated_weights(x)[FINAL_METHOD]
    return pd.Series(dict(zip(RISKY, w, strict=True)))
