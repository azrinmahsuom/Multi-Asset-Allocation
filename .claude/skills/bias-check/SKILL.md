---
description: Review the analysis code and results for look-ahead bias, survivorship bias, data snooping and other methodology flaws, checked against docs/brief.md. Use before publishing results or when a result looks too good.
---

Review this project's methodology as a sceptical investment committee member would. Read `docs/brief.md`, `docs/decisions.md`, everything in `src/analysis/`, and the README.

Check for, and cite file and line for each finding:

1. **Look-ahead bias**: signals using data not available at the time (unlagged fundamentals, restated data, same-bar execution on close prices).
2. **Survivorship bias**: universe built from current constituents; delisted securities missing.
3. **Data snooping**: parameters tuned on the full sample with no out-of-sample period; many variants tried but only the best reported.
4. **Costs and frictions**: missing or unrealistic transaction costs, taxes, FX conversion, or withholding tax where relevant.
5. **Benchmark fairness**: wrong benchmark, price vs total return mismatch, currency mismatch.
6. **Statistics**: annualisation errors, too few independent observations, results driven by one period or one security.
7. **Brief drift**: anything the code does that the brief doesn't describe, or brief items not yet implemented.
8. **Falsification**: does the evidence actually test the "what would show the hypothesis is wrong" criterion in the brief?

Output a table: Issue · Severity (High / Medium / Low) · Evidence · Fix. Lead with the most serious. If there are no High issues, say plainly that the methodology is sound enough to publish. Don't change any code; propose fixes and ask which to apply.
