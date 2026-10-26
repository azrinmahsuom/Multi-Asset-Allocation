"""Provenance record for data/raw: one MANIFEST.yaml entry per downloaded file.

The manifest is committed; the data is not. verify_data() re-hashes every file so a
silently changed or corrupted download fails loudly instead of changing results.
"""

import hashlib
from pathlib import Path

import yaml

from analysis.config import DATA_RAW, MANIFEST


class DataVerificationError(RuntimeError):
    """Raised when a raw file is missing or its hash differs from the manifest."""


def sha256(path: Path) -> str:
    """SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(manifest_path: Path = MANIFEST) -> dict[str, dict]:
    """Manifest entries keyed by path relative to data/raw (empty if no manifest yet)."""
    if not manifest_path.exists():
        return {}
    content = yaml.safe_load(manifest_path.read_text()) or {}
    return content.get("files", {})


def save(entries: dict[str, dict], manifest_path: Path = MANIFEST) -> None:
    """Write entries to the manifest, sorted by path so diffs stay readable."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Provenance of every file in data/raw. Written by analysis.sources; don't edit by hand.\n"
        "# Raw files are not committed; verify with: uv run python -m analysis.pipeline verify\n"
    )
    body = yaml.safe_dump(
        {"files": dict(sorted(entries.items()))}, sort_keys=False, allow_unicode=True
    )
    manifest_path.write_text(header + body)


def record(
    path: Path, meta: dict, manifest_path: Path = MANIFEST, raw_root: Path = DATA_RAW
) -> dict:
    """Add or replace the manifest entry for one raw file, hashing it now."""
    key = path.relative_to(raw_root).as_posix()
    entry = {**meta, "sha256": sha256(path)}
    entries = load(manifest_path)
    entries[key] = entry
    save(entries, manifest_path)
    return entry


def verify_data(manifest_path: Path = MANIFEST, raw_root: Path = DATA_RAW) -> int:
    """Check every manifest entry against its file; return the count checked.

    Raises DataVerificationError listing every missing or changed file.
    """
    entries = load(manifest_path)
    if not entries:
        raise DataVerificationError(f"{manifest_path} has no entries. Run the fetch step first.")
    problems = []
    for key, entry in entries.items():
        path = raw_root / key
        if not path.exists():
            problems.append(f"missing: {key}")
        elif (actual := sha256(path)) != entry["sha256"]:
            problems.append(
                f"hash mismatch: {key} (manifest {entry['sha256'][:12]}…, file {actual[:12]}…)"
            )
    if problems:
        raise DataVerificationError("Data verification failed:\n  " + "\n  ".join(problems))
    return len(entries)
