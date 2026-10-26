---
description: Rewrite README.md from the project's actual computed results, and draft the row for the owner's GitHub profile README. Use when results are final or have changed.
disable-model-invocation: true
---

Update the README so it reflects what the code actually produces.

1. Read `docs/brief.md`, `docs/decisions.md` and the current `README.md`.
2. Run `uv run python -m analysis.pipeline` and `uv run pytest`. If either fails, stop and report; never write numbers you didn't just compute.
3. Rewrite `README.md`, keeping its section structure:
   - **Thesis line and Headline result:** one number with context (period, benchmark, after costs).
   - **Key findings:** 3 or fewer, each tied to a figure in `reports/figures/`. Include at least one thing that didn't work or surprised you.
   - **Limitations:** specific, taken from the brief, the decision log and any `/bias-check` findings.
   - **Status:** Complete or In progress.
   - Keep the disclaimer unchanged.
4. Write for a reader skimming for 60 seconds: lead with the answer, no jargon without a gloss, no hype words.
5. Show the diff and ask before committing.
6. Finally, draft the row for the profile README at github.com/azrinmahsuom/azrinmahsuom, in this format, and show it to the owner to paste in:

   `| [repo-name](https://github.com/azrinmahsuom/repo-name) | Question in one line | Headline result |`
