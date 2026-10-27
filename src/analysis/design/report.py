"""Write docs/strategy_design.md from the design modules. Every number comes from code."""

import numpy as np
import pandas as pd

from analysis.config import ROOT
from analysis.design import allocation, bond_options, holdout, profiles, universe
from analysis.evidence import claim11_rebalancing, claim12_hedging
from analysis.report import _table_markdown

OUTPUT = ROOT / "docs" / "strategy_design.md"


def _profiles_table(plist) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Horizon": [p.horizon for p in plist],
            "Purpose": [p.purpose for p in plist],
            "Risk-capacity limits": [profiles.describe(p) for p in plist],
        },
        index=pd.Index([p.name for p in plist], name="Profile"),
    )


def _profiles_section() -> list[str]:
    return [
        "## Investor framing and horizon profiles",
        "",
        "Spending money for near-term needs sits outside the strategy; its size is left to the "
        "investor. Minimum allocation USD 25,000; daily-tradable ETFs only. Profiles are defined "
        "by risk capacity and tested on real SGD monthly returns from 1998; a GDP-weighted "
        "global JST portfolio (1871–2020) is a stress scenario.",
        "",
        "**Current limits (v2, set after the v1 holdout, owner-approved 2026-10-27).** All "
        "measures are on real SGD returns over rolling windows of the profile's horizon. The "
        "short profile keeps a drawdown cap; medium and long use horizon measures (chance of a "
        "real loss, worst rolling real return) instead of peak-to-trough caps. Limits loosen "
        "with horizon in cumulative terms; the per-year floors tighten ("
        + ", ".join(
            f"{(1 + p.worst_window_floor) ** (1 / p.window_years) - 1:.1%}"
            for p in profiles.PROFILES
        )
        + " a year), which the owner accepted.",
        "",
        _table_markdown(_profiles_table(profiles.PROFILES)),
        "",
        "Superseded v1 limits, kept for the record of the v1 finding below:",
        "",
        _table_markdown(_profiles_table(profiles.PROFILES_V1)),
        "",
        "How the limits were set, stated plainly: the profiles are generic (no actual investor's "
        "spending amount, flexibility or reserve), so investor need could not produce numbers "
        "of its own. The v1 limits began as draft starting points adjusted by the owner, with "
        "the short limit loosened after history showed the first number could not be met; the "
        "v2 limits were set after the v1 holdout. Need is used to describe and check the "
        "limits, not to derive them.",
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
        "duration is a current published figure applied to the whole period (verified from "
        "the factsheet; `reference/bond_durations.csv`); SGS returns are built from benchmark "
        "yields, not a traded index; hedges assume covered interest parity; the long layer uses "
        "US Treasuries, not global bonds.",
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
        "**Selected under the earlier rule (superseded by the risk menu; docs/decisions.md, "
        "2026-10-27):** " + "; ".join(f"{k}: {v}" for k, v in sel.items()) + ".",
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
        f"{_worst_bond_window()}). Mean-variance weights are unstable across resamples.",
        "",
    ]
    return lines


def _implementation_section() -> list[str]:
    rebal = claim11_rebalancing.run().tables["rules_after_costs"]
    hedge = claim12_hedging.run().tables["samples"]
    eq = hedge[hedge["asset_class"] == "equities"]
    annual, monthly = rebal.loc["Annual"], rebal.loc["Monthly"]
    band = rebal.loc["Band ±10 pts"]
    return [
        "## Weights within asset classes, currency policy and rebalancing",
        "",
        "**Within equities.** Hold one global market-cap-weighted equity index (developed and "
        "emerging markets) rather than fixed regional weights. The index provider updates "
        "country weights; no regional weight is hard-coded. At each annual review, the fund's "
        "published regional weights are recorded with their date in `reference/`.",
        "",
        "**Within SGS.** Market-value weights of a Singapore government bond index, with the "
        "sleeve's duration kept near the matched duration used in the bond-sleeve test "
        "(the fund choice is made in Phase 4).",
        "",
        "**Currency policy.** Equities unhedged; SGS needs no hedge (SGD). Evidence (claim 12): "
        + "; ".join(
            f"{k}: volatility in SGD {row.vol_unhedged:.1%} unhedged vs {row.vol_hedged:.1%} "
            f"hedged, real return difference {row.difference_per_year:+.1%} a year "
            f"(t = {row.difference_t:.1f})"
            for k, row in eq.iterrows()
        )
        + ". Hedging equities to SGD raised volatility without a significant change in "
        "return, so equities stay unhedged. If global bonds replace SGS (Phase 3 sensitivity), "
        "they are hedged to SGD.",
        "",
        "**Rebalancing rule (fixed now, before any Phase 3 backtest).** Rebalance to target "
        "once a year at the end of December, and also at any month-end when the equity weight "
        "is more than 10 percentage points from target. Rationale: in claim 11 the rules could "
        "not be told apart before costs, so the rule is chosen on economic grounds: few trades "
        "(minimum broker fees make small, frequent trades expensive at the USD 25,000 minimum) "
        "and a cap on drift away from the profile's risk level. Evidence, US 60/40 1962–2026 "
        f"after costs: annual {annual['cost_per_year']:.3%} a year in costs, volatility "
        f"{annual['volatility']:.1%}; ±10-point band {band['cost_per_year']:.3%}, volatility "
        f"{band['volatility']:.1%}; monthly {monthly['cost_per_year']:.3%}, volatility "
        f"{monthly['volatility']:.1%}. Phase 3 tests the rule's sensitivity without changing it.",
        "",
    ]


def _v1_finding_section() -> list[str]:
    f = holdout.v1_finding()
    return [
        "## Finding: the v1 limits were infeasible on long history",
        "",
        "Under the v1 limits, no allocation, all cash included, met the limits on the worst "
        "single JST country, nor on the GDP-weighted global portfolio over 1871–2020. The "
        "table shows the worst window (cumulative, or a year for the long profile's 0% floor) "
        "against each v1 floor. War and hyperinflation wiped out home-currency bonds and cash "
        "in single countries, and the world-war periods dragged down the global portfolio "
        "(see claims 1 and 2 of the evidence review). Testing on SGD history alone, then a holdout "
        "with a tie-break that always chose the safest near-tie, merged the three profiles "
        "into one; that result was not accepted as final and led to the v2 limits.",
        "",
        _table_markdown(f),
        "",
    ]


MENU_COLUMNS = [
    "equity_share",
    "expected_real_return",
    "max_drawdown",
    "max_drawdown_sgd",
    "max_drawdown_sgd_nominal",
    "max_drawdown_us_pre1981",
    "stress_long_bond_1940_81",
    "p_loss_holdout",
    "worst_window_holdout",
    "cvar5_holdout",
]


def _menu_display(menu: pd.DataFrame, profile: str) -> pd.DataFrame:
    m = menu.loc[profile].copy()
    m.index = [f"Drawdown no worse than {t}" for t in m.index]
    return m[["result", *[c for c in MENU_COLUMNS if c in m.columns]]]


def _sgd_only_menu(f: pd.DataFrame) -> pd.DataFrame:
    """Sensitivity, not a selection: the menu if only the SGD path (1998 onwards) set the
    drawdown."""
    g = f[f["profile"] == profiles.PROFILES[0].name]
    rows = {}
    for tol in holdout.DRAWDOWN_TOLERANCES:
        ok = g[g["max_drawdown_sgd"] >= tol]
        rows[f"Drawdown no worse than {tol:.0%}"] = (
            {
                "equity_share": ok["equity_share"].max(),
                "max_drawdown_sgd": ok.loc[ok["equity_share"].idxmax(), "max_drawdown_sgd"],
            }
            if len(ok)
            else {"equity_share": np.nan, "max_drawdown_sgd": np.nan}
        )
    return pd.DataFrame(rows).T


def _worst_window_note(f: pd.DataFrame) -> list[str]:
    real = holdout._jst_real()
    parts = []
    for p in profiles.PROFILES:
        for e in (0.0, 0.5, 1.0):
            c, year, v = holdout.h1_worst(np.array([e, 1 - e, 0.0]), p, real)
            parts.append(f"{p.name.lower()}, {e:.0%} equity: {c} to {year} ({v:.0%})")
    return [
        "The worst horizon real returns come from the non-US JST histories, which include "
        "wars and hyperinflations. Worst windows: " + "; ".join(parts) + ".",
        "",
    ]


def _worst_bond_window() -> str:
    """Worst 5-year cumulative real return of the global portfolio's bond sleeve."""
    from analysis import metrics

    glob = allocation.global_portfolio_real()
    cum = (1 + metrics.rolling_annualised(glob["bonds"], 5, 1)) ** 5 - 1
    return f"{cum.min():.0%} real over the five years to {int(cum.idxmin())}"


def _pre1940_note() -> str:
    troughs = [
        int(holdout.us_drawdown_episode(np.array([e / 10, 1 - e / 10, 0.0]))[1][:4])
        for e in range(1, 11)
    ]
    if max(troughs) < 1940:
        return (
            "For every mix with at least 10% equities the worst US episode ends before 1940, "
            "so the 1940–81 bond losses (stress column) do not bind. "
        )
    return "Some binding episodes fall in 1940–81. "


def _lowest_loss(f: pd.DataFrame) -> list:
    out = []
    for p in profiles.PROFILES:
        g = f[f["profile"] == p.name]
        out.append((p, g.loc[g["p_loss_holdout"].idxmin()]))
    return out


def _core_result_section() -> list[str]:
    f = holdout.risk_frontier()
    menu = holdout.risk_menu(f)
    lines = [
        "## Core result: a risk menu per horizon",
        "",
        "Decision rule (changed after the holdout, 2026-10-27): no single recommended "
        "portfolio. For each horizon and each maximum-drawdown tolerance ("
        + ", ".join(f"{t:.0%}" for t in holdout.DRAWDOWN_TOLERANCES)
        + "), the menu shows the highest-expected-return equity/SGS mix (1-point steps) whose "
        "maximum real drawdown is no worse than the tolerance, with its chance of a real loss "
        "over the horizon, worst horizon real return and CVaR at 5% of horizon real returns. "
        "The loss-probability rule it replaces did not constrain equity at long horizons.",
        "",
        "Definitions (fixed before the results were computed):",
        "",
        "- Maximum drawdown: the worse of the real SGD monthly path (1998 onwards) and the US "
        "real monthly path from 1871 to 1980 (Shiller equities; bonds are a modelled US "
        f"government bond duration-matched to A35, {holdout.a35_duration():.2f} years, priced "
        "from Shiller's long-rate yield with a flat curve, or the 30-year bond where yields are "
        "too high to reach that duration). Annual JST data are not used for "
        "drawdowns, because annual observations hide falls within a year. Drawdowns do not "
        "depend on the horizon, so the same mixes appear at every horizon; the horizon "
        "changes the loss measures.",
        "- Nominal SGD drawdown (max_drawdown_sgd_nominal): the SGD path before inflation, "
        "shown for context only; it is not binding.",
        "- Stress test, not binding: the drawdown with Shiller's long government bond in place "
        "of the proxy, January 1940 to December 1981 (stress_long_bond_1940_81).",
        "- P(real loss): the highest real-loss share across the three holdout tests (H1 non-US "
        "JST windows pooled across countries, H2 US before 1981 with the proxy bond, H3 global "
        "JST block bootstrap).",
        "- Worst horizon real return: the worst cumulative real return over any horizon-length "
        "window in the actual histories (H1 and H2).",
        "- CVaR 5%: the average of the worst 5% of horizon real returns, the lowest of the "
        "three tests.",
        "- Expected real return: the global JST portfolio's long-run real return.",
        "",
    ]
    for p in profiles.PROFILES:
        g = f[f["profile"] == p.name]
        shown = g[np.isclose(g["equity_share"] * 10, np.round(g["equity_share"] * 10))]
        shown = shown.assign(mix=[f"{e:.0%} equity" for e in shown["equity_share"]])
        shown = shown.set_index("mix")[MENU_COLUMNS[1:]]
        lines += [
            f"### {p.name} ({p.horizon})",
            "",
            "Risk menu:",
            "",
            _table_markdown(_menu_display(menu, p.name)),
            "",
            "Frontier (10-point steps):",
            "",
            _table_markdown(shown),
            "",
        ]
    dd_us_floor = f["max_drawdown_us_pre1981"].max()
    dd_us_at = f.loc[f["max_drawdown_us_pre1981"].idxmax(), "equity_share"]
    episodes = []
    for e in (0.0, 0.3, float(dd_us_at), 1.0):
        pk, tr, dd = holdout.us_drawdown_episode(np.array([e, 1 - e, 0.0]))
        episodes.append(f"{e:.0%} equity: {dd:.0%}, {pk} to {tr}")
    lines += [
        "### Reading",
        "",
        f"No mix keeps the US 1871–1980 real drawdown better than {dd_us_floor:.1%} (the best "
        f"is at {dd_us_at:.0%} equities). The binding episodes: "
        + "; ".join(episodes)
        + ". "
        + _pre1940_note()
        + "Tolerances tighter than that floor have no mix. Lowest P(real loss) over the "
        "horizon across all mixes (1-point steps): "
        + "; ".join(
            f"{p.name.lower()} {r['p_loss_holdout']:.1%} at {r['equity_share']:.0%} equities"
            for p, r in _lowest_loss(f)
        )
        + ". The short horizon remains outside the strategy on the loss measures.",
        "",
        *_worst_window_note(f),
        "Sensitivity, not a selection: the largest equity share meeting each tolerance if "
        "only the SGD path (1998 onwards, in-sample) set the drawdown:",
        "",
        _table_markdown(_sgd_only_menu(f)),
        "",
    ]
    return lines


def _frontier_reading(fr: pd.DataFrame) -> list[str]:
    """One computed sentence per profile: where it meets the limits in-sample and on holdout."""
    lines = []
    for p in profiles.PROFILES:
        f = fr.loc[p.name]
        tol = p.loss_probability_max
        holdout_ok = (
            (f["h1_non_us_loss_share"] <= tol)
            & (f["h2_us_pre1981_loss_share"] <= tol)
            & (f["h3_bootstrap_loss_share"] <= tol)
        )
        ins = list(f.index[f["meets_in_sample"].astype(bool)])
        both = list(f.index[f["meets_in_sample"].astype(bool) & holdout_ok])
        lowest_h1 = f["h1_non_us_loss_share"].astype(float).min()
        lines.append(
            f"- {p.name}: meets the limits in-sample at "
            + (f"{ins[0]} to {ins[-1]}" if ins else "no mix")
            + "; meets them in-sample and on all three holdout tests at "
            + (f"{both[0]} to {both[-1]}" if both else "no mix")
            + f" (lowest non-US loss share {lowest_h1:.1%} against a tolerance of {tol:.0%})."
        )
    return lines


def _holdout_section(h: dict) -> list[str]:
    t = h["table"].set_index("profile")
    sel = h["selected"]
    fr = holdout.frontier()
    infeasible = [k for k, v in sel.items() if v == holdout.INFEASIBLE]
    return [
        "## Holdout evaluation (v2)",
        "",
        "The in-sample selection uses SGD history that overlaps the backtest. Each candidate "
        "that meets the v2 limits on SGD history, plus 'Maximum equity meeting limits' (largest "
        "equity share meeting them, rest SGS, labelled post-backtest), is scored on data not "
        "used to choose it: the share of horizon-length windows with a real loss in H1 pooled "
        "non-US JST countries (annual, local currency), H2 US data before 1981 (Shiller "
        f"monthly), and H3 2,000 block-bootstrapped paths ({h['block_years']}-year blocks) of "
        "the global JST portfolio. A candidate passes if all three are within the profile's "
        "loss tolerance; among passing candidates the highest expected real return wins; if "
        "none pass, the profile is infeasible (no tie-break).",
        "",
        _table_markdown(t) if len(t) else "No candidate met the limits in-sample.",
        "",
        "**Result under the v2 rule (superseded by the risk menu; docs/decisions.md, "
        "2026-10-27):** " + "; ".join(f"{k}: {v}" for k, v in sel.items()) + ".",
        "",
        (
            "Infeasible profiles: " + ", ".join(infeasible) + ". The table below shows every "
            "measure for equity/SGS mixes in 10-point steps, so the binding limit is visible."
            if infeasible
            else "Every profile has a feasible allocation."
        ),
        "",
        _table_markdown(fr),
        "",
        *_frontier_reading(fr),
    ]


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
            *_core_result_section(),
            *_bond_section(r),
            *_universe_section(u),
            *_allocation_section(al),
            *_implementation_section(),
            *_v1_finding_section(),
            *_holdout_section(holdout.run()),
        ]
    )
    OUTPUT.write_text(text)
    return r
