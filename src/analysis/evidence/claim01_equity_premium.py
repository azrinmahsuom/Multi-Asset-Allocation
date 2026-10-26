"""Claim 1: equities have the highest long-run real return across countries, not only in the US.

Rules:
- Real return each year = (1 + nominal local-currency return) / (1 + local CPI inflation) - 1.
- Financial assets are compared on the years where equity, bond and bill returns all exist
  for that country; housing is compared separately on years where all four exist.
- Long-run return = geometric annualised real return (CAGR) over those years.
- Verdict: verdict_from_share over countries where equities have the highest CAGR.
"""

import numpy as np
import pandas as pd

from analysis import charts, data, metrics
from analysis.config import JST_CREDIT
from analysis.evidence import ClaimResult, verdict_from_share

ASSETS = {"equity": "eq_tr", "bonds": "bond_tr", "bills": "bill_rate", "housing": "housing_tr"}
FINANCIAL = ["equity", "bonds", "bills"]


def real_returns(jst: pd.DataFrame) -> pd.DataFrame:
    """Real annual returns per asset, indexed by (country, year)."""
    return pd.DataFrame(
        {name: metrics.real_returns(jst[col], jst["inflation"]) for name, col in ASSETS.items()}
    )


def _cagr(returns: pd.Series) -> float:
    return float(np.expm1(np.log1p(returns).mean())) if len(returns) else np.nan


def country_table(real: pd.DataFrame, assets: list[str]) -> pd.DataFrame:
    """Real CAGR per asset on each country's common sample, with the sample described."""
    rows = {}
    for country, group in real.groupby(level="country"):
        sample = group.droplevel("country")[assets].dropna()
        if sample.empty:
            continue
        span = range(int(sample.index.min()), int(sample.index.max()) + 1)
        missing = [year for year in span if year not in sample.index]
        rows[country] = {
            "start": span.start,
            "end": span.stop - 1,
            "years": len(sample),
            "missing_years": " ".join(map(str, missing)),
            **{asset: _cagr(sample[asset]) for asset in assets},
        }
    table = pd.DataFrame(rows).T
    table["highest"] = table[assets].astype(float).idxmax(axis=1)
    return table.sort_values("equity", ascending=False)


def _figure(table: pd.DataFrame, n_equity_top: int) -> "charts.Path":
    fig, ax = charts.figure(height_in=6.0)
    ordered = table.sort_values("equity")
    y = np.arange(len(ordered))
    for i, asset in enumerate(FINANCIAL):
        ax.scatter(
            ordered[asset].astype(float) * 100,
            y,
            s=42,
            color=charts.SERIES[i],
            label={"equity": "Equities", "bonds": "Government bonds", "bills": "Bills"}[asset],
            zorder=3,
            edgecolors=charts.SURFACE,
            linewidths=1,
        )
    ax.axvline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    ax.set_yticks(y, ordered.index)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Real annualised total return, % per year (local currency)")
    first, last = int(table["start"].min()), int(table["end"].max())
    charts.titles(
        fig,
        f"Equities had the highest real return in {n_equity_top} of {len(table)} countries",
        f"Each country's longest sample with all three assets, between {first} and {last}",
    )
    ax.legend(loc="lower right", ncols=1)
    return charts.save(fig, "claim01_real_returns_by_country", JST_CREDIT, {"jst"})


def run() -> ClaimResult:
    real = real_returns(data.jst())
    financial = country_table(real, FINANCIAL)
    with_housing = country_table(real, [*FINANCIAL, "housing"])

    n = len(financial)
    eq_top = int((financial["highest"] == "equity").sum())
    not_top = financial.index[financial["highest"] != "equity"].tolist()
    eq_vs_housing = int((with_housing["highest"] == "equity").sum())
    housing_top = int((with_housing["highest"] == "housing").sum())

    us_eq = float(financial.loc["USA", "equity"])
    us_rank = int(financial["equity"].astype(float).rank(ascending=False)["USA"])
    ex_us = financial.drop("USA")["equity"].astype(float)
    gaps = financial.loc[financial["missing_years"] != "", "missing_years"]

    figure = _figure(financial, eq_top)
    return ClaimResult(
        number=1,
        claim=(
            "Equities have the highest long-run real return across countries, not only in the US."
        ),
        verdict=verdict_from_share(eq_top, n),
        headline=(
            f"Among financial assets, equities had the highest real return in {eq_top} of {n} "
            f"countries (not in: {', '.join(not_top) or 'none'}). Including housing, equities "
            f"came first in {eq_vs_housing} of {len(with_housing)}."
        ),
        data=(
            "Jordà-Schularick-Taylor Macrohistory Database R6 (annual, local currency, nominal "
            "total returns and CPI), 1871–2020. Canada and Ireland lack a year with equity, bond "
            "and bill returns all present and are excluded."
        ),
        method=(
            "Real return each year = (1 + nominal return) / (1 + inflation) - 1. Geometric "
            "annualised real return per asset on each country's common sample. Housing is "
            "compared on the years where all four assets exist."
        ),
        findings=[
            f"Equities beat government bonds and bills in {eq_top} of {n} countries.",
            f"US equities returned {us_eq:.1%} a year in real terms, ranked {us_rank} of {n}. "
            f"The other {len(ex_us)} countries averaged {ex_us.mean():.1%} (equal-weighted; "
            f"range {ex_us.min():.1%} to {ex_us.max():.1%}).",
            f"Housing (rent included) had the highest real return in {housing_top} of "
            f"{len(with_housing)} countries on the four-asset sample.",
        ],
        caveats=[
            "Survivorship: the JST countries are developed markets that kept functioning. "
            "Markets that were wiped out (e.g. Russia after 1917, China after 1949) are absent, "
            "so cross-country equity returns are biased upward. Jorion and Goetzmann (1999, "
            "Journal of Finance 54(3)) document this; cited, not independently verified.",
            "Years missing inside a country's sample are skipped, not filled: "
            + "; ".join(f"{c} ({v})" for c, v in gaps.items())
            + ". If losses were concentrated in those years, the returns shown are too high.",
            "Housing returns are estimates for an unlevered, undiversified, illiquid asset that "
            "cannot be bought as an index. They are reported for context, are not comparable to "
            "investable index returns, and are never used as a proxy for REITs.",
            "Local-currency returns: they answer 'what did a local investor earn', not what an "
            "SGD investor would have earned.",
        ],
        tables={"financial_assets": financial, "with_housing": with_housing},
        figures=[figure],
    )
