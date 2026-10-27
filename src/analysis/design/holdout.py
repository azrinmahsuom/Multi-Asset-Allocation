"""Holdout evaluation of the allocation candidates (added after the Phase 3 backtest).

Rules (fixed before the holdout results were computed; owner-approved 2026-10-27):
- Candidates per profile: each method's allocation that met the limits in-sample, plus
  "Maximum equity share meeting the profile's limits" (post-backtest): the largest equity
  share in 1-point steps, rest in the bond sleeve the three-way comparison selected (SGS),
  that meets the limits on SGD history.
- Holdout tests (data not used to choose the allocations):
  H1 JST non-US countries: annual real local-currency returns, full history; the share of
     the 15 countries where the mix meets the limits.
  H2 US before 1981: Shiller monthly real returns (S&P Composite with dividends; 10-year
     bond), February 1871 to December 1980; the share of rolling windows of the profile's
     length meeting the limits (for the long profile, the window's maximum drawdown too).
  H3 Block bootstrap: 2,000 paths of the profile's length drawn from the global JST
     portfolio (annual real USD, 1871-2020, GDP-weighted with the previous year's GDP in USD,
     bonds hedged); block length round(150^(1/5)) = 3 years; seed config.RANDOM_SEED. Score
     = 1 - breach rate.
- Drawdown bias: annual data understate drawdowns. The ratio of the monthly to the annual
  maximum drawdown of the same mix on US data (French market and 10-year Treasury monthly vs
  JST USA annual, 1962-2020) is measured per mix and applied to H1 and H3 annual drawdowns.
- Holdout score = mean of H1, H2 and H3 scores. Per profile, candidates within 0.05 of the
  best score tie; among ties the lowest H3 breach rate wins (owner's judgement call); exact
  ties on breach rate go to the higher holdout score, then the lower equity share.
"""

import numpy as np
import pandas as pd

from analysis import bootstrap, data, metrics
from analysis.config import BOOTSTRAP_REPS
from analysis.design import allocation, profiles

TIE_BAND = 0.05
BLOCK_YEARS = round(150 ** (1 / 5))
US_END = 1980


def max_equity_candidate(p: profiles.Profile, sgd: pd.DataFrame) -> float:
    """Largest equity share (1% steps, rest SGS) meeting p's limits on SGD history."""
    for e in np.round(np.arange(1.0, -0.001, -0.01), 2):
        w = np.array([e, 1 - e, 0.0])
        real = metrics.real_returns(
            pd.Series(sgd[allocation.ASSETS].to_numpy() @ w, index=sgd.index), sgd["inflation"]
        )
        win = allocation._worst_window(real, p.window_years, 12, p.floor_is_annualised)
        ok = win >= p.worst_window_floor
        if p.max_drawdown_cap is not None:
            ok = ok and metrics.max_drawdown(real) >= p.max_drawdown_cap
        if ok:
            return float(e)
    return 0.0


def drawdown_bias(equity_share: float) -> float:
    """Monthly / annual maximum drawdown ratio for an equity/bond mix on US data, 1962-2020."""
    eq = data.monthly("us_monthly_french")["us_eq_tr_nominal_usd"]
    bd = data.monthly("us_treasury_monthly")["us_gov10_tr_nominal_usd"]
    cpi = data.monthly("fred_monthly")["CPIAUCSL"].pct_change()
    m = pd.DataFrame({"e": eq, "b": bd, "i": cpi}).dropna().loc["1962-02":"2020-12"]
    monthly = metrics.real_returns(equity_share * m["e"] + (1 - equity_share) * m["b"], m["i"])
    us = data.jst().xs("USA", level="country").loc[1962:2020]
    annual = metrics.real_returns(
        equity_share * us["eq_tr"] + (1 - equity_share) * us["bond_tr"], us["inflation"]
    )
    dd_m, dd_a = metrics.max_drawdown(monthly), metrics.max_drawdown(annual)
    return float(dd_m / dd_a) if dd_a < 0 else 1.0


def _meets(series: pd.Series, p: profiles.Profile, periods: int, dd_scale: float) -> bool:
    win = allocation._worst_window(series, p.window_years, periods, p.floor_is_annualised)
    if np.isnan(win) or win < p.worst_window_floor:
        return False
    if p.max_drawdown_cap is not None:
        return metrics.max_drawdown(series) * dd_scale >= p.max_drawdown_cap
    return True


def h1_non_us(w: np.ndarray, p, dd_scale: float) -> float:
    jst = data.jst()
    real = pd.DataFrame(
        {
            "equity": metrics.real_returns(jst["eq_tr"], jst["inflation"]),
            "bonds": metrics.real_returns(jst["bond_tr"], jst["inflation"]),
            "cash": metrics.real_returns(jst["bill_rate"], jst["inflation"]),
        }
    ).dropna()
    passed = []
    for country, g in real.groupby(level="country"):
        if country == "USA":
            continue
        s = pd.Series(g.droplevel("country").to_numpy() @ w, index=g.droplevel("country").index)
        s = s.reindex(range(int(s.index.min()), int(s.index.max()) + 1))
        passed.append(_meets(s, p, 1, dd_scale))
    return float(np.mean(passed))


def h2_us_pre1981(w: np.ndarray, p) -> float:
    sh = data.monthly("us_monthly_shiller").loc[: f"{US_END}-12"]
    port = w[0] * sh["us_eq_tr_nominal_usd"] + (w[1] + w[2]) * sh["us_gov10_tr_nominal_usd"]
    real = metrics.real_returns(port, sh["us_cpi_inflation"]).dropna()
    n = p.window_years * 12
    ok = []
    for start in range(len(real) - n + 1):
        win = real.iloc[start : start + n]
        growth = float((1 + win).prod())
        stat = growth ** (1 / p.window_years) - 1 if p.floor_is_annualised else growth - 1
        good = stat >= p.worst_window_floor
        if p.max_drawdown_cap is not None:
            good = good and metrics.max_drawdown(win) >= p.max_drawdown_cap
        ok.append(good)
    return float(np.mean(ok))


def h3_bootstrap(w: np.ndarray, p, glob: pd.DataFrame, dd_scale: float) -> float:
    """Breach rate of the profile's limits over block-bootstrapped paths of its length."""
    r = glob[allocation.ASSETS].to_numpy() @ w
    generator = bootstrap.rng()
    breaches = 0
    for _ in range(BOOTSTRAP_REPS):
        idx = bootstrap.moving_block_indices(len(r), BLOCK_YEARS, generator)[: p.window_years]
        path = r[idx]
        growth = float(np.prod(1 + path))
        stat = growth ** (1 / p.window_years) - 1 if p.floor_is_annualised else growth - 1
        bad = stat < p.worst_window_floor
        if p.max_drawdown_cap is not None:
            wealth = np.cumprod(1 + path)
            dd = float(np.min(wealth / np.maximum.accumulate(wealth) - 1)) * dd_scale
            bad = bad or dd < p.max_drawdown_cap
        breaches += int(bad)
    return breaches / BOOTSTRAP_REPS


def run() -> dict:
    comparison = allocation.compare()
    table = comparison["table"]
    sgd = allocation.sgd_history()
    glob = allocation.global_portfolio_real()
    rows, selected, bias_rows, alternative = [], {}, {}, {}
    for p in profiles.PROFILES:
        cands = {}
        for _, row in table[(table["profile"] == p.name) & table["meets_limits"]].iterrows():
            cands[row["method"]] = np.array([row["w_equity"], row["w_bonds"], row["w_cash"]])
        e = max_equity_candidate(p, sgd)
        cands["Maximum equity meeting limits (post-backtest)"] = np.array([e, 1 - e, 0.0])
        for name, w in cands.items():
            scale = drawdown_bias(float(w[0]))
            bias_rows[(p.name, name)] = scale
            h1 = h1_non_us(w, p, scale)
            h2 = h2_us_pre1981(w, p)
            breach = h3_bootstrap(w, p, glob, scale)
            real_glob = pd.Series(glob[allocation.ASSETS].to_numpy() @ w)
            rows.append(
                {
                    "profile": p.name,
                    "candidate": name,
                    "w_equity": float(w[0]),
                    "w_bonds": float(w[1]),
                    "h1_non_us_share_passing": h1,
                    "h2_us_pre1981_share_of_windows": h2,
                    "h3_bootstrap_breach_rate": breach,
                    "holdout_score": float(np.mean([h1, h2, 1 - breach])),
                    "drawdown_bias_ratio": scale,
                    "expected_real_return": float(np.expm1(np.log1p(real_glob).mean())),
                }
            )
        prof = pd.DataFrame([r for r in rows if r["profile"] == p.name])
        best = prof["holdout_score"].max()
        tied = prof[prof["holdout_score"] >= best - TIE_BAND]
        selected[p.name] = tied.sort_values(
            ["h3_bootstrap_breach_rate", "holdout_score", "w_equity"],
            ascending=[True, False, True],
        ).iloc[0]["candidate"]
        alt = tied.sort_values("expected_real_return", ascending=False).iloc[0]
        alternative[p.name] = f"{alt['candidate']} ({alt['w_equity']:.0%} equities)"
    return {
        "table": pd.DataFrame(rows),
        "selected": selected,
        "in_sample_selected": comparison["selected"],
        "if_tie_break_were_return": alternative,
        "block_years": BLOCK_YEARS,
    }
