"""Claim 6: long-dated bonds earn a reliable term premium over intermediate bonds.

All US results are monthly, nominal USD. Rules:
- Data: constant-maturity US Treasury returns built from FRED month-end yields (1, 5, 10 and
  30 years; clean.us_treasury_monthly); French 1-month T-bill as cash. February 1962 onwards
  (30-year from March 1977).
- Long vs intermediate: 10-year vs 5-year (full sample) and 30-year vs 5-year (from 1977).
- Verdict ("reliable"): verdict_from_share over non-overlapping 10-year blocks in which the
  10-year bond beat the 5-year. The mean monthly difference is also tested (HAC t-stat).
- Ex-ante split: months grouped by the yield-curve slope (10-year minus 1-year yield) known at
  the start of the month: positive vs zero-or-inverted.
- Rate eras, chosen after seeing the data (yield peak September 1981, trough 2020): reported
  as secondary and labelled as such.
- Long history: JST government bond vs bill total returns per country (nominal, annual).
"""

import numpy as np
import pandas as pd

from analysis import charts, data, metrics, stats
from analysis.evidence import ClaimResult, verdict_from_share

MATURITIES = [1, 5, 10, 30]
BLOCK_YEARS = 10
ERAS = {
    "Rising rates 1962–1981": ("1962-02", "1981-09"),
    "Falling rates 1981–2020": ("1981-10", "2020-12"),
    "2021 to latest": ("2021-01", None),
}


def us_monthly() -> pd.DataFrame:
    t = data.monthly("us_treasury_monthly")
    df = pd.DataFrame({f"{m}y": t[f"us_gov{m}_tr_nominal_usd"] for m in MATURITIES})
    df["bills"] = data.monthly("us_monthly_french")["us_bill1m_tr_nominal_usd"]
    df["slope_known"] = (t["dgs10_yield"] - t["dgs1_yield"]).shift(1)
    return df.dropna(subset=["1y", "5y", "10y", "bills"])


def maturity_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for col in ["bills", *[f"{m}y" for m in MATURITIES]]:
        r = df[col].dropna()
        bills = df.loc[r.index, "bills"]
        excess = (1 + r) / (1 + bills) - 1
        rows[col] = {
            "start": str(r.index[0]),
            "annual_return": metrics.annualised_return(r, 12),
            "excess_over_bills": metrics.annualised_return(excess, 12),
            "volatility": metrics.annualised_volatility(r, 12),
            "sharpe": metrics.sharpe_ratio(excess, 0.0, 12) if col != "bills" else np.nan,
            "max_drawdown": metrics.max_drawdown(r),
        }
    return pd.DataFrame(rows).T


def difference_test(long: pd.Series, short: pd.Series) -> dict:
    d = (long - short).dropna()
    test = stats.hac_mean_test(d)
    blocks_long = stats.block_annualised(long.loc[d.index], BLOCK_YEARS, 12)
    blocks_short = stats.block_annualised(short.loc[d.index], BLOCK_YEARS, 12)
    return {
        "start": str(d.index[0]),
        "mean_diff_annualised": test["mean"] * 12,
        "t_stat": test["t_stat"],
        "p_value": test["p_value"],
        "blocks": len(blocks_long),
        "blocks_long_won": int((blocks_long > blocks_short).sum()),
        "block_detail": "; ".join(
            f"{k}: {blocks_long[k] - blocks_short[k]:+.1%}" for k in blocks_long.index
        ),
    }


def jst_table() -> pd.DataFrame:
    jst = data.jst()[["bond_tr", "bill_rate"]].dropna()
    rows = {}
    for country, g in jst.groupby(level="country"):
        excess = (1 + g["bond_tr"]) / (1 + g["bill_rate"]) - 1
        rows[country] = {
            "years": len(g),
            "bond_minus_bill_annualised": float(np.expm1(np.log1p(excess).mean())),
        }
    return pd.DataFrame(rows).T.sort_values("bond_minus_bill_annualised")


def _figure(table: pd.DataFrame, common_start: str, end: str) -> "charts.Path":
    charts.style()
    fig, (left, right) = charts.plt.subplots(1, 2, figsize=(charts.WIDTH_IN, 4.5))
    labels = [f"{m}-year" for m in MATURITIES]
    x = np.arange(len(MATURITIES))
    rows = table.loc[[f"{m}y" for m in MATURITIES]]
    left.bar(x, rows["excess_over_bills"].astype(float) * 100, width=0.55, color=charts.SERIES[0])
    left.set_xticks(x, labels)
    left.set_ylabel("Annualised return over bills, % per year")
    left.set_title("Return over bills", fontsize=10)
    right.bar(x, rows["sharpe"].astype(float), width=0.55, color=charts.SERIES[0])
    right.set_xticks(x, labels)
    right.set_ylabel("Sharpe ratio (excess over bills)")
    right.set_title("Return per unit of risk", fontsize=10)
    for ax in (left, right):
        ax.grid(axis="x", visible=False)
        ax.axhline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    best = rows["sharpe"].astype(float).idxmax().replace("y", "-year")
    charts.titles(
        fig,
        f"Longer Treasuries paid more, but the {best} had the best return per unit of risk",
        f"US Treasuries by maturity, monthly nominal USD, common period {common_start} to {end}",
    )
    return charts.save(
        fig,
        "claim06_treasury_returns_by_maturity",
        "Source: FRED (DGS1, DGS5, DGS10, DGS30 month-end yields); Kenneth French Data Library "
        "(1-month T-bill). Bond returns built from yields. Calculations: this project.",
        {"fred", "french"},
    )


def run() -> ClaimResult:
    df = us_monthly()
    table = maturity_table(df)
    ten_vs_five = difference_test(df["10y"], df["5y"])
    thirty_vs_five = difference_test(df["30y"], df["5y"])
    five_vs_bills = difference_test(df["5y"], df["bills"])

    slope = {}
    for label, mask in {
        "curve upward-sloping": df["slope_known"] > 0,
        "curve flat or inverted": df["slope_known"] <= 0,
    }.items():
        g = df[mask]
        slope[label] = {
            "months": len(g),
            "10y_minus_bills_annualised": (g["10y"] - g["bills"]).mean() * 12,
            "10y_minus_5y_annualised": (g["10y"] - g["5y"]).mean() * 12,
        }
    slope = pd.DataFrame(slope).T

    eras = {}
    for label, (start, end) in ERAS.items():
        g = df.loc[start:end]
        eras[label] = {
            "10y_excess_over_bills": metrics.annualised_return(
                (1 + g["10y"]) / (1 + g["bills"]) - 1, 12
            ),
            "10y_minus_5y_annualised": (g["10y"] - g["5y"]).mean() * 12,
            "yield_start": data.monthly("us_treasury_monthly").loc[start, "dgs10_yield"],
        }
    eras = pd.DataFrame(eras).T

    countries = jst_table()
    n_pos = int((countries["bond_minus_bill_annualised"] > 0).sum())
    common = df.loc[df["30y"].first_valid_index() :]
    common_table = maturity_table(common)
    figure = _figure(common_table, str(common.index[0]), str(common.index[-1]))
    falling = eras.loc["Falling rates 1981–2020"]
    rising = eras.loc["Rising rates 1962–1981"]

    return ClaimResult(
        number=6,
        claim="Long-dated bonds earn a reliable term premium over intermediate bonds.",
        verdict=verdict_from_share(ten_vs_five["blocks_long_won"], ten_vs_five["blocks"]),
        headline=(
            f"The 10-year beat the 5-year in {ten_vs_five['blocks_long_won']} of "
            f"{ten_vs_five['blocks']} non-overlapping 10-year blocks; the average gap was "
            f"{ten_vs_five['mean_diff_annualised']:+.1%} a year (t = {ten_vs_five['t_stat']:.1f}). "
            f"Over bills, the 10-year earned {rising['10y_excess_over_bills']:+.1%} a year while "
            f"rates rose (1962–1981) and {falling['10y_excess_over_bills']:+.1%} while they fell "
            "(1981–2020)."
        ),
        data=(
            "Monthly, nominal USD. Constant-maturity US Treasury returns built from FRED "
            "month-end yields (DGS1, DGS5, DGS10, DGS30), February 1962 onwards (30-year from "
            "March 1977); French 1-month T-bill. Long history: JST R6 annual government bond and "
            "bill returns, 16 countries."
        ),
        method=(
            f"Annualised returns, excess over bills, volatility and Sharpe by maturity. Long "
            f"minus intermediate: mean monthly difference with a HAC t-test, and the winner in "
            f"each non-overlapping {BLOCK_YEARS}-year block. Ex-ante split by the yield-curve "
            "slope known at the start of each month."
        ),
        findings=[
            "By maturity: "
            + "; ".join(
                f"{k} (from {row.start}): {row.excess_over_bills:+.1%} a year over bills, "
                f"volatility {row.volatility:.1%}, Sharpe {row.sharpe:.2f}, worst drawdown "
                f"{row.max_drawdown:.0%}"
                for k, row in table.drop("bills").iterrows()
            )
            + ".",
            f"10-year minus 5-year by block: {ten_vs_five['block_detail']}.",
            f"30-year minus 5-year (from {thirty_vs_five['start']}): "
            f"{thirty_vs_five['mean_diff_annualised']:+.1%} a year (t = "
            f"{thirty_vs_five['t_stat']:.1f}); 30-year won {thirty_vs_five['blocks_long_won']} "
            f"of {thirty_vs_five['blocks']} blocks. 5-year minus bills: "
            f"{five_vs_bills['mean_diff_annualised']:+.1%} a year (t = "
            f"{five_vs_bills['t_stat']:.1f}).",
            "Ex-ante by yield-curve slope at the start of the month: "
            + "; ".join(
                f"{k} ({int(row.months)} months): 10-year over bills "
                f"{row['10y_minus_bills_annualised']:+.1%} a year, over 5-year "
                f"{row['10y_minus_5y_annualised']:+.1%}"
                for k, row in slope.iterrows()
            )
            + ".",
            "Rate eras (chosen after seeing the data, at the 1981 yield peak and 2020 trough): "
            + "; ".join(
                f"{k}: 10-year {row['10y_excess_over_bills']:+.1%} a year over bills, "
                f"{row['10y_minus_5y_annualised']:+.1%} over 5-year"
                for k, row in eras.iterrows()
            )
            + ".",
            f"Long history: government bonds beat bills in {n_pos} of {len(countries)} JST "
            "countries (annual, nominal).",
        ],
        caveats=[
            "Returns are built from constant-maturity yields, not traded bonds; they ignore "
            "transaction costs and the roll-down of real bond portfolios.",
            "1981–2020 was a 40-year fall in yields that flattered long bonds; the full-sample "
            "averages mix that era with the rising-rate one.",
            "Few independent blocks: 64 years give six 10-year blocks for 10y vs 5y and four "
            "for 30y vs 5y.",
            "Nominal USD; for an SGD investor, hedged returns add the SGD-USD rate difference "
            "(claim 12).",
        ],
        tables={
            "us_by_maturity": table,
            "us_by_maturity_common_period": common_table,
            "long_vs_intermediate": pd.DataFrame(
                {
                    "10y vs 5y": ten_vs_five,
                    "30y vs 5y": thirty_vs_five,
                    "5y vs bills": five_vs_bills,
                }
            ).T.drop(columns="block_detail"),
            "us_by_curve_slope": slope,
            "us_rate_eras": eras,
            "jst_bonds_vs_bills": countries,
        },
        figures=[figure],
    )
