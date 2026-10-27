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


def parse_amount(token: str) -> float:
    """'357,634' -> 357634; '(42,853)' -> -42853; '-' -> 0."""
    if token.strip("–-") == "":
        return 0.0
    negative = token.startswith("(")
    value = float(token.strip("()").replace(",", ""))
    return -value if negative else value


def statement_value(
    page_text: str, label: str, index: int, after: str | None = None, skip: int = 0
) -> float:
    """The index-th amount on the first line starting with `label` (after the text `after`,
    if given), skipping `skip` leading tokens such as a note number."""
    text = re.sub(r"\s+", " ", page_text)
    start = text.find(after) if after else 0
    if start < 0:
        raise ValueError(f"'{after}' not found")
    m = re.search(re.escape(label) + r"((?: (?:\(?[0-9][0-9,]*\)?|-))+)", text[start:])
    if m is None:
        raise ValueError(f"'{label}' not found")
    tokens = m.group(1).split()[skip:]
    return abs(parse_amount(tokens[index]))


def _page_text(document: str, page: int) -> str:
    from pypdf import PdfReader

    return PdfReader(DOCS / document).pages[page - 1].extract_text() or ""


def fund_withholding() -> pd.DataFrame:
    """Income and fund-level tax read from each fund's audited annual report at the cited page
    and column, with the effective rate (tax / income)."""
    ref = pd.read_csv(REFERENCE / "fund_withholding.csv")
    rows = {}
    for r in ref.to_dict("records"):
        get = {}
        for part in ("income", "tax"):
            after = r[f"{part}_after"] if isinstance(r[f"{part}_after"], str) else None
            get[part] = statement_value(
                _page_text(r["document"], int(r[f"{part}_page"])),
                r[f"{part}_label"],
                int(r[f"{part}_index"]),
                after,
                int(r[f"{part}_skip"]),
            )
        rows[r["ticker"]] = {
            "income_reference": float(r["income"]),
            "income_document": get["income"],
            "tax_reference": float(r["tax"]),
            "tax_document": get["tax"],
            "effective_rate": get["tax"] / get["income"],
        }
    return pd.DataFrame(rows).T


def iras_overseas_not_taxable() -> bool:
    import html

    raw = (DOCS / "IRAS_income_from_overseas.html").read_text(errors="ignore")
    raw = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", "", raw)
    page = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    return (
        "Generally, overseas income received in Singapore, including overseas income deposited "
        "into a Singapore bank account is not taxable" in page
    )


IRISH_NON_RESIDENT = (
    "will not have to self-account for tax on the occasion of a taxable event if (a) the "
    "holder of Shares is neither Irish Resident nor Irish Ordinary Resident"
)
A35_INDIVIDUALS = (
    "Individuals (whether resident in Singapore or not) are exempt from Singapore income tax "
    "on distributions"
)


def prospectus_facts() -> dict[str, bool]:
    def has(document: str, phrase: str) -> bool:
        squash = lambda s: re.sub(r"\s*-\s*", "-", s)  # noqa: E731
        return squash(phrase) in squash(text(DOCS / document))

    return {
        "iShares V non-residents untaxed": has("iShares_V_prospectus.pdf", IRISH_NON_RESIDENT),
        "iShares III non-residents untaxed": has("iShares_III_prospectus.pdf", IRISH_NON_RESIDENT),
        "A35 individuals exempt": has("A35_prospectus.pdf", A35_INDIVIDUALS),
        "IRAS overseas income not taxable": iras_overseas_not_taxable(),
    }


def factsheet_fund_duration(doc: str) -> float:
    """Fund's 'Weighted Average Duration (years)' on an Amova factsheet (third fund figure,
    after tracking error and yield)."""
    m = re.search(r"Weighted Average Duration\d? \(years\)[^F]*Fund [0-9.]+ [0-9.]+ ([0-9.]+)", doc)
    return float(m.group(1))


def ishares_calendar_returns(doc: str) -> pd.Series:
    """Share-class calendar-year returns (NAV, %, decimals) from an iShares factsheet's
    'CALENDAR YEAR PERFORMANCE' table."""
    m = re.search(r"CALENDAR YEAR PERFORMANCE ((?:\d{4} )+)Share Class ((?:-?[0-9.]+ )+)", doc)
    years = [int(y) for y in m.group(1).split()]
    values = [float(v) / 100 for v in m.group(2).split()[: len(years)]]
    return pd.Series(values, index=years)


AMOVA_PERIODS = {"1 Yr": 1, "3 Yr": 3, "5 Yr": 5}


def amova_period_returns(doc: str) -> pd.DataFrame:
    """Fund NAV returns (1, 3 and 5 years; multi-year annualised) from each 'PERFORMANCE
    SUMMARY' table in an Amova report, with the 'Returns as at' date of each table."""
    rows = []
    pattern = (
        r"Returns \(%\) 3 Mth 6 Mth 1 Yr 3 Yr 5 Yr 10 Yr Since Inception "
        r"ABF Singapore Bond Index Fund ((?:-?[0-9.]+ ){7}).*?Returns as at (\d{1,2} \w+ \d{4})"
    )
    for m in re.finditer(pattern, doc):
        values = [float(v) / 100 for v in m.group(1).split()]
        end = pd.Period(pd.Timestamp(m.group(2)), freq="M")
        for label, years in AMOVA_PERIODS.items():
            idx = ["3 Mth", "6 Mth", "1 Yr", "3 Yr", "5 Yr", "10 Yr", "SI"].index(label)
            rows.append({"period_end": end, "years": years, "issuer_return": values[idx]})
    return pd.DataFrame(rows).drop_duplicates()


def issuer_period_returns() -> pd.DataFrame:
    """Issuer-published NAV total returns for ISAC, IGLO (calendar years, USD) and A35 (1, 3
    and 5 years to each report date, SGD), from the hashed documents."""
    rows = []
    for ticker, f in (("ISAC.L", "ISAC_factsheet.pdf"), ("IGLO.L", "IGLO_factsheet.pdf")):
        for year, r in ishares_calendar_returns(text(DOCS / f)).items():
            rows.append(
                {
                    "ticker": ticker,
                    "period_end": pd.Period(f"{year}-12", freq="M"),
                    "years": 1,
                    "issuer_return": r,
                    "source": f,
                }
            )
    a35 = amova_period_returns(text(DOCS / "A35_annual_report.pdf"))
    for r in a35.to_dict("records"):
        rows.append({"ticker": "A35.SI", **r, "source": "A35_annual_report.pdf"})
    return pd.DataFrame(rows)


def extracted() -> dict[str, float]:
    isac, iglo = text(DOCS / "ISAC_factsheet.pdf"), text(DOCS / "IGLO_factsheet.pdf")
    a35 = text(DOCS / "A35_annual_report.pdf")
    return {
        "ISAC.L ter": ishares_ter(isac),
        "A35.SI ter": annual_report_ter(a35),
        "IGLO duration": ishares_duration(iglo),
        "IGLO ter": ishares_ter(iglo),
        "A35 duration": factsheet_fund_duration(text(DOCS / "A35_factsheet.pdf")),
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
        "A35 duration": float(
            durations.loc[
                durations["share_class"].str.startswith("A35"), "effective_duration_years"
            ].iloc[0]
        ),
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
    fw = fund_withholding()
    for t, r in fw.iterrows():
        for part in ("income", "tax"):
            if abs(r[f"{part}_reference"] - r[f"{part}_document"]) > 1e-9:
                bad[f"{t} {part}"] = (r[f"{part}_reference"], r[f"{part}_document"])
    prospectus = prospectus_facts()
    bad |= {k: (True, v) for k, v in prospectus.items() if not v}
    if bad:
        raise ValueError(f"reference/ differs from source documents (reference, document): {bad}")
    return {**got, **tax, **prospectus, **fw["effective_rate"].add_prefix("WHT ").to_dict()}
