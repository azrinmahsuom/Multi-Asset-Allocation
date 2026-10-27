"""Claim 2: US equities have had no negative real annualised return over any rolling 20-year
window. Tested for the US and for every JST country.

Rules:
- US: Shiller monthly S&P Composite total return deflated by Shiller's CPI, every rolling
  240-month window (overlapping), 1871 onwards. Monthly averaging in Shiller's prices has a
  negligible effect over 20 years.
- Other countries: JST annual real equity total return, every rolling 20-year window made of
  20 consecutive years with data (windows across a missing year are skipped).
- Verdict for the US claim: holds if no US window is negative. The cross-country result is
  reported alongside with verdict_from_share over countries with no negative window.
"""

import numpy as np
import pandas as pd

from analysis import charts, data, metrics
from analysis.config import JST_CREDIT
from analysis.evidence import FAILS, HOLDS, ClaimResult, verdict_from_share

YEARS = 20


def us_rolling() -> pd.Series:
    """US rolling 20-year real annualised equity return, monthly windows (Shiller)."""
    shiller = data.monthly("us_monthly_shiller")
    real = metrics.real_returns(shiller["us_eq_tr_nominal_usd"], shiller["us_cpi_inflation"])
    return metrics.rolling_annualised(real.dropna(), YEARS, 12)


def country_rolling(jst: pd.DataFrame) -> dict[str, pd.Series]:
    """Rolling 20-year real annualised equity return per JST country (annual windows)."""
    real = metrics.real_returns(jst["eq_tr"], jst["inflation"])
    out = {}
    for country, series in real.groupby(level="country"):
        series = series.droplevel("country")
        series = series.reindex(range(int(series.index.min()), int(series.index.max()) + 1))
        rolling = metrics.rolling_annualised(series, YEARS, 1)
        if len(rolling):
            out[country] = rolling
    return out


def summary(rolling: dict[str, pd.Series]) -> pd.DataFrame:
    rows = {
        country: {
            "windows": len(r),
            "negative_windows": int((r < 0).sum()),
            "share_negative": float((r < 0).mean()),
            "worst": float(r.min()),
            "worst_window_end": int(r.idxmin()),
        }
        for country, r in rolling.items()
    }
    return pd.DataFrame(rows).T.sort_values("worst")


def _figure(table: pd.DataFrame, n_negative: int) -> "charts.Path":
    fig, ax = charts.figure(height_in=6.0)
    ordered = table.sort_values("worst", ascending=False)
    y = np.arange(len(ordered))
    ax.barh(y, ordered["worst"].astype(float) * 100, height=0.6, color=charts.SERIES[0])
    ax.axvline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    labels = [
        f"{c}  ({int(row.worst_window_end) - YEARS + 1}–{int(row.worst_window_end)})"
        for c, row in ordered.iterrows()
    ]
    ax.set_yticks(y, labels)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Worst 20-year real annualised equity return, % per year (local currency)")
    charts.titles(
        fig,
        f"{n_negative} of {len(table)} countries had a 20-year stretch of negative real "
        "equity returns",
        "Worst rolling 20-year window per country (years in brackets), 1870–2020",
    )
    return charts.save(fig, "claim02_worst_20y_real_equity", JST_CREDIT, {"jst"})


def run() -> ClaimResult:
    us = us_rolling()
    us_negative = int((us < 0).sum())
    countries = summary(country_rolling(data.jst()))
    n_negative = int((countries["negative_windows"] > 0).sum())
    n = len(countries)
    worst_country = countries.index[0]
    worst = countries.iloc[0]
    us_annual = countries.loc["USA"]

    figure = _figure(countries, n_negative)
    return ClaimResult(
        number=2,
        claim=(
            "US equities have had no negative real annualised return over any rolling 20-year "
            "window. Tested across countries, not just the US."
        ),
        verdict=HOLDS if us_negative == 0 else FAILS,
        headline=(
            f"Across {n} countries, {n_negative} had at least one negative 20-year window; the "
            f"cross-country version {verdict_from_share(n - n_negative, n).lower()}. US: "
            f"{us_negative} negative window{'' if us_negative == 1 else 's'} out of {len(us)} "
            "on Shiller monthly data (worst "
            f"{us.min():.1%} a year, ending {us.idxmin()}); on JST annual data the US had "
            f"{int(us_annual['negative_windows'])}, so the US result depends on the data source."
        ),
        data=(
            "US: Robert Shiller online data, monthly, from 1871 (S&P Composite with dividends, "
            "CPI). Other countries: JST Macrohistory Database R6, annual, 1870–2020."
        ),
        method=(
            f"Real total return, compounded over every overlapping {YEARS}-year window and "
            "annualised. US windows step monthly; JST windows step annually and must contain "
            f"{YEARS} consecutive years of data."
        ),
        findings=[
            f"US, {len(us)} monthly windows ending {us.index[0]} to {us.index[-1]}: worst "
            f"{us.min():.1%} a year (window ending {us.idxmin()}), {us_negative} negative.",
            f"Sensitivity: on JST annual US data (calendar-year windows) the US had "
            f"{int(us_annual['negative_windows'])} negative windows; worst "
            f"{us_annual['worst']:.1%} a year, ending {int(us_annual['worst_window_end'])}. The "
            "verdict depends on how close the worst US window is to zero, so it is sensitive to "
            "data source and window timing.",
            f"{n_negative} of {n} countries had at least one negative 20-year real window. "
            f"Worst: {worst_country}, {worst['worst']:.1%} a year over "
            f"{int(worst['worst_window_end']) - YEARS + 1}–{int(worst['worst_window_end'])}.",
            "Countries with negative windows: "
            + ", ".join(
                f"{c} ({int(r.negative_windows)} of {int(r.windows)})"
                for c, r in countries[countries["negative_windows"] > 0].iterrows()
            )
            + ".",
        ],
        caveats=[
            "Overlapping windows share most of their years, so the number of windows overstates "
            "the number of independent observations: 150 years hold fewer than 8 separate "
            "20-year periods.",
            "The US record is one country's history, and the US had the highest equity return "
            "of the 16 countries in claim 1. Its result shouldn't be generalised.",
            "Survivorship (see claim 1): markets that were wiped out are not in the data.",
            "Local currency, before costs and taxes.",
        ],
        tables={"countries": countries, "us_summary": us.describe().to_frame("us_rolling_20y")},
        figures=[figure],
    )
