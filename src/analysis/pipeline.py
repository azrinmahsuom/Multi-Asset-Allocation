"""End-to-end run: fetch -> verify -> clean -> evidence -> design -> backtest -> headline.

Run with: uv run python -m analysis.pipeline [stage]
Stages: fetch, refresh (re-download and accept source updates), verify, clean, evidence,
design, backtest, headline, all (default).

Live sources update over time. A download that differs from the committed snapshot
(data/MANIFEST.yaml) is reported as "changed since snapshot" and the run continues; the
headline stage then writes data/processed/drift_report.md with the effect on the headline
figures. Only a missing file stops the run.
"""

import argparse

from analysis import clean, documents, headline, manifest, report, sources
from analysis.backtest import report as backtest_report
from analysis.config import FIGURES
from analysis.design import report as design_report


def fetch(refresh: bool = False) -> None:
    """Download any missing raw files and record them in data/MANIFEST.yaml."""
    manual = []
    for key, status in sources.fetch_all(refresh=refresh).items():
        if status.startswith("manual step needed"):
            manual.append(status)
            continue
        label = "changed since snapshot" if status == "changed" else status
        print(f"{label:>9}  {key}")
    if manual:
        raise SystemExit(
            "\nOne manual step before the run can continue:\n  "
            + "\n  ".join(manual)
            + "\nThen run `make all` again; files already downloaded are kept."
        )


def verify() -> None:
    """Check raw files against the snapshot hashes and reference/ against the documents.

    Missing files stop the run. Files changed since the snapshot, and reference values that
    differ from a newer document, are reported and the run continues."""
    status = manifest.data_status()
    if status["missing"]:
        raise manifest.DataVerificationError(
            "Missing raw files (run the fetch step): " + ", ".join(status["missing"])
        )
    print(f"Verified {len(status['ok'])} raw files against data/MANIFEST.yaml.")
    for key in status["changed"]:
        print(f"  changed since snapshot: {key}")
    try:
        documents.verify_reference()
        print("Verified reference/ figures against the fund and tax documents.")
    except Exception as err:  # a newer document can move or reformat a figure
        print(f"  reference/ not confirmed against the current documents: {err}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    stages = [
        "fetch",
        "refresh",
        "verify",
        "clean",
        "evidence",
        "design",
        "backtest",
        "headline",
        "all",
    ]
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
    if stage in ("backtest", "all"):
        backtest_report.run()
        print("Wrote docs/backtest_results.md.")
    if stage in ("headline", "all"):
        changed, diffs = headline.run()
        if changed:
            print(
                f"{len(changed)} sources changed since snapshot; {len(diffs)} headline figures "
                f"moved. See {headline.DRIFT_REPORT.relative_to(headline.ROOT)}."
            )
        else:
            print(f"Wrote {headline.SNAPSHOT.relative_to(headline.ROOT)} (no data drift).")


if __name__ == "__main__":
    main()
