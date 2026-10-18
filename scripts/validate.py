#!/usr/bin/env python3
"""Check every data file against the record standard (research/PROTOCOL.md).

    python3 scripts/validate.py            errors fail the run; warnings are printed
    python3 scripts/validate.py --strict   warnings also fail
    python3 scripts/validate.py SAU KEN    check only these jurisdictions

Countries whose narrative.last_deep_review is set are held to the full deep-review standard.
"""
import json, re, sys

# official gazettes and legal portals: where an act is published, not who issued it (PROTOCOL: issuer vs gazette)
GAZETTE = re.compile(r"gazette|bolet[ií]n oficial|di[aá]rio oficial|moniteur belge|staatsblad|staatscourant|slu[zž]beni (list|glasnik)|journal officiel|official journal|infoleg|legislation platform|gaceta oficial|legislation\.gov|federal register|normattiva|e-gov law|sb[ií]rka|stj[oó]rnart[ií][dð]indi|imprenta nacional|imprensa nacional|bundesgesetzblatt|gazzetta ufficiale|al meezan", re.I)
from collections import Counter
from common import DATA, LIFECYCLE, LINK_STATUS, RADAR_TYPES, WORLD_TYPES, jurisdiction_files, load

ISO = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
BOILER = "Official source located for this governance category"
DOMAINISH = re.compile(r"^(www\.)?[a-z0-9.-]+\.[a-z]{2,}$")
DEEP_FIELDS = ["issuing_authority", "publication_date", "legal_status", "summary", "language"]
# Only official documents, or official pages that carry the full text or a download, may be sources.
ALLOWED_KINDS = {"official_document", "official_publication", "legislation_portal", "consultation_portal"}
NEWS = re.compile(r"(^|\.)(spa\.gov\.sa|wam\.ae|qna\.org\.qa|bna\.bh|kuna\.net\.kw|omannews\.gov\.om|reuters\.com|apnews\.com|bbc\.|"
                  r"arabnews|saudigazette|gulfnews|thenationalnews|lexology|jdsupra|regulations\.ai|digitalpolicyalert|oecd\.ai|"
                  r"wikipedia\.org|x\.com|twitter\.com|linkedin\.com|youtube\.com)$")
LEVELS = {"national", "subnational", "local", "regional"}


def host(u):
    m = re.match(r"^https?://([^/:]+)", u or "")
    return (m.group(1).lower() if m else "")


PHOTO_LICENCES = re.compile(r"^(Public domain|CC0 1\.0|CC BY(-SA)? \d\.\d( [a-z]{2,3})?)$")
PHOTO_ROLES = ("hero", "feature", "backdrop", "band")
PHOTO_ASPECT = {"hero": 16 / 9, "feature": 4 / 5, "backdrop": 3 / 2, "band": 21 / 9}
PHOTO_FIELDS = ["role", "file", "file_small", "width", "height", "width_small", "subject", "caption", "why", "alt",
                "title", "author", "license", "license_url", "commons_url", "source_width"]
PHOTO_CAPS = {"hero": (200_000, 80_000), "other": (150_000, 60_000)}


def check_photos():
    """data/photos.json (UX phase 2d): every country has exactly four photos, one in each role (hero, feature, backdrop, band),
    cropped to that role's shape; allowed licences only; files present and within size; every field filled."""
    p = DATA / "photos.json"
    if not p.exists(): return [], []
    errs, warns = [], []
    countries = {q.stem for q in (DATA / "countries").glob("*.json") if load(q)["jurisdiction"].get("type") == "country"}
    site = DATA.parent / "site"
    data = load(p).get("countries", {})
    for cid in sorted(countries - set(data)): errs.append(f"photos {cid}: no photos")
    for cid, ph in data.items():
        E = lambda m: errs.append(f"photos {cid}: {m}")
        if cid not in countries: E("not a country file")
        ims = ph.get("photos") or []
        roles = [im.get("role") for im in ims]
        if sorted(roles) != sorted(PHOTO_ROLES): E(f"roles are {roles}; need exactly one each of {', '.join(PHOTO_ROLES)}")
        for im in ims:
            if im.get("role") not in PHOTO_ROLES: E(f"{im.get('file')} role must be one of {PHOTO_ROLES}")
            for f in PHOTO_FIELDS:
                if f not in im or (im[f] in ("", None) and f != "license_url"): E(f"{im.get('file')} missing {f}")
            if not PHOTO_LICENCES.match(im.get("license") or ""): E(f"{im.get('file')} licence not allowed: {im.get('license')}")
            if (im.get("license") or "").startswith("CC BY") and "cropped and resized" not in (im.get("changes") or ""):
                E(f"{im.get('file')} is {im.get('license')} but has no modification note (changes: \"cropped and resized\")")
            if not (im.get("commons_url") or "").startswith("https://commons.wikimedia.org/wiki/File:"): E(f"{im.get('file')} commons_url is not a Commons file page")
            a = PHOTO_ASPECT.get(im.get("role"))
            if a and im.get("width") and im.get("height") and abs(im["width"] / im["height"] - a) > 0.02 * a:
                E(f"{im.get('file')} is {im['width']}x{im['height']}, not the {im.get('role')} shape")
            caps = PHOTO_CAPS["hero" if im.get("role") == "hero" else "other"]
            for f, cap in zip(("file", "file_small"), caps):
                q = site / (im.get(f) or "")
                if not q.is_file(): E(f"missing image {im.get(f)}")
                elif q.stat().st_size > cap: warns.append(f"photos {cid}: {im.get(f)} is {q.stat().st_size // 1000} KB (target {cap // 1000} KB)")
    return errs, warns


def check_explore_overrides():
    """data/explore_overrides.json: each entry names a group label and exactly four distinct country ISO3 codes, none of them the country itself."""
    p = DATA / "explore_overrides.json"
    if not p.exists(): return []
    countries = {q.stem for q in (DATA / "countries").glob("*.json") if load(q)["jurisdiction"].get("type") == "country"}
    errs = []
    for cid, ov in load(p).items():
        if cid.startswith("_"): continue
        E = lambda m: errs.append(f"explore_overrides {cid}: {m}")
        if cid not in countries: E("not a country")
        if not isinstance(ov, dict) or not (ov.get("group") or "").strip(): E("missing group label"); continue
        cs = ov.get("countries")
        if not isinstance(cs, list) or len(cs) != 4: E("needs exactly 4 countries"); continue
        if len(set(cs)) != 4: E(f"duplicate countries {cs}")
        for c in cs:
            if c == cid: E("lists the country itself")
            elif c not in countries: E(f"{c} is not a valid country ISO3 code")
    return errs


def check_i18n():
    """Arabic interface (site/i18n/ar.json) against the approved terminology (research/aigr_arabic_terms.csv, the only authority for its terms)."""
    import json
    from common import ROOT
    errs = []
    csv_p, ar_p = ROOT / "research/aigr_arabic_terms.csv", ROOT / "site/i18n/ar.json"
    if not ar_p.exists(): return errs
    import i18n
    terms = i18n.terms()
    if not terms: return [f"{csv_p.name}: no terms"]
    d = json.loads(ar_p.read_text(encoding="utf-8"))
    E = lambda m: errs.append(f"i18n: {m}")
    for f in (csv_p, ar_p, ROOT / "site/i18n/runtime.js"):
        if re.search("[«»]", f.read_text(encoding="utf-8")): E(f"{f.name} uses «» quotation marks (use \"\")")
    low = {k.lower(): v for k, v in terms.items()}
    for en, ar in d.get("strings", {}).items():           # a CSV term used as a whole string must be the CSV's Arabic
        if en.lower() in low and ar != low[en.lower()]: E(f"strings['{en}'] = '{ar}', but the CSV term is '{low[en.lower()]}'")
        a, b = set(re.findall(r"\{(\w+)\}", en)), set(re.findall(r"\{(\w+)\}", ar))
        if a != b: E(f"strings['{en[:60]}']: placeholders {sorted(a)} vs {sorted(b)}")
    names = {"EU": "European Union", "COE": "Council of Europe", "GCC": "Gulf Cooperation Council (GCC)", "AU": "African Union"}
    for k, ar in d.get("bodies", {}).items():
        t = terms.get(names.get(k, k))
        if t and ar != t: E(f"bodies['{k}'] = '{ar}', but the CSV term is '{t}'")
    for rx, rep in d.get("patterns", []):
        try: n = re.compile(rx).groups
        except re.error as e: E(f"pattern {rx!r}: {e}"); continue
        bad = [g for g in re.findall(r"\{[td]?(\d)\}", rep) if int(g) > n]
        if bad: E(f"pattern {rx!r} refers to missing groups {bad}")
    countries = {q.stem for q in (DATA / "countries").glob("*.json")}
    miss = sorted(countries - set(d.get("countries", {})))
    if miss: E(f"countries without an Arabic name: {miss}")
    order = set(d.get("sort_order", []))
    unsorted = sorted(n for n in list(d.get("countries", {}).values()) + list(d.get("bodies", {}).values()) if n not in order)
    if unsorted: E(f"names missing from sort_order (rerun the strings generator): {unsorted}")
    for k, v in (d.get("country_overrides") or {}).items():
        if d["countries"].get(k) != v: E(f"country override {k} not applied")
    return errs


def check_translations():
    """Arabic machine translations (data/i18n/ar/): every text the Arabic pages translate must have a translation whose source
    hash matches the current English (missing or stale = error); a skipped text is a warning."""
    if not (DATA / "i18n" / "ar").is_dir(): return [], []
    from i18n_content import audit
    errs, warns = [], []
    for jid, r in audit().items():
        if r["missing"]: errs.append(f"{jid}: {len(r['missing'])} texts without an Arabic translation, e.g. {r['missing'][:3]} (python3 scripts/i18n_content.py extract {jid})")
        if r["stale"]: errs.append(f"{jid}: {len(r['stale'])} Arabic translations are stale (English changed), e.g. {r['stale'][:3]}")
        if r["skipped"]: warns.append(f"{jid}: {len(r['skipped'])} texts left untranslated (skip), e.g. {r['skipped'][:3]}")
    return errs, warns


BINDING_STATUSES = ("binding_law", "binding_regulation")
# current_status is shown to the public; research-log wording belongs in evidence_reference (shown under "Source notes")
STATUS_LOG = re.compile(r"audit 20\d\d|\bcurl\b|HTTP [0-9]{3}|not read|fetch|automated access|automated reading|blocks automated|could not be read"
                        r"|this record|the radar(?! tecnol[oó]gico)"
                        r"|held as (?:a )?leads?|in this review|\b(?:effective|publication|last_amended)_date\b|\bnull\b|WebFetch|pdftotext|headless", re.I)


# review_notes and no_material_found_note are public text too: also no agent/tool/run vocabulary
# overview summaries state what is established; process wording belongs in the method note (narrative.review_notes)
SUMMARY_PROCESS = re.compile(r"could not be|in this review|held as (?:a )?leads?", re.I)
NOTE_LOG = re.compile(STATUS_LOG.pattern + r"|\bHTTP\b|WebFetch|\bTLS\b|\bproxy\b|\bagents?\b|sub-?agent|\bPROTOCOL\b|\bpilot\b|thin pass|\btier [ABC]\b|batch run", re.I)


def check(only=None):
    cats = set(load(DATA / "meta.json")["categories"])
    errs, warns, ids, srcids = [], [], Counter(), Counter()
    for p in jurisdiction_files():
        jid = p.stem
        if only and jid not in only: continue
        try:
            r = load(p)
        except Exception as e:
            errs.append(f"{jid}: invalid JSON ({e})"); continue
        E = lambda m: errs.append(f"{jid}: {m}")
        W = lambda m: warns.append(f"{jid}: {m}")
        j = r.get("jurisdiction", {})
        if j.get("id") != jid: E(f"file name and jurisdiction.id differ ({j.get('id')})")
        deep = bool((r.get("narrative") or {}).get("last_deep_review"))
        inst_ids = set()
        for i in r.get("instruments", []):
            k = i.get("id", "?"); ids[k] += 1; inst_ids.add(k)
            t = i.get("english_title") or ""
            if i.get("jurisdiction_id") != jid: E(f"{k} has jurisdiction_id {i.get('jurisdiction_id')}")
            bad = [c for c in i.get("categories", []) if c not in cats]
            if bad: E(f"{k} unknown categories {bad}")
            if i.get("category") not in i.get("categories", []): E(f"{k} primary category not in categories")
            if i.get("legal_status") in BINDING_STATUSES and "binding-law" not in i.get("categories", []):
                E(f"{k} is {i['legal_status']} but lacks the binding-law category")
            if re.search(r"turn\d+[a-z]+\d+", json.dumps(i, ensure_ascii=False)): E(f"{k} contains a search-tool citation token (turnNsearchN)")
            for f in ("current_status", "summary"):
                m = STATUS_LOG.search(i.get(f) or "")
                if m: E(f"{k} {f} contains research-log wording '{m.group(0)}' (move it to evidence_reference)")
            if i.get("lifecycle") not in LIFECYCLE: E(f"{k} lifecycle '{i.get('lifecycle')}' not one of {LIFECYCLE}")
            for f in ["publication_date", "effective_date", "last_amended_date", "verification_date"]:
                if i.get(f) and not ISO.match(i[f]): E(f"{k} {f} not ISO date: {i[f]}")
            if not re.match(r"^https?://", i.get("source_url") or ""): E(f"{k} source_url missing or not http(s)")
            for f in ("source_url", "official_pdf_url", "official_webpage_url"):
                if i.get(f) and NEWS.search(host(i[f])): E(f"{k} {f} is a news/aggregator site, not an official source: {host(i[f])}")
            if i.get("source_kind") not in ALLOWED_KINDS: E(f"{k} source_kind '{i.get('source_kind')}' not allowed (must be one of {sorted(ALLOWED_KINDS)})")
            gl = i.get("government_level")
            if gl not in LEVELS: E(f"{k} government_level '{gl}' not one of {sorted(LEVELS)}")
            if gl in ("subnational", "local") and not i.get("subnational_unit"): E(f"{k} is {gl} but subnational_unit is empty")
            if len((i.get("official_title") or "").strip()) < 4: W(f"{k} official_title looks truncated: '{i.get('official_title')}'")
            if re.search(r"\*\*|^\w+\.\s", i.get("official_title") or ""): W(f"{k} official_title looks like scraped text")
            if GAZETTE.search(i.get("publisher_name") or ""): W(f"{k} publisher_name looks like a gazette or legal portal; use the issuing body and keep the gazette in the source/evidence fields")
            if DOMAINISH.match(i.get("publisher_name") or ""): W(f"{k} publisher is a domain, not an institution: {i.get('publisher_name')}")
            if deep:
                miss = [f for f in DEEP_FIELDS if not i.get(f)]
                if miss: E(f"{k} deep-reviewed country missing {miss} ('{t[:50]}')")
                if BOILER in (i.get("summary") or ""): E(f"{k} has boilerplate summary ('{t[:50]}')")
                if i.get("lifecycle") == "unverified": E(f"{k} lifecycle still 'unverified'")
        for s in r.get("sources", []):
            srcids[s.get("id")] += 1
            if s.get("link_status") not in LINK_STATUS: W(f"source {s.get('id')} link_status '{s.get('link_status')}'")
        for c in r.get("changes", []):
            ty = c.get("type")
            if c.get("kind") == "world" and ty not in WORLD_TYPES: E(f"change {c.get('id')} bad world type {ty}")
            if c.get("kind") == "radar" and ty not in RADAR_TYPES: E(f"change {c.get('id')} bad radar type {ty}")
            if c.get("kind") not in ("world", "radar"): E(f"change {c.get('id')} bad kind {c.get('kind')}")
            if c.get("date") and not ISO.match(c["date"]): E(f"change {c.get('id')} bad date {c['date']}")
            if c.get("source_url") and NEWS.search(host(c["source_url"])): E(f"change {c.get('id')} cites a news/aggregator site: {host(c['source_url'])}")
            removed_ids = {x.get("instrument_id") for x in r.get("changes", []) if x.get("type") == "removed"}
            if c.get("instrument_id") and c["instrument_id"] not in inst_ids and c["instrument_id"] not in removed_ids:
                E(f"change {c.get('id')} points to missing instrument {c['instrument_id']}")
        m = SUMMARY_PROCESS.search((r.get("narrative") or {}).get("summary") or "")
        if m: E(f"narrative.summary contains process wording '{m.group(0)}' (state what is established; move it to review_notes as 'Not yet verified from the official text: ...')")
        for f, v in (("narrative.review_notes", (r.get("narrative") or {}).get("review_notes")),
                     ("coverage_audit.no_material_found_note", (r.get("coverage_audit") or {}).get("no_material_found_note"))):
            m = NOTE_LOG.search(v or "")
            if m: E(f"{f} contains research-log wording '{m.group(0)}' (public text; move it to coverage_audit.technical_note)")
        if deep:
            n = r.get("narrative") or {}
            if not n.get("summary"): E("deep-reviewed but narrative.summary is empty")
            a = r.get("coverage_audit") or {}
            open_ = a.get("categories_requiring_review") or []
            if open_: E(f"deep-reviewed but categories still unreviewed: {open_}")
    for k, n in ids.items():
        if n > 1: errs.append(f"duplicate instrument id {k}")
    for k, n in srcids.items():
        if n > 1: errs.append(f"duplicate source id {k}")
    if not only:
        e2, w2 = check_photos()
        errs += e2; warns += w2
        errs += check_explore_overrides()
        errs += check_i18n()
        e3, w3 = check_translations()
        errs += e3; warns += w3
        from next_batch import QUEUE, check_queue
        errs += check_queue(load(QUEUE), [p.stem for p in (DATA / "countries").glob("*.json")])
    return errs, warns


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    errs, warns = check(set(args) or None)
    for w in warns: print("WARN ", w)
    for e in errs: print("ERROR", e)
    print(f"\n{len(errs)} errors, {len(warns)} warnings")
    sys.exit(1 if errs or ("--strict" in sys.argv and warns) else 0)
