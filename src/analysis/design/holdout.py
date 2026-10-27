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

import numpy as np
import pandas as pd

from analysis import bootstrap, data, metrics
from analysis.config import BOOTSTRAP_REPS
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


def h1_non_us(w: np.ndarray, p, real: pd.DataFrame) -> float:
    windows = []
    for country, g in real.groupby(level="country"):
        if country == "USA":
            continue
        g = g.droplevel("country")
        s = pd.Series(g.to_numpy() @ w, index=g.index)
        s = s.reindex(range(int(s.index.min()), int(s.index.max()) + 1))
        windows.append(metrics.rolling_annualised(s, p.window_years, 1))
    pooled = pd.concat(windows)
    return float((pooled < 0).mean())


def h2_us_pre1981(w: np.ndarray, p) -> float:
    sh = data.monthly("us_monthly_shiller").loc[: f"{US_END}-12"]
    port = w[0] * sh["us_eq_tr_nominal_usd"] + (w[1] + w[2]) * sh["us_gov10_tr_nominal_usd"]
    real = metrics.real_returns(port, sh["us_cpi_inflation"]).dropna()
    return allocation.loss_share(real, p.window_years, 12)


def h3_bootstrap(w: np.ndarray, p, glob: pd.DataFrame) -> float:
    r = glob[allocation.ASSETS].to_numpy() @ w
    generator = bootstrap.rng()
    losses = 0
    for _ in range(BOOTSTRAP_REPS):
        idx = bootstrap.moving_block_indices(len(r), BLOCK_YEARS, generator)[: p.window_years]
        losses += int(np.prod(1 + r[idx]) < 1)
    return losses / BOOTSTRAP_REPS


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


def final_allocations() -> dict[str, pd.Series | None]:
    """Weights (equity, bonds, cash) per profile from the v2 holdout; None if infeasible."""
    r = run()
    t = r["table"].set_index(["profile", "candidate"])
    out = {}
    for profile, cand in r["selected"].items():
        out[profile] = (
            None
            if cand == INFEASIBLE
            else pd.Series({a: float(t.loc[(profile, cand), f"w_{a}"]) for a in allocation.ASSETS})
        )
    return out


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
