"""Claim 9: real estate earns long-run returns comparable to equities. Housing and listed
REITs are kept separate; price-only house indices are never compared with total returns.

Rules:
- Housing (JST): real total return (rent included) vs real capital gain only vs real equity
  return, per country, on years where all three exist. Reported for context: housing is not
  investable as an index and is never used as a REIT proxy.
- Listed REITs (verdict): each REIT ETF's total return (close + distributions, Yahoo) against an
  equity benchmark over the same months: VNQ vs the US market (French); global and regional
  REIT ETFs vs ACWI; SGD-listed REIT ETFs vs ACWI converted to SGD. Verdict: verdict_from_share
  over ETFs whose annualised total return was at least the benchmark's.
- Diversification beyond equities (US, VNQ): (a) spanning regression of VNQ excess returns on
  US equity and 10-year Treasury excess returns (HAC); a significantly positive alpha means
  REITs add to an equity/bond portfolio at equal risk; (b) Sharpe ratios of 60/40 and 54/36/10
  (10% REITs) portfolios, rebalanced monthly; Sharpe compares portfolios at equal risk.
- Correlation of VNQ with US equities and 10-year Treasuries: full period, rolling 36 months,
  and calendar 2008–2009, 2020 and 2022.
- Sanity checks per ETF: missing months, total-return vs price-only annualised return, worst
  drawdown in 2008–2009 where covered. VNQ is also compared privately with Nareit's All Equity
  REITs series; Nareit's terms do not allow the result to be published.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from analysis import charts, clean, data, metrics, prices, sources, stats
from analysis.config import DATA_PROCESSED, DATA_RAW, JST_CREDIT
from analysis.evidence import ClaimResult, verdict_from_share

SUBPERIODS = {
    "2008–2009": ("2008-01", "2009-12"),
    "2020": ("2020-01", "2020-12"),
    "2022": ("2022-01", "2022-12"),
}
REIT_TICKERS = list(sources.REIT_ETFS)


def housing_table() -> pd.DataFrame:
    jst = data.jst()
    real = pd.DataFrame(
        {
            "housing_total": metrics.real_returns(jst["housing_tr"], jst["inflation"]),
            "housing_price_only": metrics.real_returns(jst["housing_capgain"], jst["inflation"]),
            "equity": metrics.real_returns(jst["eq_tr"], jst["inflation"]),
        }
    ).dropna()
    rows = {}
    for country, g in real.groupby(level="country"):
        cagr = {c: float(np.expm1(np.log1p(g[c]).mean())) for c in g.columns}
        rows[country] = {"years": len(g), **cagr}
    return pd.DataFrame(rows).T.sort_values("housing_total")


def etf_returns() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Monthly total and price-only returns for the REIT ETFs (trading currency)."""
    total, price = {}, {}
    for ticker in REIT_TICKERS:
        df = prices.PRICE_SOURCE.read(DATA_RAW / prices.PRICE_SOURCE.name / f"{ticker}.csv")
        df = df[df["close"].notna()]
        total[ticker] = clean.complete_months(
            metrics.total_returns_from_distributions(df["close"], df["dividend"])
        )
        price[ticker] = clean.complete_months(df["close"].pct_change().iloc[1:])
    return pd.DataFrame(total), pd.DataFrame(price)


def benchmarks() -> dict[str, pd.Series]:
    fx = data.monthly("usdsgd_month_end")["usd_vs_sgd_change"]
    acwi = data.monthly("etf_monthly")["ACWI_tr_nominal_usd"]
    return {
        "USD_US": data.monthly("us_monthly_french")["us_eq_tr_nominal_usd"],
        "USD_GLOBAL": acwi,
        "SGD_GLOBAL": metrics.to_base_currency(acwi, fx),
    }


BENCHMARK_FOR = {
    "VNQ": ("USD_US", "US market"),
    "CLR.SI": ("SGD_GLOBAL", "ACWI in SGD"),
    "CFA.SI": ("SGD_GLOBAL", "ACWI in SGD"),
    "SRT.SI": ("SGD_GLOBAL", "ACWI in SGD"),
}


def reit_vs_equity(total: pd.DataFrame) -> pd.DataFrame:
    bench = benchmarks()
    rows = {}
    for ticker in REIT_TICKERS:
        key, label = BENCHMARK_FOR.get(ticker, ("USD_GLOBAL", "ACWI"))
        pair = pd.concat(
            [total[ticker].rename("reit"), bench[key].rename("bench")], axis=1
        ).dropna()
        rows[ticker] = {
            "description": sources.REIT_ETFS[ticker][0],
            "benchmark": label,
            "period": f"{pair.index[0]} to {pair.index[-1]}",
            "reit_return": metrics.annualised_return(pair["reit"], 12),
            "benchmark_return": metrics.annualised_return(pair["bench"], 12),
            "reit_vol": metrics.annualised_volatility(pair["reit"], 12),
            "benchmark_vol": metrics.annualised_volatility(pair["bench"], 12),
            "reit_max_drawdown": metrics.max_drawdown(pair["reit"]),
            "correlation": pair["reit"].corr(pair["bench"]),
        }
    return pd.DataFrame(rows).T


def sanity(total: pd.DataFrame, price: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for ticker in REIT_TICKERS:
        t = total[ticker].dropna()
        full = pd.period_range(t.index[0], t.index[-1], freq="M")
        p = price[ticker].loc[t.index]
        crisis = t.loc["2008-01":"2009-12"]
        rows[ticker] = {
            "months": len(t),
            "missing_months": len(full.difference(t.index)),
            "total_return": metrics.annualised_return(t, 12),
            "price_only_return": metrics.annualised_return(p, 12),
            "drawdown_2008_2009": metrics.max_drawdown(crisis) if len(crisis) == 24 else np.nan,
        }
    return pd.DataFrame(rows).T


def us_reit_tests(total: pd.DataFrame) -> dict:
    french = data.monthly("us_monthly_french")
    df = pd.DataFrame(
        {
            "reit": total["VNQ"],
            "equity": french["us_eq_tr_nominal_usd"],
            "bonds": data.monthly("us_treasury_monthly")["us_gov10_tr_nominal_usd"],
            "rf": french["us_bill1m_tr_nominal_usd"],
        }
    ).dropna()
    ex = df[["reit", "equity", "bonds"]].sub(df["rf"], axis=0)
    fit = sm.OLS(ex["reit"], sm.add_constant(ex[["equity", "bonds"]])).fit(
        cov_type="HAC", cov_kwds={"maxlags": stats.newey_west_lags(len(ex))}
    )
    p6040 = 0.6 * df["equity"] + 0.4 * df["bonds"]
    p_reit = 0.54 * df["equity"] + 0.36 * df["bonds"] + 0.10 * df["reit"]
    sharpe = {
        name: metrics.sharpe_ratio((1 + p) / (1 + df["rf"]) - 1, 0.0, 12)
        for name, p in {"60/40": p6040, "54/36/10 with REITs": p_reit}.items()
    }
    corr = {"full period": (df["reit"].corr(df["equity"]), df["reit"].corr(df["bonds"]))}
    for label, (start, end) in SUBPERIODS.items():
        g = df.loc[start:end]
        corr[label] = (g["reit"].corr(g["equity"]), g["reit"].corr(g["bonds"]))
    rolling = df["reit"].rolling(36).corr(df["equity"]).dropna()
    return {
        "period": f"{df.index[0]} to {df.index[-1]}",
        "alpha_per_year": float(fit.params["const"] * 12),
        "alpha_t": float(fit.tvalues["const"]),
        "beta_equity": float(fit.params["equity"]),
        "beta_bonds": float(fit.params["bonds"]),
        "sharpe": sharpe,
        "correlations": pd.DataFrame(corr, index=["with US equities", "with 10-year Treasuries"]).T,
        "rolling_min": float(rolling.min()),
        "rolling_max": float(rolling.max()),
        "frame": df,
    }


def _private_nareit_check(total: pd.DataFrame) -> None:
    """Write the VNQ vs Nareit comparison to data/processed only (never published)."""
    path = DATA_PROCESSED / f"{clean.PRIVATE_PREFIX}us_reit_nareit_monthly.csv"
    if not path.exists():
        return
    nareit = pd.read_csv(path, index_col=0)
    nareit.index = pd.PeriodIndex(nareit.index, freq="M")
    pair = pd.concat(
        [total["VNQ"].rename("vnq"), nareit["us_reit_tr_nominal_usd"]], axis=1
    ).dropna()
    pd.DataFrame(
        {
            "correlation": [pair.corr().iloc[0, 1]],
            "vnq_annualised": [metrics.annualised_return(pair["vnq"], 12)],
            "nareit_annualised": [metrics.annualised_return(pair["us_reit_tr_nominal_usd"], 12)],
            "months": [len(pair)],
        }
    ).to_csv(DATA_PROCESSED / f"{clean.PRIVATE_PREFIX}vnq_vs_nareit_check.csv", index=False)


def _figure_housing(table: pd.DataFrame) -> "charts.Path":
    fig, ax = charts.figure(height_in=6.0)
    ordered = table.sort_values("housing_total")
    y = np.arange(len(ordered))
    labels = {
        "housing_total": "Housing, total return (rent included)",
        "housing_price_only": "Housing, price only",
        "equity": "Equities, total return",
    }
    for i, col in enumerate(labels):
        ax.scatter(
            ordered[col].astype(float) * 100,
            y,
            s=42,
            color=charts.SERIES[i],
            label=labels[col],
            zorder=3,
            edgecolors=charts.SURFACE,
            linewidths=1,
        )
    ax.axvline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    ax.set_yticks(y, ordered.index)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Real annualised return, % per year (local currency)")
    ax.set_xlim(right=float(table[list(labels)].astype(float).max().max()) * 100 + 4.5)
    ax.legend(loc="lower right", fontsize=8.5)
    gap = (table["housing_total"] - table["housing_price_only"]).astype(float).median()
    charts.titles(
        fig,
        f"Price-only house indices understate housing returns by {gap:.1%} a year (median)",
        "Real returns by country on years with housing and equity data, 1870–2020",
    )
    return charts.save(fig, "claim09_housing_total_vs_price", JST_CREDIT, {"jst"})


def _figure_reits(table: pd.DataFrame) -> "charts.Path":
    fig, ax = charts.figure(height_in=5.2)
    y = np.arange(len(table))[::-1]
    ax.barh(
        y + 0.18,
        table["reit_return"].astype(float) * 100,
        height=0.34,
        color=charts.SERIES[0],
        label="REIT ETF",
    )
    ax.barh(
        y - 0.18,
        table["benchmark_return"].astype(float) * 100,
        height=0.34,
        color=charts.SERIES[1],
        label="Equity benchmark, same months",
    )
    ax.set_yticks(
        y, [f"{t} vs {row.benchmark}\n{row.period}" for t, row in table.iterrows()], fontsize=8
    )
    ax.axvline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Annualised total return, % per year (nominal, trading currency)")
    top = float(table[["reit_return", "benchmark_return"]].astype(float).max().max()) * 100
    ax.set_xlim(right=top + 1)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncols=2, fontsize=8.5)
    n = int((table["reit_return"] >= table["benchmark_return"]).sum())
    charts.titles(
        fig,
        f"Listed REITs matched or beat equities in {n} of {len(table)} ETF comparisons",
        "Monthly total returns (close + distributions), each ETF against equities over its life",
    )
    return charts.save(
        fig,
        "claim09_reit_etfs_vs_equities",
        "Source: Yahoo Finance (REIT ETFs, ACWI); Kenneth French Data Library; FRED (DEXSIUS). "
        "Calculations: this project. ETFs are identifiers only, not recommendations.",
        {"yahoo", "french", "fred"},
    )


def run() -> ClaimResult:
    housing = housing_table()
    total, price = etf_returns()
    reits = reit_vs_equity(total)
    checks = sanity(total, price)
    us = us_reit_tests(total)
    _private_nareit_check(total)

    n_match = int((reits["reit_return"] >= reits["benchmark_return"]).sum())
    n_house = int((housing["housing_total"] >= housing["equity"]).sum())
    rent_gap = float((housing["housing_total"] - housing["housing_price_only"]).median())
    sharpe = us["sharpe"]
    figures = [_figure_reits(reits), _figure_housing(housing)]
    vnq = reits.loc["VNQ"]

    return ClaimResult(
        number=9,
        claim=(
            "Real estate earns long-run returns comparable to equities (listed REITs tested; "
            "housing reported separately)."
        ),
        verdict=verdict_from_share(n_match, len(reits)),
        headline=(
            f"Listed REIT ETFs matched or beat equities over the same months in {n_match} of "
            f"{len(reits)} cases; US REITs (VNQ, {vnq['period']}) returned "
            f"{vnq['reit_return']:.1%} a year vs {vnq['benchmark_return']:.1%} for US equities, "
            f"with a worst drawdown of {vnq['reit_max_drawdown']:.0%}. Adding 10% REITs to a "
            f"60/40 portfolio changed its Sharpe ratio from {sharpe['60/40']:.2f} to "
            f"{sharpe['54/36/10 with REITs']:.2f}; spanning alpha {us['alpha_per_year']:+.1%} a "
            f"year (t = {us['alpha_t']:.1f})."
        ),
        data=(
            "Listed REITs: Yahoo Finance monthly total returns (close + distributions) of "
            + ", ".join(REIT_TICKERS)
            + "; equities: French US market, ACWI (Yahoo), FRED month-end USD/SGD for SGD "
            "benchmarks. Housing: JST R6 annual total and capital-gain returns, 1870–2020. "
            "Nominal returns in each ETF's trading currency; housing real, local currency."
        ),
        method=(
            "Each REIT ETF compared with an equity benchmark on the same months (annualised "
            "total return, volatility, drawdown, correlation). Spanning regression of VNQ excess "
            "returns on US equity and 10-year Treasury excess returns (HAC); Sharpe of 60/40 vs "
            "54/36/10 with REITs, rebalanced monthly. Housing: real CAGR of total return vs "
            "price-only vs equities per country."
        ),
        findings=[
            "REIT ETFs vs equities: "
            + "; ".join(
                f"{t} ({row.period}): {row.reit_return:.1%} vs {row.benchmark_return:.1%} "
                f"{row.benchmark}, volatility {row.reit_vol:.1%} vs {row.benchmark_vol:.1%}, "
                f"correlation {row.correlation:.2f}"
                for t, row in reits.iterrows()
            )
            + ".",
            "US REIT correlations (VNQ): "
            + "; ".join(
                f"{k}: {row['with US equities']:.2f} with equities, "
                f"{row['with 10-year Treasuries']:.2f} with Treasuries"
                for k, row in us["correlations"].iterrows()
            )
            + f". Rolling 36-month correlation with equities ranged from {us['rolling_min']:.2f} "
            f"to {us['rolling_max']:.2f}.",
            f"Spanning test: VNQ's alpha over US equities and Treasuries was "
            f"{us['alpha_per_year']:+.1%} a year (t = {us['alpha_t']:.1f}), equity beta "
            f"{us['beta_equity']:.2f}, bond beta {us['beta_bonds']:.2f}. "
            + (
                "REITs added return at equal risk beyond equities and bonds."
                if us["alpha_t"] > 2
                else "REITs did not add a statistically significant return at equal risk beyond "
                "equities and bonds; a correlation below 1 alone is not evidence that they do."
            ),
            f"Housing (JST, real, rent included) returned at least as much as equities in "
            f"{n_house} of {len(housing)} countries. Price-only house indices understated the "
            f"real total return by a median {rent_gap:.1%} a year across countries (the net "
            "rental yield), so comparing them with total-return equities is misleading.",
            "Sanity checks: "
            + "; ".join(
                f"{t}: {int(row.months)} months, {int(row.missing_months)} missing, total "
                f"{row.total_return:.1%} vs price-only {row.price_only_return:.1%} a year"
                + (
                    f", 2008–2009 drawdown {row.drawdown_2008_2009:.0%}"
                    if pd.notna(row.drawdown_2008_2009)
                    else ""
                )
                for t, row in checks.iterrows()
            )
            + ". VNQ was also compared privately with Nareit's All Equity REITs series; the "
            "result is not reported because Nareit's terms do not permit it.",
        ],
        caveats=[
            "Listed REIT history here starts in 2004 (US) and 2008 (global); one full credit "
            "cycle. No free, long, verifiable non-US REIT total-return series was found, so "
            "nothing is spliced or extrapolated (see docs/limitations.md).",
            "ETF returns are market-price based and after fund fees; issuer cross-checks (at "
            "least 3 years per ETF) are pending in reference/etf_annual_returns.csv.",
            "Withholding tax on REIT distributions for a Singapore resident is not deducted here; "
            "it is calculated by fund domicile in Phase 4 and can be material given REIT yields.",
            "Housing returns (JST) are estimates for an unlevered, illiquid, undiversified asset "
            "and are not comparable to investable index returns.",
        ],
        tables={
            "reit_etfs_vs_equities": reits,
            "us_reit_correlations": us["correlations"],
            "reit_sanity_checks": checks,
            "housing_by_country": housing,
        },
        figures=figures,
    )
