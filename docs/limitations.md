# Limitations

Collected during the evidence review (Phase 1) and completed after the independent review (Phase 5, 2026-10-27). The README's Limitations section summarises this file.

## Data
- **Survivorship.** The multi-country data (JST) cover 16–18 developed markets that kept functioning. Markets that were wiped out are absent, so long-run equity returns are biased upward.
- **Non-US REIT history.** No free, long, verifiable non-US REIT total-return series was found. Global and regional REIT results start in 2008 (ETFs). Nothing is spliced from housing data or extrapolated, so the non-US REIT backtest is limited to the period the ETFs cover.
- **US REIT history.** Published results start in October 2004 (VNQ). Nareit's longer series (from 1972) is used only privately because its terms forbid public display and derivative works.
- **Credit after defaults.** No free long-history series of corporate bond returns after default losses was found. The long credit series (1928 onwards) is built from yields and is an upper bound.
- **Bonds built from yields.** US Treasury and TIPS returns are built from constant-maturity yields, not traded bonds.
- **Current costs only.** Bid-ask spreads and fees are today's, so historical trading costs are understated. The backtest replaces every spread with 5, 15 and 30 bps per side as a sensitivity.
- **Revised data.** US CPI is the revised series, not the figures published at the time. October 2025 CPI was never published; Treasury's TIPS contingency value is used for TIPS, and interpolation elsewhere.
- **Data checks outside CI.** Hash verification runs locally only, because several sources update daily.

## Method
- **Few independent observations.** Long-horizon statistics (20-year windows) rest on few independent observations.
- **Splits chosen after seeing the data.** Some subperiod splits (2000, 2022, the 1981 yield peak) were chosen after seeing the data and are labelled as such.
- **Hedging assumptions.** SGD hedging assumes covered interest parity without the cross-currency basis or hedging fees.
- **Equity proxy in the index layer.** The index layer (from 1998) uses developed-market equities (French developed-markets returns), while the implementation holds ACWI (ISAC.L), which includes emerging markets. Index-layer results therefore omit emerging-market returns and risk. The ETF layer (from November 2011) uses ISAC.L itself.
- **Bond proxies.** SGS returns are built from benchmark yields, not a traded index. The US bond used in the risk menu's pre-1981 path is modelled: a par bond at A35's duration, priced from Shiller's long-rate yield with a flat curve. Where yields are too high to reach that duration, the 30-year bond is used.
- **Expected returns.** The expected real return used to rank mixes is the long-run real return of a GDP-weighted global JST portfolio (1871–2020), not a forecast.

## Decisions made after seeing results
- **Changes after the holdout or after results were known.** Each is logged in `docs/decisions.md`. Together they mean the holdout is no longer a clean out-of-sample test.
  - The v2 risk limits were set after the v1 holdout.
  - The gold return-source condition was added after the first universe results.
  - The decision rule was changed to loss budgets.
  - It was then changed again to the drawdown risk menu.
  - The US bond proxy was matched to A35's duration.
  - The headline cost case (IBKR at USD 100,000) was chosen after the OCBC USD 25,000 results. It reverses the index-layer ordering of the menu mix and the global 60/40 (3.8% vs 3.9% real a year; it was 3.4% vs 3.2%).
- **In-sample SGD selection.** The risk menu's drawdown test, the bond-sleeve choice (2019–2026) and the asset-universe tests (2008–2026) use SGD-era data that overlaps the backtest.
- **Owner judgement.** These are owner choices, not results derived from data:
  - the drawdown tolerances (−20%, −30%, −40%, −50%) and the 5% tail level;
  - the horizon profiles;
  - the rebalancing-test margins and contribution assumptions;
  - the 0.5 pp cross-check tolerance.

## Costs and tax
- **Spread quotes.** Spreads come from a single dated snapshot. The ISAC.L and IGLO.L quotes come from a secondary source (to_verify). The A35.SI quote comes from SGX.
- **FX conversion.** The SGD-to-USD conversion cost for LSE trades is not published and is excluded. Platform and custody fees are not modelled.
- **GST.** Singapore GST on the IBKR commission is an assumption; the schedule does not state it.
- **Withholding tax.** The index layer applies ISAC's latest audited effective withholding rate (12.0%) to the whole history, including years before the fund existed.

## Data checks
- **Issuer return cross-check.** 27 of 29 periods are within 0.5 pp a year of the issuer's NAV returns. Two single-year gaps remain: ISAC 2019 (−62 bps) and IGLO 2025 (+69 bps). The likely cause is our market-price basis against the issuer's NAV basis, but it is unconfirmed. The REIT ETF cross-check was not run (REITs are outside the final universe).
- **Duplicate distributions.** Yahoo distribution records contained duplicates, removed by a rule (`clean.drop_duplicate_distributions`). Other data errors of this kind may remain.
