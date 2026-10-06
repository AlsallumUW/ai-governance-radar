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
