"""Claim 8: inflation-linked bonds hedge inflation. Separates the inflation accrual from the
real-yield (duration) effect.

Rules:
- A 10-year constant-maturity TIPS is built monthly from FRED month-end 10-year TIPS real
  yields (DFII10), January 2003 onwards, nominal USD:
  - real return: a real par bond bought at last month's real yield and priced at this
    month's (metrics.par_bond_return on real yields);
  - real carry: last month's real yield / 12; real-yield effect = real return - carry;
  - inflation accrual over month m: CPI-U NSA (CPIAUCNS) of month m-2 over month m-3, the
    reference-CPI lag used for TIPS;
  - nominal return = (1 + real return) (1 + accrual) - 1.
- Check: annual returns compared with the TIP ETF (Yahoo, close + distributions).
- Hedge test (verdict): share of complete calendar years in which TIPS kept pace with that
  year's CPI-U inflation (real return >= 0), via verdict_from_share. Shown alongside the
  10-year nominal Treasury on the same test.
- Inflation beta: annual nominal return regressed on annual inflation; a perfect short-term
  hedge has beta 1.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from analysis import charts, data, metrics
from analysis.evidence import ClaimResult, verdict_from_share

MATURITY = 10


def tips_monthly() -> pd.DataFrame:
    t = data.monthly("us_treasury_monthly")
    cpi = data.monthly("fred_monthly")["CPIAUCNS"]
    real_yield = t["dfii10_yield"]
    df = pd.DataFrame(index=t.index)
    df["real_return"] = metrics.par_bond_return(real_yield.shift(1), real_yield, MATURITY)
    df["real_carry"] = real_yield.shift(1) / 12
    df["real_yield_effect"] = df["real_return"] - df["real_carry"]
    df["accrual"] = (cpi.shift(2) / cpi.shift(3) - 1).reindex(df.index)
    df["tips"] = (1 + df["real_return"]) * (1 + df["accrual"]) - 1
    df["nominal_10y"] = t["us_gov10_tr_nominal_usd"]
    df["cpi"] = cpi.reindex(df.index)
    return df.dropna(subset=["tips"])


def calendar_years(df: pd.DataFrame) -> pd.DataFrame:
    """Compounded calendar-year returns for complete years, with Dec/Dec CPI-U inflation."""
    counts = df.groupby(df.index.year).size()
    years = counts.index[counts == 12]
    annual = (
        1 + df[["tips", "nominal_10y", "accrual", "real_carry", "real_yield_effect"]]
    ).groupby(df.index.year).prod() - 1
    cpi_dec = df["cpi"].groupby(df.index.year).last()
    annual["inflation"] = cpi_dec.pct_change()
    annual = annual.loc[years].dropna(subset=["inflation"])
    annual["tips_real"] = metrics.real_returns(annual["tips"], annual["inflation"])
    annual["nominal_real"] = metrics.real_returns(annual["nominal_10y"], annual["inflation"])
    return annual


def inflation_beta(returns: pd.Series, inflation: pd.Series) -> dict:
    fit = sm.OLS(returns, sm.add_constant(inflation)).fit()
    low, high = fit.conf_int().loc[inflation.name]
    return {"beta": float(fit.params[inflation.name]), "ci_low": float(low), "ci_high": float(high)}


def _figure(df: pd.DataFrame) -> "charts.Path":
    fig, ax = charts.figure(height_in=4.8)
    x = df.index.to_timestamp()
    parts = {
        "Inflation accrual": "accrual",
        "Real carry (real yield earned)": "real_carry",
        "Real-yield change (duration effect)": "real_yield_effect",
    }
    ends = {}
    for i, (label, col) in enumerate(parts.items()):
        cumulative = np.expm1(np.log1p(df[col]).cumsum()) * 100
        ax.plot(x, cumulative, color=charts.SERIES[i], label=label)
        ends[col] = cumulative.iloc[-1]
    ax.axhline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    ax.set_ylabel("Cumulative contribution, %")
    ax.legend(loc="upper left", fontsize=8.5)
    charts.titles(
        fig,
        f"TIPS: inflation added {ends['accrual']:+.0f}%, real-yield changes "
        f"{ends['real_yield_effect']:+.0f}% since {df.index[0].year}",
        f"10-year constant-maturity TIPS built from FRED real yields and CPI-U, nominal USD, "
        f"{df.index[0]} to {df.index[-1]}",
    )
    return charts.save(
        fig,
        "claim08_tips_return_components",
        "Source: FRED (DFII10 month-end real yields, CPIAUCNS). TIPS returns built from yields "
        "with a CPI lag of two to three months. Calculations: this project.",
        {"fred"},
    )


def run() -> ClaimResult:
    df = tips_monthly()
    annual = calendar_years(df)
    n_years = len(annual)
    n_tips_kept_pace = int((annual["tips_real"] >= 0).sum())
    n_nominal_kept_pace = int((annual["nominal_real"] >= 0).sum())

    total_var = df["tips"].var()
    var_share = {
        "accrual": df["accrual"].var() / total_var,
        "real_yield_effect": df["real_yield_effect"].var() / total_var,
    }
    ry_share = var_share["real_yield_effect"]
    betas = pd.DataFrame(
        {
            "TIPS (built)": inflation_beta(annual["tips"], annual["inflation"]),
            "10-year nominal Treasury": inflation_beta(annual["nominal_10y"], annual["inflation"]),
        }
    ).T

    etf = data.monthly("etf_monthly")["TIP_tr_nominal_usd"].dropna()
    etf_counts = etf.groupby(etf.index.year).size()
    etf_annual = ((1 + etf).groupby(etf.index.year).prod() - 1).loc[
        etf_counts.index[etf_counts == 12]
    ]
    check = pd.concat([annual["tips"], etf_annual.rename("tip_etf")], axis=1).dropna()

    y2022 = annual.loc[2022]
    high_inflation = annual[annual["inflation"] > annual["inflation"].median()]
    figure = _figure(df)

    return ClaimResult(
        number=8,
        claim="Inflation-linked bonds hedge inflation.",
        verdict=verdict_from_share(n_tips_kept_pace, n_years),
        headline=(
            f"Over one-year horizons, 10-year TIPS kept pace with inflation in {n_tips_kept_pace} "
            f"of {n_years} calendar years ({n_nominal_kept_pace} for nominal 10-year "
            f"Treasuries). In 2022 they returned {y2022['tips']:+.1%} against "
            f"{y2022['inflation']:.1%} inflation: the accrual added {y2022['accrual']:+.1%} but "
            f"rising real yields took {y2022['real_yield_effect']:+.1%}."
        ),
        data=(
            "Monthly, nominal USD. 10-year constant-maturity TIPS built from FRED month-end real "
            "yields (DFII10) and CPI-U NSA (CPIAUCNS), "
            f"{df.index[0]} to {df.index[-1]}. Check: TIP ETF (Yahoo). Comparison: 10-year "
            "nominal Treasury built from DGS10."
        ),
        method=(
            "Monthly TIPS return split into inflation accrual (CPI with the TIPS reference "
            "lag), real carry and real-yield change. Hedge test on complete calendar years: "
            "real return after Dec/Dec CPI-U inflation. Inflation beta from annual returns."
        ),
        findings=[
            f"Monthly variance: the real-yield effect alone is {ry_share:.0%} of total TIPS "
            f"return variance, the inflation accrual {var_share['accrual']:.0%}. Over short "
            "horizons TIPS returns are driven mainly by "
            + ("real-yield moves." if ry_share > var_share["accrual"] else "the accrual."),
            "Inflation beta (annual return on annual inflation, 95% CI): "
            + "; ".join(
                f"{k}: {row.beta:.2f} [{row.ci_low:.2f}, {row.ci_high:.2f}]"
                for k, row in betas.iterrows()
            )
            + ". A perfect one-year hedge would have a beta of 1.",
            f"In the {len(high_inflation)} years with above-median inflation, TIPS kept pace in "
            f"{int((high_inflation['tips_real'] >= 0).sum())} and nominal Treasuries in "
            f"{int((high_inflation['nominal_real'] >= 0).sum())}.",
            f"2022 decomposition: accrual {y2022['accrual']:+.1%}, real carry "
            f"{y2022['real_carry']:+.1%}, real-yield change {y2022['real_yield_effect']:+.1%}; "
            f"TIPS {y2022['tips']:+.1%} vs nominal 10-year {y2022['nominal_10y']:+.1%}.",
            f"Check against the TIP ETF ({check.index.min()}–{check.index.max()}): correlation "
            f"of annual returns {check['tips'].corr(check['tip_etf']):.2f}, average gap "
            f"{(check['tips'] - check['tip_etf']).mean():+.1%} a year (the ETF holds shorter "
            "maturities and pays a fee).",
            "Held to maturity, a TIPS locks in its real yield at purchase plus realised "
            "inflation (before the CPI lag and tax); that horizon is not tested here because "
            "the data cover fewer than three non-overlapping 10-year periods.",
        ],
        caveats=[
            "TIPS returns are built from constant-maturity real yields, not traded bonds; the "
            "real-yield series starts in 2003 and includes the low-liquidity 2008 episode.",
            "US CPI-U inflation and USD returns: an SGD investor's inflation is Singapore CPI, "
            "and there are no SGD inflation-linked government bonds to compare.",
            "The above-median-inflation split is in-sample and descriptive.",
            "Taxes on the inflation accrual are ignored.",
            "Variance shares can exceed 100% in total, because the accrual and the real-yield "
            "effect partly offset each other.",
            "October 2025 US CPI was not published; that month is filled by geometric "
            "interpolation between September and November (rule in docs/decisions.md).",
        ],
        tables={
            "annual": annual,
            "inflation_beta": betas,
            "check_vs_tip_etf": check,
        },
        figures=[figure],
    )
