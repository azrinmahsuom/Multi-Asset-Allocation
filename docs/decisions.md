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
