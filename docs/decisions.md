# Decision log

Append an entry whenever a methodology choice is made. Newest at the bottom. Every rule is applied mechanically by the code and cites its evidence; if none has been found yet, write `Evidence: pending` and add it to the brief's Open questions.

Entry template:

```
### YYYY-MM-DD — Decision title
**Context:** What prompted the choice
**Options considered:** Each option, and why it was rejected or kept
**Rule:** The exact rule the code applies, with thresholds
**Evidence:** Sources with links that support the rule, or "pending"
**What would change my mind:** The result or evidence that would reverse it
**Effect on results:** If known
```

---

### 2026-10-26 — Project scope
**Context:** Project intake.
**Options considered:** A single backtest of one allocation, or a staged project that tests common claims before designing anything. The staged project was chosen because the allocation's inputs should follow from tested evidence, not habit.
**Rule:** Six phases (0 setup, 1 evidence review of 13 claims, 2 strategy design, 3 backtest, 4 ETF implementation, 5 self-critique). Each phase ends with a checkpoint and owner approval before the next starts. Scope is set by `docs/brief.md`.
**Evidence:** Not applicable (scope choice).
**What would change my mind:** A data gap in Phase 1 that makes a phase untestable; the scope would then be cut and recorded here.
**Effect on results:** None yet.

### 2026-10-26 — Raw data is never committed
**Context:** Some sources may allow redistribution, while others (index providers, Yahoo Finance) do not.
**Options considered:** Commit raw files where the licence allows (rejected: per-source licence tracking adds risk for little benefit), or commit none.
**Rule:** Everything under `data/` except `data/MANIFEST.yaml` is gitignored. The manifest records each file's URL, series ID, retrieval date, licence, SHA-256, row count, date range and units. `verify_data` fails if a file is missing or its hash differs.
**Evidence:** Not applicable (governance choice).
**What would change my mind:** A source disappearing or changing past values in place, which would make results unreproducible from a fresh fetch.
**Effect on results:** None. Reproducibility depends on sources staying online; hash mismatches are reported, never silently accepted.

### 2026-10-26 — Risk-free rate (revised 2026-10-27)
**Context:** Sharpe and Sortino need a stated risk-free rate.
**Options considered:**
- 3-month SGD interbank rate before SORA (the first draft of this rule). Rejected: over the 101 months when both exist (Aug 2005 to Dec 2013), it averaged 1.33% a year against 0.90% for SORA. That gap would understate excess returns before 2005.
- Compounded SGD interbank overnight rate before SORA. Kept: over the same overlap it averaged 0.84% a year against SORA's 0.90%, with a 0.997 correlation. It is also the same kind of rate, a realised overnight cash return.
- 3-month US T-bill for USD results.
**Rule:**
- All SGD rates come from MAS Domestic Interest Rates (`analysis.sources`), built by `clean.sgd_risk_free_monthly`.
- From the first full month of SORA Index data (August 2005), the monthly SGD risk-free return is the change in the SORA Index over the month.
- From July 1987 to July 2005, it is the MAS interbank overnight rate compounded daily over the month (ACT/365, each quote applying until the next).
- No SGD rate exists before July 1987, so SGD Sharpe and Sortino ratios start then.
- USD results use the 3-month US T-bill (FRED TB3MS), or the 1-month T-bill where French data is used.
**Evidence:** Overlap statistics produced by `clean.sgd_risk_free_monthly` (columns `overnight_leg` and `sora_index_leg`), run 2026-10-27. MAS file notes: interbank rates were discontinued from 1 January 2014, and SORA is the volume-weighted overnight unsecured interbank SGD rate. Industry practice of using SORA for SGD cash: pending a cited source.
**What would change my mind:** A longer or more representative free SGD cash series.
**Effect on results:** Pre-2005 SGD excess returns are on the same overnight basis as later ones; the remaining gap averaged 0.06 points a year over the overlap.

### 2026-10-26 — Transaction cost fallback
**Context:** Backtests must include trading costs.
**Options considered:** Measured bid-ask spreads per ETF (preferred where data exists); a flat fallback.
**Rule:** 10 bps per side, used only when a measured cost is missing.
**Evidence:** pending
**What would change my mind:** Measured spreads for the chosen ETFs that differ materially from 10 bps.
**Effect on results:** TBD

### 2026-10-26 — Shiller data from shillerdata.com, not Yale
**Context:** Source check before the first fetch. The long-standing Yale URL (econ.yale.edu/~shiller/data/ie_data.xls) still serves a file, but its data ends 2023-09. The copy linked from shillerdata.com runs to 2026-10.
**Options considered:** The Yale URL (rejected: stale); a hard-coded shillerdata.com file link (rejected: the link carries a changing version tag).
**Rule:** `analysis.sources` reads shillerdata.com and follows the link to `ie_data.xls`, failing if no such link exists. JST's download link is resolved the same way from macrohistory.net/database/.
**Evidence:** Both files fetched on 2026-10-26: the Yale copy's last row is 2023.09, the shillerdata.com copy's is 2026.10.
**What would change my mind:** Shiller stops maintaining shillerdata.com, or names a different official location.
**Effect on results:** Adds three years of data, including 2023–2026.

### 2026-10-27 — ETF prices from yfinance behind a PriceSource interface
**Context:** REIT ETF history is needed for the REIT sleeve and the ETF-era backtest.
**Options considered:** Direct calls to Yahoo's chart endpoint (rejected: same unofficial endpoint and terms, but every breakage would be ours to fix); `yfinance` (kept: it already handles dividends, splits and adjustments and is maintained by others).
**Rule:**
- `yfinance` is pinned to exactly 1.7.0. Only `analysis.prices.YFinanceSource` imports it, so swapping providers means writing another `PriceSource`.
- History is pulled with `auto_adjust=False` and cached raw in `data/raw/yahoo/`, with SHA-256 in the manifest.
- Total return is rebuilt from the split-adjusted close plus cash distributions, reinvested at the ex-date close (`metrics.total_returns_from_distributions`). Yahoo's adjusted close is kept for cross-checks only.
- Each ETF's calendar-year total returns are cross-checked against issuer-published returns for at least 3 years (`prices.cross_check`). Any gap above 0.5 percentage points a year is logged.
- Issuer figures are often NAV-based while ours use market prices, so the basis is recorded with each reference row.
**Evidence:** Tolerance: owner's rule. Evidence: pending.
**What would change my mind:** Repeated mismatches traced to Yahoo data, which would justify switching the PriceSource.
**Effect on results:** TBD

### 2026-10-27 — Data verification runs locally, not in CI
**Context:** FRED, MAS and Yahoo update daily, so a fresh download in CI almost never matches the locally recorded hashes.
**Options considered:** Fetch and verify in CI (rejected: it would fail on nearly every run for reasons unrelated to the code); verify only from a CI cache (rejected: the cache could only be filled by CI's own download, so it would never check against the committed manifest).
**Rule:** CI runs lint and tests. `make verify` checks raw files against `data/MANIFEST.yaml` locally and runs before every results update. Source updates are accepted only through `make refresh`.
**Evidence:** Not applicable (tooling choice).
**What would change my mind:** Freezing raw data snapshots somewhere CI can read them while respecting each source's licence.
**Effect on results:** None.

### 2026-10-27 — Question-led design, no prior hypothesis
**Context:** The brief template asks for a hypothesis before results are seen.
**Options considered:** State a prior hypothesis (rejected by the owner: it would be anecdotal); derive the allocation from the evidence and the investor's constraints (kept).
**Rule:** The project answers the question in brief §3 by gathering and analysing the data, then setting the allocation from the evidence and the investor's constraints. To limit data snooping without a hypothesis, the selection rules (objective, constraints, comparison metrics) are written down in Phase 2 before any backtest results are seen. Anything chosen after seeing results is labelled in-sample.
**Evidence:** Not applicable (research design choice by the owner).
**What would change my mind:** Not applicable.
**Effect on results:** None directly. It moves the guard against data snooping from a falsifiable hypothesis to rules fixed before the backtest.

### 2026-10-27 — Licensing of JST-derived outputs
**Context:** JST data is CC BY-NC-SA 4.0, which is share-alike; the repo code is MIT.
**Options considered:** One licence for everything (rejected: MIT can't relicense share-alike material); a split between code and data-derived outputs (kept: the usual practice).
**Rule:** Code is MIT. Every figure or table derived from JST carries `config.JST_CREDIT` in its caption, stating the source, release, consultation date, citation and CC BY-NC-SA 4.0. The README Licences section gives the full citations JST requires (Jordà, Schularick and Taylor 2017; Jordà et al. 2019 for rate-of-return data).
**Evidence:** macrohistory.net/database/ "How to cite" section and licence-terms page, checked 2026-10-27.
**What would change my mind:** A change in JST's licence terms.
**Effect on results:** None.

### 2026-10-27 — Nareit data is a manual, non-redistributable input
**Context:** reit.com blocks scripted downloads, and its Terms of Use (dated 2023-07-28, s.4) forbid distributing, publicly displaying or creating derivative works of site material without written approval.
**Options considered:** Getting around the bot check (rejected); manual download recorded by hash (kept).
**Rule:** The owner saves `MonthlyHistoricalReturns.xls` to `data/raw/nareit/`. The fetch step records its SHA-256 and fails with the download URL if the file is missing. The file is gitignored. Only the "All Equity REITs" total return column is used. Total return = price return + income return was checked on the first row.
**Evidence:** Nareit Terms of Use s.4 (text supplied by the owner); file header "Returns and dividend yield in percent".
**What would change my mind:** Written approval from Nareit, which would allow publishing results derived from it.
**Effect on results:** Owner's decision, 2026-10-27: Nareit is used privately only. Outputs derived from it are written to `data/processed/` (gitignored), never to `reports/` or `docs/`. Published US REIT history starts in 2004 (VNQ), not 1972.

### 2026-10-27 — Shiller monthly prices are averages; use French for monthly statistics
**Context:** Cross-check of US equity total returns, July 1926 to June 2026. Shiller's monthly return correlates only 0.674 with French's value-weighted market return, while long-run growth rates are close (10.55% vs 10.37% a year). Shiller's monthly price is an average of daily closes, not a month-end price. Averaging smooths monthly returns and adds artificial positive autocorrelation, which biases volatility, correlation and mean-reversion tests.
**Options considered:** Shiller for everything (rejected for the reason above); French where it exists, Shiller only where nothing else exists (kept).
**Rule:** Monthly volatility, correlation and variance-ratio work on US equities uses French data (from July 1926). Shiller is used for annual figures, and for 1871–1926 only with the averaging caveat stated next to the result. Shiller series stop at the last month with a reported dividend (June 2026 in the current file), because later months use estimated inputs.
**Evidence:** Cross-check above, run 2026-10-27. Shiller vs Damodaran annual equity returns, 1928–2025: correlation 0.989. The averaging effect on autocorrelation is a known statistical result (Working, 1960, Econometrica 28(4)). The citation needs checking before publication.
**What would change my mind:** A month-end price series for 1871–1926.
**Effect on results:** Claims 3 and 5 rely mainly on French data.

### 2026-10-27 — Evidence review verdicts
**Context:** Phase 1 gives each of the 13 claims a verdict, and that verdict must not be a judgement call.
**Options considered:** Free-text verdicts (rejected: they invite case-by-case judgement); a fixed rule on the share of cases where the claim is true (kept).
**Rule:** `evidence.verdict_from_share`: *Holds* if the claim is true in every case tested (e.g. every country), *Partially holds* if true in more than half, *Fails* otherwise, *Not testable* if there is no data. A claim about a single case (e.g. "US equities never…") is true or false for that case. Each verdict's headline shows the computed number and margin, so a narrow call is visible.
**Evidence:** Not applicable (reporting rule).
**What would change my mind:** A claim whose wording implies a different test; that claim's module states its test explicitly.
**Effect on results:** Claim 2 fails on one US window at -0.2% a year (Shiller monthly data); the headline and a sensitivity finding report that the JST annual data shows none.

### 2026-10-27 — Phase 1 claim tests: windows, horizons and thresholds (claims 1–5)
**Context:** Each claim needs a test written down before its result is read. The exact rules are in each module's docstring under `src/analysis/evidence/`.
**Rule:**
- Claim 1: geometric annualised real return per asset on each country's common sample. Equities "highest" if their CAGR beats bonds and bills; housing is compared separately.
- Claim 2: 20-year rolling windows, as the claim states. US monthly windows (Shiller), JST annual windows that must be 20 consecutive years.
- Claim 3: the variance ratio at 20 years is compared with 2,000 i.i.d. resamples. Mean reversion is supported below the 5th percentile (one-sided 5%).
- Claim 4: equity weights in 1-point steps, rebalanced annually. Lowest-risk and best risk-adjusted (Sharpe) mixes at 1, 5, 10, 20 and 30 years. The claim is tested on the direction of the 1→20-year shift in the lowest-risk weight, and the shift is compared with i.i.d. resamples (95th percentile).
- Claim 5: rolling 36-month correlation. "Diversify" is tested in the hedge sense (negative correlation), with the weak sense (correlation below 1) reported alongside. Inflation regimes are terciles of trailing 12-month CPI over the sample, and so are descriptive.
**Evidence:** The 20-year window comes from the claim's own wording. The 5% one-sided level is the conventional significance level. The variance-ratio method follows Lo and MacKinlay (1988, Review of Financial Studies); cited, not independently verified. The 36-month correlation window: Evidence: pending (a common practitioner choice; no source cited yet). The 1/5/10/20/30-year horizons: Evidence: pending.
**What would change my mind:** Results that reverse under a reasonable alternative window. A sensitivity check on the 36-month window (24 and 60 months) is planned.
**Effect on results:** See docs/evidence_review.md.

### 2026-10-27 — Claim 5 revised after owner review
**Context:** The owner's review of the first claim 5 draft asked for: non-overlapping results and the effective sample size; an ex-ante inflation split as the lead result; bootstrap intervals for the post-2022 correlation, with and without 2022; portfolio-impact and safe-haven tests; frequency and nominal/real stated; and an SGD hedged vs unhedged view.
**Options considered:** Verdict on overlapping rolling windows (rejected: 740 windows hold only about 21 independent observations); inflation regimes from full-sample terciles (rejected for the lead result: they use future data).
**Rule:**
- Verdict on non-overlapping 36-month blocks (`verdict_from_share`).
- Ex-ante regimes: trailing 12-month CPI inflation, lagged two months for publication, against expanding-window tercile cut-offs (data from 1948, 120-month burn-in).
- 95% intervals from a moving-block bootstrap with block length n^(1/3).
- Portfolio impact: 60/40 rebalanced monthly vs 100% equity.
- Safe haven: Baur and Lucey (2010) regression at the 10%, 5% and 1% equity quantiles, with Newey-West lags floor(4(n/100)^(2/9)).
- SGD hedged return = USD (or USD-hedged) return + SGD rate − USD rate (covered interest parity).
- The 2000 and 2022 splits are kept as secondary and labelled with when they were chosen.
**Evidence:** Baur and Lucey (2010, Financial Review) for the safe-haven test; Hall, Horowitz and Jing (1995, Biometrika) for the block-length rule; Newey and West (1994, Review of Economic Studies) for the lag rule. All cited, not independently verified. The 120-month burn-in and the two-month CPI lag: Evidence: pending (the lag reflects the usual CPI release timing; no source cited yet).
**What would change my mind:** The regime result reversing under a different burn-in or lag; to be tested in the sensitivity pass.
**Effect on results:** The verdict is unchanged (Fails as a hedge). The lead result is now the ex-ante inflation split.

### 2026-10-27 — Phase 1 claim tests (claims 6–8)
**Context:** Each claim's test is written down before its result is read; details in each module's docstring.
**Rule:**
- Claim 6 (term premium):
  - Constant-maturity Treasury returns built from FRED month-end yields (1, 5, 10 and 30 years).
  - "Reliable" means the 10-year beat the 5-year in non-overlapping 10-year blocks (`verdict_from_share`), with a HAC t-test on the mean difference.
  - Ex-ante split by the yield-curve slope (10-year minus 1-year) known at the start of each month.
  - Rate eras (1981 peak, 2020 trough) were chosen after seeing the data and are labelled so.
- Claim 7 (credit premium):
  - Two measures: Damodaran Baa minus 10-year Treasury, which is yield-built with no defaults, so an upper bound; and LQD minus IEF, realised.
  - Verdict = share of the two with a positive annualised excess return.
  - Equity-like risk from the beta and correlation with equity excess returns, and credit returns in the worst 10% of equity periods.
- Claim 8 (inflation-linked bonds):
  - 10-year TIPS built from DFII10 real yields plus CPI-U NSA accrual, using the TIPS reference lag (CPI of month m−2 over m−3).
  - Verdict = share of complete calendar years in which TIPS kept pace with Dec/Dec CPI-U inflation.
  - Inflation beta from annual returns.
  - Checked against the TIP ETF.
**Evidence:** The TIPS indexation lag follows the US Treasury's reference-CPI method; source citation pending. Damodaran's notes confirm his Baa returns are built from yields. 10-year blocks: Evidence: pending.
**What would change my mind:** A traded-index series for long-history credit returns after defaults (none found free).
**Effect on results:** See docs/evidence_review.md.

### 2026-10-27 — Missing CPI month and zero-yield pricing
**Context:**
- FRED's CPIAUCSL and CPIAUCNS have no value for October 2025. BLS did not publish one, which is consistent with that autumn's US government shutdown.
- Separately, the 10-year TIPS real yield was exactly 0.00% at end-September 2016. The bond-pricing formula divided by the yield, so that month was dropped.
**Rule:**
- `clean.fill_single_month_gaps` fills an isolated one-month gap in a CPI series by geometric interpolation, and flags it (`<series>_interpolated`). Longer gaps stay missing.
- `metrics.par_bond_return` now uses the zero-yield limit of the annuity factor; tested.
**Evidence:** A missing value inside the FRED file (raw file unchanged; the fill is in `data/processed` only).
**What would change my mind:** BLS publishing an official value for that month, or an official fallback rule. Either would replace the interpolation.
**Effect on results:** Claim 8 now uses 22 complete calendar years instead of 20. Claim 5's inflation regimes cover the months around October 2025.

### 2026-10-27 — ETF cross-check flags outliers by modified z-score (replaces the 0.5 pp tolerance)
**Context:** The owner asked for a tolerance that can be backed up. The 0.5 percentage point figure had no source.
**Options considered:** A fixed tolerance (rejected: no evidence for any particular number); a published, data-driven outlier rule (kept).
**Rule:** `prices.cross_check` compares our calendar-year total returns with issuer-published *market-price* returns. NAV returns aren't compared, because our returns use closing prices. The gaps are pooled across all ETF-years, and a gap is flagged when its modified z-score, 0.6745 × (gap − median) / MAD, exceeds 3.5 in absolute value. The MAD is floored at 0.01 percentage points, the precision to which issuers publish returns.
**Evidence:** Iglewicz and Hoaglin (1993), *How to Detect and Handle Outliers*, as given in the NIST/SEMATECH e-Handbook of Statistical Methods, section 1.3.5.17 (https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm, checked 2026-10-27): modified z-scores with absolute value above 3.5 are labelled potential outliers. The MAD floor follows NIST's note that the score is undefined when the MAD is zero.
**What would change my mind:** Issuer data that publishes no market-price returns, so only NAV comparisons are possible; those need a separate rule.
**Effect on results:** Flags come from the data's own spread rather than an arbitrary cut-off.

### 2026-10-27 — Trading costs built from documented components (replaces the flat 10 bps)
**Context:** The owner asked for a better-supported trading-cost figure than a flat 10 bps average.
**Options considered:** A flat average (rejected: unsourced, and it hides how cost depends on trade size and fund); per-trade cost from published components (kept).
**Rule:** `costs.cost_per_side` = half the ETF's issuer-published 30-day median bid-ask spread + broker and regulatory fees at the trade size, using only rows marked `verified` in `reference/trading_costs.csv`. Three refinements:
- Published spreads are point-in-time (current) and understate spreads in earlier, more volatile periods. Backtests therefore also report the half-spread at 2× and 3×.
- Converting SGD to USD is charged only when money crosses currencies (contributions, withdrawals, or rebalancing into SGD assets). Rebalancing between USD-listed ETFs happens in USD.
- The trade size comes from the investor profile set in Phase 2.
**Evidence:**
- US ETFs relying on SEC Rule 6c-11 must publish a 30-day median bid-ask spread daily on their websites (law-firm summaries of the 2019 rule; the SEC's own text is still to be checked).
- iShares ACWI page: 0.01% as of 2026-10-23.
- Broker and regulatory fees: moomoo Singapore's published US fee schedule (primary, checked 2026-10-27).
- Two further brokers' figures come from secondary sources and are marked `to_verify`.
- The SGD→USD conversion markup: Evidence: pending (no broker found that discloses it).
**What would change my mind:** Primary fee schedules from more brokers (to take a median), or measured historical spreads.
**Effect on results:** TBD in Phase 3. The cost is likely to be well under 10 bps per side for large, liquid ETFs at typical trade sizes, but no figure is stated until the code computes it.

### 2026-10-27 — Minimum allocation of USD 25,000
**Context:** Fees with per-order minimums make trading costs depend on trade size.
**Rule:** The strategy is designed and costed for a minimum allocation of USD 25,000. Trading costs (`analysis.costs`), the number of ETFs per profile and rebalancing trade sizes are evaluated at this amount, which is the least favourable case for fixed minimum fees.
**Evidence:** Owner's investor constraint (not a market statistic).
**What would change my mind:** A different minimum set by the owner.
**Effect on results:** Phase 2–4 cost figures are computed at USD 25,000.

### 2026-10-27 — Citations checked
**Context:** Several entries cited sources as "not independently verified", and two rules had no cited evidence.
**Rule:** Each citation was checked against its publisher listing, an abstract, or the primary page. The results:

| Source | Used for | Result |
|---|---|---|
| Working (1960), Econometrica 28(4), 916–918 | Averaged prices create spurious autocorrelation (Shiller rule) | Confirmed (Econometric Society listing; the companion Cowles 1960 abstract describes the effect) |
| Jorion and Goetzmann (1999), Journal of Finance 54(3), 953–980 | Survivorship in equity returns (claim 1) | Confirmed (RePEc abstract) |
| Lo and MacKinlay (1988), Review of Financial Studies 1(1), 41–66 | Variance-ratio test (claim 3) | Confirmed (author's page) |
| Poterba and Summers (1988), Journal of Financial Economics 22(1), 27–59 | Background for claim 3 | Confirmed. The wording is corrected: their point estimates suggested mean reversion, but the random walk could not be rejected |
| Hall, Horowitz and Jing (1995), Biometrika 82(3), 561–574 | Bootstrap block length | Confirmed. **Correction:** the optimal rate is n^(1/3) for variance, but n^(1/5) for two-sided intervals. `bootstrap.block_length` now uses n^(1/5) |
| Baur and Lucey (2010), Financial Review 45(2) | Hedge and safe-haven definitions (claim 5) | The paper and its definitions are confirmed; the exact regression form is taken from the papers citing it (not checked against the full text) |
| Newey and West (1994), Review of Economic Studies 61(4), 631–653 | HAC lag rule | The paper is confirmed; the formula floor(4(n/100)^(2/9)) is not confirmed from its text. Evidence: pending |
| Siegel, *Stocks for the Long Run* | Minimum-risk tables (claim 4) | Not confirmed. The citation is removed |
| NIST e-Handbook 1.3.5.17 (Iglewicz and Hoaglin 1993) | Cross-check outlier rule | Confirmed (primary page) |
| BLS CPI release schedule | Two-month CPI lag (claim 5) | Confirmed: month t's CPI is released around the 10th–15th of month t+1, so at the start of month t the latest published CPI is t−2 |
| TreasuryDirect reference-CPI tables | TIPS lag (claim 8) | Confirmed: the reference CPI on the 1st of a month is the CPI-U of three months earlier, interpolated daily |
| US Treasury press release, 26 Nov 2025 | October 2025 CPI | Confirmed: index number 325.604 under the TIPS index contingency, not to be replaced. Claim 8 now uses it (`reference/cpi_contingency.csv`) instead of interpolation |
| ABS/SC-STS and MAS on SORA | SORA as the SGD cash benchmark | Confirmed: SORA replaced SOR (June 2023) and SIBOR (2024) |

**Evidence:** The URLs are in the session research notes. Primary pages: https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm, https://www.bls.gov/schedule/news_release/cpi.htm, https://home.treasury.gov/news/press-releases/sb0324, https://web.mit.edu/Alo/www/Papers/lo-mackinlay-88.html, https://ideas.repec.org/a/bla/jfinan/v54y1999i3p953-980.html.
**What would change my mind:** Reading the Baur–Lucey and Newey–West full texts, which may refine those two entries.
**Effect on results:** Claim 5's confidence intervals change slightly (shorter bootstrap blocks). Claim 8 uses the official October 2025 CPI value. The rest is wording only.

### 2026-10-27 — Unsourced window choices tested by sensitivity instead of citation
**Context:** Several window and horizon lengths had no cited source: the claim 3 test horizon, the claim 4 long horizon, the claim 5 correlation window, CPI lag and burn-in, and the claim 6 comparison blocks.
**Options considered:** Searching for a source for each number (rejected: these are conventions without a canonical value); testing whether the verdict depends on them (kept).
**Rule:** `evidence/sensitivity.py` reruns each claim's verdict statistic at alternatives either side of the default, and the evidence review reports any verdict that changes. A choice is treated as supported if no alternative changes the verdict; otherwise the claim is flagged as sensitive to it.
**Evidence:** Run 2026-10-27: 0 of 20 alternatives changed a verdict (table in docs/evidence_review.md).
**What would change my mind:** An alternative that flips a verdict; that claim would then report both results.
**Effect on results:** None on the verdicts; these choices no longer need a citation.

### 2026-10-27 — Phase 1 claim tests (claims 9–13)
**Context:** These are the remaining claims; each module's docstring has the full rules.
**Rule:**
- **Claim 9 (real estate).** Listed REITs and housing are kept separate.
  - Verdict: the share of 8 REIT ETFs whose total return matched or beat an equity benchmark over the same months. VNQ is compared with the French US market, global and regional REIT ETFs with ACWI, and SGD-listed REIT ETFs with ACWI in SGD.
  - Diversification is tested by a spanning regression (VNQ excess returns on US equity and Treasury excess returns) and by Sharpe ratios of 60/40 vs 54/36/10, not by correlation alone.
  - Housing (JST) is reported as total return vs price-only vs equities.
  - Nareit is compared privately only.
- **Claim 10 (best days).** A missed day earns T-bills. Verdict on whether missing the best N days lowers the return (N = 10, 20, 50, 100). Clustering is tested by a permutation of distances (2,000 draws) and by high-volatility periods known at the time.
- **Claim 11 (rebalancing).** A 60/40 US portfolio, with five rules compared against buy-and-hold. Costs come from `analysis.costs` at the USD 25,000 minimum. Verdict: the share of rules with both lower volatility and a smaller drawdown. Data-mining check: a block bootstrap of the best-vs-worst Sharpe difference, before and after costs.
- **Claim 12 (hedging, SGD).** Hedged = USD return + SGD rate − USD rate (covered interest parity); real returns use Singapore CPI. Verdict: the share of four samples whose hedged-minus-unhedged mean difference is not significant (|HAC t| < 2). Volatility ratios are reported for equities and bonds.
- **Claim 13 (behaviour gap).** Not testable without fund flows. Headline numbers from the commonly cited studies are not quoted (owner's instruction). The sequence effect is shown with equal monthly contributions over rolling 20-year windows.
**Evidence:**
- Spanning tests are the standard mean-variance test for whether an asset improves a frontier; source citation pending.
- Pfau (Advisor Perspectives, 2017) and DALBAR's response, Dichev (2007, AER 97(1)), Keswani and Stolin (2008, Finance Research Letters), and Morningstar's Mind the Gap methodology page, checked via publisher pages and listings on 2026-10-27.
- The |t| < 2 threshold is the conventional approximately-5% two-sided level.
**What would change my mind:** Issuer cross-checks that flag REIT ETF data errors (pending); access to fund-flow data (claim 13).
**Effect on results:** See docs/evidence_review.md.

### 2026-10-27 — Horizon profiles and risk-capacity limits
**Context:** Phase 2 framing. The owner set the limits in chat on 2026-10-27.
**Options considered:** Questionnaire risk tolerance (rejected in the project spec in favour of risk capacity); limits tested on US history only (rejected: claims 1 and 2 show the US was the best case).
**Rule:** Three profiles, each limit tested across all 16 JST countries (annual, real, local currency):
- Short (~5 years): worst rolling 5-year real return ≥ −10% cumulative.
- Medium (~10 years): worst rolling 10-year real return ≥ −20% cumulative.
- Long (20+ years): worst rolling 20-year real return ≥ 0% a year; and maximum peak-to-trough fall no worse than −35%. The fall is measured on both the JST annual data and the monthly SGD backtest, and the worse of the two applies, because annual data understate falls.

The spending reserve sits outside the strategy and its size is left to the investor. Selection: for each profile, the highest expected real return that meets its limits.
**Evidence:** Owner judgement (risk capacity), as stated by the owner. The measurement rules (all 16 countries; the worse of annual and monthly falls) follow from claims 1–2 and from the annual-vs-monthly drawdown difference.
**What would change my mind:** The owner revising a limit.
**Effect on results:** These limits constrain the allocation in Phase 2.

### 2026-10-27 — Bond sleeve: SGS (low confidence)
**Context:** The owner asked for three bond options compared at matched duration on portfolio-level metrics in SGD: SGS, global government bonds hedged to SGD, and global government bonds unhedged.
**Options considered:** The three options. Two alternatives the owner was offered after the results, and declined: calling it a tie and using global bonds, or splitting the sleeve between SGS and global bonds.
**Rule:** The rule fixed before computing (`design/bond_options.py`) picks the option with the lowest average rank on portfolio volatility, maximum drawdown and mean return in the worst 10% of equity months, in the main layer (same global fund, July 2019 to August 2026). The rule's outcome is SGS, and the owner chose to follow it (2026-10-27). Phase 3 also backtests the global-unhedged sleeve, to show how much the choice matters.
**Evidence:**
- The bond-option tables in `docs/strategy_design.md`.
- The winner's volatility advantage over the runner-up has a 95% interval that includes zero.
- The 1998–2026 layer (US Treasuries as the global stand-in) ranks unhedged global bonds first and SGS last.
- The main layer's winner is unchanged with the SGS sleeve matched at 5.0 or 7.5 years of duration.
- The global fund's duration (6.28 years) is a secondary-source figure, status to_verify.
**What would change my mind:** A longer like-for-like global bond history, or Phase 3 backtests showing the choice materially changes the profiles' risk limits.
**Effect on results:** The allocation's bond sleeve is SGS at about 6–7 years duration. The confidence is low and is stated wherever the sleeve is reported.

### 2026-10-27 — Asset universe inclusion rule
**Context:** Spec Phase 2: derive the asset universe from evidence, and explicitly evaluate gold and commodities.
**Options considered:** Including classes by convention (rejected by the spec); a mechanical test against the core (kept).
**Rule:** Core = global equities (unhedged in SGD) + SGS; cash is always available. A candidate is included if either:
- its spanning alpha over the core's excess returns has HAC t > 2; or
- in high-inflation months known at the time (Singapore CPI, trailing 12 months, lagged two months, expanding terciles, 120-month burn-in), it beats a core 60/40 with HAC t > 2.

Fixed-income candidates are hedged to SGD; real assets are unhedged. Candidates: investment-grade credit (LQD), inflation-linked bonds (TIP), global REITs (RWO), gold (GLD) and commodities (DBC). Monthly, SGD, from June 2008.
**Evidence:** Result in `docs/strategy_design.md`: gold included (spanning t = 2.7); the other four excluded. Gold robustness: Damodaran 1972–2025 (after fixed gold prices ended) gives an alpha in the same direction, not significant at annual frequency (t = 1.8). The 1972 cut-off rests on an economic event (the end of US gold convertibility in 1971), not on the results. Spanning tests: source citation pending.
**What would change my mind:** Gold's alpha disappearing in the Phase 3 out-of-sample and robustness checks.
**Effect on results:** The universe is global equities, SGS, cash and gold. Gold's weight is set by the allocation methods; confidence is medium.

### 2026-10-27 — Correction: inclusion requires a source of expected return (gold excluded)
**Context:** Gold passed the spanning test (t = 2.7) on 2008–2026 data. The owner questioned how a speculative asset was included. The project spec requires every candidate to state its role, *expected-return source* and evidence, but the original inclusion rule tested only statistics.
**Options considered:** Require a return source (chosen by the owner); hold gold at its market-cap weight only; keep the rule's result.
**Rule:** A candidate is included only if it has an economic source of expected return (a claim on cash flows such as coupons, dividends or rents, or an inflation-indexed accrual) **and** passes the spanning or inflation-role test. Gold and commodities have no such source and are excluded.
**Evidence:** The project spec's requirement. Gold's monthly spanning result came from a sample with a long gold rally; its annual results from 1928 and from 1972 were not significant.
**What would change my mind:** Not applicable; this restores a requirement of the spec.
**Effect on results:** Universe = global equities, SGS and cash. **This change was made after the first results were seen**, and is disclosed as such. The allocation results were computed only after this change.

### 2026-10-27 — Risk-capacity limits tested on SGD history; JST as stress scenarios
**Context:** Tested on the worst single JST country (annual, real, local currency), no allocation could meet the owner's limits, not even 100% cash: e.g. Germany 1918–1922 cash −97.9% over 5 years. Even from 1950, the median country's worst 5 years was −17% for cash and −32% for 60/40 (with global equities).
**Options considered:** SGD history as the binding test (chosen by the owner); the JST median country from 1950 with looser limits; both together (infeasible with the current limits).
**Rule:** Limits are tested on real SGD monthly returns from February 1998: developed-market equities (French, unhedged in SGD), SGS at the global fund's duration, SGD cash and Singapore CPI. Rolling windows of the profile's length are used, and the long profile's drawdown cap is checked on the same monthly path. JST worst-country results (all years, and from 1950) are reported as stress scenarios. Expected real return for selection is unchanged: the median JST country's long-run real return.
**Evidence:** The diagnostics above, run 2026-10-27. Limits are attainable on SGD history (e.g. 20/80 worst 5 years −8.6%; 60/40 maximum drawdown −35.9%).
**What would change my mind:** An SGD inflation crisis, or a longer SGD bond history, that changes which mixes pass.
**Effect on results:** The limits now reflect the investor's currency. The stress columns show the much worse outcomes in other currencies' history.

### 2026-10-27 — Allocation selection (Phase 2 result)
**Context:** Five methods compared under the profiles' limits (`design/allocation.py`).
**Rule:** As in the module's docstring. Per profile, the highest expected real return among the methods' allocations that meet the limits.
**Evidence:** `docs/strategy_design.md`: Short = glide path (about 19% equities / 81% SGS); Medium and Long = market cap (about 50/50). Selection is restricted to the five methods' outputs. Two known weaknesses: cash isn't riskless in real SGD terms, so scaling with cash doesn't always reduce risk; and the mean-variance weights are unstable across resamples.
**What would change my mind:** Phase 3 backtests, including costs, withholding tax and out-of-sample checks, that break a profile's limits.
**Effect on results:** These are the candidate allocations carried into Phase 3.

### 2026-10-27 — Portfolio-level stress test replaces single countries; short limit −15%
**Context:** The owner asked to test at portfolio level instead of on single countries. A GDP-weighted global portfolio of the JST countries was built: real USD, equities unhedged, government bonds hedged to USD with each country's bill rate, cash = US bills, and weights = the previous year's GDP in USD. Over 1871–2020, every allocation, cash included, failed the limits: global bonds lost 43% in real terms over the five years to 1920, and US bills lost 38.9% over the same window. From 1950, the medium and long limits were attainable. The short profile's −10% limit wasn't attainable on both tests even from 1950.
**Options considered:**
- For the global test, the owner was offered: start in 1950 (a choice made after seeing the data); keep the full history as a stress test only (chosen); or keep it binding (nothing qualifies).
- For the short profile: loosen the limit to −15% (chosen); keep −10% and flag the shortfall; or loosen it to −12.5%.
**Rule:**
- The limits bind on real SGD history (monthly, from February 1998).
- The global JST portfolio over 1871–2020 is reported as a stress scenario.
- Expected real return for selection = the global portfolio's real annualised return.
- The short profile's limit is now: worst 5-year real return no worse than −15% cumulative.
**Evidence:** Owner decisions on 2026-10-27, and the diagnostics above (`design/allocation.global_portfolio_real`). The −15% level is the owner's judgement; on both tests from 1950, a 20/80 mix meets it.
**What would change my mind:** A longer SGD history including an inflation crisis.
**Effect on results:** Short = risk parity (about 25/75); Medium and Long = market cap (about 50/50). This supersedes the single-country stress columns in the earlier entry "Risk-capacity limits tested on SGD history".

### 2026-10-27 — Weights within asset classes, currency policy, rebalancing rule
**Context:** The remaining Phase 2 design rules.
**Rule:**
- **Equities:** one global market-cap-weighted index (developed and emerging); no hard-coded regional weights. The fund's regional weights are recorded with their date at each annual review.
- **SGS:** market-value weights of a Singapore government bond index, with duration kept near the matched duration.
- **Currency:** equities unhedged; SGS needs no hedge; if global bonds are used (Phase 3 sensitivity), they are hedged to SGD.
- **Rebalancing:** to target every December, and at any month-end when the equity weight is more than 10 percentage points from target. Fixed now, before Phase 3; Phase 3 reports its sensitivity but doesn't change it.
**Evidence:**
- Claim 12: hedging equities to SGD raised volatility (USD/SGD moves were correlated −0.32 with US equity returns), with no significant change in return.
- Claim 11: rebalancing rules were statistically indistinguishable before costs; at USD 25,000, monthly rebalancing cost the most because of minimum fees, and annual and band rules the least.
- The 10-point band is one of the claim 11 rules. Its specific level: Evidence: pending (an economic choice to limit drift, not a measured optimum).
**What would change my mind:** Phase 3 showing the rule breaks a profile's limits while an alternative doesn't.
**Effect on results:** These are the implementation rules carried into Phase 3.
