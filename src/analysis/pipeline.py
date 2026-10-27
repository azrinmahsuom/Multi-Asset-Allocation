"""End-to-end run: fetch -> verify -> clean -> evidence -> report.

Run with: uv run python -m analysis.pipeline [stage]
Stages: fetch, refresh (re-download and accept source updates), verify, clean, evidence,
design, all (default).
"""

import argparse

from analysis import clean, manifest, report, sources
from analysis.config import FIGURES
from analysis.design import report as design_report


def fetch(refresh: bool = False) -> None:
    """Download any missing raw files and record them in data/MANIFEST.yaml."""
    for key, status in sources.fetch_all(refresh=refresh).items():
        print(f"{status:>9}  {key}")


def verify() -> None:
    """Re-hash every raw file against the manifest; raises on any mismatch."""
    print(f"Verified {manifest.verify_data()} raw files against data/MANIFEST.yaml.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    stages = ["fetch", "refresh", "verify", "clean", "evidence", "design", "all"]
    parser.add_argument("stage", nargs="?", default="all", choices=stages)
    stage = parser.parse_args().stage

    FIGURES.mkdir(parents=True, exist_ok=True)
    if stage in ("fetch", "refresh", "all"):
        fetch(refresh=stage == "refresh")
    if stage in ("verify", "all"):
        verify()
    if stage in ("clean", "all"):
        tables = clean.run()
        print(f"Wrote {len(tables)} processed tables to data/processed/.")
    if stage in ("evidence", "all"):
        results = report.run()
        print(f"Wrote docs/evidence_review.md ({len(results)} claims).")
    if stage in ("design", "all"):
        design_report.run()
        print("Wrote docs/strategy_design.md.")


if __name__ == "__main__":
    main()
