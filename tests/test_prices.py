import pandas as pd
import pytest

from analysis import prices


def test_modified_z_scores_by_hand():
    # Median 2, absolute deviations 1,0,1,0,8 -> MAD 1. Score of 10: 0.6745 * 8 / 1.
    x = pd.Series([1.0, 2.0, 3.0, 2.0, 10.0])
    assert prices.modified_z_scores(x).iloc[-1] == pytest.approx(0.6745 * 8)


def test_cross_check_flags_only_the_outlying_gap():
    ours = {
        "AAA": pd.Series({2021: 0.101, 2022: -0.199, 2023: 0.150}),
        "BBB": pd.Series({2021: 0.050, 2022: 0.031, 2023: 0.022}),
    }
    reference = pd.DataFrame(
        {
            "ticker": ["AAA"] * 3 + ["BBB"] * 3 + ["BBB"],
            "year": [2021, 2022, 2023, 2021, 2022, 2023, 2023],
            "total_return": [0.100, -0.200, 0.050, 0.049, 0.030, 0.021, 0.0],
            "basis": ["market_price"] * 6 + ["nav"],
        }
    )
    out = prices.cross_check(ours, reference)
    # Five gaps of exactly 0.1 pp give MAD 0, floored at 0.01 pp; the 10 pp gap is flagged.
    assert len(out) == 6  # the NAV row is not compared
    flagged = out.loc[out["mismatch"], ["ticker", "year"]].to_numpy().tolist()
    assert flagged == [["AAA", 2023]]
