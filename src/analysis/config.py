"""Project paths and settings. Import from here rather than hardcoding paths."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_EXTERNAL = ROOT / "data" / "external"
DATA_PROCESSED = ROOT / "data" / "processed"
REFERENCE = ROOT / "reference"  # committed, hand-researched inputs
FIGURES = ROOT / "reports" / "figures"
MANIFEST = ROOT / "data" / "MANIFEST.yaml"  # committed: provenance and hashes of data/raw

load_dotenv(ROOT / ".env")

# Source line for every figure or table derived from JST data. Share-alike: such outputs carry
# the source licence, so the caption states it, not only the README.
JST_CREDIT = (
    "Source: Jordà-Schularick-Taylor Macrohistory Database (R6, consulted 2026-10-26); "
    "Jordà et al. (2019), QJE. Licensed CC BY-NC-SA 4.0."
)

# Bootstrap settings: fixed seed so every run reproduces the same numbers.
RANDOM_SEED = 20261027
BOOTSTRAP_REPS = 2000

TRADING_DAYS = 252
# Trading costs come from analysis.costs and reference/trading_costs.csv (no flat fallback).


def get_secret(name: str) -> str:
    """Return an API key from the environment, failing clearly if it's missing."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and add it.")
    return value
