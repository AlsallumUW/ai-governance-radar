# Weekly update routine

Run by the weekly Claude scheduled task (every Sunday, 06:00 Riyadh time), or by hand. One run produces **one pull request**. Nothing reaches the live site until a person merges it. The run never merges its own PR.

`research/PROTOCOL.md` is the standard for every record. `research/BACKFILL.md` holds the run mechanics (time limits, commit-per-country, restarts). The rules that matter most are summarised under **Rules** below. If this file and PROTOCOL.md ever disagree, PROTOCOL.md wins.

## Steps

1. **Setup**
   ```bash
   git checkout main && git pull
   git checkout -b update/$(date +%F)
   ```
2. **Deep reviews.** Run `python3 scripts/next_batch.py`. The backfill is finished, so it normally prints nothing. If it prints countries (for example after a country is added to `queue.json`), deep-review them under PROTOCOL.md in full:
   - fix or complete the existing records
   - for federal or devolved countries, run the subnational pass (PROTOCOL §2a, §6)
   - add missing instruments, including each ministry's and department's own AI documents (PROTOCOL §2)
   - fill the narrative and close every coverage category
   - set `narrative.last_deep_review` last
   - add the country to `done` in `queue.json`

   If a country cannot be finished, leave `last_deep_review` unset and explain why in the PR.
3. **Retry list (once each).** For every country in `queue.json` `retry`, try once to load the official sites that were blocked. Use `retry_notes` and the country's `coverage_audit.no_material_found_note` to see which sites and items they are. Try curl (`--max-time 60`, browser user agent), then WebFetch.
   - **A site now loads:** read the blocked items. Promote leads that pass the rules, upgrade `primary_source_located` records you can now read to `reviewed_primary_metadata`, and fix anything that does not match.
   - **The country now has at least 3 readable records and nothing listed in its `retry_notes` is still blocked:** remove it from `retry` and from `retry_notes`.
   - **Still blocked:** leave the country on `retry` and do not keep retrying in the same run.
   - **Report:** add a **Retry** section to the PR that lists each country with "now loads" (what changed) or "still blocked" (which sites).
4. **Pending Convention 108 (once each).** For every country in `pending_c108`, try once to read its own ratification or accession act (PROTOCOL §2b).
   - **The act is read:** add the country to the Convention 108 record's `applies_to` in `data/regional/COE.json`, add a source citing the act, and remove the country from `pending_c108`.
   - **Report:** list the result in the PR.
5. **Sweep every country.** All 195 countries and every file in `data/regional/` are checked every week. Split the work into one sub-agent per wave in `queue.json` (9 waves) plus one for the regional bodies (EU, GCC, AU, ASEAN, CoE, UNESCO), and run them in parallel. For each country the sub-agent looks for anything published or changed since the country's last sweep (`coverage_audit.last_sweep`, or the last 30 days if unset):
   - **What to look for:**
     - new laws, regulations, strategies, guidance or consultations
     - drafts adopted, instruments entering into force, revisions, supersessions and repeals
     - court and judicial-council AI rules
     - ministries' own AI documents
   - **Where to look:**
     - the national AI body, the ICT ministry, the official gazette or legislation portal, and the data protection authority
     - parliament's bill tracker for pending AI bills (they go to leads)
     - one search in the official language and one in English: "<country> artificial intelligence <month year>"
   - **Council of Europe (regional sub-agent):** check the CETS 225 signature and ratification list on the Council of Europe's official treaty pages and keep `party_status` in `data/regional/COE.json` current. Each entry is `signed` or `ratified`, with its source:
     - `signed`: the Council of Europe page is the source.
     - `ratified`: requires the country's own ratification act as the source (gazette, legislation portal or official treaty series). Until that act's publication is confirmed, keep the country `signed`, hold the act as a lead in the country file, and explain this in the `note` field.

   Records follow PROTOCOL §1 and §3. A new record keeps `verification_level` below `reviewed_primary_metadata` unless every field was checked against the official text. Add world events only for precise dates stated on an official source.

   Set `coverage_audit.last_sweep` to today for every country checked, including those where nothing was found. A sub-agent that cannot finish its wave lists the countries it did not reach; the PR names them under **Not swept**.
6. **Commit as you go.** Commit each country's file to the branch as soon as its sub-agent finishes (BACKFILL.md step 4), so an interruption such as a usage limit only loses unfinished countries. If the run is cut off and resumed, re-check every record written before the restart against its official text before the PR opens (BACKFILL.md step 5).
7. **Validate and log**
   ```bash
   python3 scripts/validate.py          # must pass with 0 errors
   python3 scripts/log_changes.py       # writes change events vs origin/main
   python3 scripts/build.py             # must build
   ```
8. **Open the pull request.** Title: `Weekly update YYYY-MM-DD`. Do not merge it. The body must include:
   - the countries deep-reviewed (if any), each with a one-line summary
   - **Retry**: each `retry` country, "now loads" (with what changed) or "still blocked"
   - **Convention 108**: each `pending_c108` country and the result, plus any CETS 225 status changes
   - the sweep result: countries swept, countries with findings, and **Not swept**
   - **Government actions found**: new, revised, adopted and applied events
   - **Records added / moved to leads**, per country
   - **Needs review**: auto-inferred events and anything uncertain
   - **Could not verify**: sources that were blocked or unclear
   - `validate.py` output (error and warning counts)

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
