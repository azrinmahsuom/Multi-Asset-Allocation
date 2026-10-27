"""Claim 10: missing the best days destroys returns. Also tests missing the worst days and how
clustered the best and worst days are.

Rules:
- Data: French daily US market total return and 1-month T-bill, July 1926 onwards, nominal USD.
- A missed day earns that day's T-bill return instead of the market's (the investor is in cash).
- Scenarios: miss the best N, the worst N, or both, for N in 10, 20, 50 and 100 days.
- Verdict: verdict_from_share over N for which missing the best N days lowers the annualised
  return (the arithmetic claim). The headline reports the worst-day and clustering results.
- Clustering, distance: median trading days from each of the 100 best days to the nearest of
  the 100 worst days, against 2,000 random draws of 100 days (permutation test).
- Clustering, volatility: share of best and worst days falling in months of high volatility
  known at the time (trailing 21-day volatility to the previous day above its expanding 90th
  percentile, at least 252 days of history); 10% would be expected by chance.
"""

import numpy as np
import pandas as pd

from analysis import bootstrap, charts, data
from analysis.config import BOOTSTRAP_REPS
from analysis.evidence import ClaimResult, verdict_from_share

NS = [10, 20, 50, 100]
CLUSTER_N = 100


def _p(p: float) -> str:
    """A permutation p-value of zero means below 1 / number of draws."""
    return f"< {1 / BOOTSTRAP_REPS:.4f}" if p == 0 else f"= {p:.3f}"


def daily() -> pd.DataFrame:
    df = data.daily("us_daily_french")
    return pd.DataFrame(
        {"market": df["us_eq_tr_nominal_usd"], "rf": df["us_bill1m_tr_nominal_usd"]}
    ).dropna()


def annualised(returns: pd.Series) -> float:
    years = (returns.index[-1] - returns.index[0]).days / 365.25
    return float((1 + returns).prod() ** (1 / years) - 1)


def scenario(df: pd.DataFrame, best: int, worst: int) -> float:
    r = df["market"].copy()
    ranked = r.sort_values()
    missed = (
        ranked.index[len(ranked) - best :].append(ranked.index[:worst])
        if worst
        else (ranked.index[len(ranked) - best :])
    )
    r.loc[missed] = df.loc[missed, "rf"]
    return annualised(r)


def nearest_distance(best_pos: np.ndarray, worst_pos: np.ndarray) -> np.ndarray:
    worst_sorted = np.sort(worst_pos)
    idx = np.searchsorted(worst_sorted, best_pos)
    left = worst_sorted[np.clip(idx - 1, 0, len(worst_sorted) - 1)]
    right = worst_sorted[np.clip(idx, 0, len(worst_sorted) - 1)]
    return np.minimum(np.abs(best_pos - left), np.abs(right - best_pos))


def clustering(df: pd.DataFrame) -> dict:
    r = df["market"].to_numpy()
    order = np.argsort(r)
    worst_pos, best_pos = order[:CLUSTER_N], order[-CLUSTER_N:]
    observed = float(np.median(nearest_distance(best_pos, worst_pos)))
    generator = bootstrap.rng()
    random_medians = np.array(
        [
            np.median(
                nearest_distance(generator.choice(len(r), CLUSTER_N, replace=False), worst_pos)
            )
            for _ in range(BOOTSTRAP_REPS)
        ]
    )
    vol = df["market"].rolling(21).std().shift(1)
    high_cut = vol.expanding(min_periods=252).quantile(0.9)
    high_vol = (vol > high_cut).to_numpy()
    valid = high_cut.notna().to_numpy()
    in_best = high_vol[best_pos][valid[best_pos]].mean()
    in_worst = high_vol[worst_pos][valid[worst_pos]].mean()
    return {
        "median_days_best_to_worst": observed,
        "random_median_days": float(np.median(random_medians)),
        "p_value": float((random_medians <= observed).mean()),
        "best_in_high_vol": float(in_best),
        "worst_in_high_vol": float(in_worst),
        "high_vol_share_overall": float(high_vol[valid].mean()),
    }


def _figure(table: pd.DataFrame, period: str) -> "charts.Path":
    fig, ax = charts.figure(height_in=5.0)
    labels = table.index.tolist()
    y = np.arange(len(labels))[::-1]
    values = table["annualised_return"].astype(float) * 100
    ax.barh(y, values, height=0.6, color=charts.SERIES[0])
    for yi, v in zip(y, values, strict=True):
        ax.annotate(
            f"{v:.1f}%",
            (v, yi),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            fontsize=8.5,
            color=charts.TEXT,
        )
    ax.set_yticks(y, labels)
    ax.grid(axis="y", visible=False)
    ax.axvline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    ax.set_xlabel("Annualised total return, % per year (missed days earn T-bills)")
    base = table.loc["Fully invested", "annualised_return"]
    both = table.loc["Miss best and worst 20", "annualised_return"]
    charts.titles(
        fig,
        f"Missing both the best and worst 20 days: {both:.1%} a year vs {base:.1%} invested",
        f"US market, daily total returns, nominal USD, {period}",
    )
    return charts.save(
        fig,
        "claim10_missing_best_worst_days",
        "Source: Kenneth French Data Library (daily US market and 1-month T-bill). "
        "Calculations: this project.",
        {"french"},
    )


def run() -> ClaimResult:
    df = daily()
    period = f"{df.index[0]:%Y-%m-%d} to {df.index[-1]:%Y-%m-%d}"
    rows = {"Fully invested": scenario(df, 0, 0)}
    for n in NS:
        rows[f"Miss best {n}"] = scenario(df, n, 0)
    for n in NS:
        rows[f"Miss worst {n}"] = scenario(df, 0, n)
    for n in NS:
        rows[f"Miss best and worst {n}"] = scenario(df, n, n)
    table = pd.Series(rows, name="annualised_return").to_frame()
    base = rows["Fully invested"]
    n_lower = sum(rows[f"Miss best {n}"] < base for n in NS)
    both = rows["Miss best and worst 20"]
    cluster = clustering(df)
    figure = _figure(
        table.loc[["Fully invested", "Miss best 20", "Miss worst 20", "Miss best and worst 20"]],
        period,
    )

    return ClaimResult(
        number=10,
        claim="Missing the best days destroys returns.",
        verdict=verdict_from_share(n_lower, len(NS)),
        headline=(
            f"Missing the best 20 of {len(df):,} days changed the annual return from {base:.1%} "
            f"to {rows['Miss best 20']:.1%}. Missing the worst 20 gave "
            f"{rows['Miss worst 20']:.1%}, and missing both {both:.1%}. Best days sat a median "
            f"{cluster['median_days_best_to_worst']:.0f} trading days from a worst day, against "
            f"{cluster['random_median_days']:.0f} for random days (p {_p(cluster['p_value'])})."
        ),
        data=(
            "Kenneth French Data Library, daily US market total return and 1-month T-bill, "
            f"{period}, nominal USD."
        ),
        method=(
            "Annualised return over the full period with the selected days replaced by that "
            "day's T-bill return. Clustering: median distance from the 100 best to the nearest of "
            f"the 100 worst days, against {BOOTSTRAP_REPS:,} random draws of 100 days; and the "
            "share of extreme days in high-volatility periods known at the time."
        ),
        findings=[
            "; ".join(f"{k}: {v:.1%}" for k, v in rows.items()) + ".",
            f"High volatility known the day before (top 10% of trailing 21-day volatility, "
            f"expanding window) covered {cluster['high_vol_share_overall']:.0%} of days but "
            f"{cluster['best_in_high_vol']:.0%} of the 100 best days and "
            f"{cluster['worst_in_high_vol']:.0%} of the 100 worst days.",
            (
                "Best and worst days cluster in the same turbulent periods (permutation "
                f"p {_p(cluster['p_value'])}), so a strategy that avoided the worst days would "
                "likely have missed many of the best ones too; missing only the best days is "
                "not a realistic scenario."
                if cluster["p_value"] < 0.05
                else "Best and worst days were not significantly closer than random days "
                f"(p {_p(cluster['p_value'])})."
            ),
        ],
        caveats=[
            "Choosing which days to miss uses hindsight; the scenarios are illustrations, not "
            "strategies anyone could have followed.",
            "US market only, before costs and taxes. The 1930s and 1987 dominate the extreme days.",
            "The permutation test treats the 100 worst days as fixed and draws best days at "
            "random, which ignores volatility clustering in the null; it tests proximity, not "
            "cause.",
        ],
        tables={"scenarios": table, "clustering": pd.Series(cluster).to_frame("value")},
        figures=[figure],
    )
