"""Holdout evaluation of the allocation candidates (v2, owner-approved 2026-10-27).

Rules (fixed before the v2 results were computed):
- Candidates per profile: each method's allocation that meets the v2 limits on SGD history,
  plus "Maximum equity meeting limits" (post-backtest): the largest equity share in 1-point
  steps, rest in the bond sleeve the three-way comparison selected (SGS), meeting the v2
  limits on SGD history.
- Holdout tests, each giving the share of horizon-length windows with a real loss:
  H1 JST non-US countries: annual real local-currency returns, windows pooled across the 15
     countries (windows never span a missing year).
  H2 US before 1981: Shiller monthly real returns, February 1871 to December 1980.
  H3 Block bootstrap: 2,000 paths of the profile's length from the global JST portfolio
     (annual real USD, 1871-2020, GDP-weighted with the previous year's GDP in USD, bonds
     hedged); block length round(150^(1/5)) = 3 years; seed config.RANDOM_SEED.
- A candidate passes the holdout if its real-loss share is within the profile's tolerance
  in all three tests. Worst-window floors and the drawdown cap are tested in-sample only:
  in the holdout data the worst cases include wars that no allocation survives (v1 finding).
- Selection: among candidates that pass, the highest expected real return (global JST
  portfolio). If none pass, the profile is reported as infeasible; no tie-break is applied.
"""

import functools

import numpy as np
import pandas as pd

from analysis import bootstrap, data, metrics
from analysis.config import BOOTSTRAP_REPS, REFERENCE
from analysis.design import allocation, profiles

BLOCK_YEARS = round(150 ** (1 / 5))
US_END = 1980
INFEASIBLE = "infeasible"


def _sgd_test(w: np.ndarray, sgd: pd.DataFrame, p: profiles.Profile) -> dict:
    real = metrics.real_returns(
        pd.Series(sgd[allocation.ASSETS].to_numpy() @ w, index=sgd.index), sgd["inflation"]
    )
    return allocation._profile_test(real, 12, p)


def max_equity_candidate(p: profiles.Profile, sgd: pd.DataFrame) -> float | None:
    """Largest equity share (1% steps, rest SGS) meeting p's v2 limits on SGD history."""
    for e in np.round(np.arange(1.0, -0.001, -0.01), 2):
        if _sgd_test(np.array([e, 1 - e, 0.0]), sgd, p)["ok"]:
            return float(e)
    return None


def _jst_real() -> pd.DataFrame:
    jst = data.jst()
    return pd.DataFrame(
        {
            "equity": metrics.real_returns(jst["eq_tr"], jst["inflation"]),
            "bonds": metrics.real_returns(jst["bond_tr"], jst["inflation"]),
            "cash": metrics.real_returns(jst["bill_rate"], jst["inflation"]),
        }
    ).dropna()


def h1_windows(w: np.ndarray, p, real: pd.DataFrame) -> np.ndarray:
    """Cumulative real returns over every horizon-length window in each non-US JST country,
    pooled (windows never span a missing year)."""
    windows = []
    for country, g in real.groupby(level="country"):
        if country == "USA":
            continue
        g = g.droplevel("country")
        s = pd.Series(g.to_numpy() @ w, index=g.index)
        s = s.reindex(range(int(s.index.min()), int(s.index.max()) + 1))
        windows.append(metrics.rolling_annualised(s, p.window_years, 1))
    return (1 + pd.concat(windows).to_numpy()) ** p.window_years - 1


def h1_worst(w: np.ndarray, p, real: pd.DataFrame) -> tuple[str, int, float]:
    """Country, end year and cumulative real return of the worst H1 window."""
    worst = ("", 0, np.inf)
    for country, g in real.groupby(level="country"):
        if country == "USA":
            continue
        g = g.droplevel("country")
        s = pd.Series(g.to_numpy() @ w, index=g.index)
        s = s.reindex(range(int(s.index.min()), int(s.index.max()) + 1))
        cum = (1 + metrics.rolling_annualised(s, p.window_years, 1)) ** p.window_years - 1
        if len(cum) and cum.min() < worst[2]:
            worst = (str(country), int(cum.idxmin()), float(cum.min()))
    return worst


def h1_non_us(w: np.ndarray, p, real: pd.DataFrame) -> float:
    return float((h1_windows(w, p, real) < 0).mean())


A35_DURATION_REF = REFERENCE / "bond_durations.csv"
LONG_BOND_STRESS = ("1940-01", "1981-12")


def a35_duration() -> float:
    ref = pd.read_csv(A35_DURATION_REF)
    return float(
        ref.loc[ref["share_class"].str.startswith("A35"), "effective_duration_years"].iloc[0]
    )


@functools.cache
def us_bond_proxy() -> pd.Series:
    """Modelled US government bond returns duration-matched to A35 (post-holdout correction,
    2026-10-27): a par bond rolled monthly at A35's duration, priced off Shiller's long-rate
    yield with a flat curve (metrics.constant_duration_returns)."""
    sh = data.monthly("us_monthly_shiller")
    return metrics.constant_duration_returns(sh["us_gov10_yield"].dropna(), a35_duration())


def _us_real(w: np.ndarray, bonds: str = "proxy", start=None, end=f"{US_END}-12") -> pd.Series:
    """US real monthly returns of an equity/bond mix. bonds = 'proxy' (duration-matched to
    A35, modelled) or 'long' (Shiller's long government bond total return)."""
    sh = data.monthly("us_monthly_shiller").loc[start:end]
    bond = us_bond_proxy().reindex(sh.index) if bonds == "proxy" else sh["us_gov10_tr_nominal_usd"]
    port = w[0] * sh["us_eq_tr_nominal_usd"] + (w[1] + w[2]) * bond
    return metrics.real_returns(port, sh["us_cpi_inflation"]).dropna()


def _us_pre1981_real(w: np.ndarray, bonds: str = "long") -> pd.Series:
    """H2 path. The v2 record keeps Shiller's long bond; the risk menu uses the proxy."""
    return _us_real(w, bonds)


def us_drawdown_episode(w: np.ndarray) -> tuple[str, str, float]:
    """Peak month, trough month and size of the largest real drawdown on the menu's US path."""
    r = _us_pre1981_real(w, "proxy")
    wealth = (1 + r).cumprod()
    dd = wealth / wealth.cummax() - 1
    trough = dd.idxmin()
    return str(wealth.loc[:trough].idxmax()), str(trough), float(dd.min())


def h2_windows(w: np.ndarray, p, bonds: str = "long") -> np.ndarray:
    ann = metrics.rolling_annualised(_us_pre1981_real(w, bonds), p.window_years, 12)
    return (1 + ann.to_numpy()) ** p.window_years - 1


def h2_us_pre1981(w: np.ndarray, p) -> float:
    return allocation.loss_share(_us_pre1981_real(w), p.window_years, 12)


def h3_paths(w: np.ndarray, p, glob: pd.DataFrame) -> np.ndarray:
    """Cumulative real return of each bootstrap path of the horizon's length."""
    r = glob[allocation.ASSETS].to_numpy() @ w
    generator = bootstrap.rng()
    out = np.empty(BOOTSTRAP_REPS)
    for i in range(BOOTSTRAP_REPS):
        idx = bootstrap.moving_block_indices(len(r), BLOCK_YEARS, generator)[: p.window_years]
        out[i] = np.prod(1 + r[idx]) - 1
    return out


def h3_bootstrap(w: np.ndarray, p, glob: pd.DataFrame) -> float:
    return float((h3_paths(w, p, glob) < 0).mean())


def run() -> dict:
    comparison = allocation.compare()
    table = comparison["table"]
    sgd = allocation.sgd_history()
    glob = allocation.global_portfolio_real()
    jst_real = _jst_real()
    rows, selected = [], {}
    for p in profiles.PROFILES:
        cands = {}
        for _, row in table[(table["profile"] == p.name) & table["meets_limits"]].iterrows():
            cands[row["method"]] = np.array([row["w_equity"], row["w_bonds"], row["w_cash"]])
        e = max_equity_candidate(p, sgd)
        if e is not None:
            cands["Maximum equity meeting limits (post-backtest)"] = np.array([e, 1 - e, 0.0])
        for name, w in cands.items():
            h1, h2, h3 = h1_non_us(w, p, jst_real), h2_us_pre1981(w, p), h3_bootstrap(w, p, glob)
            tol = p.loss_probability_max
            real_glob = pd.Series(glob[allocation.ASSETS].to_numpy() @ w)
            rows.append(
                {
                    "profile": p.name,
                    "candidate": name,
                    "w_equity": float(w[0]),
                    "w_bonds": float(w[1]),
                    "w_cash": float(w[2]),
                    "tolerance": tol,
                    "h1_non_us_loss_share": h1,
                    "h2_us_pre1981_loss_share": h2,
                    "h3_bootstrap_loss_share": h3,
                    "passes_holdout": bool(h1 <= tol and h2 <= tol and h3 <= tol),
                    "expected_real_return": float(np.expm1(np.log1p(real_glob).mean())),
                }
            )
        prof = pd.DataFrame([r for r in rows if r["profile"] == p.name])
        passing = prof[prof["passes_holdout"]] if len(prof) else prof
        selected[p.name] = (
            passing.sort_values("expected_real_return", ascending=False).iloc[0]["candidate"]
            if len(passing)
            else INFEASIBLE
        )
    return {
        "table": pd.DataFrame(rows),
        "selected": selected,
        "in_sample_selected": comparison["selected"],
        "block_years": BLOCK_YEARS,
    }


def v1_finding() -> pd.DataFrame:
    """Why the v1 limits were infeasible: v1 limits tested on the worst single JST country
    and on the global JST portfolio (1871-2020), for all-cash and equity/bond mixes."""
    real, glob = _jst_real(), allocation.global_portfolio_real()
    rows = {}
    mixes = {
        "100% cash": [0, 0, 1],
        **{f"{e}/{100 - e}": [e / 100, 1 - e / 100, 0] for e in (0, 25, 50, 75, 100)},
    }
    for p in profiles.PROFILES_V1:
        for label, w in mixes.items():
            w = np.array(w, dtype=float)
            worst_country = []
            for _, g in real.groupby(level="country"):
                g = g.droplevel("country")
                s = pd.Series(g.to_numpy() @ w, index=g.index)
                s = s.reindex(range(int(s.index.min()), int(s.index.max()) + 1))
                worst_country.append(
                    allocation._worst_window(s, p.window_years, 1, p.floor_is_annualised)
                )
            g_series = pd.Series(glob[allocation.ASSETS].to_numpy() @ w, index=glob.index)
            rows[(p.name, label)] = {
                "v1_floor": p.worst_window_floor,
                "worst_single_country": float(np.nanmin(worst_country)),
                "global_portfolio": allocation._worst_window(
                    g_series, p.window_years, 1, p.floor_is_annualised
                ),
            }
    return pd.DataFrame(rows).T


def frontier(step: float = 0.10) -> pd.DataFrame:
    """Each profile's in-sample and holdout measures for equity/SGS mixes, to show which
    limit binds."""
    sgd = allocation.sgd_history()
    glob = allocation.global_portfolio_real()
    real = _jst_real()
    rows = {}
    for p in profiles.PROFILES:
        for e in np.round(np.arange(0, 1 + 1e-9, step), 2):
            w = np.array([e, 1 - e, 0.0])
            t = _sgd_test(w, sgd, p)
            rows[(p.name, f"{e:.0%} equity")] = {
                "sgd_worst_window": t["worst_window"],
                "sgd_loss_share": t["loss_share"],
                "sgd_max_drawdown": t["max_drawdown"],
                "meets_in_sample": t["ok"],
                "h1_non_us_loss_share": h1_non_us(w, p, real),
                "h2_us_pre1981_loss_share": h2_us_pre1981(w, p),
                "h3_bootstrap_loss_share": h3_bootstrap(w, p, glob),
            }
    return pd.DataFrame(rows).T


DRAWDOWN_TOLERANCES = [-0.20, -0.30, -0.40, -0.50]
CVAR_ALPHA = 0.05


def risk_frontier(step: float = 0.01) -> pd.DataFrame:
    """Per horizon and equity/SGS mix (post-holdout rule, 2026-10-27; US bond proxy corrected
    the same day, also post-holdout):

    - max_drawdown: the worse of the real SGD monthly path (1998 onwards) and the US real
      monthly path before 1981 with bonds = a modelled US government bond duration-matched to
      A35 (us_bond_proxy). Annual JST data are not used for drawdowns because annual
      observations hide falls within the year. Drawdowns do not depend on the horizon.
    - stress_long_bond_1940_81: drawdown with Shiller's long government bond instead, January
      1940 to December 1981. Reported, not binding.
    - p_loss_holdout: the highest real-loss share across H1, H2 (proxy bonds) and H3.
    - worst_window_holdout: the worst cumulative real return over any horizon-length window in
      the actual histories (H1 and H2; bootstrap paths are excluded).
    - cvar5_holdout: the lowest of the three tests' CVaR at 5% of horizon real returns.
    - expected_real_return: the global JST portfolio's long-run real return.
    """
    sgd = allocation.sgd_history()
    glob = allocation.global_portfolio_real()
    real = _jst_real()
    rows = []
    for e in np.round(np.arange(0, 1 + 1e-9, step), 2):
        w = np.array([e, 1 - e, 0.0])
        sgd_real = metrics.real_returns(
            pd.Series(sgd[allocation.ASSETS].to_numpy() @ w, index=sgd.index), sgd["inflation"]
        )
        dd_sgd = metrics.max_drawdown(sgd_real)
        dd_us = metrics.max_drawdown(_us_pre1981_real(w, "proxy"))
        dd_long = metrics.max_drawdown(_us_real(w, "long", *LONG_BOND_STRESS))
        g = pd.Series(glob[allocation.ASSETS].to_numpy() @ w)
        for p in profiles.PROFILES:
            h1, h3 = h1_windows(w, p, real), h3_paths(w, p, glob)
            h2 = h2_windows(w, p, "proxy")
            rows.append(
                {
                    "profile": p.name,
                    "equity_share": float(e),
                    "expected_real_return": float(np.expm1(np.log1p(g).mean())),
                    "max_drawdown": min(dd_sgd, dd_us),
                    "max_drawdown_sgd": dd_sgd,
                    "max_drawdown_us_pre1981": dd_us,
                    "stress_long_bond_1940_81": dd_long,
                    "p_loss_holdout": max(float((x < 0).mean()) for x in (h1, h2, h3)),
                    "worst_window_holdout": float(min(h1.min(), h2.min())),
                    "cvar5_holdout": min(metrics.cvar(x, CVAR_ALPHA) for x in (h1, h2, h3)),
                }
            )
    return pd.DataFrame(rows)


def risk_menu(frontier: pd.DataFrame) -> pd.DataFrame:
    """For each horizon and drawdown tolerance: the highest-expected-return mix whose maximum
    drawdown is no worse than the tolerance. A menu, not a recommendation."""
    rows = {}
    for p in profiles.PROFILES:
        f = frontier[frontier["profile"] == p.name]
        for tol in DRAWDOWN_TOLERANCES:
            ok = f[f["max_drawdown"] >= tol]
            key = (p.name, f"{tol:.0%}")
            if ok.empty:
                rows[key] = {"result": "no mix"}
                continue
            best = ok.sort_values("expected_real_return", ascending=False).iloc[0]
            rows[key] = {**best.drop("profile").to_dict(), "result": "meets tolerance"}
    return pd.DataFrame(rows).T
