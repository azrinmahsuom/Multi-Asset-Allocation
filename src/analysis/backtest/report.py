"""Write docs/backtest_results.md and the backtest figures. Every number comes from code."""

import pandas as pd

from analysis import charts, costs, metrics
from analysis.backtest import engine, robustness
from analysis.config import ROOT
from analysis.report import _table_markdown

OUTPUT = ROOT / "docs" / "backtest_results.md"
SOURCE = (
    "Source: Kenneth French Data Library; MAS (SGS yields, SGD rates); FRED (DGS10, DEXSIUS); "
    "SingStat (CPI); Yahoo Finance; Robert Shiller (dividend yield). Net of TER, withholding "
    "tax and trading costs. Calculations: this project."
)
SOURCES = {"french", "mas", "fred", "singstat", "yahoo", "shiller"}
BENCHMARKS = ["100% global equity", "Global 60/40", "Global market cap"]


def _plotted(sims: dict) -> list[str]:
    """Strategies not identical to a benchmark, then the benchmarks (at most 5 lines)."""
    weights = {**engine.strategy_weights(), **engine.benchmark_weights()}
    names = []
    for name in sims:
        if name in BENCHMARKS:
            continue
        if any(weights[name].equals(weights[b]) for b in BENCHMARKS):
            continue
        if any(weights[name].equals(weights[n]) for n in names):
            continue
        names.append(name)
    return (names + BENCHMARKS)[:5]


def _legend(name: str) -> str:
    """Name a benchmark that is also a profile's selection."""
    w = {**engine.strategy_weights(), **engine.benchmark_weights()}
    same = [k for k in engine.strategy_weights() if w[k].equals(w.get(name))]
    return f"{name} (= {', '.join(same)})" if name in BENCHMARKS and same else name


def _growth_figure(sims: dict, layer: pd.DataFrame) -> "charts.Path":
    fig, ax = charts.figure(height_in=5.0)
    names = _plotted(sims)
    for i, name in enumerate(names):
        real = metrics.real_returns(sims[name]["net"], layer.loc[sims[name].index, "inflation"])
        wealth = (1 + real).cumprod()
        ax.plot(
            wealth.index.to_timestamp(), wealth, color=charts.SERIES[i], linewidth=1.8, label=name
        )
    ax.set_yscale("log")
    ticks = [0.75, 1, 1.5, 2, 3, 4]
    ax.set_yticks(ticks, [f"{t:g}" for t in ticks])
    ax.minorticks_off()
    ax.set_ylabel("Growth of SGD 1, real (log scale)")
    ax.legend(loc="upper left", fontsize=8.5)
    eq = metrics.annualised_return(
        metrics.real_returns(sims["100% global equity"]["net"], layer["inflation"]), 12
    )
    sixty = metrics.annualised_return(
        metrics.real_returns(sims["Global 60/40"]["net"], layer["inflation"]), 12
    )
    charts.titles(
        fig,
        f"Global equities {eq:.1%} real a year vs {sixty:.1%} for a global 60/40",
        f"Index layer, monthly, real SGD, {layer.index[0]} to {layer.index[-1]}",
    )
    return charts.save(fig, "backtest_growth_index_layer", SOURCE, SOURCES)


def _drawdown_figure(sims: dict, layer: pd.DataFrame) -> "charts.Path":
    fig, ax = charts.figure(height_in=4.5)
    names = _plotted(sims)
    for i, name in enumerate(names):
        wealth = (1 + sims[name]["net"]).cumprod()
        dd = (wealth / wealth.cummax() - 1) * 100
        ax.plot(
            dd.index.to_timestamp(), dd, color=charts.SERIES[i], linewidth=1.5, label=_legend(name)
        )
    ax.set_ylabel("Drawdown from previous peak, % (nominal SGD)")
    ax.legend(loc="lower right", fontsize=8.5)
    worst = metrics.max_drawdown(sims["100% global equity"]["net"])
    sixty = metrics.max_drawdown(sims["Global 60/40"]["net"])
    charts.titles(
        fig,
        f"Worst fall: global equities {worst:.0%}, global 60/40 {sixty:.0%}",
        f"Index layer, monthly, SGD, {layer.index[0]} to {layer.index[-1]}",
    )
    return charts.save(fig, "backtest_drawdowns_index_layer", SOURCE, SOURCES)


def _cost_section(idx_sims: dict, index_layer: pd.DataFrame, weights: dict) -> list[str]:
    """Per-side cost by trade size, and cost per year under the spread sensitivity."""
    fn = engine.cost_fraction()
    sizes = [1_000, 2_500, 5_000, 10_000, 25_000]
    by_size = pd.DataFrame(
        {
            f"{a} ({t}, {m})": {f"USD {v:,}": fn(a, v, "buy") for v in sizes}
            for a, (t, m, _) in engine.INSTRUMENTS.items()
            if a != "global_unhedged"
        }
    ).T
    rows = {}
    for name, w in weights.items():
        row = {"base_case": engine.summarise(idx_sims[name], index_layer)["cost_per_year"]}
        for bps in engine.SPREAD_SENSITIVITY:
            sim = engine.simulate(index_layer, w, engine.RULE, bps)
            row[f"spread_{bps * 1e4:.0f}bps"] = engine.summarise(sim, index_layer)["cost_per_year"]
        rows[name] = row
    snap = costs.spread_snapshot()
    unverified = ", ".join(snap.index[snap["status"] != "verified"])
    spreads = "; ".join(
        f"{t} {costs.half_spread(t) * 1e4:.1f} bps" for t, _, _ in engine.INSTRUMENTS.values()
    )
    spreads = "; ".join(dict.fromkeys(spreads.split("; ")))
    return [
        "## Trading costs",
        "",
        "Cost per side = half the bid-ask spread from a dated snapshot "
        "(`reference/spread_snapshot.csv`) + published broker and exchange fees "
        "(`reference/trading_costs.csv`), with 9% GST on Singapore-charged fees; fee minimums "
        "converted at the FX rates in `reference/fx_rates.csv`. Snapshot half-spreads: "
        f"{spreads}. Spread rows still to verify against an exchange or issuer quote: "
        f"{unverified or 'none'}; results that use them depend on that check. The SGD-to-USD "
        "conversion cost for LSE trades is not published and is excluded. The schedules are "
        "cost data only, not broker recommendations.",
        "",
        "Cost of one buy order, as a fraction of the order, by order size:",
        "",
        _table_markdown(by_size),
        "",
        "Trading cost per year (index layer), base case and with every spread replaced by 5, "
        "15 or 30 bps per side (fees unchanged):",
        "",
        _table_markdown(pd.DataFrame(rows).T),
        "",
        "Rebalancing trades are sized from the USD 25,000 minimum, not the grown portfolio, so "
        "fixed minimum commissions weigh as they would at the minimum account size.",
        "",
    ]


def _frontier_turnover(layer: pd.DataFrame) -> pd.DataFrame:
    """Turnover and trading cost per year for each equity/SGS mix on the frontier (10-point
    steps); the same at every horizon, since the rebalancing rule does not depend on it."""
    rows = {}
    for e in range(10, 100, 10):
        w = pd.Series({"equity": e / 100, "bonds": 1 - e / 100})
        s = engine.summarise(engine.simulate(layer, w), layer)
        rows[f"{e}% equity"] = {
            "turnover_per_year": s["turnover_per_year"],
            "cost_per_year": s["cost_per_year"],
            **{
                f"cost_spread_{bps * 1e4:.0f}bps": engine.summarise(
                    engine.simulate(layer, w, engine.RULE, bps), layer
                )["cost_per_year"]
                for bps in engine.SPREAD_SENSITIVITY
            },
        }
    return pd.DataFrame(rows).T


def _size_section(index_layer: pd.DataFrame) -> list[str]:
    r = robustness.cost_ranking(index_layer, engine.risk_frontier())
    shown = r["costs"].loc[[e / 10 for e in range(11)]]
    shown.index = [f"{e:.0%} equity" for e in shown.index]
    shown.columns = [f"{b}, USD {v:,.0f}" for b, v in shown.columns]
    return [
        "## Portfolio size, broker schedule and the frontier ranking",
        "",
        "Trading cost per year (index layer) for each equity/SGS mix, by portfolio size and LSE "
        f"broker schedule (verified LSE schedules: {', '.join(engine.lse_brokers())}; OCBC is "
        "the high-cost case):",
        "",
        _table_markdown(shown),
        "",
        "Does the cost model change the frontier ranking? Mixes ranked by expected real return "
        "net of cost per year, against the gross ranking; menu picks re-run on net returns:",
        "",
        _table_markdown(r["table"]),
        "",
    ]


def _rebalancing_test_section(index_layer: pd.DataFrame) -> list[str]:
    t = robustness.cash_flow_test(index_layer)
    t = t.assign(
        return_gain_bps=t["return_gain"] * 1e4, drawdown_change_bps=t["drawdown_change"] * 1e4
    )
    zero = t[t["contribution"] == 0].set_index(["lse_broker", "portfolio_usd", "target"])
    cols = [
        "incumbent_real_return",
        "band_5_real_return",
        "return_gain_bps",
        "incumbent_cost_per_year",
        "band_5_cost_per_year",
        "incumbent_orders_per_year",
        "band_5_orders_per_year",
        "drawdown_change_bps",
        "band_5_preferred",
    ]
    by_flow = t.groupby(["lse_broker", "portfolio_usd", "contribution"]).agg(
        mean_return_gain_bps=("return_gain_bps", "mean"),
        mean_drawdown_change_bps=("drawdown_change_bps", "mean"),
        targets_preferring_band_5=("band_5_preferred", "sum"),
        targets=("band_5_preferred", "size"),
    )
    menu = zero[zero.index.get_level_values("target").str.startswith("Menu")]
    verdict = "; ".join(
        f"{b}, USD {v:,.0f}: {'band 5 preferred' if r['band_5_preferred'] else 'incumbent stays'}"
        for (b, v, _), r in menu.iterrows()
    )
    return [
        "## Rebalancing rule test: ±5-point band with cash-flow rebalancing",
        "",
        "Rule, comparison and decision criterion were logged in `docs/decisions.md` before "
        "this was run. The value is tracked from each portfolio size; contributions arrive "
        "each December and buy the underweight sleeves; orders pay costs at their actual "
        "size. The band rule is preferred only if its net real return is higher by more than "
        f"{robustness.DECISION_MARGIN:.2%} a year with no contribution and its maximum real "
        f"drawdown is no more than {robustness.DRAWDOWN_MARGIN:.0%} point worse.",
        "",
        f"Menu mix: {verdict}.",
        "",
        "No contributions, by target mix:",
        "",
        _table_markdown(zero[cols]),
        "",
        "With contributions (0%, 5% or 10% of the starting value a year), averaged over the "
        "target mixes:",
        "",
        _table_markdown(by_flow),
        "",
    ]


def _layer_section(title: str, layer: pd.DataFrame, weights: dict) -> tuple[list[str], dict]:
    sims = {k: engine.simulate(layer, w) for k, w in weights.items()}
    table = pd.DataFrame({k: engine.summarise(s, layer) for k, s in sims.items()}).T
    checks = pd.DataFrame(
        {k: engine.menu_check(sims[k], layer, tol) for k, (_, tol) in engine.menu_mixes().items()}
    ).T
    lines = [
        f"## {title} ({layer.index[0]} to {layer.index[-1]})",
        "",
        _table_markdown(table),
        "",
        "Menu mixes against their drawdown tolerance on this layer's real SGD path:",
        "",
        _table_markdown(checks) if len(checks) else "No menu mix.",
        "",
    ]
    return lines, sims


def run() -> dict:
    index_layer, etf_layer = engine.index_layer(), engine.etf_layer()
    weights = {**engine.strategy_weights(), **engine.benchmark_weights()}
    strategies = engine.strategy_weights()
    idx_lines, idx_sims = _layer_section("Index layer", index_layer, weights)
    etf_lines, etf_sims = _layer_section("ETF layer", etf_layer, weights)
    growth = _growth_figure(idx_sims, index_layer)
    drawdowns = _drawdown_figure(idx_sims, index_layer)
    sub = robustness.subperiods(idx_sims)
    rising = robustness.rising_rate_era(weights)
    forward = robustness.forward_outcomes({k: idx_sims[k] for k in strategies}, index_layer)
    grids = [
        robustness.parameter_grid(index_layer, w, name, tol)
        for name, (w, tol) in engine.menu_mixes().items()
    ]
    grid = pd.concat(grids) if grids else pd.DataFrame()
    attr = robustness.attribution(index_layer, weights)
    turnover = pd.DataFrame(
        {
            k: {
                "index_layer_turnover_per_year": engine.summarise(idx_sims[k], index_layer)[
                    "turnover_per_year"
                ],
                "etf_layer_turnover_per_year": engine.summarise(etf_sims[k], etf_layer)[
                    "turnover_per_year"
                ],
            }
            for k in strategies
        }
    ).T
    wht = float(index_layer["wht_drag"].mean() * 12)
    fails = grid[~grid["meets_tolerance"].astype(bool)] if len(grid) else grid

    text = "\n".join(
        [
            "# Backtest results",
            "",
            "Generated by `uv run python -m analysis.pipeline backtest`; do not edit by hand. "
            "Rules are in `src/analysis/backtest/engine.py` and `robustness.py` and were fixed "
            "before results were computed. Risk-free rate for Sharpe and Sortino: the SGD "
            "one-month rate (SORA Index from August 2005, compounded SGD interbank overnight "
            "before; MAS). All returns in SGD, net of fund TER, dividend withholding tax and "
            "trading costs at the USD 25,000 minimum; rebalancing every December and when a "
            "weight drifts more than 10 points.",
            "",
            "**Status (2026-10-27):** no single recommended portfolio. The strategies "
            "below are the distinct mixes in the risk menu of `docs/strategy_design.md` "
            "(highest expected return for each maximum-drawdown tolerance): "
            + "; ".join(strategies)
            + ". This result is not final.",
            "",
            "**In-sample caveat:** the menu's drawdown test uses SGD history that overlaps this "
            "backtest (alongside US history before 1981), so these results are not out of "
            "sample.",
            "",
            f"Withholding-tax drag on equities in the index layer averaged {wht:.2%} a year "
            "(trailing dividend yield x 15%). The ETF layer's fund prices already include TER "
            "and fund-level withholding tax.",
            "",
            *idx_lines,
            f"![Growth](../{growth.relative_to(ROOT).as_posix()})",
            "",
            f"![Drawdowns](../{drawdowns.relative_to(ROOT).as_posix()})",
            "",
            *etf_lines,
            *_cost_section(idx_sims, index_layer, weights),
            *_size_section(index_layer),
            *_rebalancing_test_section(index_layer),
            "## Turnover per profile",
            "",
            "One-way turnover from rebalancing, per year (a single-asset allocation never "
            "rebalances):",
            "",
            _table_markdown(turnover),
            "",
            "Turnover and trading cost per year for every equity/SGS mix on the frontier "
            "(index layer; 0% and 100% equity never rebalance). These apply to whichever mix a "
            "horizon's loss budget selects in `docs/strategy_design.md`:",
            "",
            _table_markdown(_frontier_turnover(index_layer)),
            "",
            "## Subperiods (index layer)",
            "",
            _table_markdown(sub),
            "",
            "## Rising-rate era and long history (global JST portfolio, real USD, annual)",
            "",
            "1950–1981 is the post-war period of rising long-term rates to the 1981 peak; "
            "1871–2020 includes both world wars. Global bonds hedged to USD stand in for SGS.",
            "",
            _table_markdown(rising),
            "",
            f"## Forward outcomes ({robustness.HORIZON_YEARS}-year, block bootstrap of the "
            "index layer, real SGD)",
            "",
            _table_markdown(forward),
            "",
            "## Parameter grid (index layer, each menu mix against its drawdown tolerance)",
            "",
            _table_markdown(grid) if len(grid) else "No menu mix.",
            "",
            "Variants that fail: "
            + ("; ".join(f"{p} – {v}" for p, v in fails.index) or "none")
            + ".",
            "",
            "## What drove returns",
            "",
            f"Annualised sleeve returns over the index layer: equities "
            f"{attr['sleeve_returns']['equity']:.1%}, SGS {attr['sleeve_returns']['bonds']:.1%}, "
            f"SGD cash {attr['sleeve_returns']['cash']:.1%} (nominal SGD). The 10-year SGS yield "
            f"fell from {attr['sgs10_start']:.2%} at the start to {attr['sgs10_min']:.2%} "
            f"({attr['sgs10_min_month']}) and ended at {attr['sgs10_end']:.2%}: much of the "
            "bond return came from falling yields, which cannot repeat from today's starting "
            "level.",
            "",
            "## Caveats",
            "",
            "- About 28 years of SGD history; the ETF layer starts in November 2011 and has no "
            "2008 crisis.",
            "- Index-layer equities are developed markets only (no emerging markets before the "
            "ETF layer); the withholding-tax drag uses the 15% treaty rate on the whole "
            "dividend yield, an approximation.",
            "- Spreads are a single dated snapshot; spreads widen in stressed markets, which "
            "the 5/15/30 bps sensitivity covers only partly.",
            "- Benchmark global bonds use US Treasuries hedged to SGD before July 2019, with no "
            "fund fee.",
            "",
        ]
    )
    OUTPUT.write_text(text)
    return {"grid": grid, "forward": forward, "subperiods": sub, "turnover": turnover}
