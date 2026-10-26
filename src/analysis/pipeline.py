"""End-to-end run: fetch -> verify -> clean -> evidence -> report.

Run with: uv run python -m analysis.pipeline [stage]
Stages: fetch, refresh (re-download and accept source updates), verify, all (default).
Clean, evidence and report stages are added in Phase 1.
"""

import argparse

from analysis import manifest, sources
from analysis.config import FIGURES


def fetch(refresh: bool = False) -> None:
    """Download any missing raw files and record them in data/MANIFEST.yaml."""
    for key, status in sources.fetch_all(refresh=refresh).items():
        print(f"{status:>9}  {key}")


def verify() -> None:
    """Re-hash every raw file against the manifest; raises on any mismatch."""
    print(f"Verified {manifest.verify_data()} raw files against data/MANIFEST.yaml.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "stage", nargs="?", default="all", choices=["fetch", "refresh", "verify", "all"]
    )
    stage = parser.parse_args().stage

    FIGURES.mkdir(parents=True, exist_ok=True)
    if stage in ("fetch", "refresh", "all"):
        fetch(refresh=stage == "refresh")
    if stage in ("verify", "all"):
        verify()


if __name__ == "__main__":
    main()
