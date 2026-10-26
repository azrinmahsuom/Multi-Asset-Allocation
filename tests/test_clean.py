import pandas as pd
import pytest

from analysis import clean


def test_shiller_month_reads_point_one_as_october():
    assert clean._shiller_month(2026.1) == pd.Period("2026-10", freq="M")
    assert clean._shiller_month(1871.01) == pd.Period("1871-01", freq="M")


def test_complete_months_drops_unfinished_final_month():
    # Jan complete (ends on its last business day), Feb ends on the 10th: dropped.
    days = pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-09", "2024-02-12"])
    daily = pd.Series([0.01, 0.01, 0.02, 0.0], index=days)
    out = clean.complete_months(daily)
    assert list(out.index.astype(str)) == ["2024-01"]
    assert out.iloc[0] == pytest.approx(1.01**2 - 1)


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
