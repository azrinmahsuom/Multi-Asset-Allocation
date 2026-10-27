import pandas as pd

from analysis import headline


def test_compare_lists_only_moved_figures():
    snap = {"a": 0.5, "b": 0.1, "gone": 1.0}
    now = {"a": 0.5, "b": 0.12, "new": 2.0}
    out = headline.compare(snap, now).set_index("figure")
    assert list(out.index) == ["b", "gone", "new"]
    assert out.loc["b", "change"] == 0.12 - 0.1
    assert pd.isna(out.loc["new", "snapshot"])


def test_drift_report_names_sources_and_figures():
    diffs = headline.compare({"x": 0.1}, {"x": 0.2})
    text = headline.drift_report(["yahoo/ISAC.L.csv"], diffs)
    assert "- yahoo/ISAC.L.csv" in text and "| x | 0.1 | 0.2 | +0.1000 |" in text
