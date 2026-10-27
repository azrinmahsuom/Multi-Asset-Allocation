"""Claim 12: long-run real returns are similar hedged and unhedged, for an SGD investor;
analysed separately for equities and bonds (the usual finding: hedging matters more for bonds).

Rules:
- Unhedged SGD return = (1 + USD return)(1 + change in USD/SGD) - 1 (FRED month-end DEXSIUS).
- Hedged SGD return = USD return (or USD-hedged fund return) + SGD one-month rate - USD
  one-month rate (covered interest parity; MAS-based SGD rate, French 1-month T-bill).
- Real SGD = deflated by Singapore CPI (SingStat M213751, NSA).
- Samples: US equities (French) and US 10-year Treasuries (built from yields) from July 1987
  (start of the SGD rate); developed-market equities (French) from July 1990; global
  aggregate bonds, unhedged (AGGG.L) vs USD-hedged (AGGU.L), from December 2017.
- Verdict: verdict_from_share over the four samples in which the mean monthly hedged-minus-
  unhedged return difference is not statistically significant (|HAC t| < 2).
- Second test: hedging's effect on volatility, equities vs bonds (ratio hedged / unhedged).
"""

import numpy as np
import pandas as pd

from analysis import charts, data, metrics, stats
from analysis.evidence import ClaimResult, verdict_from_share


def _direction(ratio: float) -> str:
    return "lowered" if ratio < 1 else "raised"


def samples() -> dict[str, tuple[str, pd.DataFrame]]:
    fx = data.monthly("usdsgd_month_end")["usd_vs_sgd_change"]
    rf_sgd = data.monthly("sgd_rf_monthly")["sgd_rf_tr_nominal_sgd"]
    rf_usd = data.monthly("us_monthly_french")["us_bill1m_tr_nominal_usd"]
    sg_infl = data.monthly("sg_cpi_monthly")["sg_inflation_month"]
    etf = data.monthly("etf_monthly")

    def build(asset_usd: pd.Series, hedge_base: pd.Series) -> pd.DataFrame:
        df = pd.DataFrame(
            {
                "unhedged": metrics.to_base_currency(asset_usd, fx),
                "hedged": metrics.hedged_return(hedge_base, rf_sgd, rf_usd),
                "carry": rf_sgd - rf_usd,
                "fx": fx,
                "inflation": sg_infl,
            }
        ).dropna()
        df["unhedged_real"] = metrics.real_returns(df["unhedged"], df["inflation"])
        df["hedged_real"] = metrics.real_returns(df["hedged"], df["inflation"])
        return df

    us_eq = data.monthly("us_monthly_french")["us_eq_tr_nominal_usd"]
    dev_eq = data.monthly("developed_monthly_french")["developed_eq_tr_nominal_usd"]
    treasury = data.monthly("us_treasury_monthly")["us_gov10_tr_nominal_usd"]
    return {
        "US equities": ("equities", build(us_eq, us_eq)),
        "Developed-market equities": ("equities", build(dev_eq, dev_eq)),
        "US 10-year Treasuries": ("bonds", build(treasury, treasury)),
        "Global aggregate bonds (ETF classes)": (
            "bonds",
            build(etf["AGGG.L_tr_nominal_usd"], etf["AGGU.L_tr_nominal_usd"]),
        ),
    }


def summarise(df: pd.DataFrame) -> dict:
    diff = stats.hac_mean_test(df["hedged"] - df["unhedged"])
    vol_h = metrics.annualised_volatility(df["hedged"], 12)
    vol_u = metrics.annualised_volatility(df["unhedged"], 12)
    return {
        "period": f"{df.index[0]} to {df.index[-1]}",
        "real_return_unhedged": metrics.annualised_return(df["unhedged_real"], 12),
        "real_return_hedged": metrics.annualised_return(df["hedged_real"], 12),
        "difference_per_year": diff["mean"] * 12,
        "difference_t": diff["t_stat"],
        "hedge_carry_per_year": df["carry"].mean() * 12,
        "usd_vs_sgd_per_year": metrics.annualised_return(df["fx"], 12),
        "vol_unhedged": vol_u,
        "vol_hedged": vol_h,
        "vol_ratio_hedged_to_unhedged": vol_h / vol_u,
        "max_drawdown_unhedged": metrics.max_drawdown(df["unhedged_real"]),
        "max_drawdown_hedged": metrics.max_drawdown(df["hedged_real"]),
    }


def _figure(table: pd.DataFrame) -> "charts.Path":
    charts.style()
    fig, (left, right) = charts.plt.subplots(1, 2, figsize=(charts.WIDTH_IN, 4.8), sharey=True)
    y = np.arange(len(table))[::-1]
    for i, (col, label) in enumerate([("unhedged", "Unhedged"), ("hedged", "Hedged to SGD")]):
        offset = 0.18 if i == 0 else -0.18
        left.barh(
            y + offset,
            table[f"real_return_{col}"].astype(float) * 100,
            height=0.34,
            color=charts.SERIES[i],
            label=label,
        )
        right.barh(
            y + offset,
            table[f"vol_{col}"].astype(float) * 100,
            height=0.34,
            color=charts.SERIES[i],
            label=label,
        )
    left.set_yticks(y, [f"{k}\n{row.period}" for k, row in table.iterrows()], fontsize=8.5)
    left.set_xlabel("Real annualised return in SGD, % per year")
    right.set_xlabel("Volatility in SGD, % per year")
    left.axvline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    for ax in (left, right):
        ax.grid(axis="y", visible=False)
    right.legend(loc="lower right")
    bonds = table[table["asset_class"] == "bonds"]["vol_ratio_hedged_to_unhedged"].astype(float)
    eq = table[table["asset_class"] == "equities"]["vol_ratio_hedged_to_unhedged"].astype(float)
    charts.titles(
        fig,
        f"Hedging changed volatility by {bonds.mean() - 1:+.0%} for bonds and "
        f"{eq.mean() - 1:+.0%} for equities on average",
        "SGD investor, monthly, real (Singapore CPI); hedges assume covered interest parity",
    )
    return charts.save(
        fig,
        "claim12_hedged_vs_unhedged_sgd",
        "Source: Kenneth French Data Library; FRED (DGS10, DEXSIUS); MAS; SingStat (CPI); "
        "Yahoo Finance (AGGG.L, AGGU.L). Calculations: this project.",
        {"french", "fred", "mas", "singstat", "yahoo"},
    )


def run() -> ClaimResult:
    rows = {}
    all_samples = samples()
    us_eq = all_samples["US equities"][1]
    fx_equity_corr = float(us_eq["fx"].corr(us_eq["hedged"] - us_eq["carry"]))
    for name, (asset_class, df) in all_samples.items():
        rows[name] = {"asset_class": asset_class, **summarise(df)}
    table = pd.DataFrame(rows).T
    similar = table["difference_t"].astype(float).abs() < 2
    n_similar = int(similar.sum())
    vol_ratio = table.groupby("asset_class")["vol_ratio_hedged_to_unhedged"].mean()
    figure = _figure(table)

    return ClaimResult(
        number=12,
        claim=(
            "Long-run real returns are similar hedged and unhedged (SGD investor; equities and "
            "bonds analysed separately)."
        ),
        verdict=verdict_from_share(n_similar, len(table)),
        headline=(
            f"Hedged and unhedged returns were not significantly different in {n_similar} of "
            f"{len(table)} samples. Hedging {_direction(vol_ratio['bonds'])} bond volatility "
            f"(hedged/unhedged ratio {vol_ratio['bonds']:.2f} on average) and "
            f"{_direction(vol_ratio['equities'])} equity volatility "
            f"({vol_ratio['equities']:.2f})."
        ),
        data=(
            "Monthly. USD assets: French US and developed-market equity total returns; US "
            "10-year Treasury built from FRED month-end yields; AGGG.L (unhedged) and AGGU.L "
            "(USD-hedged) global aggregate bond ETF classes from Yahoo. FX: FRED DEXSIUS "
            "month-end. Rates: MAS SGD (SORA-based) and French 1-month T-bill. Inflation: "
            "SingStat CPI. Returns in SGD, real."
        ),
        method=(
            "Unhedged: USD return compounded with the USD/SGD change. Hedged: USD return plus "
            "the SGD-minus-USD one-month rate (covered interest parity). Mean monthly "
            "difference tested with a HAC t-statistic; volatility compared as a ratio."
        ),
        findings=[
            "; ".join(
                f"{k} ({row.period}): real {row.real_return_unhedged:+.1%} unhedged vs "
                f"{row.real_return_hedged:+.1%} hedged a year (difference "
                f"{row.difference_per_year:+.1%}, t = {row.difference_t:.1f}); volatility "
                f"{row.vol_unhedged:.1%} vs {row.vol_hedged:.1%}"
                for k, row in table.iterrows()
            )
            + ".",
            "For equities, the unhedged USD exposure lowered volatility in SGD: the monthly "
            f"USD/SGD change correlated {fx_equity_corr:.2f} with US equity returns in USD, so "
            "the USD tended to rise against the SGD when equities fell, and hedging removed "
            "that offset."
            if vol_ratio["equities"] > 1 and fx_equity_corr < 0
            else f"For equities, hedged/unhedged volatility ratio {vol_ratio['equities']:.2f}; "
            f"USD/SGD vs US equity correlation {fx_equity_corr:.2f}.",
            "The hedged-minus-unhedged difference has two parts: the rate carry (SGD minus USD "
            "one-month rates) and the USD/SGD move. "
            + "; ".join(
                f"{k}: carry {row.hedge_carry_per_year:+.1%} a year, USD vs SGD "
                f"{row.usd_vs_sgd_per_year:+.1%} a year"
                for k, row in table.iloc[[0, 3]].iterrows()
            )
            + ".",
        ],
        caveats=[
            "Hedged returns assume covered interest parity with monthly forwards at MAS SGD and "
            "US T-bill rates; real forward hedges also pay a cross-currency basis and dealing "
            "spreads, and SGD-hedged share classes charge a fee.",
            "The SGD appreciated against the USD over much of the sample; one currency path, "
            "about 39 years at most, is a small sample for currency effects.",
            "US assets stand in for global ones in the long samples; the like-for-like global "
            "bond comparison starts in December 2017.",
            "Before costs and withholding tax.",
        ],
        tables={"samples": table},
        figures=[figure],
    )
