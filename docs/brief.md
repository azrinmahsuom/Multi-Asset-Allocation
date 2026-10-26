# Project brief

Filled in at the start of the project and read before every task. Update it whenever the scope changes, and log why in `docs/decisions.md`.

## 1. Name
Multi-Asset-Allocation

## 2. Type
Research

## 3. Goal
Build an evidence-based, long-horizon multi-asset allocation for a Singapore-dollar (SGD) investor, implemented with low-cost ETFs. The project:

1. Tests common asset allocation claims against data instead of repeating them.
2. Designs an allocation with explicit, defensible reasoning.
3. Backtests it honestly, including costs, withholding tax, FX and data-snooping risk.
4. Turns it into an ETF portfolio an investor could actually buy.
5. Critiques its own results.

The work runs in six phases (0 setup, 1 evidence review, 2 strategy design, 3 backtest, 4 implementation, 5 self-critique), with a checkpoint and owner approval at the end of each.

## 4. Audience
Recruiters and investment hiring managers at a digital wealth platform. Secondary: any SGD-based long-horizon investor reading on GitHub.

## 5. Hypothesis (research only)
None. In the owner's words (2026-10-27): "A hypothesis will be anecdotal, whereas data driven allocation makes more sense. So what I prefer is the paper and research starting off with the question we are trying to answer, gathering all the data, analysing it, and coming up with the allocation based on that and any constraints of the investor."

## 6. Universe, period, frequency, currency
- Universe:
  - Phase 1: the asset classes behind the 13 claims, from public long-history data (US and multi-country equities, government bills and bonds, investment-grade credit, inflation-linked bonds, housing, REITs, FX).
  - Phases 2–4: candidate sleeves of global equities, government bonds, inflation-linked bonds, investment-grade credit, REITs and cash/T-bills. Gold and commodities are evaluated explicitly, for inclusion or exclusion.
- Period: the longest reliable history for each source (from 1870 for JST, 1871 for Shiller, 1926 for French, 1928 for Damodaran). For the ETF-implementable backtest, the period the chosen ETFs actually existed.
- Frequency: annual and monthly for long-history work; daily where a claim needs it (claim 10).
- Currency: SGD for the strategy and backtest. Source-currency results (mostly USD) are labelled as such in Phase 1. · Returns: total return, nominal and real. Any price-only series is labelled as price-only.

## 7. Benchmark
- Global 60/40 (equity/bonds)
- Global market-capitalisation multi-asset portfolio (the neutral benchmark)
- 100% global equity

## 8. Data and sources
One source per line, with whether results derived from it can be published. Update "Pulled on" each time the data is re-downloaded. Hand-researched inputs live in `reference/` instead, with their own `checked_on` dates. Each URL, series ID and licence is verified by fetching it at the start of Phase 1. Raw files are never committed; `data/MANIFEST.yaml` records the hash and licence of each one.

| Data | Source | Script | Pulled on | Publishable? |
|---|---|---|---|---|
| US stocks, dividends, earnings, CPI, long rate (monthly, 1871-01 to 2026-10) | Robert Shiller online data, shillerdata.com (the Yale copy is stale, ending 2023-09) | `analysis.sources` | 2026-10-26 | Derived results only; no licence stated |
| US market and factor returns (monthly 1926-07 to 2026-08; daily 1926-07-01 to 2026-08-31) | Kenneth French Data Library | `analysis.sources` | 2026-10-26 | Derived results only; no licence stated |
| US stocks, T-bills, T-bonds, Baa corporates, real estate, gold (annual, 1928 to 2025) | Aswath Damodaran, histretSP.xls | `analysis.sources` | 2026-10-26 | Derived results only; no licence stated |
| 18-country equity, bond, bill, housing total returns (annual, 1870 to 2020) | Jordà-Schularick-Taylor Macrohistory Database, release R6 | `analysis.sources` | 2026-10-26 | Yes, CC BY-NC-SA 4.0 with citation |
| Treasury yields (TB3MS, GS1, GS5, GS10, GS30), TIPS (FII10), CPI (CPIAUCSL), SGD per USD (EXSIUS) | FRED | `analysis.sources` | 2026-10-26 | Yes, public domain with citation |
| Moody's Baa and Aaa corporate yields (BAA, AAA) | FRED | `analysis.sources` | 2026-10-26 | Derived results only; copyrighted |
| SGD interbank overnight and 3-month (daily, Jul 1987 to Dec 2013); SORA, SORA Index, 3-month compounded SORA (daily, 2005 onwards) | MAS Domestic Interest Rates (eservices.mas.gov.sg) | `analysis.sources` | 2026-10-27 | Yes, MAS dataset terms with attribution |
| SG CPI, SGS yields | SingStat / MAS | Phase 1 | TBD | TBD (verify terms) |
| US equity REIT total return: All Equity REITs (monthly, 1971-12 to 2026-09) | Nareit, MonthlyHistoricalReturns.xls | Manual download, recorded by `analysis.sources` | 2026-10-27 | **No.** Private validation only (owner's decision, 2026-10-27); its terms (s.4) prohibit public display and derivative works |
| REIT ETF daily prices and distributions: VNQ, VNQI, RWO, REET, IDWP.L, CLR.SI, CFA.SI, SRT.SI | Yahoo Finance via `yfinance` 1.7.0 (pinned) | `analysis.prices` / `analysis.sources` | 2026-10-27 | Derived results only; Yahoo terms |
| Issuer-published ETF annual returns (cross-check) | Issuer websites | Hand-entered in `reference/etf_annual_returns.csv` | TBD | Cited, not redistributed |
| ETF documents (TER, domicile, replication, AUM) and ETF prices | ETF issuer sites; free price data (Phase 3–4) | TBD | TBD | TBD |

## 9. Processing steps
1. Fetch each source to `data/raw/<source>/` and record it in `data/MANIFEST.yaml`.
2. Verify hashes (`verify_data`), failing loudly on any mismatch.
3. Clean into tidy total-return series with units in the column names (`data/processed/`).
4. Phase 1: test each of the 13 claims and write `docs/evidence_review.md` with its figures.
5. Phase 2: design the strategy and write `docs/strategy_design.md`.
6. Phase 3: run the index-level and ETF-era backtests, robustness checks and results summary.
7. Phase 4: map sleeves to ETFs, calculate all-in costs and publish model portfolios.
8. Phase 5: independent review, then `docs/limitations.md`.

One command rebuilds everything: `make all` (wraps `uv run python -m analysis.pipeline`).

## 10. Outputs
- `README.md`: a one-screen summary, a headline chart, key findings including where common claims failed, links to the docs, a "Built with AI assistance" note, and how to reproduce.
- `docs/`: `evidence_review.md`, `strategy_design.md`, backtest results, implementation, `limitations.md`, `decisions.md`.
- `data/MANIFEST.yaml` (committed; the data itself is not).
- `reports/figures/*.png`.

## 11. Run cadence (tool only)
Not applicable (Research). The model portfolio tables in Phase 4 are dated and carry a refresh rule.

## 12. Limits, assumptions and things to avoid
Each threshold or default cites its evidence, or says `Evidence: pending` (and is listed under Open questions).
- Transaction costs: measured from ETF bid-ask spreads in Phase 3 where available; fallback 10 bps per side, Evidence: pending.
- Risk-free rate: SGD, from MAS. Monthly change in the SORA Index from August 2005; the compounded interbank overnight rate from July 1987 to July 2005 (see decisions.md). USD results use US T-bills.
- Dividend withholding tax by ETF domicile for a Singapore resident, from cited primary sources (`reference/`).
- No look-ahead: weights, rules and parameters are either chosen with data available at the time, or fixed ex ante on economic grounds. Anything tuned in-sample is reported as in-sample.
- Survivorship: multi-country data excludes markets that were wiped out; this is disclosed wherever it matters.
- Every claim, including textbook ones and the owner's own, is a hypothesis to test.
- Naming rules: ETF issuer names and tickers are allowed as product identifiers only. Never name the owner's employer or its strategy names. Never reproduce the structure, specific weights, screening thresholds or ranking weights from any firm's internal or published materials. No custodian or broker recommendations. Language stays neutral, with no endorsement wording. Every ETF selection is dated ("as of YYYY-MM") and labelled illustrative, not investment advice.
- Public academic and data sources only.
- Figures that can't be reproduced (e.g. commercial yearbooks) are labelled "cited but not independently verified".

### REIT sleeve requirements (added 2026-10-27)
0. Published US REIT results use REIT ETF total returns (VNQ, from 2004). Nareit's All Equity REITs series is used only privately: to sanity-check the ETF series over the overlap and to inform the analysis. No figure, table or statistic derived from Nareit appears in the README, `docs/` or `reports/`. As a result, the published REIT history starts in 2004 and covers one full cycle (2008–09) plus 2020 and 2022, which goes into `docs/limitations.md`.
1. REITs are measured with a listed-REIT total-return series. Never use house price indices or housing returns (including JST housing) as a REIT proxy. Housing results, if shown, are reported separately and labelled as housing.
2. Sources: Nareit FTSE Nareit All Equity REITs (US, monthly, from 1972); total-return history of liquid REIT ETFs (US, developed ex-US, global, a UCITS global REIT ETF); an S-REIT ETF for an optional SGD comparison. Each ETF series states whether it uses adjusted close or price plus distributions.
3. If no free, long, verifiable non-US REIT total-return series exists, say so. Don't splice in housing data or extrapolate. Limit the non-US REIT backtest to the period actually covered and record the limit in `docs/limitations.md`.
4. Every REIT series has a manifest entry with frequency, currency and price vs total return.
5. Sanity checks before use: no gaps or duplicate dates; price-only vs total-return CAGR compared; 2008–09 drawdown checked for plausibility; ETF returns cross-checked against the issuer's published annual returns for at least 3 years, with mismatches logged.
6. Analysis: return, volatility, drawdown and rolling correlation with equities and bonds, over the full period and in subperiods (incl. 2008–09, 2020, 2022). Diversification is tested by comparing portfolios with and without REITs at equal risk, not by correlation alone. Withholding-tax drag on REIT distributions is calculated by ETF domicile for a Singapore resident.

## 13. How we know the code is correct
- Every function in `metrics.py` matches a hand calculation on a small example. A Sharpe ratio reconciles exactly with its stated inputs.
- `verify_data` passes: raw-file hashes match `data/MANIFEST.yaml`.
- Cleaned series reconcile with published figures from the same source where the source publishes them.
- `make all` on a fresh clone rebuilds every figure and table.

## 14. What would show the hypothesis is wrong
Not applicable: no hypothesis (see §5).

## 15. Open questions
- Transaction cost fallback of 10 bps per side. Evidence: pending.
- JST's CC BY-NC-SA 4.0 share-alike term may apply to published charts derived from JST, while the repo code is MIT. Decide how JST-derived figures are licensed and credited.
- JST ends in 2020, so 2022 regime tests (claims 5 and 8) rely on US data only.
- SingStat series (SG CPI) and SGS yields: not yet fetched.
- Issuer annual returns for the cross-check (at least 3 years per ETF) are not yet entered in `reference/etf_annual_returns.csv`.
- The 0.5 pp per year cross-check tolerance was set by the owner. Evidence: pending.
- Data verification is local only (`make verify`); CI can't reproduce hashes of daily-updating sources.
- Length of the SGD hedging-cost history (SG short rates, USD/SGD from 1981 on FRED) for claim 12.
