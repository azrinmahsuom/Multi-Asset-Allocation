# Limitations

Collected during the evidence review (Phase 1); completed in Phase 5.

## Data
- **Survivorship.** The multi-country data (JST) cover 16–18 developed markets that kept functioning. Markets that were wiped out are absent, so long-run equity returns are biased upward.
- **Non-US REIT history.** No free, long, verifiable non-US REIT total-return series was found. Global and regional REIT results start in 2008 (ETFs). Nothing is spliced from housing data or extrapolated, so the non-US REIT backtest is limited to the period the ETFs cover.
- **US REIT history.** Published results start in October 2004 (VNQ). Nareit's longer series (from 1972) is used only privately because its terms forbid public display and derivative works.
- **Credit after defaults.** No free long-history series of corporate bond returns after default losses was found. The long credit series (1928 onwards) is built from yields and is an upper bound.
- **Bonds built from yields.** US Treasury and TIPS returns are built from constant-maturity yields, not traded bonds.
- **Current costs only.** Bid-ask spreads and fees are today's, so historical trading costs are understated; backtests show 2× and 3× spreads.
- **Revised data.** US CPI is the revised series, not the figures published at the time. October 2025 CPI was never published; Treasury's TIPS contingency value is used for TIPS, and interpolation elsewhere.
- **Data checks outside CI.** Hash verification runs locally only, because several sources update daily.

## Method
- **Few independent observations.** Long-horizon statistics (20-year windows) rest on few independent observations.
- **Splits chosen after seeing the data.** Some subperiod splits (2000, 2022, the 1981 yield peak) were chosen after seeing the data and are labelled as such.
- **Hedging assumptions.** SGD hedging assumes covered interest parity without the cross-currency basis or hedging fees.
