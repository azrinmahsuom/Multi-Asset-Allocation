<!-- START HERE (removed by /new-project)
New project from the template? Clone the repo, open the folder in VS Code, then start a *new* Claude Code session in it before running /new-project.
(Project skills don't load in a session started before the folder existed.)
It interviews you, writes docs/brief.md and fills in this README. Delete this block once done. -->

# {{Project Title}}

> **One-line thesis:** {{e.g. "Singapore REITs with sub-35% gearing outperformed the index on a risk-adjusted basis, 2015–2025."}}

![CI](https://github.com/azrinmahsuom/{{repo-name}}/actions/workflows/ci.yml/badge.svg)

## Summary

| | |
|---|---|
| **Question** | {{What are you trying to find out?}} |
| **Universe / period** | {{e.g. SGX-listed REITs, Jan 2015 – Dec 2025, monthly}} |
| **Method** | {{e.g. factor screen + backtest, DCF, regression}} |
| **Headline result** | {{One number with context, e.g. "Sharpe 0.82 vs 0.51 benchmark, net of 20 bps costs"}} |
| **Status** | {{In progress / Complete}} |

## Key findings

1. {{Finding, with the chart that shows it}}
2. {{Finding}}
3. {{What surprised you, or what didn't work}}

![Headline chart](reports/figures/headline.png)

## Limitations

Be specific.

- {{e.g. Survivorship bias: universe is today's constituents}}
- {{e.g. No transaction costs below monthly rebalancing}}
- {{e.g. Small sample: 11 years, one rate cycle}}

## Before you start

- [uv](https://docs.astral.sh/uv/), which installs Python for you: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- The GitHub CLI [`gh`](https://cli.github.com/), signed in with `gh auth login` (needed to clone a private repo)
- git, with `user.name` and `user.email` set (`git config --global user.name "Your Name"`)

## Reproduce it

```bash
git clone https://github.com/azrinmahsuom/{{repo-name}}.git
cd {{repo-name}}
uv sync                  # create the environment
cp .env.example .env     # add any API keys (never committed)
uv run pytest            # check everything works
uv run python -m analysis.pipeline   # run the analysis end to end
```

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

| Source | What | Licence / terms |
|---|---|---|
| {{e.g. Yahoo Finance via yfinance}} | {{Daily prices}} | {{Personal, non-commercial use}} |

## Disclaimer

This is a personal research project built on publicly available data. It is not investment advice, not a recommendation to buy or sell any security, and does not represent the views of any employer.
