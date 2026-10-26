# Multi-Asset Allocation for a Singapore-Dollar Investor

> **One-line thesis:** TBD (written once the evidence review and backtest are complete).

![CI](https://github.com/azrinmahsuom/Multi-Asset-Allocation/actions/workflows/ci.yml/badge.svg)

## Summary

| | |
|---|---|
| **Question** | Which long-horizon multi-asset allocation, built from low-cost ETFs, is best supported by evidence for an SGD-based investor, and which common allocation claims hold up when tested? |
| **Universe / period** | Global equities, government and inflation-linked bonds, investment-grade credit, REITs, cash; gold and commodities evaluated. Longest reliable public history per source (from 1870 for multi-country data), plus the ETF era for the implementable backtest. Annual, monthly and daily. |
| **Method** | Replicate 13 common claims against public data; compare five allocation methods (horizon glide path, global market-cap, minimum-variance, shrinkage mean-variance, risk parity); backtest in SGD net of costs, withholding tax and FX against a global 60/40, a global market-cap portfolio and 100% global equity. |
| **Headline result** | TBD |
| **Status** | In progress |

## Key findings

1. TBD
2. TBD
3. TBD

## Limitations

- TBD. Filled in from the evidence review, the decision log and the independent review.

## Before you start

- [uv](https://docs.astral.sh/uv/), which installs Python for you: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- The GitHub CLI [`gh`](https://cli.github.com/), signed in with `gh auth login` (needed to clone a private repo)
- git, with `user.name` and `user.email` set (`git config --global user.name "Your Name"`)

## Reproduce it

```bash
git clone https://github.com/azrinmahsuom/Multi-Asset-Allocation.git
cd Multi-Asset-Allocation
uv sync                  # create the environment
cp .env.example .env     # add any API keys (never committed)
uv run pytest            # check everything works
make all                 # download data, verify hashes, run the analysis end to end
```

**One manual step.** Nareit's site blocks scripted downloads, so its file must be saved by hand before `make all`:

1. Download <https://www.reit.com/sites/default/files/returns/MonthlyHistoricalReturns.xls> in a browser (listed on [Nareit's monthly index page](https://www.reit.com/data-research/reit-indexes/monthly-index-values-returns)).
2. Save it as `data/raw/nareit/MonthlyHistoricalReturns.xls`.

If the file is missing, the pipeline stops and prints this URL. Nareit updates the file monthly, so a fresh copy may not match the SHA-256 in `data/MANIFEST.yaml`. If so, `make verify` reports it, and `make refresh` records the new version.

On macOS, keep the project outside iCloud-synced folders (e.g. `~/Developer`). If it must live in `~/Documents`, put the environment in a folder iCloud skips: `uv venv .venv.nosync && ln -s .venv.nosync .venv && uv sync`.

## Repository layout

```
├── data/              Downloaded, processed and personal data (git-ignored, created by the code)
├── docs/              Project brief and methodology decision log
├── notebooks/         Exploration only; anything reusable moves to src/
├── reference/         Hand-researched inputs, each row with source and date checked (committed)
├── reports/           Final write-up and figures (committed)
├── src/analysis/      Reusable code: loading, cleaning, metrics, pipeline
└── tests/             Tests for the code in src/
```

## Data sources

Each source's terms were checked on its own website (October 2026). No raw data is committed; `data/MANIFEST.yaml` records each file's URL, retrieval date, licence and SHA-256 hash.

| Source | What | Licence / terms |
|---|---|---|
| Robert Shiller online data (shillerdata.com) | US stocks, dividends, earnings, CPI, long rates, from 1871 | No licence stated; derived results only |
| Kenneth French Data Library | US market and factor returns, from 1926 | No licence stated; derived results only |
| Aswath Damodaran, historical returns | US stocks, T-bills, T-bonds, Baa corporates, real estate, from 1928 | No licence stated; derived results only |
| Jordà-Schularick-Taylor Macrohistory Database, release R6 (consulted 2026-10-26) | Multi-country equity, bond, bill and housing total returns, 1870–2020 | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), citation required (see Licences) |
| FRED | Treasury and TIPS yields, CPI, USD/SGD, corporate yields | Public domain, except Moody's corporate yields (copyrighted) |
| Monetary Authority of Singapore | SGD interbank rates (1987–2013), SORA and SORA Index (2005 onwards) | MAS dataset terms: free to use and share with attribution. Source: MAS |
| Nareit | FTSE Nareit US Real Estate Index Series, monthly from 1971 | All rights reserved; no redistribution or derivative works without Nareit's written approval |
| Yahoo Finance (via `yfinance`) | REIT ETF prices and distributions | Personal use; derived results only |

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
