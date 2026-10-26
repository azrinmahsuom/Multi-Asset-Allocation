"""Download public data sources to data/raw/<source>/ and record each file in the manifest.

Every URL, series ID and licence below was checked by fetching it (2026-10-26). Landing
pages are scraped for the current file link where the file URL carries a changing version
tag (Shiller, JST), so a moved file fails loudly rather than being guessed.

A file already on disk is not re-downloaded. If a fresh download differs from the hash in
the committed manifest, the fetch fails; accept the new version only via fetch_all(refresh=True).
"""

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
        for ticker, (label, currency) in REIT_ETFS.items()
    ]
)


def fetch(raw: RawFile, refresh: bool = False) -> str:
    """Download one file and record it. Returns 'skipped', 'recorded' or 'changed'.

    'changed' means a new download differs from the committed manifest hash: the new file is
    kept on disk, the manifest is left alone, and verify_data() will fail until refreshed.

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
        if previous and not refresh and previous["sha256"] != manifest.sha256(raw.path):
            return "changed"

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
    """Fetch every registered file; raise if any source changed since the manifest."""
    results = {raw.path.relative_to(DATA_RAW).as_posix(): fetch(raw, refresh) for raw in REGISTRY}
    changed = [key for key, status in results.items() if status == "changed"]
    if changed:
        raise manifest.DataVerificationError(
            "These sources changed since data/MANIFEST.yaml was written: "
            + ", ".join(changed)
            + ". Review the change, then re-run with refresh to accept it."
        )
    return results
