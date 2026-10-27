# Multi-Asset Allocation for a Singapore-Dollar Investor

> **One-line thesis:** For an SGD investor, the strongest evidence supports a risk menu, not one "optimal" portfolio. How much equity a drawdown limit allows depends on which history you trust. On SGD data since 1998, a −40% limit allows 67% equities. Across a century of US history, no equity/bond mix stays above about −44%, and only a −50% limit is achievable (59% equities).

![CI](https://github.com/azrinmahsuom/Multi-Asset-Allocation/actions/workflows/ci.yml/badge.svg)

## Summary for recruiters

- **Problem:** which long-horizon mix of low-cost ETFs is best supported by evidence for an investor who spends Singapore dollars? And which popular allocation claims survive testing?
- **What I built:** a reproducible Python research pipeline. One command (`make all`) does the full run:
  - downloads 63 raw files from public sources and verifies each against a SHA-256 manifest;
  - tests 13 textbook claims;
  - designs and stress-tests allocations on held-out data;
  - backtests them in SGD after fund fees, withholding tax, FX and trading costs from published broker and exchange schedules.
- **How I worked:**
  - Every methodology choice is a written rule, logged with its evidence before the result was computed ([decision log](docs/decisions.md)).
  - Rule changes made after seeing holdout results are labelled as such.
  - Tax rates and fund costs are read from audited reports, treaty texts and prospectuses, and the code checks them against the documents.
- **Main result:**
  - Over 5 years, every mix has a 21% or higher historical chance of losing money in real terms, so short-horizon money sits outside the strategy.
  - Over 10–20 years, the binding risk is drawdown depth. How deep a drawdown each history shows is set out in the [risk menu](#the-risk-menu-sgd-era-vs-us-century).
- **Skills shown:** asset allocation, portfolio construction and backtesting, robust statistics (block bootstrap, HAC errors, shrinkage), fixed-income modelling from yields, fund tax analysis, data engineering and testing (pytest, ruff, CI).

| | |
|---|---|
| **Question** | Which long-horizon multi-asset allocation of low-cost ETFs is best supported by evidence for an SGD-based investor, and which common allocation claims hold up? |
| **Data** | Public sources only: Jordà-Schularick-Taylor (16 countries, 1871–2020), Shiller (US, 1871 onwards), French, Damodaran, FRED, MAS, SingStat, ETF prices, and fund and tax documents. |
| **Base currency** | SGD. Returns are total returns, in real terms after Singapore CPI unless stated. The risk-free rate is the SGD one-month rate (SORA Index from August 2005, compounded interbank overnight rate before; MAS). |
| **Benchmarks** | 100% global equity; global 60/40; global market-cap multi-asset. |
| **Status** | Evidence review, strategy design and backtest are complete. ETF implementation tables and an independent review are still to come. |

## Key findings

1. **The risk menu is the core result.** For each horizon, the menu shows the highest-return mix of global equities and Singapore government bonds (SGS) that stays within a drawdown limit. It also shows each mix's chance of a real loss, its worst historical outcome and the average of its worst 5% of outcomes. There is no single recommended portfolio. [Details](#the-risk-menu-sgd-era-vs-us-century).
2. **Of the 13 textbook claims, 4 hold, 4 hold partly, 4 fail and 1 can't be tested with public data.** For example:
   - The US stock–bond correlation depends on inflation: −0.17 in low-inflation months (the 95% interval includes zero) and +0.29 in high-inflation months.
   - Long-run mean reversion in equities isn't statistically supported in any of 16 countries.
   - Listed REITs didn't match equities in any of 8 cases.
   - [Full evidence review](docs/evidence_review.md).
3. **The US century is the binding constraint.** No equity/SGS mix keeps the US 1871–1980 real drawdown better than −43.7%. Balanced mixes are bound by the First World War inflation (1915–20), and equity-heavy mixes by 1929–32.
4. **Short-horizon money doesn't belong in the strategy.** Over 5 years, every mix lost money in real terms in at least 21.5% of held-out historical windows (the lowest is at 48% equities).
5. **The broker schedule matters more than spreads at small sizes.** Holding the 59% equity mix at USD 25,000 costs 3.2 bps a year in trading with the low-cost published LSE schedule, against 33.9 bps with the high-cost one. Costs never change which mix the menu picks.
6. **Fund domicile matters for tax.**
   - An Irish-domiciled global equity fund lost 12.0% of its dividends to withholding tax (its audited 2025 report).
   - A US-domiciled fund distributing to a Singapore resident would lose 30%.
   - US-domiciled funds also count as US assets for US estate tax, with a return required above USD 60,000.

## The risk menu: SGD era vs US century

The drawdown limit is the investor's choice. The table shows the most equity each limit allows, depending on which history sets the drawdown (real terms, equities and SGS only):

| Maximum real drawdown accepted | SGD era only (1998–2026, in-sample) | Binding rule: worse of SGD era and US 1871–1980 |
|---|---|---|
| −20% | no mix | no mix |
| −30% | 49% equities (−29.8%) | no mix |
| −40% | 67% equities (−39.6%) | no mix |
| −50% | 88% equities (−49.6%) | **59% equities** (−49.4%) |

The SGD era since 1998 is the investor's own currency and market, but it is only 28 years long and includes no inflation shock comparable to the First World War or the 1970s. The US series adds a century of crises.

The binding rule takes the worse of the two. For US bonds it uses a modelled US government bond matched to the duration of the SGS fund (8.18 years). It's built from Shiller's long-rate yield and labelled as modelled.

How the 59% equity mix behaves on each horizon (held-out data: 15 non-US countries, the US before 1981, and a block bootstrap of the global portfolio):

| Horizon | Chance of a real loss | Worst real outcome over the horizon | Average of the worst 5% | Context: nominal SGD drawdown | Stress: US long bonds 1940–81 |
|---|---|---|---|---|---|
| ~5 years | 22.1% | −92.7% | −57.8% | −30.1% | −36.4% |
| ~10 years | 16.6% | −94.4% | −70.8% | −30.1% | −36.4% |
| 20+ years | 15.9% | −92.1% | −74.7% | −30.1% | −36.4% |

The worst outcomes come from the non-US histories, which include wars and hyperinflations: Germany to 1922, Japan to 1945, France to 1950–51, and Portugal after 1974.

Full menus, frontiers and definitions are in [docs/strategy_design.md](docs/strategy_design.md).

## Backtest

Results in SGD, net of fund fees, withholding tax and trading costs. The index layer uses the high-cost broker schedule at USD 25,000. Rebalancing happens every December, or sooner when a weight drifts more than 10 points. A ±5-point band with cash-flow rebalancing was tested against this rule and not adopted.

| Index layer, 1998-02 to 2026-08 | Real return a year | Volatility | Max drawdown (nominal) | Worst 5 years (a year) |
|---|---|---|---|---|
| Menu mix: 59% equities, 41% SGS | 3.4% | 7.9% | −29.8% | −2.4% |
| 100% global equity | 5.0% | 13.5% | −51.2% | −7.1% |
| Global 60/40 | 3.2% | 7.8% | −29.5% | −2.0% |
| Global market cap | 2.8% | 6.8% | −22.8% | −0.8% |

| ETF layer, 2011-11 to 2026-08 | Real return a year | Volatility | Max drawdown (nominal) |
|---|---|---|---|
| Menu mix: 59% equities, 41% SGS | 5.4% | 7.1% | −16.1% |
| 100% global equity | 9.4% | 11.3% | −19.6% |
| Global 60/40 | 4.7% | 7.1% | −17.0% |
| Global market cap | 3.6% | 6.2% | −16.4% |

![Growth of SGD 1 in real terms](reports/figures/backtest_growth_index_layer.png)

The menu mix is not out of sample here: its drawdown test uses SGD history that overlaps the backtest. The full tables, robustness checks, cost sensitivity and the rebalancing test are in [docs/backtest_results.md](docs/backtest_results.md).

**Illustrative instruments, as of 2026-10.** These are not recommendations:
- iShares MSCI ACWI UCITS ETF (ISAC, LSE; Irish-domiciled, accumulating; TER 0.20%);
- ABF Singapore Bond Index Fund (A35, SGX; total expense ratio 0.24%).

The SGS sleeve was chosen over global bonds by a pre-set rule, and the choice is logged as low confidence.

## Limitations

- **Post-holdout changes.** The decision rule changed twice after holdout results were seen (loss budgets, then the drawdown menu), and the US bond proxy was corrected afterwards. Each change is logged, but the holdout is no longer a clean test.
- **Survivorship.** The multi-country data cover developed markets that survived. Markets that were wiped out, such as Russia after 1917 and China after 1949, are absent, so equity returns across countries are biased upward.
- **Short SGD history.** About 28 years of SGD data, with the ETF layer starting in November 2011. SGD-era results are in-sample.
- **Modelled series.**
  - SGS returns are built from benchmark yields, not a traded index.
  - The US bond proxy assumes a flat yield curve.
  - Expected returns come from the GDP-weighted global JST portfolio (1871–2020).
- **Costs and tax.**
  - Spreads are a single dated snapshot. Two of the three quotes come from a secondary source and are marked to_verify; a 5/15/30 bps sensitivity covers this.
  - The SGD→USD conversion cost isn't published and is excluded.
  - The fund's latest withholding rate is applied to the whole history.
- **Owner judgement.** The drawdown limits, the 5% tail level, the horizon profiles and the rebalancing-test margins are the owner's judgement calls, not results derived from data.
- **Not yet done.** The issuer annual-return cross-check for ETFs, ETF implementation tables per profile, and an independent methodology review.

## Before you start

- [uv](https://docs.astral.sh/uv/), which installs Python for you: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- The GitHub CLI [`gh`](https://cli.github.com/), signed in with `gh auth login` (needed to clone a private repo)
- git, with `user.name` and `user.email` set (`git config --global user.name "Your Name"`)

## How to reproduce

```bash
git clone https://github.com/azrinmahsuom/Multi-Asset-Allocation.git
cd Multi-Asset-Allocation
uv sync                  # create the environment
cp .env.example .env     # add any API keys (never committed)
uv run pytest            # check everything works
make all                 # download data, verify hashes, run the analysis end to end
```

`make all` regenerates [docs/evidence_review.md](docs/evidence_review.md), [docs/strategy_design.md](docs/strategy_design.md), [docs/backtest_results.md](docs/backtest_results.md) and every figure. Every number in this README comes from those generated files.

**One manual step.** Nareit's site blocks scripted downloads, so its file must be saved by hand before `make all`:

1. Download <https://www.reit.com/sites/default/files/returns/MonthlyHistoricalReturns.xls> in a browser (listed on [Nareit's monthly index page](https://www.reit.com/data-research/reit-indexes/monthly-index-values-returns)).
2. Save it as `data/raw/nareit/MonthlyHistoricalReturns.xls`.

If the file is missing, the pipeline stops and prints this URL. Nareit updates the file monthly, so a fresh copy may not match the SHA-256 in `data/MANIFEST.yaml`. If so, `make verify` reports it, and `make refresh` records the new version. The same applies to any source that updates in place.

On macOS, keep the project outside iCloud-synced folders (e.g. `~/Developer`). If it must live in `~/Documents`, put the environment in a folder iCloud skips: `uv venv .venv.nosync && ln -s .venv.nosync .venv && uv sync`.

## Repository layout

```
├── data/              Downloaded and processed data (git-ignored; MANIFEST.yaml records hashes)
├── docs/              Brief, decision log and the generated results documents
├── notebooks/         Exploration only; anything reusable moves to src/
├── reference/         Hand-researched inputs (fees, spreads, tax rates), each with source and date
├── reports/figures/   Figures referenced from the docs and this README
├── src/analysis/      Pipeline: sources, cleaning, metrics, evidence, design, backtest
└── tests/             Tests with small hand-checkable inputs
```

## Data sources

Each source's terms were checked on its own website (October 2026). No raw data is committed; `data/MANIFEST.yaml` records each file's URL, retrieval date, licence and SHA-256 hash.

| Source | What | Licence / terms |
|---|---|---|
| Robert Shiller online data (shillerdata.com) | US stocks, dividends, CPI, long rates, from 1871 | No licence stated; derived results only |
| Kenneth French Data Library | US and developed-market returns, from 1926 | No licence stated; derived results only |
| Aswath Damodaran, historical returns | US stocks, T-bills, T-bonds, Baa corporates, from 1928 | No licence stated; derived results only |
| Jordà-Schularick-Taylor Macrohistory Database, release R6 (consulted 2026-10-26) | Multi-country equity, bond, bill and housing total returns, 1870–2020 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), citation required (see Licences) |
| FRED | Treasury and TIPS yields, CPI, exchange rates, corporate yields | Public domain, except Moody's corporate yields (copyrighted) |
| Monetary Authority of Singapore | SGD interbank rates, SORA and SORA Index, SGS benchmark yields | MAS dataset terms: free to use and share with attribution. Source: MAS |
| SingStat | Singapore CPI | Licence terms still to be confirmed |
| SGX | A35 bid/ask snapshot | Quote data, cited by date |
| Fund and tax documents | Fund factsheets, audited annual reports and prospectuses (iShares, Amova); US–Ireland treaty and IRS publications; Irish Revenue manual; IRAS | Cited; documents not redistributed |
| Broker schedules | moomoo SG, OCBC and Interactive Brokers published fee pages | Cost data only; no broker is recommended |
| Nareit | FTSE Nareit US Real Estate Index Series, monthly from 1971 | All rights reserved; used privately to check the ETF data only; no published result is derived from it |
| Yahoo Finance (via `yfinance`) | ETF prices and distributions; two spread quotes | Personal use; derived results only |

## Licences

- **Code:** MIT ([LICENSE](LICENSE)).
- **Figures and tables derived from the Jordà-Schularick-Taylor Macrohistory Database:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), the licence of the source data ([terms](https://www.macrohistory.net/database/licence-terms/)). Each such figure says so in its caption. Release R6, consulted 2026-10-26. Cite as:
  - Òscar Jordà, Moritz Schularick, and Alan M. Taylor. 2017. "Macrofinancial History and the New Business Cycle Facts." In *NBER Macroeconomics Annual 2016*, volume 31, edited by Martin Eichenbaum and Jonathan A. Parker. Chicago: University of Chicago Press.
  - Òscar Jordà, Katharina Knoll, Dmitry Kuvshinov, Moritz Schularick, and Alan M. Taylor. 2019. "The Rate of Return on Everything, 1870–2015." *Quarterly Journal of Economics*, 134(3), 1225–1298. (Required by JST for any use of its rate-of-return data.)
- **Other sources:** credited by name. Their raw data is not republished.

## Built with AI assistance

This is my original project, built with AI assistance. All analysis choices and conclusions are my own, and every number comes from code in this repo or a cited source.

## Disclaimer

This is a personal research project built on publicly available data. It is not investment advice, not a recommendation to buy or sell any security, and does not represent the views of any employer. Any ETFs named are dated, illustrative examples identified by issuer and ticker only; naming a fund is not an endorsement of it, and no custodian or broker is recommended.
