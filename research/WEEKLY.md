# Weekly update routine

Run by the weekly Claude scheduled task, or by hand. One run produces **one pull request**. Nothing reaches the live site until a person merges it.

## Steps

1. **Setup**
   ```bash
   git checkout main && git pull
   git checkout -b update/$(date +%F)
   ```
2. **Deep-review batch.** Run `python3 scripts/next_batch.py` to get this run's countries (one tier A country, or a batch of tier B/C countries; see PROTOCOL §6). Apply `research/PROTOCOL.md` in full to each one:
   - fix or complete the existing records
   - for federal or devolved countries, run the subnational pass (PROTOCOL §2a)
   - add missing instruments
   - fill the narrative
   - close every coverage category
   - set `narrative.last_deep_review`
   - add the country to `done` in `queue.json`

   If a country cannot be finished, leave `last_deep_review` unset and explain why in the PR.
3. **Sweep for news.** Countries already in `done` get a quick check for anything new since their last review: new laws, drafts adopted, documents entering into force, revisions, and superseded or repealed instruments. Search each country's AI body and gazette, and run a general "<country> artificial intelligence regulation <month year>" search. Update the records and add world events with exact dates.
4. **Validate and log**
   ```bash
   python3 scripts/validate.py          # must pass with 0 errors
   python3 scripts/log_changes.py       # writes change events vs origin/main
   python3 scripts/build.py             # must build
   ```
5. **Open the pull request.** Title: `Weekly update YYYY-MM-DD: <countries>`. The body must include:
   - the countries deep-reviewed, each with a one-line summary
   - **Government actions found**: the list of new, revised, adopted and applied events
   - **Needs review**: auto-inferred events and anything uncertain
   - **Could not verify**: sources that were blocked or unclear
   - `validate.py` output (error and warning counts)

## Rules

- Official documents only (PROTOCOL §1): the document itself, or an official page with the full text or a download. No news agencies, press, aggregators or social media.
- Never mark something binding or in force without the official text saying so.
- Do not touch `site/` or `scripts/` in a weekly run. Propose tool changes in the PR description instead.
- Link checking runs separately in GitHub Actions every Monday (`.github/workflows/links.yml`).
