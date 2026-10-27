"""Claim 7: corporate bonds earn a credit premium, and how much equity-like risk they carry.

Rules:
- Long history: Damodaran annual Baa corporate vs 10-year Treasury returns, 1928 onwards,
  nominal USD. Both are built from yields (Damodaran's notes), so the Baa series includes no
  default losses: its premium is an upper bound.
- Realised: LQD (investment-grade corporates) vs IEF (7-10 year Treasuries), monthly total
  returns from Yahoo (close + distributions), August 2002 onwards, nominal USD. Net of
  defaults and fund costs; durations are similar but not identical.
- Credit excess return = (1 + corporate) / (1 + Treasury) - 1.
- Verdict: verdict_from_share over the two measures (long history, realised) with a positive
  annualised credit excess return.
- Equity-like risk: beta and correlation of credit excess returns with equity excess returns
  over bills (Damodaran S&P 500 annual; French US market monthly), and credit excess returns
  in the worst equity periods.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from analysis import charts, data, metrics, stats
from analysis.evidence import ClaimResult, verdict_from_share


def _excess(a: pd.Series, b: pd.Series) -> pd.Series:
    return ((1 + a) / (1 + b) - 1).dropna()


def equity_link(credit: pd.Series, equity_excess: pd.Series) -> dict:
    df = pd.concat([credit.rename("credit"), equity_excess.rename("equity")], axis=1).dropna()
    fit = sm.OLS(df["credit"], sm.add_constant(df["equity"])).fit(
        cov_type="HAC", cov_kwds={"maxlags": stats.newey_west_lags(len(df))}
    )
    worst = df["equity"] <= df["equity"].quantile(0.10)
    return {
        "beta_to_equity": float(fit.params["equity"]),
        "beta_t": float(fit.tvalues["equity"]),
        "correlation": float(df["credit"].corr(df["equity"])),
        "r_squared": float(fit.rsquared),
        "credit_in_worst_10pct_equity": float(df.loc[worst, "credit"].mean()),
        "credit_other_periods": float(df.loc[~worst, "credit"].mean()),
    }


def long_history() -> tuple[pd.Series, pd.Series]:
    d = data.annual("us_annual_damodaran")
    credit = _excess(d["us_baa_tr_nominal_usd"], d["us_gov10_tr_nominal_usd"])
    equity = _excess(d["us_eq_tr_nominal_usd"], d["us_bill3m_tr_nominal_usd"])
    return credit, equity


def realised() -> tuple[pd.Series, pd.Series]:
    etf = data.monthly("etf_monthly")
    credit = _excess(etf["LQD_tr_nominal_usd"], etf["IEF_tr_nominal_usd"])
    french = data.monthly("us_monthly_french")
    equity = _excess(french["us_eq_tr_nominal_usd"], french["us_bill1m_tr_nominal_usd"])
    return credit, equity


def _figure(long_credit: pd.Series, real_credit: pd.Series) -> "charts.Path":
    fig, ax = charts.figure(height_in=4.8)
    real_annual = (1 + real_credit).groupby(real_credit.index.year).prod() - 1
    full = real_annual.index[(real_credit.groupby(real_credit.index.year).size() == 12).to_numpy()]
    real_annual = real_annual.loc[full]
    overlap = long_credit.loc[real_annual.index.min() : real_annual.index.max()]
    x = np.arange(len(overlap))
    ax.bar(
        x - 0.2,
        overlap * 100,
        width=0.4,
        color=charts.SERIES[0],
        label="Baa minus 10-year Treasury, built from yields (no defaults)",
    )
    ax.bar(
        x + 0.2,
        real_annual.loc[overlap.index] * 100,
        width=0.4,
        color=charts.SERIES[1],
        label="LQD minus IEF, realised (after defaults and costs)",
    )
    ax.axhline(0, color=charts.TEXT_SECONDARY, linewidth=0.8)
    ax.set_xticks(x[::2], [str(y) for y in overlap.index[::2]])
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Credit excess return, % per year")
    ax.legend(loc="upper right", fontsize=8.5)
    gap = np.expm1(np.log1p(overlap).mean()) - np.expm1(
        np.log1p(real_annual.loc[overlap.index]).mean()
    )
    charts.titles(
        fig,
        f"Yield-built credit returns beat realised ones by {gap:.1%} a year, "
        f"{overlap.index.min()}–{overlap.index.max()}",
        "Annual US investment-grade credit return over Treasuries, nominal USD, two measures",
    )
    return charts.save(
        fig,
        "claim07_credit_excess_two_measures",
        "Source: Aswath Damodaran, historical returns (Baa, T-bond); Yahoo Finance (LQD, IEF). "
        "Calculations: this project.",
        {"damodaran", "yahoo"},
    )


def run() -> ClaimResult:
    long_credit, long_equity = long_history()
    real_credit, real_equity = realised()

    measures = {}
    for label, credit, ppy in [
        (
            f"Long history {long_credit.index[0]}–{long_credit.index[-1]} (annual, yield-built)",
            long_credit,
            1,
        ),
        (
            f"Realised {real_credit.index[0]} to {real_credit.index[-1]} (monthly, LQD vs IEF)",
            real_credit,
            12,
        ),
    ]:
        test = stats.hac_mean_test(credit)
        measures[label] = {
            "annualised_excess": metrics.annualised_return(credit, ppy),
            "volatility": metrics.annualised_volatility(credit, ppy),
            "mean_t_stat": test["t_stat"],
            "worst_drawdown": metrics.max_drawdown(credit),
        }
    measures = pd.DataFrame(measures).T
    n_pos = int((measures["annualised_excess"] > 0).sum())

    links = pd.DataFrame(
        {
            "Long history (annual)": equity_link(long_credit, long_equity),
            "Realised (monthly)": equity_link(real_credit, real_equity),
        }
    ).T
    crisis = real_credit.loc["2008-01":"2009-03"]
    figure = _figure(long_credit, real_credit)
    long_row, real_row = measures.iloc[0], measures.iloc[1]

    return ClaimResult(
        number=7,
        claim="Corporate bonds earn a credit premium, and carry some equity-like risk.",
        verdict=verdict_from_share(n_pos, len(measures)),
        headline=(
            f"Investment-grade credit beat Treasuries by {long_row['annualised_excess']:+.1%} a "
            f"year on the long yield-built series (no defaults, an upper bound) and by "
            f"{real_row['annualised_excess']:+.1%} realised since 2002 (t = "
            f"{real_row['mean_t_stat']:.1f}). Its equity beta was "
            f"{links.iloc[1]['beta_to_equity']:.2f} monthly, and its return relative to Treasuries "
            f"was {(1 + crisis).prod() - 1:.0%} from January 2008 to March 2009."
        ),
        data=(
            "Long history: Aswath Damodaran annual Baa corporate and 10-year Treasury returns, "
            "both built from yields, 1928 onwards, nominal USD. Realised: Yahoo Finance monthly "
            "total returns of LQD and IEF, nominal USD. Equity: Damodaran S&P 500 (annual) and "
            "French US market (monthly), over bills."
        ),
        method=(
            "Credit excess return over duration-similar Treasuries; annualised geometric "
            "return, HAC t-test on the mean. Equity link: regression of credit excess on equity "
            "excess (HAC errors), correlation, and credit excess in the worst 10% of equity "
            "periods."
        ),
        findings=[
            "; ".join(
                f"{k}: {row.annualised_excess:+.1%} a year (t = {row.mean_t_stat:.1f}), "
                f"volatility {row.volatility:.1%}, worst drawdown {row.worst_drawdown:.0%}"
                for k, row in measures.iterrows()
            )
            + ".",
            "Equity-like risk: "
            + "; ".join(
                f"{k}: beta {row.beta_to_equity:.2f} (t = {row.beta_t:.1f}), correlation "
                f"{row.correlation:.2f}, equities explain {row.r_squared:.0%} of the variance; "
                f"average credit excess {row.credit_in_worst_10pct_equity:+.1%} in the worst 10% "
                f"of equity periods vs {row.credit_other_periods:+.1%} otherwise"
                for k, row in links.iterrows()
            )
            + ".",
        ],
        caveats=[
            "The long series is built from Moody's Baa yields with no default losses, so its "
            "premium is an upper bound. The realised series is short (since 2002) and covers "
            "one major credit crisis.",
            "LQD and IEF durations are similar but not identical, so part of the realised "
            "excess return is a duration effect; fund fees are included in both.",
            "Investment grade only; high yield is outside the asset universe in the brief.",
            "Nominal USD before tax.",
        ],
        tables={"credit_excess": measures, "equity_link": links},
        figures=[figure],
    )
