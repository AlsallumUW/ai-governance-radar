# Arabic machine translations

The Arabic pages (`/ar/`) show translations of published content, with a small "النص الأصلي" link beside each translated
title or summary that opens the original. The Arabic Methodology states: "النصوص العربية للوثائق غير المنشورة بالعربية مترجمة،
والنص الأصلي هو المرجع." They are stored in `data/i18n/ar/` (one file per country, `regional/` for bodies, `_global.json`), keyed by
record id, each with a hash of its English source. `scripts/validate.py` fails when a text has no translation or its
English has changed since it was translated (stale), so new or changed records are translated in the same PR.

Translated: instrument English titles (only when the official title is not Arabic), summaries and status notes
(`current_status`); a country's or body's narrative summary, lead institutions, review notes and technical coverage note;
change-event titles; photo captions and alt text. Not translated: official titles, names in credits, licences.

## Workflow
```bash
python3 scripts/i18n_content.py status                 # what is missing or stale
python3 scripts/i18n_content.py extract SAU DEU > /tmp/work.json
# fill in "ar" for every item (a list for lead_institutions), or set "skip": "<reason>" if it cannot be done confidently
python3 scripts/i18n_content.py apply /tmp/work.json   # checks numbers, acronyms, digits, quotation marks; stores
```
`apply` rejects a translation that drops a number or a Latin acronym, uses Eastern Arabic digits or «»; fix and rerun.

## Fields
- `title`: the English title of a document, or the title of a change event (e.g. "California SB 53 signed into law").
  Translate as a title: concise, no full stop added.
- `summary`: a short description of a document. `status`: a note on its legal or publication status.
- `summary`/`review_notes`/`coverage_note` with an ISO3 `where` and a jurisdiction-level key: country overview and
  research method notes.
- `lead_institutions`: list of institution names.
- `caption`/`alt`: photo caption / alt text (places, buildings, landscapes).

## Rules
1. **Terminology**: use the Arabic terms in `research/aigr_arabic_terms.csv` (the only authority for those terms) exactly as written wherever the English term appears
   (inflect only where Arabic grammar strictly requires agreement). Country and body names: exactly as in `site/i18n/ar.json` (`countries`, `bodies`).
2. **Faithful**: translate what is there. Never add, omit, explain, soften or strengthen. Keep modality exact:
   shall/must → يجب / تلتزم; should → ينبغي; may → يجوز; binding → ملزم; non-binding → غير ملزم; voluntary → طوعي;
   draft → مسودة; in force → ساري المفعول; not yet → لم ... بعد; "no binding effect is stated" → "لم يُذكر أي أثر ملزم".
   Hedges ("appears", "reportedly", "not confirmed") must stay hedged.
3. **Numbers and dates unchanged**, Western digits (0-9) only. Every number in the English must appear in the Arabic
   exactly (years, article numbers, bill numbers, counts, versions like 1.1, "2025/493"). Dates: "8 May 2026" →
   "8 مايو 2026"; months: يناير فبراير مارس أبريل مايو يونيو يوليو أغسطس سبتمبر أكتوبر نوفمبر ديسمبر. ISO dates
   (2026-10-13) stay as written. Hijri dates stay as written, "H"/"AH" → "هـ".
4. **Names**:
   - Institutions: translate to Arabic, then keep any English acronym in Latin in parentheses, e.g. "Saudi Data and
     Artificial Intelligence Authority (SDAIA)" → "الهيئة السعودية للبيانات والذكاء الاصطناعي (SDAIA)". Every Latin
     acronym of 3+ capital letters in the English must stay in the Arabic, in Latin letters.
   - Names of laws/documents cited inside a sentence: translate descriptively, keep official numbers/codes (SB 53,
     ISO/IEC 42001, GDPR, C(2019)34, Royal Decree M/148) in Latin.
   - People's names, product and system names, website names (e.g. Istitlaa, Commons), and quoted original-language
     titles in other languages (French, Spanish, German...): keep in the original Latin script.
   - Use established Arabic names where they exist (e.g. European Union → الاتحاد الأوروبي, United Nations → الأمم المتحدة).
5. **Quotation marks**: use "" only, never «».
6. **Style**: clear Modern Standard Arabic, neutral and formal, as an official gazette or a policy brief would write.
   No transliteration of ordinary English words. Keep sentence boundaries.
7. Never re-translate an official title that is already Arabic (the tool does not extract those).
