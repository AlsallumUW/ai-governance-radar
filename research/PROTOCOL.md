# Country deep-review protocol

The standard every country must meet before `narrative.last_deep_review` is set. `scripts/validate.py` enforces the mechanical parts. The judgement parts are up to the researcher.

## 1. Scope: what counts

Include **official government or official-body publications** that govern, steer or set expectations for AI:

| Category key | Include |
|---|---|
| `binding-law` | AI-specific laws, regulations and decrees. Also general laws with explicit AI provisions. |
| `strategy` | National AI strategies, action plans, and digital strategies with an AI pillar |
| `government-governance` | AI governance frameworks, adoption frameworks, national AI bodies' founding instruments |
| `ethics` | AI ethics principles, responsible-AI frameworks |
| `risk-assurance` | Risk-management frameworks, impact assessments, assurance and audit guidance |
| `public-sector` | Rules and guidance for government use of AI |
| `procurement` | AI procurement guidance, model clauses, tender rules |
| `cyber-security` | AI security guidance from the national cyber authority |
| `data-privacy` | Data protection law and the regulator's AI guidance (the law itself counts: it governs AI training and use) |
| `transparency` | Algorithm registers, transparency or labelling standards |
| `standards` | National standards body adoptions (e.g. ISO/IEC 42001 and 5339) |
| `sandbox` | Regulatory sandboxes that cover AI |
| `index-readiness` | Government-published AI indices or maturity assessments |
| `sectoral` | Sector regulators' AI rules (health, finance, education, telecoms, media) |
| `generative-ai` | Generative or agentic AI guidance |
| `drafts` | Drafts and public consultations (never labelled binding) |
| `international` | Treaties or regional instruments the country has signed or ratified |
| `historical` | Superseded strategies and laws, kept for the timeline |

Exclude news articles, press releases with no document, think-tank reports, and private-sector codes. Exclude announcements of intent unless an official document exists.

### Source rule: official documents only

A record's `source_url` must be **the document itself** (PDF, or a gazette or legislation page with the full text), or **an official page of the issuing body that carries the full text or a download link**. Allowed `source_kind` values are `official_document`, `official_publication`, `legislation_portal` and `consultation_portal`.

The following are **never** sources, even when official:

- news agencies, including state agencies (SPA, WAM, QNA, BNA, KUNA, ONA)
- newspapers
- aggregators (OECD.AI, regulations.ai, Digital Policy Alert)
- law-firm notes
- social media

`validate.py` rejects them. If a document is known to exist but no official full text is online yet, record it under `leads` in the country file (not as an instrument) and promote it once the document is published.

## 2. Where to search (every country, every time)

1. National AI body or AI office, if any
2. Ministry responsible for digital, ICT or communications
3. Official gazette or legislation portal (search "artificial intelligence" in the **official language**)
4. Parliament (bills, committee reports)
5. Data protection authority
6. National cybersecurity authority
7. National standards body
8. Central procurement authority
9. Sector regulators: central bank or financial regulator, health, telecoms, education
10. Government open-consultation portal
11. **Discovery aids only:** OECD.AI policy database, UNESCO RAM country reports, regional bodies (AU, ASEAN, GCC, OAS). Use them to find documents, but always record the official government source, never the aggregator.

Search in the official language(s) **and** English. Record every query in `coverage_audit.search_queries`.

## 2a. Levels of government

Each instrument has a `government_level`:

| Level | Meaning | Extra field |
|---|---|---|
| `national` | Central government | — |
| `subnational` | State, province, emirate, Land, region, devolved government | `subnational_unit`, e.g. "Colorado", "Dubai", "Bavaria", "Scotland" |
| `local` | City or municipality, e.g. New York City Local Law 144 | `subnational_unit`, e.g. "New York City" |
| `regional` | Stored once in `data/regional/` and shown in every member country automatically | — |

Subnational and local instruments live in the **country's** file. The site lists them under "State, provincial & local".

**Federal and devolved countries** need a subnational pass in their deep review: USA (50 states plus major cities), Canada (provinces), Australia (states), Germany (Länder), India (states), China (provinces and major cities), UAE (emirates), Brazil, Mexico, Spain (autonomous communities), UK (Scotland, Wales, Northern Ireland), Switzerland (cantons). Search each state legislature and executive portal for AI laws, executive orders and guidance.

## 2b. Regional and international instruments

Instruments from the EU, GCC, AU, ASEAN, UNESCO and similar bodies are stored **once** in `data/regional/<body>.json`. Each file lists its `members`. Each instrument has an `applies_to` value:

- `"members"`: applies to every member (e.g. the EU AI Act → all 27 EU states)
- a list of country codes: applies only to those countries (e.g. treaty signatories or parties)
- `"none"`: not yet attached to any country, pending verification

`build.py` attaches each instrument to every country it applies to. The country page then lists it with the national documents, marked "<body> level · applies here", and its dated changes appear in the country's Changes tab.

Never copy a regional instrument into a country file. A country's own **transposition or implementing law** (e.g. a national law designating AI Act authorities) is a national instrument and goes in the country file.

## 3. Record standard (each instrument)

Required for a deep-reviewed country:

- `official_title`: the full title in the original language. Never a page fragment or the site name.
- `english_title`: an accurate English title (official translation if one exists)
- `issuing_authority`: the institution's name, not its web domain
- `publication_date`: ISO date (`YYYY-MM-DD`, or `YYYY-MM` / `YYYY` if that is all the source states)
- `effective_date`: for binding instruments, when it applies (null for guidance)
- `legal_status`: one of `binding_law`, `binding_regulation`, `administrative_policy_mandatory_in_scope`, `administrative_guideline`, `nonbinding_guidance`, `voluntary_code`, `national_strategy`, `consultation_draft`, `regulatory_opinion`, `international_treaty`
- `lifecycle`: `draft` | `consultation` | `published` | `adopted` | `in_force` | `superseded` | `repealed`
- `summary`: 2–3 sentences specific to this document, covering what it does, who it binds or guides, and any key obligations. **No boilerplate.**
- `language`: ISO 639-1 code
- `supersedes` / `superseded_by`: instrument ids, where applicable
- `source_url`: the official page; `official_pdf_url` if a PDF exists
- `verification_level`: `reviewed_primary_metadata` once the fields above have been checked against the source

Also for the country:

- `narrative.summary`: 4–6 sentences covering the country's AI-governance approach, main instruments, lead institutions and current direction
- `narrative.lead_institutions`: names of the bodies leading AI governance
- `narrative.review_notes`: **public text**, shown to readers. In plain language, say which institutions were searched, which official sites could not be accessed, and what is pending (documents held as leads, gaps to fill later). Do not include HTTP, TLS or proxy errors, tool names, or the names of commercial or aggregator sites. Put those technical details in `coverage_audit.no_material_found_note`.
- `coverage_audit.categories_with_findings` and `categories_where_no_material_was_found`: **every one of the 18 categories must be in one of these two lists**, so `categories_requiring_review` ends up empty
- `narrative.last_deep_review`: the review date. Set it last, only when everything above is done.

"Searched, nothing found" is a valid, valuable result. Record it, never leave it blank.

## 4. Verification rules

- Every fact must come from the official source document or page. If a fact is not stated there, leave it null.
- Do not infer legal effect. A strategy is not binding. A draft is not adopted until an official source says so.
- If two official sources conflict (e.g. dates), record the primary legal text's value and add a note in `current_status`.
- Keep instrument ids stable. When updating a record, edit it in place; never delete and re-create it.

## 5. Logging changes

`scripts/log_changes.py` logs radar events (added, corrected, link, removed) and infers status changes automatically. When the source gives a precise date for a **government action**, also add the world event by hand in the country's `changes`:

```json
{"date": "2025-08-02", "kind": "world", "type": "applied", "jurisdiction_id": "EU",
 "instrument_id": "i-1c0d85e38d12", "title": "AI Act: GPAI obligations apply",
 "detail": "…", "source_url": "https://…", "needs_review": false}
```

The types are `published`, `revised`, `consultation`, `adopted`, `applied`, `superseded` and `repealed`. Set `needs_review: false` only after checking the event against the source.

## 6. Review tiers and run size

Every country gets the **same standard** (§1–§5): all 18 categories closed, official sources only. Tiers only set how much work to expect, and so how many countries fit in one run. They are listed in `research/queue.json` under `tiers`.

| Tier | Who | Extra work | Per run |
|---|---|---|---|
| A | Federal or devolved countries, and the largest AI-policy producers (USA, China, India, Germany, UK, France, Japan, Korea, Singapore…) | Subnational pass (§2a) where relevant; expect 15+ instruments and a large sector-regulator layer | 1 country. The USA may take several runs (federal; then states in groups); add it to `done` only when every part is finished |
| B | Most countries | — | Up to 6 |
| C | Small states and countries with little published AI policy | — | Up to 12 |

`python3 scripts/next_batch.py` prints the next run's countries; `--plan` prints every remaining run.

**Changing tiers.** If a tier C country turns out to have 6 or more national instruments, finish it, then move it to B in `queue.json` and say so in the PR. If a tier B country needs a subnational pass or clearly exceeds a run, stop after it, move it to A and list the rest of the batch as not started.

**Working in parallel.** In a run with several countries, each country may be researched by its own sub-agent. Give each one this protocol in full and its country file. The lead researcher then runs `validate.py`, opens at least two `source_url`s per country to spot-check them, and writes the PR.
