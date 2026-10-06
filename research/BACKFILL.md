# Backfill: deep-review every country

A one-off push to give all 195 countries a deep review, run from Claude Code (which can push to this repo). After the backfill, the weekly task's deep-review step only handles countries that need a re-review.

## How one run works

1. `git checkout main && git pull && git checkout -b backfill/$(date +%F)-<first country code>`
2. `python3 scripts/next_batch.py`: the countries for this run (one tier A country, or a batch of B/C countries; PROTOCOL §6).
3. One sub-agent per country, in parallel. Each gets PROTOCOL.md in full and its country file, and returns the completed file.
4. The lead: reads each file, runs `python3 scripts/validate.py` (0 errors), opens at least two `source_url`s per country, adds the countries to `done` in `queue.json`, then runs `log_changes.py` and `build.py`.
5. Commit, push, open one PR titled `Deep review: <countries>` with the WEEKLY.md body (countries with a one-line summary, government actions, needs review, could not verify). Do not merge.

## Running several at once

Runs touch different country files, so several can run side by side on separate branches. Only `queue.json` (`done`) and `data/changes-global.json` can conflict. When merging PRs one after another, resolve those by keeping both sides' entries. Three or four parallel runs is a sensible ceiling: it keeps the review load manageable.

## Prompt to paste into Claude Code

> Read research/BACKFILL.md, research/PROTOCOL.md and research/WEEKLY.md in full. Then do backfill runs one after another, following BACKFILL.md: each run takes the countries printed by scripts/next_batch.py, researches each country in its own sub-agent, validates, and opens its own PR. Before starting the next run, add the finished countries to `done` locally so next_batch.py moves on. Stop after <N> runs, or earlier if you are close to a usage limit, and give me a list of the PRs with the counts of instruments added and items under "Could not verify".
