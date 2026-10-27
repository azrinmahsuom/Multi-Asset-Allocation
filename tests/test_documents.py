import pytest

from analysis import documents


def test_ishares_parsers():
    doc = "Share Class Currency : USD Total Expense Ratio : 0.20% ... Effective Duration : 6.27 yrs"
    assert documents.ishares_ter(doc) == pytest.approx(0.002)
    assert documents.ishares_duration(doc) == pytest.approx(6.27)


def test_annual_report_ter_takes_current_year():
    doc = "Average daily NAV S$ 1,150,550,969 Total expense ratio1 % 0.24 0.26 2026 2025"
    assert documents.annual_report_ter(doc) == pytest.approx(0.0024)


def test_tax_parsers():
    treaty = "b) 15 percent of the gross amount of the dividends in all other cases."
    assert documents.treaty_dividend_rate(treaty) == pytest.approx(0.15)
    assert documents.statutory_rate("are subject to U.S. tax of 30%. A reduced") == 0.30
    doc = (
        "exceeds the filing threshold of $60,000. the maximum unified credit is $13,000. "
        "stock of corporations organized in or under U.S. law is property located in the "
        "United States, and all other corporate stock is property located outside the "
        "United States."
    )
    facts = documents.estate_facts(doc)
    assert facts["threshold"] == 60_000 and facts["credit"] == 13_000
    assert facts["us_stock_is_us_situs"] and facts["foreign_stock_outside_us"]
