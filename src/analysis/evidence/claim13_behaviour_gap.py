"""Claim 13: investors underperform the funds they invest in (the "behaviour gap").

Rules:
- The claim needs fund-flow data (dollar-weighted investor returns), which this project does
  not have, so the verdict is "Not testable with our data". Headline numbers from the
  commonly cited studies are deliberately not quoted (owner's instruction); their methods and
  critiques are summarised instead.
- One part of the main critique is testable: a gap between dollar-weighted and time-weighted
  returns arises from the sequence of returns alone, with no timing decisions. Illustration:
  an investor adds the same amount every month into the US market (French, monthly) for 20
  years. For each 20-year window starting in January of each year, the dollar-weighted return
  (monthly internal rate of return, annualised) is compared with the time-weighted return.
"""

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from analysis import charts, data, metrics
from analysis.evidence import NOT_TESTABLE, ClaimResult

YEARS = 20


def dollar_weighted_return(returns: np.ndarray) -> float:
    """Annualised IRR of equal contributions at the start of each month, valued at the end."""
    growth = np.cumprod((1 + returns)[::-1])[::-1]  # value at end of 1 unit invested at month i
    final = growth.sum()
    n = len(returns)

    def gap(rate: float) -> float:
        return sum((1 + rate) ** (n - i) for i in range(n)) - final

    monthly = brentq(gap, -0.5, 0.5)
    return float((1 + monthly) ** 12 - 1)


def windows() -> pd.DataFrame:
    r = data.monthly("us_monthly_french")["us_eq_tr_nominal_usd"].dropna()
    rows = {}
    for year in range(r.index[0].year + 1, r.index[-1].year + 1):
        start = pd.Period(f"{year}-01", freq="M")
        part = r.loc[start : start + YEARS * 12 - 1]
        if len(part) < YEARS * 12:
            break
        dw = dollar_weighted_return(part.to_numpy())
        tw = metrics.annualised_return(part, 12)
        rows[start.year] = {"time_weighted": tw, "dollar_weighted": dw, "gap": dw - tw}
    return pd.DataFrame(rows).T


def _figure(table: pd.DataFrame) -> "charts.Path":
    fig, ax = charts.figure(height_in=4.5)
    gap = table["gap"].astype(float) * 100
    ax.plot(table.index, gap, color=charts.SERIES[0], marker="o", markersize=4)
    ax.axhline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    ax.set_xlabel("First year of the 20-year contribution window")
    ax.set_ylabel("Dollar- minus time-weighted, pts a year")
    charts.titles(
        fig,
        f"With no timing at all, the gap ranged from {gap.min():+.1f} to {gap.max():+.1f} "
        "pts a year",
        "Equal monthly contributions to the US market for 20 years; return sequence only",
    )
    return charts.save(
        fig,
        "claim13_sequence_gap",
        "Source: Kenneth French Data Library (US market total return). Calculations: this project.",
        {"french"},
    )


def run() -> ClaimResult:
    table = windows()
    gap = table["gap"].astype(float)
    figure = _figure(table)
    return ClaimResult(
        number=13,
        claim="Investors underperform the funds they invest in.",
        verdict=NOT_TESTABLE,
        headline=(
            "Fund-flow data are needed and not available here. Our data do show that a gap "
            "between investor (dollar-weighted) and fund (time-weighted) returns appears without "
            f"any behaviour: for steady monthly saving over {len(table)} rolling 20-year windows, "
            f"it ranged from {gap.min():+.1%} to {gap.max():+.1%} a year (median "
            f"{gap.median():+.1%})."
        ),
        data=(
            "Kenneth French Data Library, US market total return, monthly, nominal USD. "
            "Literature: publisher listings and summaries cited below."
        ),
        method=(
            "Dollar-weighted return: annualised internal rate of return of equal start-of-month "
            "contributions valued at the end of each 20-year window. Time-weighted return: the "
            "annualised market return over the same window."
        ),
        findings=[
            "What the studies measure: DALBAR's Quantitative Analysis of Investor Behavior and "
            "Morningstar's 'Mind the Gap' compare an estimate of investors' dollar-weighted "
            "returns (from fund flows) with funds' time-weighted returns. Dichev (2007, American "
            "Economic Review 97(1)) applied dollar-weighted returns to whole stock markets.",
            "Critiques: Pfau (Advisor Perspectives, 2017) and others argued that DALBAR's method "
            "mixes the effect of investor timing with the plain consequence of money arriving "
            "over time, and overstates the gap; DALBAR responded that it measures a broader "
            "investor-return concept (including withdrawals and charges). Keswani and Stolin "
            "(2008, Finance Research Letters) found Dichev's results not robust across "
            "sub-periods and data coverage. Morningstar's method weights each month by the "
            "assets invested and is generally reported as giving a smaller gap.",
            f"Sequence effect alone, in our data: {int((gap < 0).sum())} of {len(table)} windows "
            f"had a negative dollar-weighted minus time-weighted gap and "
            f"{int((gap > 0).sum())} a positive one, with no timing decisions involved. Any "
            "comparison of investor and fund returns must separate this effect before "
            "attributing the gap to behaviour.",
        ],
        caveats=[
            "The illustration uses steady contributions to a US market index; real investors' "
            "flows, fund choice and fees differ.",
            "Literature summaries rely on publisher listings, abstracts and the authors' "
            "published exchanges; the full texts of the DALBAR reports (paid) were not reviewed.",
            "For this project's investor, the practical implication is behavioural: a "
            "rule-based rebalancing policy fixed in advance (claim 11, Phase 2) limits "
            "discretionary timing.",
        ],
        tables={"windows": table},
        figures=[figure],
    )
