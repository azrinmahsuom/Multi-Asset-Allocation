"""Write docs/strategy_design.md from the design modules. Every number comes from code."""

import pandas as pd

from analysis.config import ROOT
from analysis.design import allocation, bond_options, profiles, universe
from analysis.report import _table_markdown

OUTPUT = ROOT / "docs" / "strategy_design.md"


def _profiles_section() -> list[str]:
    table = pd.DataFrame(
        {
            "Horizon": [p.horizon for p in profiles.PROFILES],
            "Purpose": [p.purpose for p in profiles.PROFILES],
            "Risk-capacity limits": [profiles.describe(p) for p in profiles.PROFILES],
        },
        index=pd.Index([p.name for p in profiles.PROFILES], name="Profile"),
    )
    return [
        "## Investor framing and horizon profiles",
        "",
        "Spending money for near-term needs sits outside the strategy; its size is left to the "
        "investor. Minimum allocation USD 25,000; daily-tradable ETFs only. Profiles are defined "
        "by risk capacity. Limits set by the owner on 2026-10-27 and tested on real SGD monthly "
        "returns from 1998 (owner decisions, 2026-10-27). A GDP-weighted global JST portfolio "
        "(1871–2020) is reported as a stress scenario: on it no allocation, cash included, "
        "meets the limits, because of the world wars.",
        "",
        _table_markdown(table),
        "",
        "Selection rule: for each profile, the allocation with the highest expected real return "
        "that meets all of its limits.",
        "",
    ]


def _bond_section(r: dict) -> list[str]:
    lo, hi = r["vol_diff_ci"]
    long_winner = r["long"]["average_rank"].astype(float).idxmin()
    agree = long_winner == r["winner"]
    m_lo, m_hi = r["sgs_maturity_main"]
    return [
        "## Bond sleeve: SGS vs global hedged vs global unhedged",
        "",
        "Rules fixed before computing (`analysis.design.bond_options`): three options at matched "
        "duration; 60% global equities unhedged in SGD plus 40% bond option, monthly, before "
        "costs; ranked on portfolio volatility, maximum drawdown and mean return in the worst "
        "10% of equity months, all in SGD; lowest average rank in the main layer wins.",
        "",
        f"**Main layer, same fund ({r['main_period']}).** Global government bonds: iShares "
        "Global Govt Bond UCITS ETF, unhedged (IGLO.L) and USD-hedged (SGLU.AS) classes. SGS "
        f"matched to the fund's published effective duration of {r['target_duration']:.2f} years "
        f"(SGS maturity {m_lo:.1f}–{m_hi:.1f} years).",
        "",
        _table_markdown(r["main"]),
        "",
        f"**Long layer ({r['long_period']}).** US 10-year Treasury as the global stand-in; SGS "
        "matched to its duration each month.",
        "",
        _table_markdown(r["long"]),
        "",
        f"![Bond options](../{r['figure'].relative_to(ROOT).as_posix()})",
        "",
        f"**Rule outcome: {r['winner']}.** Its portfolio-volatility difference from the runner-up "
        f"({r['runner_up']}) has a 95% interval of {lo:+.2%} to {hi:+.2%}"
        + (" (includes zero)" if lo <= 0 <= hi else "")
        + ". The long layer ranks "
        + (f"{long_winner} first as well." if agree else f"{long_winner} first, the opposite.")
        + " Sensitivity of the main-layer winner to the SGS duration: "
        + "; ".join(f"{d:.1f} years: {w}" for d, w in r["sensitivity"].items())
        + ".",
        "",
        "**Decision (owner, 2026-10-27): follow the rule; the bond sleeve is SGS, logged as low "
        "confidence.** Phase 3 also backtests the global-unhedged sleeve to show how much the "
        "choice matters.",
        "",
        "Caveats: the main layer is about seven years and includes 2022; the global fund's "
        "duration is a current published figure (status to_verify in "
        "`reference/bond_durations.csv`); SGS returns are built from benchmark yields, not a "
        "traded index; hedges assume covered interest parity; the long layer uses US Treasuries, "
        "not global bonds.",
        "",
    ]


def _universe_section(u: dict) -> list[str]:
    t = u["table"]
    full, floating = u["gold_long"]["full"], u["gold_long"]["floating"]
    included = [k for k, v in t["included"].items() if v]
    excluded = [k for k, v in t["included"].items() if not v]
    return [
        "## Asset universe",
        "",
        "Rules fixed before computing (`analysis.design.universe`): core = global equities "
        "(unhedged in SGD) + the SGS sleeve; cash is always available. A candidate joins if its "
        "spanning alpha over the core has HAC t > 2, or if it beats a core 60/40 in "
        "high-inflation months known at the time (Singapore CPI) with HAC t > 2, and it must have "
        "an economic source of expected return (cash flows or indexation). Fixed-income "
        f"candidates are hedged to SGD; real assets are unhedged. Sample {u['period']}, monthly, "
        "SGD.",
        "",
        _table_markdown(t),
        "",
        f"![Asset universe tests](../{u['figure'].relative_to(ROOT).as_posix()})",
        "",
        f"**Included by the rule: {', '.join(included) or 'none'}. Excluded: "
        f"{', '.join(excluded) or 'none'}.**",
        "",
        "Gold robustness (annual, Damodaran, against US stocks and 10-year Treasuries): "
        f"{full['period']} alpha {full['alpha']:+.1%} a year (t = {full['alpha_t']:.1f}); "
        f"{floating['period']}, after the end of fixed gold prices, {floating['alpha']:+.1%} "
        f"(t = {floating['alpha_t']:.1f}), real return {floating['gold_real_return']:.1%} a year. "
        "Same direction as the monthly result but not significant at annual frequency. With five "
        "candidates tested, a stricter threshold of about t > 2.33 (one-sided 5% divided by 5) "
        "is reported for reference.",
        "",
        "Roles and sources of expected return:",
        "",
        "- Global equities: growth; the equity risk premium (claim 1).",
        "- SGS: risk reduction in SGD; term premium and income (claims 5, 6; bond-sleeve test).",
        "- Cash (SGD one-month rate): liquidity; the short profile's anchor.",
        "- Gold: excluded. It passed the spanning test, but has no economic source of expected "
        "return (no cash flows); the return-source condition was added after the first results, "
        "at the owner's direction, because the spec requires it (docs/decisions.md).",
        "- Excluded classes and the evidence: investment-grade credit (claim 7: equity-like risk, "
        "premium not reliable after defaults), inflation-linked bonds (claim 8: real-yield moves "
        "dominate over one-year horizons), REITs (claim 9: no return added at equal risk), "
        "commodities (failed both tests).",
        "",
    ]


def _allocation_section(al: dict) -> list[str]:
    t = al["table"].copy()
    cols = [
        "profile",
        "method",
        "share_in_risky_mix",
        "w_equity",
        "w_bonds",
        "w_cash",
        "expected_real_return",
        "worst_window_sgd",
        "max_drawdown_sgd",
        "sgd_real_return",
        "sgd_volatility",
        "meets_limits",
        "worst_window_global",
        "max_drawdown_global",
        "global_stress_passes",
    ]
    sel = al["selected"]
    lines = [
        "## Allocation methods and selection",
        "",
        "Rules fixed before computing (`analysis.design.allocation`): five methods give risky "
        "weights over global equities and SGS; each profile holds the largest share of that mix "
        "(rest in SGD cash) that meets its limits on real SGD history "
        f"({al['sgd_period']}); expected real return is the long-run real return of a "
        f"GDP-weighted global portfolio of the JST countries ({al['global_years']}, real USD, "
        "bonds hedged), which is also reported as a stress scenario; per profile the highest "
        "expected real return wins. Estimated methods use "
        f"monthly SGD data ({al['monthly_period']}).",
        "",
        "**Selected:** " + "; ".join(f"{k}: {v}" for k, v in sel.items()) + ".",
        "",
        _table_markdown(t[cols].set_index("profile")),
        "",
        f"![Allocation methods](../{al['figure'].relative_to(ROOT).as_posix()})",
        "",
        "Weight sensitivity (5th–95th percentile over 2,000 moving-block bootstrap resamples of "
        "the monthly data):",
        "",
        _table_markdown(al["bootstrap_ranges"]),
        "",
        "Glide-path equity weight, interquartile range across JST countries: "
        + "; ".join(f"{p}: {al['risky_weights'].loc[(p, 'Glide path IQR'), 'equity']}" for p in sel)
        + ".",
        "",
        "Caveats: SGD cash lost purchasing power in parts of the sample, so mixing a risky "
        "portfolio with cash does not always reduce real risk; methods that failed a limit at "
        "full weight ended at all cash, which can fail too (shown as not meeting limits). The "
        "SGD history is about 28 years without an SGD inflation crisis. The global stress "
        "columns show the same allocations on 1871–2020: every allocation, cash included, fails "
        "the limits there because of the First World War and 1940s inflation (global bonds "
        "-43% real over the five years to 1920). Mean-variance weights are unstable across "
        "resamples.",
        "",
    ]
    return lines


def run() -> dict:
    r = bond_options.run()
    u = universe.run()
    al = allocation.run()
    text = "\n".join(
        [
            "# Strategy design",
            "",
            "Generated by `uv run python -m analysis.pipeline design`; do not edit by hand. "
            "Decisions and their reasons are logged in `docs/decisions.md`.",
            "",
            *_profiles_section(),
            *_bond_section(r),
            *_universe_section(u),
            *_allocation_section(al),
        ]
    )
    OUTPUT.write_text(text)
    return r
