"""Backtest data layers, strategies, benchmarks and metrics (all monthly, in SGD).

Rules (fixed before results were computed):
- Index layer (February 1998 onwards, from the start of SGS yields):
  - Equities: French developed-markets total return converted to SGD (unhedged), less a
    dividend withholding-tax drag (trailing 12-month dividend yield x 15%, the US-Ireland
    treaty rate an Irish-domiciled fund pays; ACWI's yield from 2009, Shiller's US yield
    before) and the representative fund's TER (reference/etf_costs.csv, ISAC.L).
  - SGS: matched-duration SGS returns (design.bond_options) less A35.SI's TER.
  - Cash: the SGD one-month rate (MAS-based).
  - Global government bonds hedged to SGD (benchmarks only): US 10-year Treasury hedged to
    SGD as the stand-in, no fund fee.
- ETF layer (November 2011 onwards): ISAC.L (Irish UCITS, MSCI ACWI) converted to SGD and
  A35.SI (SGD), total returns from prices and distributions, which already include TER and
  fund-level withholding tax; benchmark global bonds: SGLU.AS hedged to SGD from July 2019,
  the US 10-year stand-in before.
- Strategies: each feasible profile's v2 holdout selection (design.holdout.final_allocations)
  and, for reference, the in-sample picks.
- Benchmarks: 100% global equity; global 60/40 (equities / global bonds hedged); global
  market-cap multi-asset (equity and bond weights from reference/market_cap_weights.csv,
  bonds hedged).
- Rebalancing: every December and at any month-end when a weight is more than 10 points from
  target (design rule); trading costs on trades sized from the USD 25,000 minimum
  (analysis.costs): half the dated bid-ask spread snapshot of the instrument that implements
  each sleeve (INSTRUMENTS) plus published fees for its market (SGX: moomoo SG schedule and SGX
  fees; LSE: OCBC online schedule and LSE levies) with 9% GST on Singapore-charged fees.
  Sensitivity: the spread replaced by 5, 15 and 30 bps per side.
- Metrics: annualised return (nominal SGD), real annualised return (Singapore CPI),
  volatility, Sharpe and Sortino over the SGD one-month rate, maximum drawdown and months to
  recover, worst rolling 1/3/5/10-year annualised returns, turnover and costs per year.
"""

import numpy as np
import pandas as pd

from analysis import costs, data, metrics, portfolio, prices
from analysis.config import DATA_RAW, REFERENCE
from analysis.design import allocation, bond_options, holdout

RULE = {"type": "calendar_or_threshold", "months": 12, "band": 0.10}
MINIMUM_ALLOCATION = 25_000.0
WHT_RATE = 0.15
# Sleeve -> (instrument whose spread is used, market, broker schedule). IGLO.L is the cost proxy
# for both benchmark global-bond sleeves.
INSTRUMENTS = {
    "equity": ("ISAC.L", "LSE", "OCBC"),
    "bonds": ("A35.SI", "SGX", "moomoo SG"),
    "global_bonds": ("IGLO.L", "LSE", "OCBC"),
    "global_unhedged": ("IGLO.L", "LSE", "OCBC"),
}
SPREAD_SENSITIVITY = [0.0005, 0.0015, 0.0030]


def _ter(ticker: str) -> float:
    ref = pd.read_csv(REFERENCE / "etf_costs.csv").set_index("ticker")
    return float(ref.loc[ticker, "ter"])


def dividend_yield() -> pd.Series:
    """Trailing 12-month dividend yield: ACWI (Yahoo) from 2009, Shiller US D/P before."""
    acwi = prices.PRICE_SOURCE.read(DATA_RAW / prices.PRICE_SOURCE.name / "ACWI.csv")
    monthly_div = acwi["dividend"].groupby(acwi.index.to_period("M")).sum()
    month_price = acwi["close"].groupby(acwi.index.to_period("M")).last()
    acwi_dy = (monthly_div.rolling(12).sum() / month_price).dropna()
    raw = pd.read_excel(DATA_RAW / "shiller" / "ie_data.xls", sheet_name="Data", header=7)
    raw = raw[pd.to_numeric(raw["Date"], errors="coerce").notna()]
    idx = pd.PeriodIndex([f"{d:.2f}".replace(".", "-") for d in raw["Date"]], freq="M")
    shiller_dy = pd.Series((raw["D"] / raw["P"]).to_numpy(dtype=float), index=idx).dropna()
    start = acwi_dy.index[0]
    return pd.concat([shiller_dy.loc[: start - 1], acwi_dy])


def _hedged_us10(c: dict) -> pd.Series:
    us10 = data.monthly("us_treasury_monthly")["us_gov10_tr_nominal_usd"]
    return metrics.hedged_return(us10, c["rf_sgd"], c["rf_usd"])


def index_layer() -> pd.DataFrame:
    c = bond_options._common()
    dev = data.monthly("developed_monthly_french")["developed_eq_tr_nominal_usd"]
    gross = metrics.to_base_currency(dev, c["fx"])
    drag = dividend_yield().reindex(gross.index) * WHT_RATE / 12
    equity = gross - drag - _ter("ISAC.L") / 12
    df = pd.DataFrame(
        {
            "equity": equity,
            "cash": c["rf_sgd"],
            "global_bonds": _hedged_us10(c),
            "inflation": c["sg_infl"],
            "wht_drag": drag,
        }
    ).dropna()
    sgs = bond_options.sgs_matched(pd.Series(bond_options.target_duration(), index=df.index))
    df = df.join((sgs["sgs"] - _ter("A35.SI") / 12).rename("bonds"), how="inner")
    return df.dropna()


def etf_layer() -> pd.DataFrame:
    c = bond_options._common()
    etf = data.monthly("etf_monthly")
    sglu = metrics.hedged_return(etf["SGLU.AS_tr_nominal_usd"], c["rf_sgd"], c["rf_usd"])
    global_bonds = sglu.combine_first(_hedged_us10(c))
    df = pd.DataFrame(
        {
            "equity": metrics.to_base_currency(etf["ISAC.L_tr_nominal_usd"], c["fx"]),
            "bonds": etf["A35.SI_tr_nominal_sgd"],
            "cash": c["rf_sgd"],
            "global_bonds": global_bonds,
            "inflation": c["sg_infl"],
        }
    )
    return df.dropna()


def benchmark_weights() -> dict[str, pd.Series]:
    mc = allocation.market_cap_weights()
    return {
        "100% global equity": pd.Series({"equity": 1.0}),
        "Global 60/40": pd.Series({"equity": 0.6, "global_bonds": 0.4}),
        "Global market cap": pd.Series({"equity": mc[0], "global_bonds": mc[1]}),
    }


def strategy_weights() -> dict[str, pd.Series]:
    """Each feasible profile's v2 holdout selection, and, for reference, the in-sample picks
    of every profile (infeasible profiles have no adopted allocation)."""
    out = {}
    for profile, w in holdout.final_allocations().items():
        if w is not None:
            out[f"{profile} profile (v2)"] = w[w > 0]
    for profile, w in allocation.selected_weights().items():
        out[f"In-sample {profile.lower()} pick"] = w[w > 0]
    return out


def infeasible_profiles() -> list[str]:
    return [p for p, w in holdout.final_allocations().items() if w is None]


def cost_fraction(spread_per_side: float | None = None) -> portfolio.CostFn:
    """Cost per side by sleeve; spread_per_side replaces every snapshot half-spread."""
    gst = costs.gst_rate()
    fees = {a: costs.fee_rows(b, m) for a, (_, m, b) in INSTRUMENTS.items()}
    spreads = {
        a: costs.half_spread(t) if spread_per_side is None else spread_per_side
        for a, (t, _, _) in INSTRUMENTS.items()
    }
    px = {a: costs.mid_price_usd(t) for a, (t, _, _) in INSTRUMENTS.items()}

    def fn(asset: str, value: float, side: str) -> float:
        if asset == "cash":
            return 0.0
        return costs.cost_per_side(value, px[asset], spreads[asset], fees[asset], side, gst)

    return fn


def simulate(
    layer: pd.DataFrame,
    weights: pd.Series,
    rule: dict = RULE,
    spread_per_side: float | None = None,
) -> pd.DataFrame:
    returns = layer[list(weights.index)]
    return portfolio.simulate(
        returns, weights, rule, cost_fraction(spread_per_side), MINIMUM_ALLOCATION
    )


def recovery_months(net: pd.Series) -> float:
    r = metrics.recovery_periods(net)
    return float(r) if r is not None else np.nan


def summarise(sim: pd.DataFrame, layer: pd.DataFrame) -> dict:
    net = sim["net"]
    rf = layer.loc[net.index, "cash"]
    real = metrics.real_returns(net, layer.loc[net.index, "inflation"])
    excess = (1 + net) / (1 + rf) - 1
    years = len(net) / 12
    out = {
        "annual_return": metrics.annualised_return(net, 12),
        "real_annual_return": metrics.annualised_return(real, 12),
        "volatility": metrics.annualised_volatility(net, 12),
        "sharpe": metrics.sharpe_ratio(excess, 0.0, 12),
        "sortino": metrics.sortino_ratio(excess, 0.0, 12),
        "max_drawdown": metrics.max_drawdown(net),
        "recovery_months": recovery_months(net),
        "turnover_per_year": sim["turnover"].sum() / years,
        "cost_per_year": sim["cost"].sum() / years,
    }
    for y in (1, 3, 5, 10):
        roll = metrics.rolling_annualised(net, y, 12)
        out[f"worst_{y}y"] = float(roll.min()) if len(roll) else np.nan
    return out


def profile_check(sim: pd.DataFrame, layer: pd.DataFrame, profile) -> dict:
    """The profile's limits on the backtest's real monthly path ('not testable' when the
    sample is shorter than the profile's window)."""
    real = metrics.real_returns(sim["net"], layer.loc[sim.index, "inflation"])
    roll = metrics.rolling_annualised(real, profile.window_years, 12)
    dd = metrics.max_drawdown(real)
    if not len(roll):
        untestable = "not testable"
        return {"worst_window_real": np.nan, "max_drawdown_real": dd, "meets_limits": untestable}
    worst = (
        float(roll.min())
        if profile.floor_is_annualised
        else float((1 + roll.min()) ** profile.window_years - 1)
    )
    ok = worst >= profile.worst_window_floor
    if profile.max_drawdown_cap is not None:
        ok = ok and dd >= profile.max_drawdown_cap
    return {"worst_window_real": worst, "max_drawdown_real": dd, "meets_limits": bool(ok)}
