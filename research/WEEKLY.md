# Weekly update routine (daily rotation)

The scheduled task runs **every day at 06:00 Riyadh time**. Each run sweeps one day's group of countries, so all 195 countries and the regional bodies are covered once a week. All seven runs of a week commit to the same branch and the same pull request. Nothing reaches the live site until a person merges that PR. A run never merges it.

`research/PROTOCOL.md` is the standard for every record. `research/BACKFILL.md` covers run mechanics: time limits, commit-per-country and restarts. The **Rules** section below summarises both. If this file and PROTOCOL.md ever disagree, PROTOCOL.md wins.

## The rotation

`research/queue.json` → `sweep_days.days` lists seven groups, balanced by workload (tier A = 3, B = 1, C = 0.5; regional bodies count 1 each):
- Day 1 = Monday … Day 7 = Sunday (ISO weekday in Asia/Riyadh).
- Day 1 is GCC + MENA and also carries the regional bodies: EU, GCC, AU, ASEAN, CoE and UNESCO.
- Today's group comes from `TZ=Asia/Riyadh date +%u` (1–7).
- The week is the ISO week: `TZ=Asia/Riyadh date +%G-W%V`, for example `2026-W43`.

## Steps (each daily run)

1. **Pick the day and the week.**
   ```bash
   DAY=$(TZ=Asia/Riyadh date +%u)          # 1 = Monday ... 7 = Sunday
   WEEK=$(TZ=Asia/Riyadh date +%G-W%V)     # e.g. 2026-W43
   BR=update/week-$WEEK
   ```
   Today's group is the entry in `sweep_days.days` whose `day` equals `$DAY`.
2. **Branch.** If `origin/$BR` exists, check it out and merge `origin/main` into it. On conflicts keep both sides; `research/queue.json` and `data/changes-global.json` are the usual ones. Otherwise create `$BR` from `main`.
   ```bash
   git fetch origin
   if git ls-remote --exit-code --heads origin "$BR" >/dev/null; then
     git checkout -B "$BR" "origin/$BR" && git merge origin/main
   else
     git checkout -B "$BR" origin/main
   fi
   ```
3. **Deep reviews (Day 1 only).** Run `python3 scripts/next_batch.py`. The backfill is finished, so it normally prints nothing. If it prints countries, deep-review them under PROTOCOL.md in full and add them to `done`. If a country cannot be finished, leave `last_deep_review` unset and say why in the PR.
4. **Sweep today's group.** This is a change check, not a deep review: **at most 5 minutes per country**. Run sub-agents in parallel, each taking a slice of the group. For each country, look for anything published or changed since `coverage_audit.last_sweep` (or the last 30 days if unset).
   - **What to look for:**
     - new laws, regulations, strategies, guidance or consultations
     - drafts adopted, instruments entering into force, revisions, supersessions, repeals
     - new court or judicial-council AI rules
     - ministries' own AI documents
   - **Where to look:**
     - the national AI body, the ICT ministry, and the official gazette or legislation portal
     - the data protection authority
     - parliament's bill tracker (pending bills go to leads)
     - one search in the official language and one in English: "<country> artificial intelligence <month year>"
   - **What to record:**
     - add or update records under PROTOCOL §1, §3 and §4
     - add world events only for precise dates stated on an official source
     - set `coverage_audit.last_sweep` to today for every country checked, including those with no findings
   - **If the 5-minute cap stops a country:** note what was not checked and move on.
5. **Regional bodies (Day 1 only).** Sweep `data/regional/*.json` the same way. Also keep the CETS 225 `party_status` in `data/regional/COE.json` current:
   - `signed` comes from the Council of Europe's official treaty page.
   - `ratified` needs the country's own ratification act as the source (gazette, legislation portal or official treaty series). Until the act's publication is confirmed, keep the country `signed`, hold the act as a lead in the country file, and explain in `note`.
6. **Retry and Convention 108 for today's group.** Retry countries are tried here once, beyond the 5-minute sweep.
   - **Retry:** for each country in today's group that is on `retry`, try once to load the blocked official sites. `retry_notes` and `coverage_audit.no_material_found_note` list them. Use curl (`--max-time 60`, browser user agent), then WebFetch.
     - **A site now loads:** read the blocked items, promote leads that pass the rules, upgrade `primary_source_located` records you can now read, and fix anything that does not match.
     - **When to remove a country from `retry` and `retry_notes`:** only once it has at least 3 readable records and nothing in its retry note is still blocked.
     - **Report:** record "now loads" (what changed) or "still blocked" (which sites).
   - **Convention 108:** for each country in today's group that is on `pending_c108`, try once to read its own ratification or accession act (PROTOCOL §2b). If it is read, add the country to the Convention 108 record's `applies_to` in `data/regional/COE.json`, cite the act as a source, and remove it from `pending_c108`.
7. **Commit as you go.** Commit each country's file to `$BR` as soon as its sub-agent finishes, and push. An interruption then loses only unfinished countries. If a run is cut off and resumed, re-check every record written before the restart against its official text before updating the PR (BACKFILL.md step 5).
8. **Validate and log.**
   ```bash
   python3 scripts/validate.py          # must pass with 0 errors
   python3 scripts/log_changes.py       # writes change events vs origin/main
   python3 scripts/build.py             # must build
   ```
   Commit and push.
9. **Pull request.** One PR per week, titled `Weekly update <WEEK>` (for example `Weekly update 2026-W43`), from `$BR` to `main`. Never merge it.
   - **No open PR for `$BR` yet:** open it with today's results.
   - **PR already open:** update its body. Add or replace today's section and keep earlier days' sections unchanged.
   - **Today's section** is headed `## Day <DAY> (<weekday> <YYYY-MM-DD>): <group name>` and contains:
     - countries swept, and countries with findings
     - **Not swept** (or stopped by the 5-minute cap, with what was not checked)
     - **Government actions found**: new, revised, adopted and applied events
     - **Records added / moved to leads**, per country
     - **Retry**: each retry country in the group, "now loads" (with what changed) or "still blocked"
     - **Convention 108 / CETS 225**: results for the group's `pending_c108` countries and, on Day 1, any CETS 225 status change
     - **Needs review** and **Could not verify**
     - `validate.py` output (error and warning counts)
   - **Week summary at the top of the body:** keep a short list of which days have run so far, with totals of actions found and records added.

## Rules

**Sources (PROTOCOL §1)**
- Official documents only: the document itself, or an official page of the issuer with the full text or a download link.
- Never sources: news agencies (including state agencies such as SPA, WAM, QNA, BNA, KUNA and ONA), newspapers, aggregators (OECD.AI, regulations.ai, Digital Policy Alert), law-firm notes, social media. Use them only to discover documents.
- A file hosted by a third party counts only if the issuer's own official page names that host.
- Central-government publication portals count for that government's own bodies.
- An official copy hosted by another state body counts as official. This covers gazette copies (for example on a central bank's site or a state-run legal information institute) and any other government document when the issuer's own site cannot be reached. Say in `current_status` where the copy is hosted.
- Regulator decisions cite the decision itself, not the press release.
- If a document exists but no official text can be read, record it as a lead, not an instrument.

**Scope test (PROTOCOL §1)**
- An instrument is included only if it governs, steers or sets expectations for AI.
- These go to leads, not records:
  - an institution's internal plan to use AI
  - a general instrument that mentions AI only in passing
  - a single institution's internal policy (for example one university's AI-use policy)
  - pending bills
  - announcements without a document
- Sector-wide rules from a regulator or ministry are records.
- **AI skills and education frameworks:** national skills, training and education standards frameworks, including national curriculum frameworks, issued by a national authority are records only if they are specifically about AI (or explicitly "data and AI"). General digital or ICT skills frameworks that mention AI in passing are leads, and so are other curricula.

**Classification (PROTOCOL §3)**
- Court and judicial-council AI rules (practice directions, notices, judicial codes) are `administrative_policy_mandatory_in_scope`: binding on courts and court users only, not general regulations.
- A strategy is not binding.
- A draft is not adopted until an official source says so.
- Never mark something binding or in force without the official text saying so.

**Dates (PROTOCOL §4)**
- Use only a date printed in the document or stated on the issuer's own page (gazette date, launch notice, "first published" date). A year printed in the title or on the cover gives a year-only date.
- Never use file metadata: PDF creation or modification dates, file names, upload paths, CMS "last updated", "created" or post dates.
- Never use a date that comes only from a search-engine snippet or a rendering of a page you could not read.
- Effective dates computed from the instrument's own commencement clause and its official publication date are allowed. Cite the clause in `current_status` (for example "computed from art. X: in force N days after publication on YYYY-MM-DD").
- A signing date is not an effective date unless a commencement clause makes it one.
- No stated date: the item goes to leads with the note "official document on <site>; no stated publication date".

**Convention 108 and CETS 225 (PROTOCOL §2b)**
- A country joins the Convention 108 record's `applies_to` only when its own ratification or accession act is read in its gazette or legislation portal.
- For countries that ratify by executive act, the government's official treaty series or foreign-ministry treaty record counts as the source.
- Countries whose act cannot be read stay on `pending_c108`.
- CETS 225 `party_status` rules are under step 5 above.
- Never copy a regional instrument into a country file. A country's own implementing law is a national record.

**Fetching and download limits (BACKFILL.md)**
- Two fetch methods: curl (`--max-time 60`, browser user agent), then WebFetch. Mark a record `primary_source_located` only after both fail, and say so in `check_method`.
- Every download has a 60–90 second limit.
- Never wait more than 10 minutes on one site.
- Use a gazette's own search instead of bulk-downloading. Never download more than 100 gazette issues in one run.
- Leave no background loops running.

**Run mechanics**
- Commit each country as it finishes.
- Keep instrument ids stable: edit records in place.
- Do not touch `site/` or `scripts/` in a weekly run. Propose tool changes in the PR description instead.
- Link checking runs separately in GitHub Actions every Monday (`.github/workflows/links.yml`).
