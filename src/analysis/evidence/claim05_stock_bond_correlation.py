"""Claim 5: bonds diversify equities.

Rules:
- US monthly: French market total return vs a constant-maturity 10-year Treasury built from
  month-end FRED yields (clean.us_treasury_monthly), February 1962 onwards. Nominal USD.
- Rolling 36-month correlation of monthly returns. Diversification in the claim's strong
  sense (a hedge) means negative correlation. Verdict: verdict_from_share over rolling
  windows with correlation below zero.
- Inflation regimes: trailing 12-month US CPI inflation (FRED CPIAUCSL), split into terciles
  over the sample (data-defined, descriptive, in-sample). The 1970s (1973–1981) and 2022 are
  reported as the owner-specified episodes.
- Tail test: in the worst 5% of equity months, the share in which bonds had a positive return.
- Cross-country: JST annual real equity vs bond returns, correlation over each country's
  sample, and in years with inflation above vs below that country's median.
"""

import pandas as pd

from analysis import charts, data, metrics
from analysis.evidence import ClaimResult, verdict_from_share

WINDOW = 36
EPISODES = {"1973–1981": ("1973-01", "1981-12"), "2022": ("2022-01", "2022-12")}


def us_monthly() -> pd.DataFrame:
    equity = data.monthly("us_monthly_french")["us_eq_tr_nominal_usd"]
    bonds = data.monthly("us_treasury_monthly")["us_gov10_tr_nominal_usd"]
    cpi = data.monthly("fred_monthly")["CPIAUCSL"]
    df = pd.DataFrame(
        {"equity": equity, "bonds": bonds, "inflation_12m": cpi.pct_change(12)}
    ).dropna(subset=["equity", "bonds"])
    df["rolling_corr"] = df["equity"].rolling(WINDOW).corr(df["bonds"])
    return df


def _figure(us: pd.DataFrame, n_neg: int, n_win: int) -> "charts.Path":
    charts.style()
    fig, (top, bottom) = charts.plt.subplots(
        2, 1, figsize=(charts.WIDTH_IN, 6.0), sharex=True, height_ratios=[2, 1]
    )
    x = us.index.to_timestamp()
    top.plot(x, us["rolling_corr"], color=charts.SERIES[0], linewidth=1.6)
    top.axhline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    top.set_ylabel(f"{WINDOW}-month correlation")
    top.set_ylim(-1, 1)
    bottom.plot(x, us["inflation_12m"] * 100, color=charts.SERIES[1], linewidth=1.6)
    bottom.set_ylabel("CPI inflation, % y/y")
    for label, (start, end) in EPISODES.items():
        for ax in (top, bottom):
            ax.axvspan(pd.Timestamp(start), pd.Timestamp(end), color=charts.GRID, alpha=0.6, lw=0)
        top.annotate(
            label,
            (pd.Timestamp(start), 0.9),
            fontsize=8,
            color=charts.TEXT_SECONDARY,
        )
    charts.titles(
        fig,
        f"US stock–bond correlation was negative in {n_neg / n_win:.0%} of 3-year windows",
        f"Rolling {WINDOW}-month correlation of US equity and 10-year Treasury returns "
        f"(top) and US inflation (bottom), {us.index[0]} to {us.index[-1]}",
    )
    return charts.save(
        fig,
        "claim05_stock_bond_correlation_us",
        "Source: Kenneth French Data Library (US market total return); FRED (DGS10 month-end "
        "yields, CPIAUCSL). 10-year bond returns built from yields. Calculations: this project.",
        {"french", "fred"},
    )


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


def run() -> ClaimResult:
    us = us_monthly()
    windows = us["rolling_corr"].dropna()
    n_win, n_neg = len(windows), int((windows < 0).sum())

    terciles = pd.qcut(us["inflation_12m"], 3, labels=["low", "middle", "high"])
    by_regime = pd.DataFrame(
        {
            label: {
                "months": int((terciles == label).sum()),
                "inflation_range": f"{us.loc[terciles == label, 'inflation_12m'].min():.1%}"
                f" to {us.loc[terciles == label, 'inflation_12m'].max():.1%}",
                "correlation": us.loc[terciles == label, "equity"].corr(
                    us.loc[terciles == label, "bonds"]
                ),
            }
            for label in ["low", "middle", "high"]
        }
    ).T
    episodes = {
        label: us.loc[start:end, "equity"].corr(us.loc[start:end, "bonds"])
        for label, (start, end) in EPISODES.items()
    }
    since_2022 = us.loc["2022-01":]
    episodes[f"2022-01 to {us.index[-1]}"] = since_2022["equity"].corr(since_2022["bonds"])
    pre_2000 = us.loc[:"1999-12"]
    post_2000 = us.loc["2000-01":"2021-12"]

    corr_pre = pre_2000["equity"].corr(pre_2000["bonds"])
    corr_post = post_2000["equity"].corr(post_2000["bonds"])
    corr_since_2022 = since_2022["equity"].corr(since_2022["bonds"])

    worst = us["equity"] <= us["equity"].quantile(0.05)
    bonds_up_in_worst = float((us.loc[worst, "bonds"] > 0).mean())

    countries = jst_table()
    n_c = len(countries)
    n_c_neg = int((countries["corr_all"] < 0).sum())
    n_high_above_low = int(
        (countries["corr_high_inflation"] > countries["corr_low_inflation"]).sum()
    )

    figure = _figure(us, n_neg, n_win)
    return ClaimResult(
        number=5,
        claim="Bonds diversify equities.",
        verdict=verdict_from_share(n_neg, n_win),
        headline=(
            f"US stock–bond correlation was negative in {n_neg} of {n_win} rolling 3-year "
            f"windows ({n_neg / n_win:.0%}). It was {corr_pre:.2f} over 1962–1999, "
            f"{corr_post:.2f} over 2000–2021 and {corr_since_2022:.2f} since 2022."
        ),
        data=(
            "US: Kenneth French market total return and a 10-year constant-maturity Treasury "
            "return built from FRED month-end yields (DGS10), monthly from February 1962; FRED "
            "CPIAUCSL for inflation. Cross-country: JST Macrohistory Database R6, annual real "
            "returns."
        ),
        method=(
            f"Rolling {WINDOW}-month Pearson correlation of monthly nominal returns. Correlation "
            "by inflation tercile (trailing 12-month CPI). Bond returns in the worst 5% of "
            "equity months. JST: correlation of annual real returns, split at each country's "
            "median inflation."
        ),
        findings=[
            "US correlation by inflation tercile: "
            + "; ".join(
                f"{label} ({row.inflation_range}): {row.correlation:.2f}"
                for label, row in by_regime.iterrows()
            )
            + ".",
            "Episodes: " + "; ".join(f"{k}: {v:.2f}" for k, v in episodes.items()) + ".",
            "Definition used for the verdict: bonds 'diversify' in the strong sense of hedging "
            "(negative correlation). In the weak sense, correlation below 1, they diversified "
            f"in every window: the highest 3-year correlation was {windows.max():.2f} "
            f"({windows.idxmax()}).",
            f"In the worst 5% of US equity months, 10-year Treasuries had a positive return "
            f"{bonds_up_in_worst:.0%} of the time.",
            f"Across {n_c} JST countries (annual, real), the full-sample correlation was "
            f"negative in {n_c_neg}; correlation was higher in high-inflation years than in "
            f"low-inflation years in {n_high_above_low} of {n_c}.",
        ],
        caveats=[
            "Inflation terciles are defined on the full sample, so the regime split is "
            "descriptive and in-sample, not a forecasting rule.",
            "Correlation measures co-movement, not size: a low correlation with a small bond "
            "return does little to offset a large equity loss.",
            "The 10-year bond return is built from yields (par bond, semi-annual coupons), not "
            "a traded index; it matched Damodaran's annual 10-year returns with correlation "
            "0.99 over 1963–2025.",
            "Nominal USD. For an SGD investor, currency hedging changes the bond leg (claim 12).",
        ],
        tables={
            "us_by_inflation_tercile": by_regime,
            "us_episodes": pd.Series(episodes, name="correlation").to_frame(),
            "countries": countries,
        },
        figures=[figure],
    )
