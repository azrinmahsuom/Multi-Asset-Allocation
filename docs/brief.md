# Project brief

Filled in at the start of the project and read before every task. Update it whenever the scope changes, and log why in `docs/decisions.md`.

## 1. Name
{{Repo name, e.g. etf-domicile-tax-drag}}

## 2. Type
{{Research (answers a question once) or Tool (runs repeatedly)}}

## 3. Goal
{{In plain language: what question does this answer, or what problem does it solve?}}

## 4. Audience
{{Who uses the output? e.g. "Me", or the real users of the tool.}}

## 5. Hypothesis (research only)
{{What you expect to find, and why. Written before seeing any results.}}

## 6. Universe, period, frequency, currency
- Universe: {{e.g. Irish- and US-domiciled S&P 500 ETFs}}
- Period: {{Research: start to end · Tool: rolling measurement window, e.g. "trailing 36 months to the latest month-end"}}
- Frequency: {{daily / monthly}}
- Currency: {{SGD / USD}} · Returns: {{total / price-only}}

## 7. Benchmark
{{What results are compared against.}}

## 8. Data and sources
One source per line, with whether results derived from it can be published. Update "Pulled on" each time the data is re-downloaded. Hand-researched inputs live in `reference/` instead, with their own `checked_on` dates.

| Data | Source | Script | Pulled on | Publishable? |
|---|---|---|---|---|
| {{Daily prices}} | {{yfinance}} | {{`analysis.data.download_prices`}} | {{YYYY-MM-DD}} | {{Yes, derived results}} |

## 9. Processing steps
1. {{Step}}
2. {{Step}}

## 10. Outputs
{{e.g. README with headline chart; reports/figures/*.png; summary table}}

## 11. Run cadence (tool only)
{{How often it runs and who starts it, e.g. "by hand, quarterly".}}

## 12. Limits, assumptions and things to avoid
Each threshold or default cites its evidence, or says `Evidence: pending` (and is listed under Open questions).
- Transaction costs: {{e.g. measured from bid-ask spreads; fallback 10 bps per side, Evidence: pending}}
- Risk-free rate: {{3M SORA / 3M T-bill, or "not needed" for a Tool that doesn't compute excess returns}}
- {{Other constraints}}

## 13. How we know the code is correct
{{e.g. metrics match a hand calculation on a 3-row example; totals reconcile to source}}

## 14. What would show the hypothesis is wrong
{{The specific result that would change your conclusion.}}

## 15. Open questions
- {{Anything still undecided. Add to this list instead of assuming.}}
