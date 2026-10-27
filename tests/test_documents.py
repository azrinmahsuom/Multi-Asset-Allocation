import pytest

from analysis import documents


def test_ishares_parsers():
    doc = "Share Class Currency : USD Total Expense Ratio : 0.20% ... Effective Duration : 6.27 yrs"
    assert documents.ishares_ter(doc) == pytest.approx(0.002)
    assert documents.ishares_duration(doc) == pytest.approx(6.27)


def test_annual_report_ter_takes_current_year():
    doc = "Average daily NAV S$ 1,150,550,969 Total expense ratio1 % 0.24 0.26 2026 2025"
    assert documents.annual_report_ter(doc) == pytest.approx(0.0024)
