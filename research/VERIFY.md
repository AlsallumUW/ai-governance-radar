# Source re-verification (campaign started 27 October 2026)

Goal: every record on the site re-checked against its official source, field by field. A sample check on 27 October found at least one wrong detail in about 3 of every 10 records that could be reached (wrong article, past-due wording, unsupported claim, missed amendment, decree date used as publication date).

Run by the daily scheduled task "AIGR source re-verification", or by hand. One run handles about 60 records (`records_per_run` in `research/verify_queue.json`), finishing whole jurisdictions. Nothing reaches the live site until a person merges the pull request.

## Each run

1. **Setup.** Fetch `main`. Branch `verify/<ISO year>-W<week>`: create it from `main`, or check it out and merge `origin/main` into it.
2. **Pick the work.** Take jurisdictions from `order` in `research/verify_queue.json` that are not in `done`, in order, until about 60 records are covered.
3. **Check every record** of each jurisdiction against the official source (`source_url`, `official_pdf_url`):
   - `official_title`, `english_title` (right document, accurate translation)
   - `issuing_authority` (the issuing body only; no act numbers, dates or approval notes — PROTOCOL rule 6)
   - `publication_date` (date of official publication; a decree or signature date is not a publication date unless the source says so), `effective_date`, `last_amended_date`
   - `legal_status` and `lifecycle` ("in force" only for binding texts; check for repeal, replacement or amendment since the record was made)
   - every concrete fact in `current_status` and `summary` (dates, article numbers, deadlines, who it binds). Remove anything the official text does not support.
4. **How to reach sources.** WebFetch first. If the site blocks the cloud (Gulf government sites, Légifrance, pravo.gov.ru, law.go.kr, many gazettes), use the built-in browser on Faisal's computer (request site access, read the page text; for PDFs, load pdf.js from cdnjs in the page and extract the text). Gazettes that work in the browser are listed in research/STATUS notes (Moniteur belge, adilet, cbd.minjust.gov.kg, qavanin.ir, peraturan.bpk.go.id, Asamblea SV PDFs, El Peruano). If a source still cannot be read after two tries, add `{"id": <jurisdiction>, "instrument_id": ..., "url": ..., "date": <today>}` to `unreachable` and move on. Never use news, law firms, aggregators or search snippets as evidence.
5. **Fix in place.** Keep instrument ids. Every changed English text gets its Arabic updated in `data/i18n/ar/` with the new `src` hash (Arabic first, glossary terms, "" quotes). Public wording rules (PROTOCOL §5): no research steps, no unofficial sources; unverified points read "Not yet verified from the official text: …" / "لم يُتحقَّق بعد من النص الرسمي: …". For each record checked, set `verification_date` to today.
6. **Government actions.** If the check finds a real dated action (amendment, entry into force, repeal), add the world event by hand with the official source and `needs_review: false`.
7. **Close out.** Add each finished jurisdiction to `done` (`{"id": ..., "date": ..., "records": n, "corrected": n}`). Commit per jurisdiction. Run `python3 scripts/validate.py` (0 errors), `python3 scripts/log_changes.py`, `python3 scripts/build.py`, push.
8. **Pull request.** Open or update "Source re-verification <ISO year>-W<week>". Body per day: jurisdictions done, records checked / corrected / unreachable, and a list of corrections (field: old → new, official source). Never merge it; never push to `main`.

## Rules

- Official sources only. Never infer legal effect. Do not touch `site/` or `scripts/`.
- If two official sources conflict, record the primary legal text's value and note the other in `current_status`.
- Do not rewrite text that is correct; this campaign fixes errors, it is not a style pass.
