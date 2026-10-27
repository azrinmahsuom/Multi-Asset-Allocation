"""Sensitivity of claim verdicts to window and horizon choices that have no cited source.

Rule: each choice is rerun at alternatives either side of the default. If no alternative
changes the verdict, the choice does not drive the result; if one does, it is flagged as
sensitive and reported next to the claim.
"""

import numpy as np
import pandas as pd

from analysis import data, metrics
from analysis.evidence import claim03_mean_reversion as c3
from analysis.evidence import claim04_horizon_mix as c4
from analysis.evidence import claim05_stock_bond_correlation as c5
from analysis.evidence import claim06_term_premium as c6
from analysis.evidence import verdict_from_share


def _row(claim, parameter, value, default, statistic, verdict):
    return {
        "claim": claim,
        "parameter": parameter,
        "value": value,
        "default": value == default,
        "statistic": statistic,
        "verdict": verdict,
    }


def claim5_window() -> list[dict]:
    us = c5.us_monthly()
    rows = []
    for window in [24, 36, 60]:
        blocks = c5.non_overlapping(us["equity"], us["bonds"], window)
        n_neg = int((blocks["correlation"] < 0).sum())
        rows.append(
            _row(
                5,
                "correlation window (months)",
                window,
                c5.WINDOW,
                f"{n_neg} of {len(blocks)} blocks negative",
                verdict_from_share(n_neg, len(blocks)),
            )
        )
    return rows


def claim5_regimes() -> list[dict]:
    """Does 'correlation higher in high- than low-inflation regimes' survive lag/burn-in?"""
    us = c5.us_monthly()
    cpi = data.monthly("fred_monthly")["CPIAUCSL"]
    rows = []
    for parameter, values, default, key in [
        ("CPI publication lag (months)", [1, 2, 3], c5.CPI_LAG_MONTHS, "lag"),
        ("regime burn-in (months)", [60, 120, 180], c5.BURN_IN_MONTHS, "burn_in"),
    ]:
        for v in values:
            reg = c5.exante_regimes(cpi, **{key: v})["regime"].reindex(us.index)
            corr = {
                r: us.loc[reg == r, "equity"].corr(us.loc[reg == r, "bonds"])
                for r in ("low", "high")
            }
            higher = corr["high"] > corr["low"]
            rows.append(
                _row(
                    5,
                    parameter,
                    v,
                    default,
                    f"high {corr['high']:.2f} vs low {corr['low']:.2f}",
                    "high > low" if higher else "high <= low",
                )
            )
    return rows


def claim4_horizon() -> list[dict]:
    inputs = c4.country_inputs(data.jst())
    rows = []
    for long in [10, 15, 20, 25, 30]:
        up = 0
        n = 0
        for g in inputs.values():
            if len(g) < 3 * long:
                continue
            s, b, r = (g[c].to_numpy() for c in ("stocks", "bonds", "bills"))
            shift = (
                c4.optimal_weights(s, b, r, long)["min_variance"]
                - c4.optimal_weights(s, b, r, c4.SHORT)["min_variance"]
            )
            up += int(shift > 0)
            n += 1
        rows.append(
            _row(
                4,
                "long horizon compared with 1 year (years)",
                long,
                c4.LONG,
                f"{up} of {n} countries shift towards equities",
                verdict_from_share(up, n),
            )
        )
    return rows


def claim6_blocks() -> list[dict]:
    df = c6.us_monthly()
    rows = []
    for years in [5, 10, 15]:
        t = c6.difference_test(df["10y"], df["5y"], years)
        rows.append(
            _row(
                6,
                "comparison block (years)",
                years,
                c6.BLOCK_YEARS,
                f"10y beat 5y in {t['blocks_long_won']} of {t['blocks']} blocks",
                verdict_from_share(t["blocks_long_won"], t["blocks"]),
            )
        )
    return rows


def claim3_horizon() -> list[dict]:
    jst = data.jst()
    real = np.log1p(metrics.real_returns(jst["eq_tr"], jst["inflation"]))
    rows = []
    for years in [10, 15, 20]:
        n_sup = n = 0
        for _, series in real.groupby(level="country"):
            run_ = c3.longest_run(series.droplevel("country"))
            if len(run_) < 3 * c3.TEST_YEARS:
                continue
            res = c3.test_market(run_.to_numpy(), [years])
            n_sup += int(res["variance_ratio"].iloc[0] < res["iid_p5"].iloc[0])
            n += 1
        rows.append(
            _row(
                3,
                "variance-ratio test horizon (years)",
                years,
                c3.TEST_YEARS,
                f"supported in {n_sup} of {n} countries",
                verdict_from_share(n_sup, n),
            )
        )
    return rows


def run() -> pd.DataFrame:
    table = pd.DataFrame(
        claim3_horizon() + claim4_horizon() + claim5_window() + claim5_regimes() + claim6_blocks()
    )
    defaults = table[table["default"]].set_index(["claim", "parameter"])["verdict"]
    table["changes_verdict"] = [
        row.verdict != defaults[(row.claim, row.parameter)] for row in table.itertuples()
    ]
    return table
