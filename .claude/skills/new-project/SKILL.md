---
description: Project intake. Interviews the owner, writes docs/brief.md, and fills the README placeholders. Run once at the start of every new project.
disable-model-invocation: true
---

Run the intake for this new project.

1. Read `AGENTS.md`, `docs/brief.md` and `README.md`.
2. Ask the owner the brief's questions **one at a time**, in order. For each, show the question, a one-line example, and your suggested default where one exists. Wait for the answer before asking the next.
   - At every question, offer the option "accept the suggested defaults for all remaining questions". If chosen, fill the rest with the defaults, mark each as `Evidence: pending` where it sets a threshold or default, and list them under "Open questions".
   - After question 2, skip question 5 and question 14 for a Tool, and question 11 for Research.
   - Skip a question when an earlier answer already covered it (e.g. the benchmark is often given with the universe), and say which answer covered it.
   - If an answer is vague (e.g. "analyse REITs"), ask one follow-up to make it specific and testable. Don't ask more than one.
   - When an answer sets a threshold or default (costs, cut-offs, rates, minimum sizes), ask what evidence supports it. If there is none yet, record it as `Evidence: pending` and add it to "Open questions".
   - Never answer a question on the owner's behalf. The hypothesis in particular must be in their words.
3. Write the answers into `docs/brief.md`, replacing every `{{placeholder}}`. Anything the owner was unsure about goes under "Open questions".
4. Fill the README placeholders that the brief now answers (title, thesis line, question, universe/period, method, status "In progress", data sources). Replace `{{repo-name}}` with the GitHub repository name (from `git remote get-url origin`, or ask), not the local folder name, which can contain spaces. Leave the headline result, key findings and chart as `TBD`.
5. **Tool projects:** the brief and README are written for Research, so adapt them:
   - README: "One-line thesis" becomes "One line" (what the tool does and for whom); "Key findings" becomes "Latest run" (date run, and the output it produced).
   - Brief §6: Period is a rolling measurement window (e.g. "trailing 36 months to the latest month-end"), not a fixed start and end.
   - Brief §12: ask whether a risk-free rate is needed at all instead of defaulting one; write "not needed" if the tool doesn't compute excess returns.
6. Rename `{{One-line project description}}` in `pyproject.toml` to the goal.
7. Add a dated first entry to `docs/decisions.md` recording the scope, plus one entry per threshold or default set in the brief, each with its Rule and Evidence (or `Evidence: pending`).
8. Remove the "Start here" block from the top of `README.md`.
9. Keep the AI setup out of the project repo, so the published project shows no sign of AI assistance:
   - Append `AGENTS.md`, `CLAUDE.md` and `.claude/` to `.git/info/exclude` (local only, never committed).
   - Run `git rm -r --cached --quiet AGENTS.md CLAUDE.md .claude` so git stops tracking them; the files stay on disk and keep working.
   - Delete the "# Local tool settings" block from `.gitignore` (the exclude now covers it).
   - Check that `git ls-files` lists none of those paths and `git grep -niE "claude|anthropic|codex|AGENTS.md"` finds nothing, and tell the owner the result.
   - Tell the owner: the first commit (created from the template) still contains these files in history; a fresh clone of the project won't have them, so copy them back from the template when working on another machine.
10. Show a short summary of the brief, list any open questions, and propose the first two build steps. Ask before committing.
