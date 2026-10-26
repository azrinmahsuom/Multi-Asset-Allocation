---
description: Re-download source data, rerun the pipeline, and report how the results changed versus the README.
disable-model-invocation: true
---

Refresh this project's data and results.

1. Read `docs/brief.md` (sections 8 and 11) and the Layout section of `AGENTS.md`.
2. Ask before downloading anything large or anything needing an API key.
3. Re-download the raw data using the project's download functions, then run `uv run python -m analysis.pipeline` and `uv run pytest`.
4. Update the "Pulled on" dates in the Data and sources table in `docs/brief.md` §8.
5. List the files in `reference/` with their oldest `checked_on` date and any `to_verify` rows, so the owner can decide what to re-check by hand. Don't change their dates yourself.
6. Compare the new headline numbers with those in `README.md` and show a before/after table. Flag any change large enough to alter a conclusion.
7. Don't edit the README's results yourself; suggest running `/write-readme` if they changed.
