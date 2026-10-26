"""Phase 1 evidence review: one module per claim, each with run() -> ClaimResult.

Verdicts are mechanical (see verdict_from_share) so no claim is judged case by case.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

HOLDS, PARTIAL, FAILS, NOT_TESTABLE = (
    "Holds",
    "Partially holds",
    "Fails",
    "Not testable with our data",
)


def verdict_from_share(n_true: int, n_total: int) -> str:
    """Holds if true in every case, partially if in more than half, fails otherwise."""
    if n_total == 0:
        return NOT_TESTABLE
    if n_true == n_total:
        return HOLDS
    return PARTIAL if n_true > n_total / 2 else FAILS


@dataclass
class ClaimResult:
    number: int
    claim: str
    verdict: str
    headline: str  # one sentence with the key number, written from computed values
    data: str
    method: str
    findings: list[str]
    caveats: list[str]
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    figures: list[Path] = field(default_factory=list)
