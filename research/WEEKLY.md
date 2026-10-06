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
3. **Sweep every country.** All 195 countries and every file in `data/regional/` are checked every week, not only those in `done`. Split the work into one sub-agent per wave in `queue.json` (9 waves) plus one for the regional bodies (EU, GCC, AU, ASEAN, CoE, UNESCO), and run them in parallel. For each country the sub-agent looks for anything published or changed since the country's last sweep (`coverage_audit.last_sweep`, or the last 30 days if unset):
   - new laws, regulations, strategies, guidance or consultations
   - drafts adopted, instruments entering into force, revisions, supersessions and repeals
   - where to look: the national AI body, the ICT ministry, the official gazette or legislation portal, and the data protection authority, plus one search in the official language and one in English: "<country> artificial intelligence <month year>"

   Records follow PROTOCOL §1 and §3 even for countries not yet deep-reviewed (official sources only; a new record in a country without a deep review keeps `verification_level` below `reviewed_primary_metadata` unless every field was checked). Add world events with exact dates. Set `coverage_audit.last_sweep` to today for every country checked, including those where nothing was found. A sub-agent that cannot finish its wave lists the countries it did not reach; the PR names them under **Not swept**.
4. **Validate and log**
   ```bash
   python3 scripts/validate.py          # must pass with 0 errors
   python3 scripts/log_changes.py       # writes change events vs origin/main
   python3 scripts/build.py             # must build
   ```
5. **Open the pull request.** Title: `Weekly update YYYY-MM-DD: <countries>`. The body must include:
   - the countries deep-reviewed, each with a one-line summary
   - the sweep result: countries swept, countries with findings, and **Not swept**
   - **Government actions found**: the list of new, revised, adopted and applied events
   - **Needs review**: auto-inferred events and anything uncertain
   - **Could not verify**: sources that were blocked or unclear
   - `validate.py` output (error and warning counts)

## Rules

- Official documents only (PROTOCOL §1): the document itself, or an official page with the full text or a download. No news agencies, press, aggregators or social media.
- Never mark something binding or in force without the official text saying so.
- Do not touch `site/` or `scripts/` in a weekly run. Propose tool changes in the PR description instead.
- Link checking runs separately in GitHub Actions every Monday (`.github/workflows/links.yml`).
