"""Asset universe: which candidate asset classes join the core (global equities + SGS).

Rules (fixed before results were computed):
- Core: global equities (ACWI, unhedged in SGD) and the SGS bond sleeve (matched duration, see
  design/bond_options.py). Cash (the SGD one-month rate) is always available for liquidity.
- Candidates, monthly returns in SGD: investment-grade credit (LQD) and inflation-linked bonds
  (TIP), both hedged to SGD (fixed income is hedged; claim 12); global REITs (RWO), gold (GLD)
  and commodities (DBC), unhedged. Common sample from the latest start date.
- A candidate is included only if it has an economic source of expected return (a claim on
  cash flows: coupons, dividends or rents, or an inflation-indexed accrual) AND passes either
  test below. (The return-source condition was added on 2026-10-27 after the first results,
  at the owner's direction, because the project spec requires an expected-return source for
  every asset and the original rule omitted it; see docs/decisions.md.)
  1. Spanning: regressing its excess return (over the SGD rate) on the core's two excess
     returns gives an alpha with HAC t > 2: it adds return at equal risk.
  2. Inflation role: in months classed high-inflation using only information available then
     (Singapore CPI, trailing 12 months, lagged 2 months, against expanding-window terciles
     with a 120-month burn-in), its mean monthly return beats a core 60/40 with HAC t > 2.
- Gold long-history check (not part of the rule): Damodaran annual gold vs S&P 500 and the
  10-year Treasury, 1928 onwards, nominal USD.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from analysis import charts, data, metrics, stats
from analysis.design import bond_options

CANDIDATES = {
    "Investment-grade credit": ("LQD", "hedged"),
    "Inflation-linked bonds": ("TIP", "hedged"),
    "Global REITs": ("RWO", "unhedged"),
    "Gold": ("GLD", "unhedged"),
    "Commodities": ("DBC", "unhedged"),
}
# Economic source of expected return: a claim on cash flows or an indexation accrual.
RETURN_SOURCE = {
    "Investment-grade credit": "coupons; credit spread over government bonds",
    "Inflation-linked bonds": "real coupons plus inflation-indexed accrual",
    "Global REITs": "rents passed through as dividends",
    "Gold": None,  # no cash flows; returns come from price changes only
    "Commodities": None,  # futures: collateral yield plus price and roll; no cash-flow claim
}
CPI_LAG_MONTHS, BURN_IN_MONTHS = 2, 120


def sg_inflation_regime() -> pd.Series:
    cpi = data.monthly("sg_cpi_monthly")["sg_cpi"]
    known = cpi.pct_change(12).shift(CPI_LAG_MONTHS)
    high_cut = known.expanding(min_periods=BURN_IN_MONTHS).quantile(2 / 3)
    return (known > high_cut).where(high_cut.notna())


def monthly_sgd() -> pd.DataFrame:
    fx = data.monthly("usdsgd_month_end")["usd_vs_sgd_change"]
    rf_sgd = data.monthly("sgd_rf_monthly")["sgd_rf_tr_nominal_sgd"]
    rf_usd = data.monthly("us_monthly_french")["us_bill1m_tr_nominal_usd"]
    etf = data.monthly("etf_monthly")
    cols = {
        "equity": metrics.to_base_currency(etf["ACWI_tr_nominal_usd"], fx),
        "rf": rf_sgd,
        "high_inflation": sg_inflation_regime(),
    }
    for name, (ticker, hedge) in CANDIDATES.items():
        usd = etf[f"{ticker}_tr_nominal_usd"]
        cols[name] = (
            metrics.hedged_return(usd, rf_sgd, rf_usd)
            if hedge == "hedged"
            else metrics.to_base_currency(usd, fx)
        )
    df = pd.DataFrame(cols)
    sgs = bond_options.sgs_matched(pd.Series(bond_options.target_duration(), index=df.index))
    return df.join(sgs["sgs"].rename("sgs"), how="inner").dropna()


def test_candidate(df: pd.DataFrame, name: str) -> dict:
    ex = df[["equity", "sgs", name]].sub(df["rf"], axis=0)
    fit = sm.OLS(ex[name], sm.add_constant(ex[["equity", "sgs"]])).fit(
        cov_type="HAC", cov_kwds={"maxlags": stats.newey_west_lags(len(ex))}
    )
    core = 0.6 * df["equity"] + 0.4 * df["sgs"]
    high = df["high_inflation"].astype(bool)
    infl = stats.hac_mean_test((df[name] - core)[high])
    spanning_pass = bool(fit.tvalues["const"] > 2)
    inflation_pass = bool(infl["t_stat"] > 2)
    return {
        "annual_return": metrics.annualised_return(df[name], 12),
        "volatility": metrics.annualised_volatility(df[name], 12),
        "correlation_with_equity": df[name].corr(df["equity"]),
        "spanning_alpha": float(fit.params["const"] * 12),
        "spanning_t": float(fit.tvalues["const"]),
        "high_inflation_months": int(high.sum()),
        "high_inflation_excess_vs_core": infl["mean"] * 12,
        "high_inflation_t": infl["t_stat"],
        "return_source": RETURN_SOURCE[name] or "none",
        "passes_spanning": spanning_pass,
        "passes_inflation_role": inflation_pass,
        "included": RETURN_SOURCE[name] is not None and (spanning_pass or inflation_pass),
    }


GOLD_FLOAT_START = 1972  # US gold convertibility ended in August 1971; earlier prices were fixed


def _gold_spanning(d: pd.DataFrame) -> dict:
    ex = (
        d[["gold_price_nominal_usd", "us_eq_tr_nominal_usd", "us_gov10_tr_nominal_usd"]]
        .sub(d["us_bill3m_tr_nominal_usd"], axis=0)
        .dropna()
    )
    fit = sm.OLS(
        ex["gold_price_nominal_usd"],
        sm.add_constant(ex[["us_eq_tr_nominal_usd", "us_gov10_tr_nominal_usd"]]),
    ).fit(cov_type="HAC", cov_kwds={"maxlags": stats.newey_west_lags(len(ex))})
    real = metrics.real_returns(d["gold_price_nominal_usd"], d["us_cpi_inflation"]).dropna()
    return {
        "period": f"{ex.index[0]}–{ex.index[-1]}",
        "alpha": float(fit.params["const"]),
        "alpha_t": float(fit.tvalues["const"]),
        "gold_real_return": float(np.expm1(np.log1p(real).mean())),
    }


def gold_long_history() -> dict:
    """Annual check: full Damodaran history and the free-floating period from 1972."""
    d = data.annual("us_annual_damodaran")
    return {"full": _gold_spanning(d), "floating": _gold_spanning(d.loc[GOLD_FLOAT_START:])}


def _figure(table: pd.DataFrame, period: str) -> "charts.Path":
    charts.style()
    fig, (left, right) = charts.plt.subplots(1, 2, figsize=(charts.WIDTH_IN, 4.4), sharey=True)
    y = np.arange(len(table))[::-1]
    left.barh(y, table["spanning_t"].astype(float), height=0.55, color=charts.SERIES[0])
    right.barh(y, table["high_inflation_t"].astype(float), height=0.55, color=charts.SERIES[0])
    for ax, title in [(left, "Spanning alpha t-stat"), (right, "High-inflation excess t-stat")]:
        ax.axvline(2, color=charts.TEXT_SECONDARY, linewidth=0.8, linestyle="--")
        ax.axvline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
        ax.set_xlabel(title + " (pass > 2)")
        ax.grid(axis="y", visible=False)
    left.set_yticks(y, table.index)
    n = int(table["included"].sum())
    charts.titles(
        fig,
        f"{n} of {len(table)} candidate asset classes passed an inclusion test",
        f"SGD investor, monthly, core = global equities + SGS, {period}",
    )
    return charts.save(
        fig,
        "design_asset_universe_tests",
        "Source: Yahoo Finance (ACWI, LQD, TIP, RWO, GLD, DBC); MAS (SGS yields, SGD rates); FRED "
        "(DEXSIUS); SingStat (CPI); Kenneth French Data Library. Calculations: this project.",
        {"yahoo", "mas", "fred", "singstat", "french"},
    )


def run() -> dict:
    df = monthly_sgd()
    table = pd.DataFrame({name: test_candidate(df, name) for name in CANDIDATES}).T
    period = f"{df.index[0]} to {df.index[-1]}"
    return {
        "table": table,
        "period": period,
        "gold_long": gold_long_history(),
        "figure": _figure(table, period),
    }
