"""Claim 3: equity volatility of annualised returns falls with horizon faster than i.i.d.
returns would imply (mean reversion).

Rules:
- Measure: variance ratio VR(k) of real log returns (bootstrap.variance_ratio). Under i.i.d.
  returns VR = 1 and the volatility of annualised k-period returns falls as 1/sqrt(k);
  VR < 1 means it falls faster.
- Benchmark: VR of 2,000 i.i.d. resamples of the same returns (same length), which also
  captures the small-sample bias of overlapping windows.
- Test per market: mean reversion is supported if VR at 20 years is below the 5th percentile
  of the i.i.d. distribution (one-sided 5% level).
- US: French monthly market total return deflated by Shiller CPI, July 1926 onwards (not
  Shiller's averaged prices). Other countries: JST annual real equity returns, longest run of
  consecutive years per country.
- Verdict: verdict_from_share over the 16 JST countries; the US monthly result is reported
  alongside.
"""

import numpy as np
import pandas as pd

from analysis import bootstrap, charts, data, metrics
from analysis.config import BOOTSTRAP_REPS
from analysis.evidence import ClaimResult, verdict_from_share

US_HORIZONS_MONTHS = [12, 24, 60, 120, 240]
JST_HORIZONS_YEARS = [2, 5, 10, 20]
TEST_YEARS = 20


def us_real_log_returns() -> pd.Series:
    french = data.monthly("us_monthly_french")["us_eq_tr_nominal_usd"]
    cpi = data.monthly("us_monthly_shiller")["us_cpi_inflation"]
    real = metrics.real_returns(french, cpi).dropna()
    return np.log1p(real)


def longest_run(series: pd.Series) -> pd.Series:
    """Longest stretch of consecutive (integer-indexed) years without missing values."""
    s = series.dropna()
    breaks = np.flatnonzero(np.diff(s.index.to_numpy()) != 1)
    starts = np.r_[0, breaks + 1]
    ends = np.r_[breaks + 1, len(s)]
    i = int(np.argmax(ends - starts))
    return s.iloc[starts[i] : ends[i]]


def test_market(log_returns: np.ndarray, horizons: list[int]) -> pd.DataFrame:
    observed = [bootstrap.variance_ratio(log_returns, k) for k in horizons]
    sims = bootstrap.iid_variance_ratios(log_returns, horizons)
    return pd.DataFrame(
        {
            "variance_ratio": observed,
            "iid_p5": np.percentile(sims, 5, axis=0),
            "iid_median": np.median(sims, axis=0),
            "iid_p95": np.percentile(sims, 95, axis=0),
            "share_of_iid_below": [(sims[:, j] < observed[j]).mean() for j in range(len(horizons))],
        },
        index=pd.Index(horizons, name="horizon"),
    )


def _figure(us: pd.DataFrame, period: str) -> "charts.Path":
    fig, ax = charts.figure(height_in=5.0)
    years = us.index / 12
    ax.fill_between(
        years, us["iid_p5"], us["iid_p95"], color=charts.SERIES[0], alpha=0.15, linewidth=0
    )
    ax.plot(years, us["iid_median"], color=charts.SERIES[0], linewidth=1, linestyle="--")
    ax.plot(years, us["variance_ratio"], color=charts.SERIES[0], marker="o", markersize=7)
    ax.axhline(1, color=charts.TEXT_SECONDARY, linewidth=0.8)
    ax.set_xticks(years, [f"{int(y)}" for y in years])
    ax.set_xlabel("Horizon, years")
    ax.set_ylabel("Variance ratio (1 = no mean reversion)")
    ax.annotate(
        "US real equity return",
        (years[-1], us["variance_ratio"].iloc[-1]),
        xytext=(-10, -18),
        textcoords="offset points",
        ha="right",
        color=charts.TEXT,
    )
    ax.annotate(
        f"5–95% range of {BOOTSTRAP_REPS:,} i.i.d. resamples (dashed: median)",
        (years[1], us["iid_p95"].iloc[1]),
        xytext=(0, 8),
        textcoords="offset points",
        color=charts.TEXT_SECONDARY,
        fontsize=9,
    )
    inside = us["iid_p5"].iloc[-1] <= us["variance_ratio"].iloc[-1]
    charts.titles(
        fig,
        "US equity risk at 20 years is "
        + ("within" if inside else "below")
        + " the range expected without mean reversion",
        f"Variance ratio of real monthly US market returns by horizon, {period}",
    )
    return charts.save(
        fig,
        "claim03_variance_ratio_us",
        "Source: Kenneth French Data Library (US market total return); Robert Shiller (CPI). "
        "Calculations: this project.",
        {"french", "shiller"},
    )


def run() -> ClaimResult:
    us_log = us_real_log_returns()
    us = test_market(us_log.to_numpy(), US_HORIZONS_MONTHS)
    us_20 = us.loc[TEST_YEARS * 12]
    us_supported = bool(us_20["variance_ratio"] < us_20["iid_p5"])
    period = f"{us_log.index[0]} to {us_log.index[-1]}"

    jst = data.jst()
    real = np.log1p(metrics.real_returns(jst["eq_tr"], jst["inflation"]))
    rows = {}
    for country, series in real.groupby(level="country"):
        run_ = longest_run(series.droplevel("country"))
        if len(run_) < 3 * TEST_YEARS:
            continue
        result = test_market(run_.to_numpy(), JST_HORIZONS_YEARS)
        r20 = result.loc[TEST_YEARS]
        rows[country] = {
            "start": int(run_.index[0]),
            "end": int(run_.index[-1]),
            "vr_10y": result.loc[10, "variance_ratio"],
            "vr_20y": r20["variance_ratio"],
            "iid_p5_20y": r20["iid_p5"],
            "iid_median_20y": r20["iid_median"],
            "supported": bool(r20["variance_ratio"] < r20["iid_p5"]),
        }
    countries = pd.DataFrame(rows).T.sort_values("vr_20y")
    n_supported = int(countries["supported"].sum())
    n = len(countries)
    below_median = int((countries["vr_20y"] < countries["iid_median_20y"]).sum())

    figure = _figure(us, period)
    return ClaimResult(
        number=3,
        claim=(
            "Equity volatility of annualised returns falls with horizon faster than i.i.d. "
            "returns would imply (mean reversion)."
        ),
        verdict=verdict_from_share(n_supported, n),
        headline=(
            f"Mean reversion at 20 years is statistically supported in {n_supported} of {n} "
            f"countries. US (monthly, {period}): variance ratio "
            f"{us_20['variance_ratio']:.2f} against an i.i.d. 5–95% range of "
            f"{us_20['iid_p5']:.2f}–{us_20['iid_p95']:.2f}."
        ),
        data=(
            "US: Kenneth French Data Library market total return (monthly) deflated by Shiller "
            "CPI. Other countries: JST Macrohistory Database R6 real equity returns (annual), "
            "longest run of consecutive years per country (at least 60)."
        ),
        method=(
            "Variance ratio VR(k): variance of overlapping k-period real log returns divided by "
            "k times the one-period variance. VR = 1 under i.i.d. returns. Each market is "
            f"compared with {BOOTSTRAP_REPS:,} i.i.d. resamples of its own returns (fixed seed). "
            "Mean reversion counts as supported if the 20-year VR is below the resamples' 5th "
            "percentile."
        ),
        findings=[
            f"US 20-year variance ratio {us_20['variance_ratio']:.2f}; "
            f"{us_20['share_of_iid_below']:.0%} of i.i.d. resamples were lower. "
            + (
                "Mean reversion is supported."
                if us_supported
                else "Not distinguishable from i.i.d. at the 5% level."
            ),
            f"{below_median} of {n} countries have a 20-year variance ratio below the i.i.d. "
            f"median (the direction mean reversion predicts); {n_supported} are below the 5th "
            "percentile.",
            "Variance ratios below 1 are expected even with no mean reversion: the i.i.d. "
            f"median at 20 years is {us_20['iid_median']:.2f} for the US sample, because "
            "overlapping windows in a finite sample bias the ratio down.",
        ],
        caveats=[
            "With 16 countries tested at the 5% level, about one false positive is expected "
            "by chance.",
            "Overlapping 20-year windows in 60–150 years of data give few independent "
            "observations; the bootstrap range is wide for this reason.",
            "The i.i.d. bootstrap removes all time dependence, including volatility clustering, "
            "which can affect the variance ratio's distribution. A block bootstrap would be a "
            "robustness check.",
            "Background: Poterba and Summers (1988, Journal of Financial Economics 22(1)) "
            "found point estimates consistent with mean reversion in the US and 17 other "
            "countries, but could not reject the random walk at conventional levels, which is "
            "the same pattern found here. Lo and MacKinlay (1988, Review of Financial Studies "
            "1(1)) developed the variance-ratio test.",
        ],
        tables={"us": us, "countries": countries},
        figures=[figure],
    )
