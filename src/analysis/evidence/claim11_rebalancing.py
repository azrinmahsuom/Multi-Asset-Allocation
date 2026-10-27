"""Claim 11: rebalancing reduces volatility and drawdown.

Rules:
- Portfolio: 60% US equity / 40% 10-year Treasury, monthly returns from February 1962, nominal
  USD (French market; Treasury built from FRED month-end yields). 1-month T-bill as cash.
- Rules compared with buy-and-hold: calendar monthly, quarterly, annual; threshold bands of 5
  and 10 percentage points (checked at month-ends).
- Costs: analysis.costs at the USD 25,000 minimum allocation, using the ACWI and IEF
  published spreads and reference prices as stand-ins for the equity and bond legs, and the
  verified broker and regulatory fee rows.
- Verdict: verdict_from_share over rebalancing rules that have both lower volatility and a
  smaller maximum drawdown than buy-and-hold.
- Data mining: the best rule by Sharpe is compared with the worst using a moving-block
  bootstrap of the Sharpe difference (95% interval); if it includes zero, picking the
  "best" rule is fitting noise.
"""

import numpy as np
import pandas as pd

from analysis import bootstrap, charts, costs, data, metrics, portfolio
from analysis.config import BOOTSTRAP_REPS
from analysis.evidence import ClaimResult, verdict_from_share

TARGET = pd.Series({"equity": 0.6, "bonds": 0.4})
RULES = {
    "Buy and hold": {"type": "never"},
    "Monthly": {"type": "calendar", "months": 1},
    "Quarterly": {"type": "calendar", "months": 3},
    "Annual": {"type": "calendar", "months": 12},
    "Band ±5 pts": {"type": "threshold", "band": 0.05},
    "Band ±10 pts": {"type": "threshold", "band": 0.10},
}
STAND_INS = {"equity": "ACWI", "bonds": "IEF"}
MINIMUM_ALLOCATION = 25_000.0


def cost_fraction() -> portfolio.CostFn:
    fees = costs.fee_rows("moomoo SG", "US")
    spreads = {a: costs.half_spread(t) for a, t in STAND_INS.items()}
    prices = {a: costs.reference_price(t) for a, t in STAND_INS.items()}

    def fn(asset: str, value: float, side: str) -> float:
        return costs.cost_per_side(value, prices[asset], spreads[asset], fees, side)

    return fn


def inputs() -> tuple[pd.DataFrame, pd.Series]:
    french = data.monthly("us_monthly_french")
    df = pd.DataFrame(
        {
            "equity": french["us_eq_tr_nominal_usd"],
            "bonds": data.monthly("us_treasury_monthly")["us_gov10_tr_nominal_usd"],
            "rf": french["us_bill1m_tr_nominal_usd"],
        }
    ).dropna()
    return df[["equity", "bonds"]], df["rf"]


def summarise(sim: pd.DataFrame, rf: pd.Series) -> dict:
    net = sim["net"]
    excess = (1 + net) / (1 + rf.loc[net.index]) - 1
    years = len(net) / 12
    return {
        "annual_return": metrics.annualised_return(net, 12),
        "volatility": metrics.annualised_volatility(net, 12),
        "sharpe": metrics.sharpe_ratio(excess, 0.0, 12),
        "max_drawdown": metrics.max_drawdown(net),
        "equity_weight_max": sim["w_equity"].max(),
        "rebalances_per_year": sim["rebalanced"].sum() / years,
        "turnover_per_year": sim["turnover"].sum() / years,
        "cost_per_year": sim["cost"].sum() / years,
    }


def sharpe_difference_ci(a: pd.Series, b: pd.Series, rf: pd.Series) -> tuple[float, float]:
    ea, eb = (((1 + s) / (1 + rf.loc[s.index]) - 1).to_numpy() for s in (a, b))
    n = len(ea)
    block = bootstrap.block_length(n)
    generator = bootstrap.rng()
    diffs = np.empty(BOOTSTRAP_REPS)
    for i in range(BOOTSTRAP_REPS):
        idx = bootstrap.moving_block_indices(n, block, generator)
        sa = ea[idx].mean() / ea[idx].std(ddof=1)
        sb = eb[idx].mean() / eb[idx].std(ddof=1)
        diffs[i] = (sa - sb) * np.sqrt(12)
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def _figure(table: pd.DataFrame, period: str) -> "charts.Path":
    charts.style()
    fig, (left, right) = charts.plt.subplots(1, 2, figsize=(charts.WIDTH_IN, 4.6), sharey=True)
    y = np.arange(len(table))[::-1]
    left.barh(y, table["volatility"].astype(float) * 100, height=0.6, color=charts.SERIES[0])
    right.barh(y, -table["max_drawdown"].astype(float) * 100, height=0.6, color=charts.SERIES[0])
    left.set_yticks(y, table.index)
    left.set_xlabel("Annualised volatility, %")
    right.set_xlabel("Maximum drawdown, % (larger = worse)")
    for ax in (left, right):
        ax.grid(axis="y", visible=False)
    n_better = int(
        (
            (table["volatility"] < table.loc["Buy and hold", "volatility"])
            & (table["max_drawdown"] > table.loc["Buy and hold", "max_drawdown"])
        ).sum()
    )
    charts.titles(
        fig,
        f"{n_better} of {len(table) - 1} rebalancing rules cut both volatility and drawdown",
        f"US 60/40 equity/10-year Treasury, monthly, net of costs at USD 25,000, {period}",
    )
    return charts.save(
        fig,
        "claim11_rebalancing_rules",
        "Source: Kenneth French Data Library; FRED (DGS10 month-end yields); iShares and moomoo "
        "SG published spreads and fees. Calculations: this project.",
        {"french", "fred"},
    )


def run() -> ClaimResult:
    returns, rf = inputs()
    fn = cost_fraction()
    sims = {
        name: portfolio.simulate(returns, TARGET, rule, fn, MINIMUM_ALLOCATION)
        for name, rule in RULES.items()
    }
    table = pd.DataFrame({name: summarise(sim, rf) for name, sim in sims.items()}).T
    bh = table.loc["Buy and hold"]
    rebal = table.drop("Buy and hold")
    better = (rebal["volatility"] < bh["volatility"]) & (rebal["max_drawdown"] > bh["max_drawdown"])
    best, worst = rebal["sharpe"].astype(float).idxmax(), rebal["sharpe"].astype(float).idxmin()
    lo, hi = sharpe_difference_ci(sims[best]["net"], sims[worst]["net"], rf)
    gross = {name: portfolio.simulate(returns, TARGET, rule) for name, rule in RULES.items()}
    gross_table = pd.DataFrame({name: summarise(sim, rf) for name, sim in gross.items()}).T
    glo, ghi = sharpe_difference_ci(gross[best]["net"], gross[worst]["net"], rf)
    period = f"{returns.index[0]} to {returns.index[-1]}"
    figure = _figure(table, period)
    monthly, annual = table.loc["Monthly"], table.loc["Annual"]

    return ClaimResult(
        number=11,
        claim="Rebalancing reduces volatility and drawdown.",
        verdict=verdict_from_share(int(better.sum()), len(rebal)),
        headline=(
            f"{int(better.sum())} of {len(rebal)} rebalancing rules had lower volatility and a "
            f"smaller maximum drawdown than buy-and-hold ({bh['volatility']:.1%} volatility, "
            f"{bh['max_drawdown']:.0%} drawdown, equity drifting up to "
            f"{bh['equity_weight_max']:.0%}). Annual rebalancing: {annual['volatility']:.1%} and "
            f"{annual['max_drawdown']:.0%}. The best rule by Sharpe ({best}) was "
            + ("indistinguishable from" if lo <= 0 <= hi else "distinguishable from")
            + f" the worst ({worst}) after costs: 95% interval for the difference {lo:+.2f} to "
            f"{hi:+.2f}; before costs, {glo:+.2f} to {ghi:+.2f}."
        ),
        data=(
            "Monthly, nominal USD. French US market total return; 10-year constant-maturity "
            f"Treasury built from FRED month-end yields; French 1-month T-bill. {period}."
        ),
        method=(
            "Simulated 60/40 portfolios with weights drifting between rebalances "
            "(analysis.portfolio). Costs per leg at the USD 25,000 minimum allocation: half the "
            "published bid-ask spread (ACWI, IEF) plus broker and regulatory fees. Sharpe over "
            "T-bills. Best-versus-worst Sharpe difference by moving-block bootstrap."
        ),
        findings=[
            "; ".join(
                f"{k}: return {row.annual_return:.2%}, volatility {row.volatility:.1%}, Sharpe "
                f"{row.sharpe:.2f}, max drawdown {row.max_drawdown:.0%}, turnover "
                f"{row.turnover_per_year:.1%} a year, costs {row.cost_per_year:.3%} a year"
                for k, row in table.iterrows()
            )
            + ".",
            f"Costs at USD 25,000: monthly rebalancing {monthly['cost_per_year']:.3%} a year, "
            f"annual {annual['cost_per_year']:.3%} a year.",
            f"Buy-and-hold's equity weight drifted up to {bh['equity_weight_max']:.0%}, so the "
            "comparison is partly between different average risk levels, not only between "
            "rebalancing methods.",
            f"Data-mining check: after costs, Sharpe ratios across the five rules ranged from "
            f"{rebal['sharpe'].min():.2f} to {rebal['sharpe'].max():.2f}; before costs, from "
            f"{gross_table.drop('Buy and hold')['sharpe'].min():.2f} to "
            f"{gross_table.drop('Buy and hold')['sharpe'].max():.2f}. Where the best-versus-worst "
            "interval excludes zero only after costs, the difference comes from trading costs "
            "(minimum fees per order), not from the rebalancing rule itself. Picking one rule "
            "from several after seeing results would otherwise be fitting noise.",
        ],
        caveats=[
            "Spreads and fees are today's; historical costs were higher, which matters most for "
            "monthly rebalancing. Per-share fees use current ETF prices as stand-ins.",
            "Taxes are ignored (Singapore has no capital gains tax for individuals, but "
            "withholding tax on distributions applies; see Phase 3).",
            "The US Treasury leg is built from yields, not traded; one 64-year sample with one "
            "long fall in rates.",
        ],
        tables={"rules_after_costs": table, "rules_before_costs": gross_table},
        figures=[figure],
    )
