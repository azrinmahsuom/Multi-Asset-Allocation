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
    if bad:
        raise ValueError(f"reference/ differs from fund documents (reference, document): {bad}")
    return got
