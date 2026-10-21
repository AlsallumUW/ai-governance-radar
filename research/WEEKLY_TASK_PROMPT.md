# Prompt for the daily Claude scheduled task (weekly rotation)

Schedule: every day at 06:00 Riyadh time (Asia/Riyadh). Each run starts a fresh session with this prompt and sweeps that day's group from `research/queue.json` → `sweep_days`.

---

You are running today's part of the weekly update of the AI Governance Radar repository (github.com/AlsallumUW/ai-governance-radar). Each day of the week sweeps one group of countries. All runs in a week share one branch and one pull request, which stays open for a person to review. Never merge it, and never push to `main`.

1. **Get the repository.** Clone it, or use the checkout in your working directory. Read `research/WEEKLY.md`, `research/PROTOCOL.md`, `research/BACKFILL.md` and `research/TRANSLATION_AR.md` in full. Follow WEEKLY.md step by step. PROTOCOL.md is the standard for every record and wins if anything disagrees.
2. **Work out the day and the week.**
   - `DAY=$(TZ=Asia/Riyadh date +%u)` gives 1 (Monday) to 7 (Sunday). `WEEK=$(TZ=Asia/Riyadh date +%G-W%V)`.
   - Today's group is the entry in `research/queue.json` → `sweep_days.days` whose `day` equals `DAY`.
   - Day 1 also covers every body in `data/regional/` (WEEKLY.md step 5), any open `update-request` issues and any deep reviews printed by `scripts/next_batch.py`.
3. **Branch** `update/week-$WEEK`.
   - If it already exists on origin, check it out and merge `origin/main` into it (keep both sides on conflicts).
   - Otherwise create it from `main`.
4. **Sweep today's group only** (WEEKLY.md step 4).
   - This is a change check, not a deep review: at most 5 minutes per country.
   - Run sub-agents in parallel, each taking a slice of the group. Give each one PROTOCOL.md in full and the rules below.
   - Set `coverage_audit.last_sweep` to today for every country checked.
5. **Day 1 only: regional bodies** (WEEKLY.md step 5). Keep CETS 225 `party_status` in `data/regional/COE.json` current.
   - For OECD, ICESCO, ALECSO, G7 and G20, check new or revised AI instruments on the body's own official site and membership changes; for the OECD, also new adherents to the AI Recommendation (update `adherents` and `applies_to` like CETS 225).
   - Retry each lead in `research/queue.json` → `sweep_days.monday_leads` once (Osaka G20 Leaders' Declaration, ALECSO 17 June 2025 approval, ICESCO adoption of the Riyadh Charter, League of Arab States AI texts on las.int).
6. **Retry and Convention 108 in today's group** (WEEKLY.md step 6).
   - Try each of today's countries that is on `retry` once, and record which now load and what changed.
   - Try each of today's countries on `pending_c108` once.
6b. **Every day, whatever today's group: closed consultations and the daily watch list** (WEEKLY.md step 4). These are not tied to any country's sweep day.
   - Run `python3 scripts/due_consultations.py --apply`.
   - Check every item in `research/queue.json` → `daily_watch` once, today, even if its country belongs to another day's group (for example SAU on a Wednesday). Follow the item's `look_for` and `where`.
   - In today's PR section, always include a line `**Daily watch:** <id> checked <date>: <what was found, or "no final version yet">`. Never write that an item was skipped because of the day.
7. **Commit each country** to the branch as soon as its sub-agent finishes, and push.
8. **Log, translate, validate** (WEEKLY.md step 8).
   - Run `python3 scripts/log_changes.py`.
   - **Arabic translations in the same PR:** every new or changed record (and new change events) gets its Arabic machine translation now. Run `python3 scripts/i18n_content.py extract <ISO3> ... > /tmp/work.json` for today's changed countries (and `_global` if needed), translate under `research/TRANSLATION_AR.md` using `research/aigr_arabic_terms.csv` terms exactly, then `python3 scripts/i18n_content.py apply /tmp/work.json`. Faithful translation only: never add, soften or strengthen legal effect; names, numbers and dates unchanged; never re-translate an official Arabic title.
   - Run `python3 scripts/validate.py` (0 errors required; missing or stale Arabic translations are errors), then `python3 scripts/build.py`. Commit and push.
9. **Pull request** (WEEKLY.md step 9).
   - If no open PR exists for `update/week-$WEEK`, open one titled `Weekly update $WEEK`.
   - If one exists, update its body: add or replace today's `## Day <DAY> (<weekday> <date>): <group>` section, keep the other days' sections, and refresh the week summary at the top.
   - Never merge.

Rules (full text in PROTOCOL.md and WEEKLY.md):

**Sources**
- Official documents only: the document itself, or the issuer's official page with the full text or a download link.
- Never sources: news agencies (including state agencies such as SPA and WAM), newspapers, aggregators, law-firm notes or social media. Use them only to discover documents.
- A third-party host counts only if the issuer's own page names it.
- An official copy hosted by another state body counts as official. This covers gazette copies and any other government document when the issuer's own site cannot be reached. Say where the copy is hosted in `current_status`.
- If no official text can be read, the item is a lead.

**Scope test**
- Include only instruments that govern, steer or set expectations for AI.
- These are leads, not records:
  - internal plans to use AI
  - passing mentions of AI
  - single institutions' internal policies
  - pending bills
  - announcements without a document
- Sector-wide rules from a regulator or ministry are records.
- National skills, training, education and curriculum frameworks issued by a national authority are records only if they are specifically about AI (or "data and AI"). General digital or ICT skills frameworks are leads.

**Court rules**
- Court and judicial-council AI rules are `administrative_policy_mandatory_in_scope` (binding on courts and court users only).

**Legal effect**
- Never infer legal effect. Strategies are not binding. Drafts are not adopted until an official source says so.

**Dates**
- Use only a date printed in the document or stated on the issuer's own page.
- Never use file metadata, file names, upload paths or CMS "last updated" stamps.
- Never use a date seen only in a search snippet.
- Effective dates may be computed from the instrument's own commencement clause and its official publication date, with the clause cited.
- No stated date means the item is a lead.

**Convention 108**
- Add a country to `applies_to` only from its own ratification or accession act. For countries that ratify by executive act, the official treaty series or foreign-ministry treaty record counts as the source.
- Otherwise keep the country on `pending_c108`.

**CETS 225**
- `signed` comes from the Council of Europe's official page.
- `ratified` only with the country's own ratification act as the source.

**Fetching**
- Fetch with curl (`--max-time 60`), then WebFetch. Mark a record located-only only after both fail.
- Every download has a 60–90 second limit.
- Spend at most 5 minutes per country in the sweep, and never more than 10 minutes on one site.
- Never download more than 100 gazette issues in one run.
- If a site blocks automated access, try the issuer's other official channels. If none works, leave the field null and list it under "Could not verify".

**Repository**
- Keep instrument ids stable.
- Do not edit `site/` or `scripts/`.
- If the run is interrupted and resumed, re-check every record written before the restart.

**Finish** with a short summary:
- the PR link
- the day and group
- countries swept, and countries not swept or stopped by the cap
- retry countries that now load
- Convention 108 or CETS 225 changes
- the number of government actions found
- records added
- the number of items needing review
- the number of texts translated into Arabic (and any skipped)
- the daily watch result for each item
