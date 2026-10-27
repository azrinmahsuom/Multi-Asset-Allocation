"""Download public data sources to data/raw/<source>/ and record each file in the manifest.

Every URL, series ID and licence below was checked by fetching it (2026-10-26). Landing
pages are scraped for the current file link where the file URL carries a changing version
tag (Shiller, JST), so a moved file fails loudly rather than being guessed.

A file already on disk is not re-downloaded. If a fresh download differs from the hash in
the committed manifest, it is kept and reported as changed since snapshot (see
analysis.headline for the drift report); accept the new version only via fetch_all(refresh=True).
"""

import json
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

from analysis import manifest, prices
from analysis.config import DATA_RAW

TIMEOUT = 120
HEADERS = {"User-Agent": "Multi-Asset-Allocation research (github.com/azrinmahsuom)"}

NO_LICENCE = "No licence stated by the source; free download. Treated as not redistributable."
FRED_PUBLIC = "Public domain, citation requested (FRED series page)."
FRED_MOODYS = "Copyrighted (Moody's), citation required (FRED series page). Not redistributable."
JST_LICENCE = (
    "CC BY-NC-SA 4.0 (macrohistory.net/database/licence-terms/). Non-commercial use, "
    "citation required, share-alike."
)


@dataclass(frozen=True)
class RawFile:
    """One file to download, with the provenance written to the manifest."""

    source: str  # folder under data/raw
    filename: str
    name: str
    landing_page: str
    series: str
    licence: str
    redistributable: bool
    units: str
    resolve_url: Callable[[], str]
    describe: Callable[[Path], tuple[int, str, str]]  # (rows, start, end)
    download: Callable[[str], bytes] = lambda url: _get(url).content
    manual: bool = False  # owner downloads it in a browser; fetch only records it

    @property
    def path(self) -> Path:
        return DATA_RAW / self.source / self.filename


def _get(url: str) -> requests.Response:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    return response


MAS_RATES_PAGE = "https://eservices.mas.gov.sg/statistics/dir/DomesticInterestRates.aspx"
# Checkbox positions on the MAS form, checked against their labels on 2026-10-27.
MAS_COLUMNS = {
    0: "Interbank Overnight",
    4: "Interbank 3-month",
    13: "SORA",
    14: "SORA Index",
    16: "3-month Compounded SORA",
}


MAS_SGS_PAGE = "https://eservices.mas.gov.sg/statistics/fdanet/BenchmarkPricesAndYields.aspx"
SGS_TENORS = ["Two", "Five", "Seven", "Ten", "Fifteen", "Twenty", "Thirty"]


def _download_mas_sgs(url: str) -> bytes:
    """Submit the MAS SGS benchmark prices and yields form: daily yields, 1988 to this year."""
    session = requests.Session()
    session.headers.update(HEADERS)
    page = session.get(url, timeout=TIMEOUT)
    page.raise_for_status()
    form = dict(
        re.findall(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page.text)
    )
    prefix = "ctl00$ContentPlaceHolder1$"
    for tenor in SGS_TENORS:
        if f"{prefix}{tenor}YearBondYieldCheckBox" not in page.text:
            raise RuntimeError(f"MAS SGS form has no {tenor}-year yield box; it may have changed.")
    form.update(
        {
            prefix + "StartYearDropDownList": "1988",
            prefix + "StartMonthDropDownList": "1",
            prefix + "EndYearDropDownList": str(pd.Timestamp.today().year),
            prefix + "EndMonthDropDownList": "12",
            prefix + "FrequencyDropDownList": "D",
            prefix + "DownloadButton": "Download",
        }
    )
    form.update({f"{prefix}{t}YearBondYieldCheckBox": "on" for t in SGS_TENORS})
    response = session.post(url, data=form, timeout=TIMEOUT * 2)
    response.raise_for_status()
    if "text/csv" not in response.headers.get("content-type", ""):
        raise RuntimeError("MAS did not return a CSV. The form may have changed.")
    return response.content


def _describe_mas_sgs(path: Path) -> tuple[int, str, str]:
    dates = []
    year = month = None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = line.split(",")
        if len(parts) < 4 or not parts[2].strip().isdigit():
            continue
        year, month = parts[0].strip() or year, parts[1].strip() or month
        dates.append(pd.to_datetime(f"{year} {month} {parts[2].strip()}", format="%Y %b %d"))
    return len(dates), min(dates).strftime("%Y-%m-%d"), max(dates).strftime("%Y-%m-%d")


def _download_mas_rates(url: str) -> bytes:
    """Submit the MAS Domestic Interest Rates form (an ASP.NET page) and return the CSV.

    Requests every daily observation from January 1987 to December of the current year.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    page = session.get(url, timeout=TIMEOUT)
    page.raise_for_status()
    form = dict(
        re.findall(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page.text)
    )
    labels = dict(
        re.findall(r'for="ContentPlaceHolder1_ColumnsCheckBoxList_(\d+)">([^<]*)', page.text)
    )
    for i, label in MAS_COLUMNS.items():
        if labels.get(str(i), "").strip().lower() != label.lower():
            raise RuntimeError(
                f"MAS form column {i} is {labels.get(str(i))!r}, expected {label!r}."
            )
    prefix = "ctl00$ContentPlaceHolder1$"
    form.update(
        {
            prefix + "StartYearDropDownList": "1987",
            prefix + "EndYearDropDownList": str(pd.Timestamp.today().year),
            prefix + "StartMonthDropDownList": "1",
            prefix + "EndMonthDropDownList": "12",
            prefix + "Button2": "Download",
        }
    )
    form.update({f"{prefix}ColumnsCheckBoxList${i}": "on" for i in MAS_COLUMNS})
    response = session.post(url, data=form, timeout=TIMEOUT)
    response.raise_for_status()
    if "text/csv" not in response.headers.get("content-type", ""):
        raise RuntimeError("MAS did not return a CSV. The form may have changed.")
    return response.content


def _link_on_page(page: str, pattern: str) -> Callable[[], str]:
    """Resolver that finds the first href matching pattern on a landing page."""

    def resolve() -> str:
        html = _get(page).text
        match = re.search(rf'href="([^"]*{pattern}[^"]*)"', html)
        if not match:
            raise RuntimeError(
                f"No link matching {pattern!r} on {page}. The source may have moved."
            )
        href = match.group(1)
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return re.match(r"https?://[^/]+", page).group(0) + href
        return href

    return resolve


def _fixed(url: str) -> Callable[[], str]:
    return lambda: url


# --- describe(): row count and date range of each raw file, for the manifest ---


def _describe_shiller(path: Path) -> tuple[int, str, str]:
    df = pd.read_excel(path, sheet_name="Data", header=7)
    dates = pd.to_numeric(df["Date"], errors="coerce").dropna()
    as_month = [f"{d:.2f}".replace(".", "-") for d in (dates.iloc[0], dates.iloc[-1])]
    return len(dates), as_month[0], as_month[1]


def _describe_french(date_digits: int) -> Callable[[Path], tuple[int, str, str]]:
    """French CSVs hold several tables; count rows of the first (monthly or daily) one."""

    def describe(path: Path) -> tuple[int, str, str]:
        with zipfile.ZipFile(path) as zf:
            text = zf.read(zf.namelist()[0]).decode("latin-1")
        dates = []
        for line in text.splitlines():
            match = re.match(rf"\s*(\d{{{date_digits}}})\s*,", line)
            if match:
                dates.append(match.group(1))
            elif dates and line.strip() and not line.strip()[0].isdigit():
                break  # end of the first table
        fmt = "%Y%m" if date_digits == 6 else "%Y%m%d"
        start, end = (pd.to_datetime(d, format=fmt) for d in (dates[0], dates[-1]))
        out = "%Y-%m" if date_digits == 6 else "%Y-%m-%d"
        return len(dates), start.strftime(out), end.strftime(out)

    return describe


def _describe_damodaran(path: Path) -> tuple[int, str, str]:
    df = pd.read_excel(path, sheet_name="Returns by year", header=None)
    header_row = df.index[df[0] == "Year"][0]
    years = pd.to_numeric(df.loc[header_row + 1 :, 0], errors="coerce")
    years = years[(years > 1800) & (years < 2200)].astype(int)
    return len(years), str(years.min()), str(years.max())


def _describe_jst(path: Path) -> tuple[int, str, str]:
    df = pd.read_excel(path, usecols=["year", "country"])
    return len(df), str(df["year"].min()), str(df["year"].max())


def mas_first_table(path: Path) -> list[tuple[pd.Timestamp, list[str]]]:
    """Dated rows of the first table in the MAS CSV.

    The file repeats its header every year and leaves year and month blank after their first
    row, e.g. "1987,Jul,01,2.75,4.31,-" then ",,02,7.00,4.38,-". A second table (SORA Index
    and compounded SORA) follows the first; it starts when the dates restart.
    """
    rows, year, month = [], None, None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = line.split(",")
        if len(parts) < 4 or not parts[2].strip().isdigit():
            continue
        year = parts[0].strip() or year
        month = parts[1].strip() or month
        date = pd.to_datetime(f"{year} {month} {parts[2].strip()}", format="%Y %b %d")
        if rows and date < rows[-1][0]:
            break  # second table begins
        rows.append((date, [p.strip() for p in parts[3:]]))
    return rows


def _describe_mas(path: Path) -> tuple[int, str, str]:
    rows = mas_first_table(path)
    with_data = [date for date, values in rows if any(v not in ("", "-") for v in values)]
    return len(rows), with_data[0].strftime("%Y-%m-%d"), with_data[-1].strftime("%Y-%m-%d")


def _describe_nareit(path: Path) -> tuple[int, str, str]:
    df = pd.read_excel(path, sheet_name="Index Data", header=None, usecols=[0])
    dates = pd.to_datetime(df[0], errors="coerce").dropna()
    return len(dates), dates.iloc[0].strftime("%Y-%m"), dates.iloc[-1].strftime("%Y-%m")


def _describe_singstat(path: Path) -> tuple[int, str, str]:
    columns = json.loads(path.read_text())["Data"]["row"][0]["columns"]
    months = [pd.to_datetime(c["key"], format="%Y %b") for c in columns]
    return len(months), min(months).strftime("%Y-%m"), max(months).strftime("%Y-%m")


def _describe_pdf(path: Path) -> tuple[int, str, str]:
    """Page count and the document's 'as at/as of' date or financial year end, if found."""
    from pypdf import PdfReader

    reader = PdfReader(path)
    text = re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in reader.pages[:3]))
    m = re.search(r"(?:as (?:at|of)|year ended) (\d{1,2}[ -](?:[A-Z][a-z]{2,8})[ -]\d{4})", text)
    date = m.group(1) if m else "unknown"
    return len(reader.pages), date, date


AMOVA_A35 = "https://sg.amova-am.com/general/funds/detail/abf-singapore-bond-index-fund"
ISHARES_UK = "https://www.ishares.com/uk/individual/en/literature/fact-sheet/"
ISHARES_LIT = "https://www.ishares.com/gls-download/literature/"
BLACKROCK_LIT = "https://www.blackrock.com/gls-download/literature/"
FUND_DOCUMENTS = [
    (
        "ISAC_factsheet.pdf",
        "iShares MSCI ACWI UCITS ETF USD (Acc), factsheet",
        "https://www.ishares.com/uk/individual/en/products/251850/ishares-msci-acwi-ucits-etf",
        "monthly factsheet (TER, domicile, benchmark)",
        _fixed(ISHARES_UK + "ssac-ishares-msci-acwi-ucits-etf-fund-fact-sheet-en-gb.pdf"),
    ),
    (
        "IGLO_factsheet.pdf",
        "iShares Global Govt Bond UCITS ETF USD (Dist), factsheet",
        "https://www.ishares.com/uk/individual/en/products/251753/ishares-global-government-bond-ucits-etf",
        "monthly factsheet (TER, effective duration, benchmark)",
        _fixed(ISHARES_UK + "iglo-ishares-global-govt-bond-ucits-etf-fund-fact-sheet-en-gb.pdf"),
    ),
    (
        "A35_factsheet.pdf",
        "ABF Singapore Bond Index Fund, factsheet",
        AMOVA_A35,
        "monthly factsheet (fees, benchmark)",
        _link_on_page(AMOVA_A35, r"ABF-SINGAPORE-BOND-INDEX-FUND-FACTSHEET\.pdf"),
    ),
    (
        "A35_annual_report.pdf",
        "ABF Singapore Bond Index Fund, audited annual report",
        AMOVA_A35,
        "audited annual report (total expense ratio)",
        _link_on_page(AMOVA_A35, r"annual-report/ABF2\.pdf"),
    ),
    (
        "A35_prospectus.pdf",
        "ABF Singapore Bond Index Fund, prospectus",
        AMOVA_A35,
        "prospectus (taxation of distributions)",
        _link_on_page(AMOVA_A35, r"prospectus/PROSPECTUS_ABF2\.pdf"),
    ),
    (
        "iShares_V_annual_report.pdf",
        "iShares V plc (issuer of ISAC), audited annual report, year ended 30 November 2025",
        "https://www.ishares.com/uk/individual/en/products/251850/ishares-msci-acwi-ucits-etf",
        "audited annual report (dividend income and withholding tax by fund)",
        _fixed(BLACKROCK_LIT + "annual-report/ishares-v-plc-annual-report-en-30-nov-25.pdf"),
    ),
    (
        "iShares_III_annual_report.pdf",
        "iShares III plc (issuer of IGLO), audited annual report, year ended 30 June 2025",
        "https://www.ishares.com/uk/individual/en/products/251753/ishares-global-government-bond-ucits-etf",
        "audited annual report (interest income and withholding tax by fund)",
        _fixed(BLACKROCK_LIT + "annual-report/ishares-iii-plc-annual-report-en-30-jun-25.pdf"),
    ),
    (
        "iShares_V_prospectus.pdf",
        "iShares V plc, prospectus",
        "https://www.ishares.com/uk/individual/en/products/251850/ishares-msci-acwi-ucits-etf",
        "prospectus (Irish taxation of non-resident shareholders)",
        _fixed(ISHARES_LIT + "prospectus/ishares-v-plc-prospectus-en.pdf"),
    ),
    (
        "iShares_III_prospectus.pdf",
        "iShares III plc, prospectus",
        "https://www.ishares.com/uk/individual/en/products/251753/ishares-global-government-bond-ucits-etf",
        "prospectus (Irish taxation of non-resident shareholders)",
        _fixed(ISHARES_LIT + "prospectus/ishares-iii-plc-prospectus-en.pdf"),
    ),
]


IRS_PDF = "https://www.irs.gov/pub/irs-pdf/"
IRAS_OVERSEAS = (
    "https://www.iras.gov.sg/taxes/individual-income-tax/basics-of-individual-income-tax/"
    "what-is-taxable-what-is-not/income-received-from-overseas"
)


def _describe_html(path: Path) -> tuple[int, str, str]:
    return len(path.read_bytes()), "n/a", "n/a"


TAX_DOCUMENTS = [
    (
        "US_Ireland_treaty.pdf",
        "US-Ireland income tax convention (1997), treaty text",
        "https://www.irs.gov/businesses/international-businesses/ireland-tax-treaty-documents",
        "Article 10 (dividends) withholding rates",
        _fixed("https://www.irs.gov/pub/irs-trty/ireland.pdf"),
    ),
    (
        "IRS_p515.pdf",
        "IRS Publication 515, Withholding of Tax on Nonresident Aliens and Foreign Entities",
        "https://www.irs.gov/publications/p515",
        "statutory 30% withholding on US-source income of foreign persons",
        _fixed(IRS_PDF + "p515.pdf"),
    ),
    (
        "IRS_p901.pdf",
        "IRS Publication 901, U.S. Tax Treaties",
        "https://www.irs.gov/publications/p901",
        "list of US income tax treaty countries (no Singapore treaty)",
        _fixed(IRS_PDF + "p901.pdf"),
    ),
    (
        "IRS_i706na.pdf",
        "Instructions for Form 706-NA (estate of a nonresident not a US citizen)",
        "https://www.irs.gov/forms-pubs/about-form-706-na",
        "US-situs rules, filing threshold, unified credit, death-tax treaty list",
        _fixed(IRS_PDF + "i706na.pdf"),
    ),
    (
        "Revenue_TDM_27-01A-03.pdf",
        "Irish Revenue Tax and Duty Manual Part 27-01A-03, Exchange Traded Funds",
        "https://www.revenue.ie/en/tax-professionals/tdm/income-tax-capital-gains-tax-corporation-tax/part-27/index.aspx",
        "Irish stamp duty on Irish-domiciled ETFs",
        _fixed(
            "https://www.revenue.ie/en/tax-professionals/tdm/income-tax-capital-gains-tax-"
            "corporation-tax/part-27/27-01a-03-20201001155445.pdf"
        ),
    ),
]


def _describe_fred(path: Path) -> tuple[int, str, str]:
    df = pd.read_csv(path)
    return len(df), str(df.iloc[0, 0])[:7], str(df.iloc[-1, 0])[:7]


# --- registry ---

FRED_SERIES = {
    "TB3MS": ("3-month Treasury bill, secondary market rate", "Monthly average, % p.a.", True),
    "GS1": ("1-year Treasury constant maturity yield", "Monthly average, % p.a.", True),
    "GS5": ("5-year Treasury constant maturity yield", "Monthly average, % p.a.", True),
    "GS10": ("10-year Treasury constant maturity yield", "Monthly average, % p.a.", True),
    "GS30": ("30-year Treasury constant maturity yield", "Monthly average, % p.a.", True),
    "FII10": ("10-year TIPS constant maturity real yield", "Monthly average, % p.a., real", True),
    "CPIAUCSL": ("US CPI, all urban consumers", "Monthly index, 1982-84=100, SA", True),
    "CPIAUCNS": (
        "US CPI, all urban consumers (TIPS index basis)",
        "Monthly index, 1982-84=100, NSA",
        True,
    ),
    "EXSIUS": ("Singapore dollars to one US dollar", "Monthly average, SGD per USD", True),
    "BAA": ("Moody's seasoned Baa corporate bond yield", "Monthly average, % p.a.", False),
    "AAA": ("Moody's seasoned Aaa corporate bond yield", "Monthly average, % p.a.", False),
    # Daily series give true month-end yields; monthly FRED yields are monthly averages.
    "DTB3": ("3-month Treasury bill, secondary market rate", "Daily, % p.a., discount basis", True),
    "DGS1": ("1-year Treasury constant maturity yield", "Daily, % p.a.", True),
    "DGS5": ("5-year Treasury constant maturity yield", "Daily, % p.a.", True),
    "DGS10": ("10-year Treasury constant maturity yield", "Daily, % p.a.", True),
    "DGS30": ("30-year Treasury constant maturity yield", "Daily, % p.a.", True),
    "DFII10": ("10-year TIPS constant maturity real yield", "Daily, % p.a., real", True),
    "DEXSIUS": ("Singapore dollars to one US dollar, noon buying rate", "Daily, SGD per USD", True),
}

# REIT ETFs (identifiers only, not recommendations), as of 2026-10. History start dates
# checked on Yahoo on 2026-10-27.
REIT_ETFS = {
    "VNQ": ("US REITs, from 2004", "USD"),
    "VNQI": ("developed and emerging ex-US real estate, from 2010", "USD"),
    "RWO": ("global REITs, from 2008", "USD"),
    "REET": ("global REITs, from 2014", "USD"),
    "IDWP.L": ("UCITS developed-markets property yield, USD line, from 2008", "USD"),
    "CLR.SI": ("Singapore REITs, from 2017", "SGD"),
    "CFA.SI": ("Asia ex-Japan REITs, from 2017", "SGD"),
    "SRT.SI": ("Singapore REITs, from 2021", "SGD"),
}

# Global equity and bond ETFs for SGD-perspective tests (identifiers only), as of 2026-10.
# AGGG.L and AGGU.L are the unhedged and USD-hedged classes of the same global aggregate
# bond fund, so hedging is compared on one index.
GLOBAL_ETFS = {
    "ACWI": ("global equities (developed and emerging), from 2008", "USD"),
    "AGGG.L": ("UCITS global aggregate bonds, unhedged, distributing, from 2017", "USD"),
    "AGGU.L": ("UCITS global aggregate bonds, USD-hedged, accumulating, from 2017", "USD"),
    # Same global government bond fund: unhedged (IGLO.L) and USD-hedged (SGLU.AS) classes.
    "IGLO.L": ("UCITS global government bonds, unhedged, distributing, from 2009", "USD"),
    "SGLU.AS": ("UCITS global government bonds, USD-hedged, accumulating, from 2019", "USD"),
}

# US bond ETFs: realised returns after default losses and costs, used to check returns built
# from yields (identifiers only), as of 2026-10.
BOND_ETFS = {
    "LQD": ("US investment-grade corporate bonds, from 2002", "USD"),
    "IEF": ("US Treasuries 7-10 years, from 2002", "USD"),
    "TIP": ("US Treasury inflation-protected securities, from 2003", "USD"),
}

# Real-asset candidates for the asset-universe tests (identifiers only), as of 2026-10.
REAL_ASSET_ETFS = {
    "GLD": ("gold bullion, from 2004", "USD"),
    "DBC": ("diversified commodity futures, from 2006", "USD"),
}

# Representative funds for the ETF-level backtest (identifiers only; final choice in Phase 4).
STRATEGY_ETFS = {
    "ISAC.L": ("UCITS global equities (MSCI ACWI), Irish-domiciled, USD, accumulating", "USD"),
    "A35.SI": ("Singapore bond index fund (SGS and quasi-government), SGD", "SGD"),
}

ETFS = {**REIT_ETFS, **GLOBAL_ETFS, **BOND_ETFS, **REAL_ASSET_ETFS, **STRATEGY_ETFS}

FRENCH_FTP = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FRENCH_UNITS = (
    "{freq}, % per {period}, USD nominal. Mkt-RF (value-weighted US market total return "
    "minus RF), SMB, HML, RF (1-month T-bill)."
)

REGISTRY: list[RawFile] = (
    [
        RawFile(
            source="shiller",
            filename="ie_data.xls",
            name="Robert Shiller online data",
            landing_page="https://shillerdata.com/",
            series="ie_data.xls, sheet Data",
            licence=NO_LICENCE,
            redistributable=False,
            units=(
                "Monthly. S&P Composite price, dividends, earnings (USD nominal), CPI, 10-year "
                "Treasury yield (% p.a.), plus Shiller's real total-return and bond-return columns."
            ),
            resolve_url=_link_on_page("https://shillerdata.com/", r"ie_data\.xls"),
            describe=_describe_shiller,
        ),
        RawFile(
            source="french",
            filename="F-F_Research_Data_Factors_CSV.zip",
            name="Kenneth French Data Library",
            landing_page="https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html",
            series="Fama/French 3 Factors (monthly)",
            licence=NO_LICENCE,
            redistributable=False,
            units=FRENCH_UNITS.format(freq="Monthly", period="month"),
            resolve_url=_fixed(FRENCH_FTP + "F-F_Research_Data_Factors_CSV.zip"),
            describe=_describe_french(6),
        ),
        RawFile(
            source="french",
            filename="F-F_Research_Data_Factors_daily_CSV.zip",
            name="Kenneth French Data Library",
            landing_page="https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html",
            series="Fama/French 3 Factors (daily)",
            licence=NO_LICENCE,
            redistributable=False,
            units=FRENCH_UNITS.format(freq="Daily", period="day"),
            resolve_url=_fixed(FRENCH_FTP + "F-F_Research_Data_Factors_daily_CSV.zip"),
            describe=_describe_french(8),
        ),
        RawFile(
            source="french",
            filename="Developed_3_Factors_CSV.zip",
            name="Kenneth French Data Library",
            landing_page="https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html",
            series="Fama/French Developed 3 Factors (monthly)",
            licence=NO_LICENCE,
            redistributable=False,
            units=(
                "Monthly, % per month, USD nominal. Mkt-RF (developed-markets value-weighted "
                "total return minus RF), SMB, HML, RF (1-month US T-bill)."
            ),
            resolve_url=_fixed(FRENCH_FTP + "Developed_3_Factors_CSV.zip"),
            describe=_describe_french(6),
        ),
        RawFile(
            source="damodaran",
            filename="histretSP.xls",
            name="Aswath Damodaran, historical returns on stocks, bonds and bills",
            landing_page="https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html",
            series="histretSP.xls, sheet Returns by year",
            licence=NO_LICENCE,
            redistributable=False,
            units=(
                "Annual, USD nominal, decimal. S&P 500 incl. dividends, small cap, 3-month T-bill, "
                "10-year T-bond, Baa corporate, real estate, gold total returns; CPI inflation."
            ),
            resolve_url=_fixed("https://pages.stern.nyu.edu/~adamodar/pc/datasets/histretSP.xls"),
            describe=_describe_damodaran,
        ),
        RawFile(
            source="jst",
            filename="JSTdataset.xlsx",
            name="Jordà-Schularick-Taylor Macrohistory Database",
            landing_page="https://www.macrohistory.net/database/",
            series="JST dataset (country-year panel); release named in url",
            licence=JST_LICENCE,
            redistributable=True,
            units=(
                "Annual, local currency nominal. eq_tr, bond_tr, housing_tr total returns "
                "(decimal), bill_rate (decimal), cpi (index), xrusd (local currency per USD)."
            ),
            resolve_url=_link_on_page(
                "https://www.macrohistory.net/database/", r"JSTdataset\w*\.xlsx"
            ),
            describe=_describe_jst,
        ),
        RawFile(
            source="mas",
            filename="domestic_interest_rates.csv",
            name="Monetary Authority of Singapore, Domestic Interest Rates",
            landing_page=MAS_RATES_PAGE,
            series=", ".join(MAS_COLUMNS.values()) + " (daily)",
            licence=(
                "MAS Terms of Use of Datasets (mas.gov.sg/terms-of-use): royalty-free licence to "
                "use and distribute, commercially or not, with a notice acknowledging MAS as the "
                "source."
            ),
            redistributable=True,
            units=(
                "Daily, % p.a., SGD. Interbank rates Jul 1987 to Dec 2013 (discontinued by MAS "
                "from 1 Jan 2014). SORA and 3-month compounded SORA (backward-looking) from "
                "2005; SORA Index is a compounded overnight index level."
            ),
            resolve_url=_fixed(MAS_RATES_PAGE),
            describe=_describe_mas,
            download=_download_mas_rates,
        ),
        RawFile(
            source="mas",
            filename="sgs_benchmark_yields.csv",
            name="Monetary Authority of Singapore, SGS benchmark prices and yields",
            landing_page=MAS_SGS_PAGE,
            series="SGS benchmark yields, 2/5/7/10/15/20/30-year (daily, average closing bid)",
            licence=(
                "MAS Terms of Use of Datasets (mas.gov.sg/terms-of-use): royalty-free licence to "
                "use and distribute, with a notice acknowledging MAS as the source."
            ),
            redistributable=True,
            units=(
                "Daily, % p.a., SGD. Average of SGS primary dealers' closing bid yields; the "
                "7-year benchmark was discontinued on 1 February 2011."
            ),
            resolve_url=_fixed(MAS_SGS_PAGE),
            describe=_describe_mas_sgs,
            download=_download_mas_sgs,
        ),
        RawFile(
            source="singstat",
            filename="M213751_cpi_monthly.json",
            name="Singapore Department of Statistics, CPI (2024 = 100), monthly",
            landing_page="https://tablebuilder.singstat.gov.sg/table/TS/M213751",
            series="M213751, All Items Index (and sub-indices), not seasonally adjusted",
            licence=(
                "Singapore Open Data Licence according to SingStat's app terms; the Table "
                "Builder's own terms not confirmed. Treated as not redistributable until verified."
            ),
            redistributable=False,
            units="Monthly index, 2024 = 100, NSA, SGD.",
            resolve_url=_fixed("https://tablebuilder.singstat.gov.sg/api/table/tabledata/M213751"),
            describe=_describe_singstat,
        ),
        RawFile(
            source="nareit",
            filename="MonthlyHistoricalReturns.xls",
            name="Nareit, FTSE Nareit U.S. Real Estate Index Series monthly history",
            landing_page="https://www.reit.com/data-research/reit-indexes/monthly-index-values-returns",
            series="Index Data sheet; All Equity REITs total return",
            licence=(
                "Nareit Terms of Use (reit.com, dated 2023-07-28) s.4: no distribution, public "
                "display or derivative works of site material without Nareit's prior written "
                "approval; index series also subject to FTSE terms. Not redistributable."
            ),
            redistributable=False,
            units=(
                "Monthly, USD, % per month. Total, price and income returns and index levels "
                "for each REIT index; total return = price return + income return."
            ),
            resolve_url=_fixed(
                "https://www.reit.com/sites/default/files/returns/MonthlyHistoricalReturns.xls"
            ),
            describe=_describe_nareit,
            manual=True,
        ),
    ]
    + [
        RawFile(
            source="documents",
            filename=filename,
            name=name,
            landing_page=landing,
            series="Fund document (PDF): " + what,
            licence="Issuer document; downloaded for citation only. Not redistributable.",
            redistributable=False,
            units="PDF; figures extracted by analysis.documents and checked against reference/.",
            resolve_url=resolver,
            describe=_describe_pdf,
        )
        for filename, name, landing, what, resolver in FUND_DOCUMENTS
    ]
    + [
        RawFile(
            source="documents",
            filename=filename,
            name=name,
            landing_page=landing,
            series="Tax document (PDF): " + what,
            licence="Government publication; downloaded for citation only.",
            redistributable=False,
            units="PDF; facts extracted by analysis.documents and checked against reference/.",
            resolve_url=resolver,
            describe=_describe_pdf,
        )
        for filename, name, landing, what, resolver in TAX_DOCUMENTS
    ]
    + [
        RawFile(
            source="documents",
            filename="IRAS_income_from_overseas.html",
            name="IRAS, Income received from overseas (web page)",
            landing_page=IRAS_OVERSEAS,
            series="Tax document (HTML): Singapore tax on overseas income of individuals",
            licence="Government publication; downloaded for citation only.",
            redistributable=False,
            units="HTML; facts extracted by analysis.documents and checked against reference/.",
            resolve_url=_fixed(IRAS_OVERSEAS),
            describe=_describe_html,
        )
    ]
    + [
        RawFile(
            source="fred",
            filename=f"{series_id}.csv",
            name=f"FRED: {title}",
            landing_page=f"https://fred.stlouisfed.org/series/{series_id}",
            series=series_id,
            licence=FRED_PUBLIC if public else FRED_MOODYS,
            redistributable=public,
            units=units,
            resolve_url=_fixed(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"),
            describe=_describe_fred,
        )
        for series_id, (title, units, public) in FRED_SERIES.items()
    ]
    + [
        RawFile(
            source=prices.PRICE_SOURCE.name,
            filename=f"{ticker}.csv",
            name=f"{prices.PRICE_SOURCE.name}: {ticker} ({label})",
            landing_page=f"https://finance.yahoo.com/quote/{ticker}/history",
            series=ticker,
            licence=prices.PRICE_SOURCE.licence,
            redistributable=prices.PRICE_SOURCE.redistributable,
            units=f"Daily, {currency}. {prices.PRICE_SOURCE.adjustment}",
            resolve_url=_fixed(f"yfinance: Ticker({ticker!r}).history(period='max')"),
            describe=prices.describe,
            download=lambda _url, ticker=ticker: prices.PRICE_SOURCE.download(ticker),
        )
        for ticker, (label, currency) in ETFS.items()
    ]
)


def fetch(raw: RawFile, refresh: bool = False) -> str:
    """Download one file and record it. Returns 'skipped', 'recorded', 'unchanged' or 'changed'.

    'changed' means a new download differs from the committed manifest hash: the new file is
    kept on disk and the manifest (the snapshot) is left alone; the pipeline reports it as
    changed since snapshot until it is accepted with refresh.

    Manual files are never downloaded. A missing one raises with the URL to fetch it from; a
    present one is recorded on first sight (or on refresh), dated by the file's save time.
    """
    key = raw.path.relative_to(DATA_RAW).as_posix()
    url = raw.resolve_url()
    if raw.manual:
        if not raw.path.exists():
            raise FileNotFoundError(
                f"{raw.name} must be downloaded by hand (the site blocks scripts). "
                f"Download {url} in a browser and save it as {raw.path}."
            )
        if key in manifest.load() and not refresh:
            return "skipped"
        retrieved = pd.Timestamp.fromtimestamp(raw.path.stat().st_mtime).strftime("%Y-%m-%d")
    else:
        if raw.path.exists() and not refresh:
            return "skipped"
        content = raw.download(url)
        raw.path.parent.mkdir(parents=True, exist_ok=True)
        raw.path.write_bytes(content)
        retrieved = pd.Timestamp.today().strftime("%Y-%m-%d")
        previous = manifest.load().get(key)
        if previous and not refresh:
            # Keep the snapshot's entry: an identical file needs no new record.
            same = previous["sha256"] == manifest.sha256(raw.path)
            return "unchanged" if same else "changed"

    rows, start, end = raw.describe(raw.path)
    manifest.record(
        raw.path,
        {
            "source": raw.name,
            "url": url,
            "landing_page": raw.landing_page,
            "series": raw.series,
            "retrieved": retrieved,
            "manual_download": raw.manual,
            "licence": raw.licence,
            "redistributable": raw.redistributable,
            "rows": rows,
            "start": start,
            "end": end,
            "units": raw.units,
        },
    )
    return "recorded"


def fetch_all(refresh: bool = False) -> dict[str, str]:
    """Fetch every registered file. A download that differs from the manifest snapshot is kept
    and reported as 'changed' (the run continues and the drift report shows its effect on
    the headline figures); `refresh` accepts the new versions into the manifest."""
    results = {}
    for raw in REGISTRY:
        key = raw.path.relative_to(DATA_RAW).as_posix()
        try:
            results[key] = fetch(raw, refresh)
        except FileNotFoundError as err:  # a manual download not yet saved
            results[key] = f"manual step needed: {err}"
    return results
