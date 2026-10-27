"""Headline figures and the drift report.

reports/headline_figures.json (committed) is the snapshot of the README's headline figures
at the committed data. Each full run recomputes them. If any raw file differs from its
manifest hash (a live source updated since the snapshot), the snapshot is kept and
data/processed/drift_report.md lists the changed sources and every headline figure that
moved, so a fresh download reports drift instead of failing. With no data change, the
snapshot is rewritten (identical on a cache rebuild; a code change shows in git diff).
"""

import json
from pathlib import Path

import pandas as pd

from analysis import manifest
from analysis.backtest import engine
from analysis.backtest import report as backtest_report
from analysis.config import DATA_PROCESSED, ROOT
from analysis.design import holdout, profiles

SNAPSHOT = ROOT / "reports" / "headline_figures.json"
DRIFT_REPORT = DATA_PROCESSED / "drift_report.md"
DECIMALS = 4


def _round(value: float) -> float:
    return round(float(value), DECIMALS)


def compute() -> dict[str, float]:
    """The README's headline figures, keyed by a readable name."""
    out: dict[str, float] = {}
    frontier = engine.risk_frontier()
    menu = holdout.risk_menu(frontier)
    for p in profiles.PROFILES:
        for tol in holdout.DRAWDOWN_TOLERANCES:
            row = menu.loc[(p.name, f"{tol:.0%}")]
            key = f"menu {p.name.lower()} {tol:.0%}"
            met = row["result"] == "meets tolerance"
            out[f"{key}: equity share"] = _round(row["equity_share"]) if met else -1.0
            if met:
                out[f"{key}: P(real loss)"] = _round(row["p_loss_holdout"])
    sgd = frontier[frontier["profile"] == profiles.PROFILES[0].name]
    for tol in holdout.DRAWDOWN_TOLERANCES:
        ok = sgd[sgd["max_drawdown_sgd"] >= tol]
        out[f"SGD-era sensitivity {tol:.0%}: equity share"] = (
            _round(ok["equity_share"].max()) if len(ok) else -1.0
        )
    weights = {**engine.strategy_weights(), **engine.benchmark_weights()}
    for layer_name, layer in (("index", engine.index_layer()), ("ETF", engine.etf_layer())):
        for name, w in weights.items():
            s = engine.summarise(engine.simulate(layer, w), layer)
            for metric in ("real_annual_return", "volatility", "max_drawdown"):
                out[f"{layer_name} layer {name}: {metric}"] = _round(s[metric])
    table, _, wht = backtest_report.implementation_table()
    for name, r in table.iterrows():
        out[f"implementation {name}: all-in bps a year"] = round(float(r["all_in_annual_bps"]), 2)
    out["ISAC effective withholding rate"] = _round(wht)
    return out


def load_snapshot(path: Path = SNAPSHOT) -> dict[str, float]:
    return json.loads(path.read_text()) if path.exists() else {}


def compare(snapshot: dict[str, float], now: dict[str, float]) -> pd.DataFrame:
    """Every headline figure that is new, gone or different from the snapshot."""
    rows = []
    for key in sorted(set(snapshot) | set(now)):
        old, new = snapshot.get(key), now.get(key)
        if old != new:
            change = new - old if old is not None and new is not None else None
            rows.append({"figure": key, "snapshot": old, "now": new, "change": change})
    return pd.DataFrame(rows, columns=["figure", "snapshot", "now", "change"])


def drift_report(changed_sources: list[str], diffs: pd.DataFrame) -> str:
    lines = [
        "# Drift report",
        "",
        "Written by `uv run python -m analysis.pipeline` when the data differ from the committed "
        "snapshot (data/MANIFEST.yaml and reports/headline_figures.json). Not committed.",
        "",
        "## Sources changed since snapshot",
        "",
        *(f"- {k}" for k in changed_sources),
        *(["- none"] if not changed_sources else []),
        "",
        "## Effect on headline figures",
        "",
    ]
    if diffs.empty:
        lines.append("No headline figure changed.")
    else:
        lines += ["| Figure | Snapshot | Now | Change |", "|---|---|---|---|"]
        for r in diffs.itertuples():
            change = "" if r.change is None or pd.isna(r.change) else f"{r.change:+.4f}"
            old = "absent" if pd.isna(r.snapshot) else r.snapshot
            new = "absent" if pd.isna(r.now) else r.now
            lines.append(f"| {r.figure} | {old} | {new} | {change} |")
    lines += [
        "",
        "Shares and returns are decimals (0.59 = 59%); -1 means no mix meets the tolerance. "
        "To accept the new data as the snapshot: `make refresh`, rerun, and commit the "
        "manifest, the regenerated docs and reports/headline_figures.json.",
    ]
    return "\n".join(lines) + "\n"


def run() -> tuple[list[str], pd.DataFrame]:
    """Recompute the headline figures; return the changed sources and the moved figures."""
    snapshot = load_snapshot()
    now = compute()
    changed = manifest.data_status()["changed"]
    diffs = compare(snapshot, now)
    if changed:
        DRIFT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        DRIFT_REPORT.write_text(drift_report(changed, diffs))
    else:
        SNAPSHOT.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n")
        if DRIFT_REPORT.exists():
            DRIFT_REPORT.unlink()
    return changed, diffs
