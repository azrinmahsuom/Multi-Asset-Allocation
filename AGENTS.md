# AGENTS.md

Shared instructions for any coding agent working in this repository (Claude Code reads this through `CLAUDE.md`; Codex reads it directly). Read it at the start of every session, then read `docs/brief.md`.

## What this repo is

A public investment project by Azrin Mahsuom, CFA. The README must stand on its own for anyone reading it on GitHub, and every number in it must be reproducible from the code.

`docs/brief.md` is the source of truth for this project's goal, scope, method and success criteria. If it still contains `{{placeholders}}`, stop and suggest running `/new-project` before writing any analysis code.

## Hard rules

1. **Public data only.** Never use files that look like they came from an employer, client or internal system (client names, account numbers, internal identifiers, firm templates or letterheads). If unsure, stop and ask.
2. **No secrets in code, output or commits.** API keys come from `.env` via `analysis.config.get_secret`. Never print, log or hardcode them, and never read `.env` directly.
3. **Never commit data files.** Everything under `data/` is git-ignored. Code must be able to re-download or regenerate `data/raw/` and `data/processed/`; `data/external/` holds personal inputs supplied by the owner and is never published.
4. **No look-ahead bias.** A signal at time t uses only data available at t. Lag fundamentals by their publication delay. If you can't guarantee this, say so explicitly.
5. **No survivorship bias without disclosure.** If the universe is today's constituents, state it in the README's Limitations.
6. **Never fabricate numbers.** Every figure in the README or reports must come from running the code. If it hasn't been computed, write `TBD`.
7. **Stay within the brief.** If a request goes beyond `docs/brief.md`, point it out and ask whether to update the brief first. Add anything unresolved to its "Open questions" section rather than silently assuming.
8. **Every decision is rule-based and evidence-backed.** Each methodology choice, threshold and default is written as an explicit rule the code applies mechanically (no case-by-case judgement), and cites the research or data that supports it in `docs/decisions.md`. If no evidence has been found yet, mark the rule `Evidence: pending` and add it to the brief's Open questions; never present an unsupported choice as settled.

## How to work with the owner

- The owner reads Python but writes little of it. After each change, explain in two or three plain sentences what changed and why, and point to the file and function.
- Run tests and lint freely. **Ask before** installing packages, downloading large datasets, committing, or pushing.
- When making a methodology choice, add a dated entry to `docs/decisions.md` with its Rule and Evidence.

## Layout

The root `README.md` is the only README. Folder rules live here.

- `src/analysis/`: all reusable logic. Small functions, type hints, docstrings.
  - `config.py` paths and settings · `data.py` load/clean · `metrics.py` returns and risk · `pipeline.py` end-to-end run
- `data/`: git-ignored; the code creates the folders it needs.
  - `raw/` downloads exactly as received. Never edit by hand.
  - `processed/` cleaned, analysis-ready outputs, written only by `src/analysis/`.
  - `external/` personal inputs that must not be published (e.g. holdings).
  - Record each downloaded source, the script that pulls it and the date pulled in the Data and sources table in `docs/brief.md` §8.
- `reference/`: committed, hand-researched inputs that code can't regenerate (e.g. fee schedules, tax rates, candidate lists), as CSV. Every row has a `source` (link or document), a `checked_on` date (YYYY-MM-DD) and a `status`: `verified` (checked against a primary document) or `to_verify` (secondary source only). Results that depend on `to_verify` rows say so.
- `notebooks/`: exploration and scratch work only, named `NN-short-description.ipynb` (e.g. `01-explore-prices.ipynb`).
  - Import from `src/analysis` rather than redefining functions. Code needed twice moves to `src/analysis/` with a test.
  - Clear outputs of large dataframes before committing.
  - Final results belong in `reports/`, not in a notebook. Start JupyterLab with `uv run jupyter lab`.
- `reports/`: final, reader-facing output, committed.
  - `report.md` is the full write-up (optional; for short projects the root README is enough).
  - `figures/` PNG charts referenced from the README, saved at 150–200 dpi, 1200px wide.
- `docs/brief.md` project intake · `docs/decisions.md` methodology log.
- `tests/`: a test for every function in `metrics.py`, using small hand-checkable inputs.

## Commands

```bash
uv sync                         # install / update environment
uv add <package>                # add a dependency (never pip install)
uv run pytest                   # tests
uv run ruff check . --fix       # lint
uv run ruff format .            # format
uv run python -m analysis.pipeline
```

Run tests and lint before saying any task is done.

## Finance conventions

- Simple returns for portfolio aggregation; log returns only when stated. Annualise with the right periods (252 daily, 52 weekly, 12 monthly).
- State the currency, whether returns are total or price-only, and the risk-free rate and its source. Fallback unless the brief says otherwise (Evidence: pending until the project cites a source): SGD with 3M SORA, or USD with 3M T-bill.
- Backtests include transaction costs and state the rebalancing rule. Fallback when measured costs are missing (Evidence: pending until the project cites a source): 10 bps per side.
- Always compare against the benchmark named in the brief.
- Charts: a title that states the takeaway, labelled axes with units, the period, and a source line.

## Git

- Small commits with imperative messages: `Add drawdown metric`, `Fix dividend adjustment in loader`.
- While the repo is private, commit to `main`. Once public, use a branch and pull request for anything beyond a small fix.
- Never force-push to `main`.
- No AI attribution anywhere in the project: no `Co-Authored-By` or "Generated with" lines in commits or pull requests, and no mention of AI tools in the README, reports, code or comments.
- `AGENTS.md`, `CLAUDE.md` and `.claude/` are kept out of project repos (via `.git/info/exclude`, set up by `/new-project`). Never commit them or refer to them in committed files.
