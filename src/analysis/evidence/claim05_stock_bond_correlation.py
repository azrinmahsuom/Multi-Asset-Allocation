"""Claim 5: bonds diversify equities.

All US results are monthly, nominal USD unless a column says real. Rules:
- Data: French US market total return; a constant-maturity 10-year Treasury return built
  from FRED month-end yields (clean.us_treasury_monthly); FRED CPIAUCSL; French 1-month
  T-bill as the USD risk-free rate. February 1962 onwards.
- Lead test, ex-ante inflation regimes: each month is classed low/middle/high by the
  trailing 12-month CPI inflation known at the time (lagged CPI_LAG_MONTHS for publication),
  against tercile cut-offs computed only from months up to then (expanding window from
  1948, at least BURN_IN_MONTHS of history). No future data is used to label a month.
- Verdict: "diversify" in the strong (hedge) sense means negative correlation. It is judged on
  non-overlapping 36-month blocks, which are independent samples, with verdict_from_share.
  Overlapping rolling windows are shown for the time profile only.
- Confidence intervals: moving-block bootstrap (block = n^(1/5) months), 95% percentile.
- Portfolio impact: 60/40 equity/bond, rebalanced monthly, against 100% equity.
- Safe haven (Baur and Lucey 2010 form): regress bond returns on equity returns plus
  interactions with dummies for equity months in the bottom 10%, 5% and 1% (full-sample
  quantiles). A hedge has a non-positive slope overall; a safe haven has a non-positive
  total slope in the extreme months. HAC standard errors.
- SGD view: equity unhedged in SGD; bonds unhedged (converted at month-end USD/SGD) and
  hedged (plus the SGD-minus-USD one-month rate difference). Long proxy: developed-market
  equities vs US 10-year Treasuries, July 1990 onwards. Like-for-like: global equity ETF
  (ACWI) vs the unhedged and USD-hedged classes of one global aggregate bond fund, December
  2017 onwards.
- Long history: JST annual real equity vs bond returns per country, split at each country's
  median inflation (descriptive, in-sample).
"""

import textwrap

import numpy as np
import pandas as pd
import statsmodels.api as sm

from analysis import bootstrap, charts, data, metrics
from analysis.evidence import ClaimResult, verdict_from_share

WINDOW = 36
CPI_LAG_MONTHS = 2
BURN_IN_MONTHS = 120
EQUITY_WEIGHT = 0.6
SAFE_HAVEN_QUANTILES = [0.10, 0.05, 0.01]
REGIMES = ["low", "middle", "high"]

_PRIOR = (
    "set in the code before its first run, but informed by published research on a post-2000 "
    "sign change, so not independent of the data"
)
# Secondary splits, with when and why each was chosen (reported in the findings).
EPISODES = {
    "1962–1999": ("1962-02", "1999-12", _PRIOR),
    "2000–2021": ("2000-01", "2021-12", _PRIOR),
    "1973–1981": ("1973-01", "1981-12", "named in the project spec, after the event"),
    "2022": ("2022-01", "2022-12", "named in the project spec, after the event"),
    "2022 to latest": ("2022-01", None, "requested with a confidence interval, after the event"),
    "2023 to latest (excl. 2022)": ("2023-01", None, "requested, after the event"),
}


# --- data -----------------------------------------------------------------------------


def exante_regimes(
    cpi: pd.Series, lag: int = CPI_LAG_MONTHS, burn_in: int = BURN_IN_MONTHS
) -> pd.DataFrame:
    """Inflation known at each month and its regime, using only information available then."""
    known = cpi.pct_change(12).shift(lag)
    low_cut = known.expanding(min_periods=burn_in).quantile(1 / 3)
    high_cut = known.expanding(min_periods=burn_in).quantile(2 / 3)
    regime = pd.Series(
        np.select([known <= low_cut, known <= high_cut], ["low", "middle"], "high"),
        index=known.index,
    ).where(low_cut.notna())
    return pd.DataFrame({"inflation_known": known, "regime": regime})


def us_monthly() -> pd.DataFrame:
    equity = data.monthly("us_monthly_french")
    cpi = data.monthly("fred_monthly")["CPIAUCSL"]
    df = pd.DataFrame(
        {
            "equity": equity["us_eq_tr_nominal_usd"],
            "rf": equity["us_bill1m_tr_nominal_usd"],
            "bonds": data.monthly("us_treasury_monthly")["us_gov10_tr_nominal_usd"],
            "inflation_month": cpi.pct_change(),
        }
    ).join(exante_regimes(cpi))
    df = df.dropna(subset=["equity", "bonds"])
    df["equity_real"] = metrics.real_returns(df["equity"], df["inflation_month"])
    df["bonds_real"] = metrics.real_returns(df["bonds"], df["inflation_month"])
    df["rolling_corr"] = df["equity"].rolling(WINDOW).corr(df["bonds"])
    return df


def sgd_samples() -> dict[str, pd.DataFrame]:
    """Equity and bond returns in SGD, unhedged and hedged, for the two samples."""
    fx = data.monthly("usdsgd_month_end")["usd_vs_sgd_change"]
    rf_sgd = data.monthly("sgd_rf_monthly")["sgd_rf_tr_nominal_sgd"]
    rf_usd = data.monthly("us_monthly_french")["us_bill1m_tr_nominal_usd"]
    developed = data.monthly("developed_monthly_french")["developed_eq_tr_nominal_usd"]
    treasury = data.monthly("us_treasury_monthly")["us_gov10_tr_nominal_usd"]
    etf = data.monthly("etf_monthly")

    def build(equity_usd, bond_unhedged_usd, bond_hedged_usd):
        return pd.DataFrame(
            {
                "equity": metrics.to_base_currency(equity_usd, fx),
                "bonds_unhedged": metrics.to_base_currency(bond_unhedged_usd, fx),
                "bonds_hedged": metrics.hedged_return(bond_hedged_usd, rf_sgd, rf_usd),
            }
        ).dropna()

    return {
        "Developed equities vs US Treasuries (proxy)": build(developed, treasury, treasury),
        "Global equity ETF vs global aggregate bond ETF": build(
            etf["ACWI_tr_nominal_usd"],
            etf["AGGG.L_tr_nominal_usd"],
            etf["AGGU.L_tr_nominal_usd"],
        ),
    }


def jst_table() -> pd.DataFrame:
    jst = data.jst()
    real = pd.DataFrame(
        {
            "equity": metrics.real_returns(jst["eq_tr"], jst["inflation"]),
            "bonds": metrics.real_returns(jst["bond_tr"], jst["inflation"]),
            "inflation": jst["inflation"],
        }
    ).dropna()
    rows = {}
    for country, g in real.groupby(level="country"):
        high = g["inflation"] > g["inflation"].median()
        rows[country] = {
            "years": len(g),
            "corr_all": g["equity"].corr(g["bonds"]),
            "corr_high_inflation": g.loc[high, "equity"].corr(g.loc[high, "bonds"]),
            "corr_low_inflation": g.loc[~high, "equity"].corr(g.loc[~high, "bonds"]),
        }
    return pd.DataFrame(rows).T.sort_values("corr_all")


# --- statistics -----------------------------------------------------------------------


def corr_with_ci(x: pd.Series, y: pd.Series) -> dict:
    lo, hi = bootstrap.correlation_ci(x.to_numpy(), y.to_numpy())
    return {"months": len(x), "correlation": x.corr(y), "ci_low": lo, "ci_high": hi}


def portfolio_impact(equity: pd.Series, bonds: pd.Series) -> dict:
    """60/40 (monthly rebalanced) vs 100% equity: volatility reduction and diversification."""
    port = EQUITY_WEIGHT * equity + (1 - EQUITY_WEIGHT) * bonds
    vol_e, vol_b, vol_p = (metrics.annualised_volatility(s, 12) for s in (equity, bonds, port))
    return {
        "vol_equity": vol_e,
        "vol_60_40": vol_p,
        "vol_reduction": 1 - vol_p / vol_e,
        "diversification_ratio": (EQUITY_WEIGHT * vol_e + (1 - EQUITY_WEIGHT) * vol_b) / vol_p,
    }


def non_overlapping(equity: pd.Series, bonds: pd.Series, window: int = WINDOW) -> pd.DataFrame:
    """Correlation in consecutive, non-overlapping `window`-month blocks from the first month."""
    rows = []
    for b in range(len(equity) // window):
        part = slice(b * window, (b + 1) * window)
        e, d = equity.iloc[part], bonds.iloc[part]
        rows.append({"start": str(e.index[0]), "end": str(e.index[-1]), "correlation": e.corr(d)})
    return pd.DataFrame(rows)


def safe_haven(equity: pd.Series, bonds: pd.Series, cutoffs: dict[float, float]) -> pd.DataFrame:
    """Baur-Lucey regression: hedge slope and total slopes in the extreme equity months."""
    X = pd.DataFrame({"equity": equity})
    for q, cut in cutoffs.items():
        X[f"eq_x_bottom_{q:.0%}"] = equity * (equity <= cut)
    X = sm.add_constant(X)
    lags = int(np.floor(4 * (len(equity) / 100) ** (2 / 9)))
    fit = sm.OLS(bonds, X).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    terms = {"all months (hedge)": ["equity"]}
    included = ["equity"]
    for q in cutoffs:
        included = [*included, f"eq_x_bottom_{q:.0%}"]
        terms[f"bottom {q:.0%} equity months (safe haven)"] = included
    out = {}
    for label, names in terms.items():
        test = fit.t_test(np.array([1.0 if c in names else 0.0 for c in X.columns]))
        out[label] = {"slope": float(np.squeeze(test.effect)), "p_value": float(test.pvalue)}
    return pd.DataFrame(out).T


def classify(slope: float, p: float) -> str:
    if slope < 0 and p < 0.05:
        return "strong (significantly negative)"
    if slope <= 0 or p >= 0.05:
        return "weak (not significantly positive)"
    return "no (significantly positive)"


# --- figures --------------------------------------------------------------------------


def _ci_errors(df: pd.DataFrame) -> tuple[pd.Series, np.ndarray]:
    corr = df["correlation"].astype(float)
    low, high = df["ci_low"].astype(float), df["ci_high"].astype(float)
    return corr, np.vstack([corr - low, high - corr])


def _figure_regimes(regimes: pd.DataFrame, period: str) -> "charts.Path":
    fig, ax = charts.figure(height_in=4.5)
    x = np.arange(len(regimes))
    corr, err = _ci_errors(regimes)
    ax.errorbar(
        x, corr, yerr=err, fmt="o", markersize=9, color=charts.SERIES[0], capsize=6, elinewidth=2
    )
    ax.axhline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    ax.set_xticks(x, [f"{r}\n({row.inflation_range})" for r, row in regimes.iterrows()])
    ax.set_xlim(-0.6, len(regimes) - 0.4)
    ax.set_ylim(-1, 1)
    ax.grid(axis="x", visible=False)
    ax.set_xlabel("Inflation regime known at the time (trailing 12-month US CPI)")
    ax.set_ylabel("Stock–bond correlation (95% CI)")
    high, low = regimes.loc["high", "correlation"], regimes.loc["low", "correlation"]
    charts.titles(
        fig,
        "US stocks and bonds moved together more in high-inflation regimes"
        if high > low
        else "US stock–bond correlation was not higher in high-inflation regimes",
        f"Monthly US equity vs 10-year Treasury returns, nominal USD, by ex-ante inflation "
        f"regime, {period}",
    )
    return charts.save(
        fig,
        "claim05_correlation_by_inflation_regime",
        "Source: Kenneth French Data Library; FRED (DGS10 month-end yields, CPIAUCSL). "
        "Bond returns built from yields; regimes use only past CPI. Calculations: this project.",
        {"french", "fred"},
    )


def _figure_rolling(us: pd.DataFrame, blocks: pd.DataFrame) -> "charts.Path":
    charts.style()
    fig, (top, bottom) = charts.plt.subplots(
        2, 1, figsize=(charts.WIDTH_IN, 6.0), sharex=True, height_ratios=[2, 1]
    )
    x = us.index.to_timestamp()
    top.plot(
        x,
        us["rolling_corr"],
        color=charts.SERIES[0],
        linewidth=1.6,
        label=f"Rolling {WINDOW}-month (overlapping)",
    )
    ends = [pd.Period(e, freq="M").to_timestamp() for e in blocks["end"]]
    top.scatter(
        ends,
        blocks["correlation"],
        color=charts.SERIES[1],
        s=40,
        zorder=3,
        edgecolors=charts.SURFACE,
        label=f"Non-overlapping {WINDOW}-month blocks (at block end)",
    )
    top.axhline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    top.set_ylabel("Correlation")
    top.set_ylim(-1, 1)
    top.legend(loc="lower left")
    bottom.plot(x, us["inflation_known"] * 100, color=charts.SERIES[2], linewidth=1.6)
    bottom.set_ylabel("CPI inflation\nknown, % y/y")
    n_neg = int((blocks["correlation"] < 0).sum())
    charts.titles(
        fig,
        f"Stock–bond correlation was negative in {n_neg} of {len(blocks)} independent "
        "3-year blocks",
        f"US equity vs 10-year Treasury, monthly nominal USD (top); inflation known then "
        f"(bottom), {us.index[0]}–{us.index[-1]}",
    )
    return charts.save(
        fig,
        "claim05_stock_bond_correlation_us",
        "Source: Kenneth French Data Library; FRED (DGS10 month-end yields, CPIAUCSL). "
        "Bond returns built from yields. Calculations: this project.",
        {"french", "fred"},
    )


def _figure_sgd(sgd: pd.DataFrame) -> "charts.Path":
    fig, ax = charts.figure(height_in=4.5)
    samples = list(dict.fromkeys(sgd["sample"]))
    offsets = {"unhedged": -0.12, "hedged": 0.12}
    for i, hedge in enumerate(["unhedged", "hedged"]):
        sub = sgd[sgd["bonds"] == hedge].set_index("sample").loc[samples]
        corr, err = _ci_errors(sub)
        ax.errorbar(
            np.arange(len(samples)) + offsets[hedge],
            corr,
            yerr=err,
            fmt="o",
            markersize=9,
            capsize=6,
            elinewidth=2,
            color=charts.SERIES[i],
            label=f"Bonds {hedge} into SGD",
        )
    ax.axhline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    labels = [
        "\n".join([*textwrap.wrap(s, 28), sgd.loc[sgd["sample"] == s, "period"].iloc[0]])
        for s in samples
    ]
    ax.set_xticks(np.arange(len(samples)), labels)
    ax.set_xlim(-0.6, len(samples) - 0.4)
    ax.set_ylim(-1, 1)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Correlation with equities in SGD (95% CI)")
    ax.legend(loc="lower right")
    corr = sgd.pivot_table(index="sample", columns="bonds", values="correlation")
    n_lower = int((corr["unhedged"] < corr["hedged"]).sum())
    charts.titles(
        fig,
        f"SGD view: unhedged bonds were less correlated with equities in {n_lower} of "
        f"{len(corr)} samples",
        "Correlation of monthly SGD returns: equities unhedged; bonds unhedged vs hedged to SGD",
    )
    return charts.save(
        fig,
        "claim05_sgd_hedged_unhedged",
        "Source: Kenneth French Data Library; FRED (DGS10, DEXSIUS month-end); MAS (SORA, "
        "interbank); Yahoo Finance (ACWI, AGGG.L, AGGU.L). Hedge return assumes covered "
        "interest parity. Calculations: this project.",
        {"french", "fred", "mas", "yahoo"},
    )


# --- claim ----------------------------------------------------------------------------


def _regime_table(sample: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for r in REGIMES:
        g = sample[sample["regime"] == r]
        rows[r] = {
            "inflation_range": f"{g['inflation_known'].min():.1%} to "
            f"{g['inflation_known'].max():.1%}",
            **corr_with_ci(g["equity"], g["bonds"]),
            "correlation_real": g["equity_real"].corr(g["bonds_real"]),
            **portfolio_impact(g["equity"], g["bonds"]),
        }
    return pd.DataFrame(rows).T


def _sgd_table() -> pd.DataFrame:
    rows = []
    for name, df in sgd_samples().items():
        for hedge in ["unhedged", "hedged"]:
            bonds = df[f"bonds_{hedge}"]
            rows.append(
                {
                    "sample": name,
                    "period": f"{df.index[0]} to {df.index[-1]}",
                    "bonds": hedge,
                    **corr_with_ci(df["equity"], bonds),
                    "bond_vol": metrics.annualised_volatility(bonds, 12),
                    **portfolio_impact(df["equity"], bonds),
                }
            )
    return pd.DataFrame(rows)


def run() -> ClaimResult:
    us = us_monthly()
    period = f"{us.index[0]} to {us.index[-1]}"
    sample = us.dropna(subset=["regime"])
    regimes = _regime_table(sample)

    blocks = non_overlapping(us["equity"], us["bonds"])
    n_blocks, n_neg_blocks = len(blocks), int((blocks["correlation"] < 0).sum())
    windows = us["rolling_corr"].dropna()

    episodes = pd.DataFrame(
        {
            label: {**corr_with_ci(g["equity"], g["bonds"]), "chosen": note}
            for label, (start, end, note) in EPISODES.items()
            for g in [us.loc[start:end]]
        }
    ).T

    cutoffs = {q: us["equity"].quantile(q) for q in SAFE_HAVEN_QUANTILES}
    haven = safe_haven(us["equity"], us["bonds"], cutoffs)
    haven_by_regime = {
        r: safe_haven(g["equity"], g["bonds"], cutoffs).loc[
            "bottom 5% equity months (safe haven)", "slope"
        ]
        for r in REGIMES
        for g in [sample[sample["regime"] == r]]
    }
    worst = us["equity"] <= cutoffs[0.05]

    full = portfolio_impact(us["equity"], us["bonds"])
    port = EQUITY_WEIGHT * us["equity"] + (1 - EQUITY_WEIGHT) * us["bonds"]
    dd_equity, dd_port = metrics.max_drawdown(us["equity"]), metrics.max_drawdown(port)

    sgd = _sgd_table()
    countries = jst_table()
    n_c = len(countries)
    n_c_higher = int((countries["corr_high_inflation"] > countries["corr_low_inflation"]).sum())

    figures = [
        _figure_regimes(regimes, f"{sample.index[0]} to {sample.index[-1]}"),
        _figure_rolling(us, blocks),
        _figure_sgd(sgd),
    ]
    low, high = regimes.loc["low"], regimes.loc["high"]
    n_eff = len(us) // WINDOW
    latest = episodes.loc["2022 to latest"]
    ex2022 = episodes.loc["2023 to latest (excl. 2022)"]

    return ClaimResult(
        number=5,
        claim="Bonds diversify equities.",
        verdict=verdict_from_share(n_neg_blocks, n_blocks),
        summary_label=(
            "Fails as a hedge; diversifies outside high-inflation regimes (60/40 volatility "
            f"{full['vol_60_40']:.1%} vs {full['vol_equity']:.1%} for equities; maximum drawdown "
            f"{dd_port:.0%} vs {dd_equity:.0%})"
        ),
        headline=(
            "It depends on inflation. In months classed low-inflation using only data known at "
            f"the time, the US stock–bond correlation was {low['correlation']:.2f} (95% CI "
            f"{low['ci_low']:.2f} to {low['ci_high']:.2f}); in high-inflation months "
            f"{high['correlation']:.2f} ({high['ci_low']:.2f} to {high['ci_high']:.2f}). As a "
            f"hedge (negative correlation), bonds qualified in {n_neg_blocks} of {n_blocks} "
            "independent 3-year blocks."
        ),
        data=(
            "Monthly, nominal USD (real-return correlations alongside). US equity: French market "
            "total return. Bonds: 10-year constant-maturity Treasury return built from FRED "
            "month-end yields. Inflation: FRED CPIAUCSL. "
            f"Period {period}. SGD view: French developed-markets equities, ACWI, AGGG.L and "
            "AGGU.L, FRED month-end USD/SGD, MAS SGD rates. Long history: JST R6, annual, real."
        ),
        method=(
            "Regimes: trailing 12-month CPI inflation lagged two months for publication, against "
            "tercile cut-offs from data up to that month only (expanding window, 10-year "
            "burn-in). Correlations with 95% moving-block bootstrap intervals. Verdict on "
            f"non-overlapping {WINDOW}-month blocks. Portfolio impact: 60/40 rebalanced monthly vs "
            "100% equity. Safe-haven regression after Baur and Lucey (2010) with HAC errors."
        ),
        findings=[
            "Ex-ante inflation regimes (lead result): "
            + "; ".join(
                f"{r} ({row.inflation_range}, {int(row.months)} months): correlation "
                f"{row.correlation:.2f} [{row.ci_low:.2f}, {row.ci_high:.2f}], real "
                f"{row.correlation_real:.2f}; 60/40 cut volatility by {row.vol_reduction:.0%}"
                for r, row in regimes.iterrows()
            )
            + ".",
            f"Effective sample: {len(us)} months give {len(windows)} overlapping 3-year windows "
            f"but only {n_eff} independent ones. Non-overlapping blocks: {n_neg_blocks} of "
            f"{n_blocks} negative.",
            f"Since 2022: correlation {latest['correlation']:.2f} [{latest['ci_low']:.2f}, "
            f"{latest['ci_high']:.2f}] over {int(latest['months'])} months. Excluding 2022: "
            f"{ex2022['correlation']:.2f} [{ex2022['ci_low']:.2f}, {ex2022['ci_high']:.2f}] over "
            f"{int(ex2022['months'])} months.",
            "Secondary splits, with when they were chosen: "
            + "; ".join(
                f"{k}: {row.correlation:.2f} ({row.chosen})"
                for k, row in episodes.iloc[:4].iterrows()
            )
            + ".",
            f"Portfolio impact, full sample: 60/40 volatility {full['vol_60_40']:.1%} vs "
            f"{full['vol_equity']:.1%} for equities ({full['vol_reduction']:.0%} lower); "
            f"maximum drawdown {dd_port:.0%} vs {dd_equity:.0%}.",
            "Safe haven, full sample: "
            + "; ".join(
                f"{label}: slope {row.slope:.2f} (p={row.p_value:.2f}), "
                f"{classify(row.slope, row.p_value)}"
                for label, row in haven.iterrows()
            )
            + f". Bonds rose in {(us.loc[worst, 'bonds'] > 0).mean():.0%} of the worst 5% of "
            "equity months.",
            "Safe-haven slope in the bottom 5% of equity months, by ex-ante regime: "
            + "; ".join(f"{r}: {s:.2f}" for r, s in haven_by_regime.items())
            + ".",
            "SGD investor: "
            + "; ".join(
                f"{row.sample} ({row.period}), bonds {row.bonds}: correlation "
                f"{row.correlation:.2f} [{row.ci_low:.2f}, {row.ci_high:.2f}], bond volatility "
                f"{row.bond_vol:.1%}, 60/40 cut volatility by {row.vol_reduction:.0%}"
                for row in sgd.itertuples()
            )
            + ".",
            f"Long history (JST, annual, real, 16 countries): correlation was higher in "
            f"high-inflation years than in low-inflation years in {n_c_higher} of {n_c} "
            "countries.",
        ],
        caveats=[
            "CPIAUCSL is today's revised, seasonally adjusted series, not the figures published "
            "at the time; the two-month lag covers publication timing but not revisions.",
            "Safe-haven quantile cut-offs use the full sample, so that test is descriptive. "
            "Hedge and safe-haven definitions follow Baur and Lucey (2010, Financial Review "
            "45(2)); the regression form with extreme-quantile interactions is as described in "
            "the literature citing them, not checked against the paper's full text.",
            "Bootstrap block length n^(1/5), the rate Hall, Horowitz and Jing (1995, Biometrika "
            "82(3)) give for two-sided intervals. Regime subsets are not contiguous, so their "
            "blocks can span regime changes. The Newey-West lag rule floor(4(n/100)^(2/9)) is "
            "attributed to Newey and West (1994); the formula was not checked against the "
            "paper's text.",
            "SGD hedged returns assume covered interest parity with one-month forwards at MAS SGD "
            "and US 1-month T-bill rates; real hedges also pay a cross-currency basis and dealing "
            "spreads. The long SGD sample uses US Treasuries as a stand-in for global bonds; the "
            "like-for-like ETF sample is short (from December 2017).",
            "Correlation measures co-movement, not size; the portfolio-impact figures show size.",
            "The JST split at each country's median inflation is in-sample and descriptive.",
            "Regime inflation ranges overlap because the cut-offs use only past data and move "
            "over time: a month at 2% could be 'high' in the low-inflation 1960s and 'low' "
            "after the 1970s.",
        ],
        tables={
            "us_by_exante_inflation_regime": regimes,
            "us_non_overlapping_blocks": blocks.set_index("start"),
            "us_episodes": episodes,
            "us_safe_haven": haven,
            "sgd_hedged_vs_unhedged": sgd.set_index("sample"),
            "jst_countries": countries,
        },
        figures=figures,
    )
