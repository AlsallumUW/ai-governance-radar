# Prompt for the weekly Claude scheduled task

Schedule: every Sunday at 06:00 Riyadh time (Asia/Riyadh). Each run starts a fresh session with this prompt.

---

You are running the weekly update of the AI Governance Radar repository: github.com/AlsallumUW/ai-governance-radar. The goal is one pull request with this week's changes, left open for a person to review. Never merge it.

1. **Get the repository.** Clone it, or use the checkout in your working directory, and update `main`. Read in full: `research/WEEKLY.md`, `research/PROTOCOL.md` and `research/BACKFILL.md`. Follow WEEKLY.md step by step. PROTOCOL.md is the standard for every record and wins if anything disagrees.
2. **Create the branch** `update/<YYYY-MM-DD>` (today's date) from `main`.
3. **Deep reviews:** run `python3 scripts/next_batch.py` and deep-review any countries it prints (WEEKLY.md step 2). It normally prints nothing.
4. **Retry list:** try every country in `research/queue.json` `retry` once (WEEKLY.md step 3). Record which ones now load and what changed. Leave the rest on `retry`.
5. **Pending Convention 108:** try every country in `pending_c108` once (WEEKLY.md step 4).
6. **Weekly sweep:** cover all 195 countries and the regional bodies (WEEKLY.md step 5). Use one sub-agent per wave plus one for the regional bodies, in parallel. Each sub-agent gets PROTOCOL.md in full and the rules below. Keep CETS 225 `party_status` in `data/regional/COE.json` current. Set `coverage_audit.last_sweep` for every country checked.
7. **Commit each country** to the branch as soon as its sub-agent finishes.
8. **Validate:** run `python3 scripts/validate.py` (0 errors required), then `python3 scripts/log_changes.py`, then `python3 scripts/build.py`.
9. **Push and open the PR.** Push the branch and open one pull request titled `Weekly update <YYYY-MM-DD>`, with the body described in WEEKLY.md step 8. Do not merge it.

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
- Otherwise keep it on `pending_c108`.

**CETS 225**
- `signed` comes from the Council of Europe's official page.
- `ratified` only with the country's own ratification act as the source.

**Fetching**
- Fetch with curl (`--max-time 60`), then WebFetch. Mark a record located-only only after both fail.
- Every download has a 60–90 second limit.
- Never spend more than 10 minutes on one site.
- Never download more than 100 gazette issues in one run.
- If a site blocks automated access, try the issuer's other official channels (gazette, consultation portal, other official pages). If none works, leave the field null and list it under "Could not verify".

**Repository**
- Keep instrument ids stable.
- Do not edit `site/` or `scripts/`.
- If the run is interrupted and resumed, re-check every record written before the restart.

**Finish** with a short summary:
- the PR link
- countries deep-reviewed
- retry countries that now load
- Convention 108 or CETS 225 changes
- the number of government actions found
- records added
- the number of items needing review
- countries not swept
