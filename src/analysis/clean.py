"""Raw files -> tidy, analysis-ready tables in data/processed/.

Conventions:
- Returns are simple decimals per period (0.01 = 1%).
- Monthly tables are indexed by month ("YYYY-MM"), annual tables by year.
- Column names state what the series is: <market>_<asset>_<tr|price>_<nominal|real>_<ccy>.
- A period whose data is incomplete or estimated by the source is dropped, never filled.
"""

import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import metrics, prices, sources
from analysis.config import DATA_PROCESSED, DATA_RAW

# Shown in every Nareit-derived file name: those outputs must stay in data/processed.
PRIVATE_PREFIX = "private_"


def _save(df: pd.DataFrame, name: str) -> pd.DataFrame:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA_PROCESSED / f"{name}.csv")
    return df


def _shiller_month(value: float) -> pd.Period:
    """Shiller dates are year.month floats where 1871.1 means October: format to 2 dp."""
    year, month = f"{value:.2f}".split(".")
    return pd.Period(f"{year}-{month}", freq="M")


def shiller_monthly(path: Path = DATA_RAW / "shiller" / "ie_data.xls") -> pd.DataFrame:
    """US stocks (S&P Composite) and 10-year Treasuries, monthly, from 1871.

    Equity total return: (P_t + D_t / 12) / P_{t-1} - 1, with D the annualised dividend.
    Bond total return: Shiller's "Monthly Total Bond Returns" column minus 1.
    Rule: stop at the last month with a reported dividend; later months use estimated
    inputs (the file notes estimated CPI and intra-month prices).
    """
    raw = pd.read_excel(path, sheet_name="Data", header=7)
    raw = raw[pd.to_numeric(raw["Date"], errors="coerce").notna()].copy()
    raw.index = pd.PeriodIndex([_shiller_month(d) for d in raw["Date"]], name="month")
    raw = raw.loc[: raw["D"].last_valid_index()]

    price, dividend = raw["P"].astype(float), raw["D"].astype(float)
    out = pd.DataFrame(index=raw.index)
    out["us_eq_tr_nominal_usd"] = (price + dividend / 12) / price.shift(1) - 1
    out["us_eq_price_nominal_usd"] = price / price.shift(1) - 1
    out["us_gov10_tr_nominal_usd"] = raw.iloc[:, 17].astype(float) - 1
    out["us_cpi_inflation"] = raw["CPI"].astype(float).pct_change()
    out["us_gov10_yield"] = raw["Rate GS10"].astype(float) / 100
    return out.iloc[1:]


def french_market(path: Path, date_digits: int, market: str = "us") -> pd.DataFrame:
    """Value-weighted market total return and the 1-month US T-bill, from a French file.

    Market total return = (Mkt-RF + RF) / 100. Only the first table (monthly or daily) is read.
    French marks missing values as -99.99; those become missing.
    """
    rows = []
    for line in _french_csv_text(path).splitlines():
        match = re.match(rf"\s*(\d{{{date_digits}}})\s*,(.*)", line)
        if match:
            rows.append([match.group(1), *[float(x) for x in match.group(2).split(",")]])
        elif rows and line.strip() and not line.strip()[0].isdigit():
            break
    df = pd.DataFrame(rows, columns=["date", "mkt_rf", "smb", "hml", "rf"]).replace(-99.99, np.nan)
    if date_digits == 6:
        df.index = pd.PeriodIndex(pd.to_datetime(df["date"], format="%Y%m"), freq="M", name="month")
    else:
        df.index = pd.DatetimeIndex(pd.to_datetime(df["date"], format="%Y%m%d"), name="date")
    out = pd.DataFrame(index=df.index)
    out[f"{market}_eq_tr_nominal_usd"] = (df["mkt_rf"] + df["rf"]) / 100
    out["us_bill1m_tr_nominal_usd"] = df["rf"] / 100
    return out


def _french_csv_text(path: Path) -> str:
    """Text of the single CSV inside a French zip."""
    with zipfile.ZipFile(path) as zf:
        return zf.read(zf.namelist()[0]).decode("latin-1")


DAMODARAN_COLUMNS = {
    1: "us_eq_tr_nominal_usd",  # S&P 500 incl. dividends
    2: "us_smallcap_tr_nominal_usd",
    3: "us_bill3m_tr_nominal_usd",
    4: "us_gov10_tr_nominal_usd",
    5: "us_baa_tr_nominal_usd",
    6: "us_housing_price_nominal_usd",  # home prices only, no rent: housing, not REITs
    7: "gold_price_nominal_usd",
    20: "us_cpi_inflation",
}


def damodaran_annual(path: Path = DATA_RAW / "damodaran" / "histretSP.xls") -> pd.DataFrame:
    """US annual returns, 1928 onwards, from the 'Returns by year' sheet."""
    raw = pd.read_excel(path, sheet_name="Returns by year", header=None)
    header = raw.index[raw[0] == "Year"][0]
    body = raw.loc[header + 1 :]
    years = pd.to_numeric(body[0], errors="coerce")
    body = body[(years > 1800) & (years < 2200)]
    out = body[list(DAMODARAN_COLUMNS)].astype(float)
    out.columns = list(DAMODARAN_COLUMNS.values())
    out.index = pd.Index(body[0].astype(int), name="year")
    return out


JST_COLUMNS = [
    "eq_tr",
    "bond_tr",
    "bill_rate",
    "housing_tr",
    "housing_capgain",
    "eq_capgain",
    "cpi",
    "xrusd",
    "gdp",
]


def jst_annual(path: Path = DATA_RAW / "jst" / "JSTdataset.xlsx") -> pd.DataFrame:
    """Country-year panel of nominal local-currency total returns, plus inflation.

    JST returns are already decimals. inflation is the change in each country's CPI.
    """
    raw = pd.read_excel(path, usecols=["year", "country", "iso", *JST_COLUMNS])
    raw = raw.sort_values(["country", "year"])
    raw["inflation"] = raw.groupby("country")["cpi"].pct_change()
    return raw.set_index(["country", "year"])


def fred_monthly(series: list[str] | None = None) -> pd.DataFrame:
    """FRED monthly series side by side, in FRED's units (% p.a. for yields)."""
    series = series or [k for k, v in sources.FRED_SERIES.items() if v[1].startswith("Monthly")]
    frames = []
    for series_id in series:
        df = pd.read_csv(DATA_RAW / "fred" / f"{series_id}.csv", index_col=0, parse_dates=True)
        df.index = df.index.to_period("M")
        frames.append(pd.to_numeric(df.iloc[:, 0], errors="coerce").rename(series_id))
    out = pd.concat(frames, axis=1).sort_index()
    out.index.name = "month"
    for cpi in [c for c in CPI_SERIES if c in out.columns]:
        out[cpi], out[f"{cpi}_interpolated"] = fill_single_month_gaps(out[cpi])
    return out


CPI_SERIES = ["CPIAUCSL", "CPIAUCNS"]


def fill_single_month_gaps(index_level: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Fill isolated one-month gaps inside a price index by geometric interpolation.

    Rule: only a single missing month between two published months is filled (e.g. October
    2025 US CPI, not published by BLS); longer gaps stay missing. Returns the filled series
    and a flag marking the filled months.
    """
    missing = index_level.isna()
    isolated = missing & index_level.shift(1).notna() & index_level.shift(-1).notna()
    filled = np.exp(np.log(index_level).interpolate(limit=1, limit_area="inside"))
    filled = index_level.where(~isolated, filled)
    return filled, isolated


TREASURY_MATURITIES = {"DGS1": 1, "DGS5": 5, "DGS10": 10, "DGS30": 30}


def fred_month_end(series: list[str], scale: float = 100) -> pd.DataFrame:
    """Last daily observation of each complete month, divided by scale (yields: % -> decimal)."""
    frames = []
    for series_id in series:
        df = pd.read_csv(DATA_RAW / "fred" / f"{series_id}.csv", index_col=0, parse_dates=True)
        daily = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna() / scale
        month_end = daily.groupby(daily.index.to_period("M")).last()
        if not _month_complete(daily.index[-1]):
            month_end = month_end.iloc[:-1]
        frames.append(month_end.rename(series_id))
    out = pd.concat(frames, axis=1).sort_index()
    out.index.name = "month"
    return out


def usdsgd_month_end() -> pd.DataFrame:
    """Month-end SGD per USD (FRED DEXSIUS) and its monthly change (USD vs SGD)."""
    rate = fred_month_end(["DEXSIUS"], scale=1)["DEXSIUS"]
    return pd.DataFrame({"sgd_per_usd": rate, "usd_vs_sgd_change": rate.pct_change()})


def us_treasury_monthly() -> pd.DataFrame:
    """Monthly total returns of constant-maturity US Treasuries built from month-end yields.

    Each month: a par bond bought at last month-end's yield, priced at this month-end's
    yield (metrics.par_bond_return). Also returns the month-end yields themselves.
    """
    yields = fred_month_end([*TREASURY_MATURITIES, "DFII10"])
    out = pd.DataFrame(index=yields.index)
    for series_id, maturity in TREASURY_MATURITIES.items():
        y = yields[series_id]
        out[f"us_gov{maturity}_tr_nominal_usd"] = metrics.par_bond_return(y.shift(1), y, maturity)
    for column in yields.columns:
        out[f"{column.lower()}_yield"] = yields[column]
    return out.iloc[1:]


def sg_cpi_monthly(path: Path = DATA_RAW / "singstat" / "M213751_cpi_monthly.json") -> pd.DataFrame:
    """Singapore CPI all-items index (NSA) and its monthly change."""
    rows = json.loads(path.read_text())["Data"]["row"]
    all_items = next(r for r in rows if r["rowText"].strip().lower() == "all items")
    index = pd.Series(
        {
            pd.Period(pd.to_datetime(c["key"], format="%Y %b"), freq="M"): float(c["value"])
            for c in all_items["columns"]
        }
    ).sort_index()
    index.index.name = "month"
    return pd.DataFrame({"sg_cpi": index, "sg_inflation_month": index.pct_change()})


SGS_FILE = DATA_RAW / "mas" / "sgs_benchmark_yields.csv"


def sgs_month_end_yields(path: Path = SGS_FILE) -> pd.DataFrame:
    """Month-end SGS benchmark yields (decimals) by tenor in years, last observation per month.

    The final month is dropped if incomplete (same 3-day rule as other daily series).
    """
    rows, tenors, year, month = [], None, None, None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if tenors is None and len(parts) > 3 and "Bond Yield" in line:
            tenors = [int(re.search(r"(\d+)-Year", p).group(1)) for p in parts[3:] if p]
            continue
        if tenors is None or len(parts) < 4 or not parts[2].isdigit():
            continue
        year, month = parts[0] or year, parts[1] or month
        date = pd.to_datetime(f"{year} {month} {parts[2]}", format="%Y %b %d")
        cells = parts[3 : 3 + len(tenors)]
        values = [float(v) / 100 if v not in ("", "-") else np.nan for v in cells]
        rows.append([date, *values])
    daily = pd.DataFrame(rows, columns=["date", *tenors]).set_index("date").sort_index()
    month_end = daily.groupby(daily.index.to_period("M")).last()
    if not _month_complete(daily.index[-1]):
        month_end = month_end.iloc[:-1]
    month_end.index.name = "month"
    month_end.columns = [f"sgs_{t}y" for t in tenors]
    return month_end


def mas_tables(path: Path = DATA_RAW / "mas" / "domestic_interest_rates.csv") -> list[pd.DataFrame]:
    """Every table in the MAS CSV as a daily DataFrame of floats ('-' becomes missing).

    A table starts at a header line whose text differs from the current one; the file
    repeats the same header every year inside a table.
    """
    tables, header, rows, year, month = [], None, [], None, None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if parts[0].startswith(("End of Period", "SORA Value Date")):
            names = [p for p in parts[3:] if p]
            if names != header:
                if rows:
                    tables.append(_mas_frame(rows, header))
                header, rows = names, []
            continue
        if len(parts) < 4 or not parts[2].isdigit() or header is None:
            continue
        year, month = parts[0] or year, parts[1] or month
        date = pd.to_datetime(f"{year} {month} {parts[2]}", format="%Y %b %d")
        rows.append([date, *parts[3 : 3 + len(header)]])
    if rows:
        tables.append(_mas_frame(rows, header))
    return tables


def _mas_frame(rows: list[list], header: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["date", *header]).set_index("date")
    return df.apply(pd.to_numeric, errors="coerce")


def sgd_risk_free_monthly(tables: list[pd.DataFrame] | None = None) -> pd.DataFrame:
    """Monthly SGD risk-free return under the rule in docs/decisions.md (Risk-free rate).

    - From the first full month of SORA Index data: index(last value date of month) /
      index(last value date of previous month) - 1.
    - Before that: the interbank overnight rate compounded over the month (ACT/365, each
      quote applying until the next one), the same realised overnight cash return as SORA.
    Also returns both legs separately so their overlap can be compared.
    """
    tables = tables or mas_tables()
    overnight = next(t for t in tables if "Interbank Overnight" in t.columns)
    overnight = overnight["Interbank Overnight"].dropna()

    days = overnight.index.to_series().diff().shift(-1).dt.days.fillna(1)
    growth = 1 + overnight / 100 * days / 365
    overnight_leg = growth.groupby(overnight.index.to_period("M")).prod() - 1

    sora_index = next(t for t in tables if "SORA Index" in t.columns)["SORA Index"]
    index_eom = sora_index.dropna().groupby(sora_index.dropna().index.to_period("M")).last()
    if not _month_complete(sora_index.dropna().index[-1]):
        index_eom = index_eom.iloc[:-1]
    sora_leg = index_eom.pct_change()
    first_full_month = index_eom.index[0] + 1
    sora_leg = sora_leg.loc[first_full_month:]

    out = pd.DataFrame({"overnight_leg": overnight_leg, "sora_index_leg": sora_leg})
    out["sgd_rf_tr_nominal_sgd"] = out["sora_index_leg"].where(
        out.index >= first_full_month, out["overnight_leg"]
    )
    out.index.name = "month"
    return out.dropna(subset=["sgd_rf_tr_nominal_sgd"])


def _month_complete(last_day: pd.Timestamp) -> bool:
    """True if last_day is within 3 calendar days of its month's last business day, and that
    business day is not still in the future (a month in progress is never complete)."""
    month_end = (last_day + pd.offsets.BMonthEnd(0)).normalize()
    if month_end > pd.Timestamp.today().normalize():
        return False
    return (month_end - last_day.normalize()).days <= 3


def complete_months(daily: pd.Series) -> pd.Series:
    """Monthly returns from month-end levels of the compounded daily returns.

    Rules: the first month is dropped (it has no prior month-end, so it would cover only part
    of the month); the last month is kept only if its last observation is within 3 calendar
    days of that month's last business day.
    """
    level = (1 + daily).cumprod()
    monthly = level.groupby(level.index.to_period("M")).last().pct_change().iloc[1:]
    if not _month_complete(daily.index[-1]):
        monthly = monthly.iloc[:-1]
    monthly.index.name = "month"
    return monthly


DUPLICATE_DISTRIBUTION_DAYS = 7


def drop_duplicate_distributions(
    dividend: pd.Series, max_gap_days: int = DUPLICATE_DISTRIBUTION_DAYS
) -> pd.Series:
    """Remove repeated records of one distribution: a non-zero amount equal to the previous
    non-zero amount and dated within max_gap_days of it (e.g. A35.SI's January 2025
    distribution appears on 2 and 3 January in the Yahoo data). Real distributions are at
    least about a month apart."""
    out = dividend.copy()
    paid = dividend[dividend.fillna(0) > 0]
    prev_date, prev_amount = None, None
    for date, amount in paid.items():
        if (
            prev_date is not None
            and amount == prev_amount
            and (pd.Timestamp(date) - pd.Timestamp(prev_date)).days <= max_gap_days
        ):
            out.loc[date] = 0.0
            continue
        prev_date, prev_amount = date, amount
    return out


def etf_monthly() -> pd.DataFrame:
    """Monthly total returns (close + distributions) of each ETF, trading currency."""
    columns = {}
    for ticker, (_label, currency) in sources.ETFS.items():
        df = prices.PRICE_SOURCE.read(DATA_RAW / prices.PRICE_SOURCE.name / f"{ticker}.csv")
        df = df[df["close"].notna()]
        dividend = drop_duplicate_distributions(df["dividend"])
        daily = metrics.total_returns_from_distributions(df["close"], dividend)
        columns[f"{ticker}_tr_nominal_{currency.lower()}"] = complete_months(daily)
    return pd.DataFrame(columns)


def nareit_monthly(
    path: Path = DATA_RAW / "nareit" / "MonthlyHistoricalReturns.xls",
) -> pd.DataFrame:
    """PRIVATE: FTSE Nareit All Equity REITs total and price return, monthly, from 1972.

    Nareit's terms forbid public display or derivative works, so this is used only to check
    the ETF series. Saved under a 'private_' name; never write it to reports/ or docs/.
    """
    raw = pd.read_excel(path, sheet_name="Index Data", header=None)
    group = raw.iloc[5].ffill()
    kind = raw.iloc[6].ffill().astype(str) + " " + raw.iloc[7].astype(str)
    total = raw.columns[(group == "All Equity REITs") & (kind == "Total Return")][0]
    price = raw.columns[(group == "All Equity REITs") & (kind == "Price Return")][0]
    dates = pd.to_datetime(raw[0], errors="coerce")
    body = raw[dates.notna()]
    out = pd.DataFrame(
        {
            "us_reit_tr_nominal_usd": body[total].astype(float) / 100,
            "us_reit_price_nominal_usd": body[price].astype(float) / 100,
        }
    )
    out.index = pd.PeriodIndex(dates[dates.notna()], freq="M", name="month")
    return out.dropna()


def run() -> dict[str, pd.DataFrame]:
    """Build and save every processed table."""
    raw = DATA_RAW / "french"
    return {
        "us_monthly_shiller": _save(shiller_monthly(), "us_monthly_shiller"),
        "us_monthly_french": _save(
            french_market(raw / "F-F_Research_Data_Factors_CSV.zip", 6), "us_monthly_french"
        ),
        "developed_monthly_french": _save(
            french_market(raw / "Developed_3_Factors_CSV.zip", 6, market="developed"),
            "developed_monthly_french",
        ),
        "usdsgd_month_end": _save(usdsgd_month_end(), "usdsgd_month_end"),
        "us_daily_french": _save(
            french_market(raw / "F-F_Research_Data_Factors_daily_CSV.zip", 8), "us_daily_french"
        ),
        "us_annual_damodaran": _save(damodaran_annual(), "us_annual_damodaran"),
        "jst_annual": _save(jst_annual(), "jst_annual"),
        "fred_monthly": _save(fred_monthly(), "fred_monthly"),
        "us_treasury_monthly": _save(us_treasury_monthly(), "us_treasury_monthly"),
        "sgd_rf_monthly": _save(sgd_risk_free_monthly(), "sgd_rf_monthly"),
        "sg_cpi_monthly": _save(sg_cpi_monthly(), "sg_cpi_monthly"),
        "sgs_month_end_yields": _save(sgs_month_end_yields(), "sgs_month_end_yields"),
        "etf_monthly": _save(etf_monthly(), "etf_monthly"),
        "us_reit_nareit": _save(nareit_monthly(), PRIVATE_PREFIX + "us_reit_nareit_monthly"),
    }
