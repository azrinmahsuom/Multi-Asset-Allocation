import pandas as pd
import pytest

from analysis import clean


def test_shiller_month_reads_point_one_as_october():
    assert clean._shiller_month(2026.1) == pd.Period("2026-10", freq="M")
    assert clean._shiller_month(1871.01) == pd.Period("1871-01", freq="M")


def test_complete_months_drops_partial_first_and_last_month():
    # Jan starts mid-month (partial, dropped). Feb is complete: 1.02 * 1.01 - 1.
    # Mar ends on the 10th (incomplete, dropped).
    days = pd.to_datetime(["2024-01-17", "2024-01-31", "2024-02-15", "2024-02-29", "2024-03-08"])
    daily = pd.Series([0.05, 0.01, 0.02, 0.01, 0.03], index=days)
    out = clean.complete_months(daily)
    assert list(out.index.astype(str)) == ["2024-02"]
    assert out.iloc[0] == pytest.approx(1.02 * 1.01 - 1)


def test_sgd_risk_free_splices_overnight_then_sora_index():
    # Overnight 3.65% quoted on 1 Feb (applies 2 days, to 3 Feb) and on 3 Feb (applies until
    # the next quote on 1 Mar). Feb growth is the product of the two accruals.
    # SORA Index starts mid-Feb, so its first full month is March: 1.01 / 1.00 - 1 = 1%.
    overnight = pd.DataFrame(
        {"Interbank Overnight": [3.65, 3.65, 7.30]},
        index=pd.to_datetime(["2005-02-01", "2005-02-03", "2005-03-01"]),
    )
    sora = pd.DataFrame(
        {"SORA Index": [0.99, 1.00, 1.01]},
        index=pd.to_datetime(["2005-02-15", "2005-02-28", "2005-03-31"]),
    )
    out = clean.sgd_risk_free_monthly([overnight, sora])
    rf = out["sgd_rf_tr_nominal_sgd"]
    feb_days_to_next = (pd.Timestamp("2005-03-01") - pd.Timestamp("2005-02-03")).days
    expected_feb = (1 + 0.0365 * 2 / 365) * (1 + 0.0365 * feb_days_to_next / 365) - 1
    assert rf[pd.Period("2005-02", freq="M")] == pytest.approx(expected_feb)
    assert rf[pd.Period("2005-03", freq="M")] == pytest.approx(0.01)  # SORA leg, not overnight


def test_mas_tables_splits_on_changed_header(tmp_path):
    path = tmp_path / "mas.csv"
    path.write_text(
        "End of Period,,,Interbank 3-Month\n"
        "1987,Jul,01,4.31\n"
        "End of Period,,,Interbank 3-Month\n"
        "1988,Jan,04,-\n"
        "SORA Value Date,,,SORA Publication Date,SORA,SORA Index\n"
        "2005,Jul,01,04 Jul 2005,1.9,0.89\n"
    )
    first, second = clean.mas_tables(path)
    assert list(first.columns) == ["Interbank 3-Month"]
    assert first["Interbank 3-Month"].isna().tolist() == [False, True]
    assert second.loc["2005-07-01", "SORA Index"] == pytest.approx(0.89)


def test_fill_single_month_gaps_only_fills_isolated_months():
    import numpy as np

    s = pd.Series([100.0, np.nan, 121.0, np.nan, np.nan, 130.0])
    filled, flag = clean.fill_single_month_gaps(s)
    assert filled.iloc[1] == pytest.approx(110.0)  # geometric midpoint of 100 and 121
    assert filled.iloc[3:5].isna().all()  # two-month gap left missing
    assert flag.tolist() == [False, True, False, False, False, False]


def test_drop_duplicate_distributions():
    idx = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-07-01", "2025-07-30", "2025-08-29"])
    div = pd.Series([0.0126, 0.0126, 0.0132, 0.01, 0.01], index=idx)
    out = clean.drop_duplicate_distributions(div)
    # The 3 January repeat goes; equal monthly payments a month apart stay.
    assert out.tolist() == [0.0126, 0.0, 0.0132, 0.01, 0.01]
