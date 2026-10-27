"""Figures extracted from issuer documents in data/raw/documents, checked against reference/.

Each reference value that cites a fund document must equal the value extracted here;
verify_reference() raises if any differs, so a changed factsheet is caught.
"""

import re
from pathlib import Path

import pandas as pd

from analysis.config import DATA_RAW, REFERENCE

DOCS = DATA_RAW / "documents"


def text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    return re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in reader.pages))


def ishares_ter(doc: str) -> float:
    """'Total Expense Ratio : 0.20%' on an iShares factsheet."""
    return float(re.search(r"Total Expense Ratio : ([0-9.]+)%", doc).group(1)) / 100


def ishares_duration(doc: str) -> float:
    """'Effective Duration : 6.27 yrs' on an iShares fixed-income factsheet."""
    return float(re.search(r"Effective Duration : ([0-9.]+) yrs", doc).group(1))


def annual_report_ter(doc: str) -> float:
    """'Total expense ratio1 % 0.24 0.24' (current year first) in an IMAS-format annual report."""
    return float(re.search(r"Total expense ratio\d? % ([0-9.]+)", doc).group(1)) / 100


def treaty_dividend_rate(doc: str) -> float:
    """Portfolio dividend rate in a US treaty: 'b) 15 percent of the gross amount of the
    dividends in all other cases'."""
    m = re.search(r"(\d+) percent of the gross amount of the dividends in all other cases", doc)
    return float(m.group(1)) / 100


def statutory_rate(doc: str) -> float:
    """'subject to U.S. tax of 30%' in IRS Publication 515."""
    return float(re.search(r"subject to U\.S\. tax of (\d+)%", doc).group(1)) / 100


def estate_facts(doc: str) -> dict[str, float | bool]:
    """Filing threshold, unified credit and stock situs rule in the Form 706-NA instructions."""
    threshold = re.search(r"filing threshold of \$([0-9,]+)", doc).group(1)
    credit = re.search(r"maximum unified credit is \$([0-9,]+)", doc).group(1)
    return {
        "threshold": float(threshold.replace(",", "")),
        "credit": float(credit.replace(",", "")),
        "us_stock_is_us_situs": "stock of corporations organized in or under U.S. law is "
        "property located in the United States" in doc,
        "foreign_stock_outside_us": "all other corporate stock is property located outside "
        "the United States" in doc,
    }


def tax_facts() -> dict[str, float | bool]:
    """Facts behind reference/withholding_tax.csv, read from the cited documents."""
    estate = estate_facts(text(DOCS / "IRS_i706na.pdf"))
    isac = text(DOCS / "ISAC_factsheet.pdf")
    return {
        "US-Ireland dividend rate": treaty_dividend_rate(text(DOCS / "US_Ireland_treaty.pdf")),
        "US statutory rate": statutory_rate(text(DOCS / "IRS_p515.pdf")),
        "Singapore in US treaty list": "Singapore" in text(DOCS / "IRS_p901.pdf"),
        "Singapore in death-tax treaty list": "Singapore" in text(DOCS / "IRS_i706na.pdf"),
        "estate filing threshold": estate["threshold"],
        "estate unified credit": estate["credit"],
        "US stock is US-situs": estate["us_stock_is_us_situs"],
        "foreign stock outside US": estate["foreign_stock_outside_us"],
        "ISAC accumulates": "Use of Income : Accumulating" in isac,
        "ISAC Irish": "Domicile : Ireland" in isac,
        "A35 no income tax": "There is no income tax for the financial year"
        in text(DOCS / "A35_annual_report.pdf"),
        "Irish ETF stamp duty exempt": "Irish stamp duty does not apply to the transfer of "
        "shares in Irish domiciled ETFs" in text(DOCS / "Revenue_TDM_27-01A-03.pdf"),
    }


EXPECTED_TAX_FACTS = {
    "Singapore in US treaty list": False,
    "Singapore in death-tax treaty list": False,
    "estate filing threshold": 60_000.0,
    "estate unified credit": 13_000.0,
    "US stock is US-situs": True,
    "foreign stock outside US": True,
    "ISAC accumulates": True,
    "ISAC Irish": True,
    "A35 no income tax": True,
    "Irish ETF stamp duty exempt": True,
}


def extracted() -> dict[str, float]:
    isac, iglo = text(DOCS / "ISAC_factsheet.pdf"), text(DOCS / "IGLO_factsheet.pdf")
    a35 = text(DOCS / "A35_annual_report.pdf")
    return {
        "ISAC.L ter": ishares_ter(isac),
        "A35.SI ter": annual_report_ter(a35),
        "IGLO duration": ishares_duration(iglo),
        "IGLO ter": ishares_ter(iglo),
    }


def verify_reference() -> dict[str, float]:
    """Raise if reference/ values that cite fund documents differ from the documents."""
    got = extracted()
    costs = pd.read_csv(REFERENCE / "etf_costs.csv").set_index("ticker")
    durations = pd.read_csv(REFERENCE / "bond_durations.csv")
    checks = {
        "ISAC.L ter": float(costs.loc["ISAC.L", "ter"]),
        "A35.SI ter": float(costs.loc["A35.SI", "ter"]),
        "IGLO duration": float(durations["effective_duration_years"].iloc[0]),
    }
    bad = {k: (v, got[k]) for k, v in checks.items() if abs(v - got[k]) > 1e-9}
    wht = pd.read_csv(REFERENCE / "withholding_tax.csv")
    rate = dict(zip(wht["source_document"], wht["rate"], strict=True))
    tax = tax_facts()
    expected = {
        **EXPECTED_TAX_FACTS,
        "US-Ireland dividend rate": float(rate["US_Ireland_treaty.pdf; IRS_i706na.pdf"]),
        "US statutory rate": float(rate["IRS_p515.pdf; IRS_p901.pdf; IRS_i706na.pdf"]),
    }
    bad |= {k: (v, tax[k]) for k, v in expected.items() if tax[k] != v}
    if bad:
        raise ValueError(f"reference/ differs from source documents (reference, document): {bad}")
    return {**got, **tax}
