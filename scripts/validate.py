#!/usr/bin/env python3
"""Check every data file against the record standard (research/PROTOCOL.md).

    python3 scripts/validate.py            errors fail the run; warnings are printed
    python3 scripts/validate.py --strict   warnings also fail
    python3 scripts/validate.py SAU KEN    check only these jurisdictions

Countries whose narrative.last_deep_review is set are held to the full deep-review standard.
"""
import re, sys
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
PHOTO_SUBJECTS = {"parliament", "monument", "heritage_site", "landscape", "skyline"}
PHOTO_FIELDS = ["file", "file_small", "width", "height", "title", "author", "license", "license_url", "commons_url", "shows", "alt"]


def check_photos():
    """data/photos.json (UX phase 2b): allowed licences only, files present and within size, every field filled."""
    p = DATA / "photos.json"
    if not p.exists(): return [], []
    errs, warns = [], []
    countries = {q.stem for q in (DATA / "countries").glob("*.json")}
    site = DATA.parent / "site"
    for cid, ph in load(p).get("countries", {}).items():
        E = lambda m: errs.append(f"photos {cid}: {m}")
        if cid not in countries: E("not a country file")
        ims = ([ph["hero"]] if ph.get("hero") else []) + list(ph.get("secondary") or [])
        if not ph.get("hero") and not ph.get("fallback_reason"): E("no hero and no fallback_reason")
        if len(ph.get("secondary") or []) > 2: E("more than 2 secondary photos")
        for im in ims:
            for f in PHOTO_FIELDS:
                if f not in im or (im[f] in ("", None) and f != "license_url"): E(f"{im.get('file')} missing {f}")
            if not PHOTO_LICENCES.match(im.get("license") or ""): E(f"{im.get('file')} licence not allowed: {im.get('license')}")
            if (im.get("license") or "").startswith("CC BY") and "cropped and resized" not in (im.get("changes") or ""):
                E(f"{im.get('file')} is {im.get('license')} but has no modification note (changes: \"cropped and resized\")")
            if im.get("subject_type") not in PHOTO_SUBJECTS: E(f"{im.get('file')} subject_type must be one of {sorted(PHOTO_SUBJECTS)}")
            if not (im.get("why") or "").strip(): E(f"{im.get('file')} missing why")
            if not (im.get("commons_url") or "").startswith("https://commons.wikimedia.org/wiki/File:"): E(f"{im.get('file')} commons_url is not a Commons file page")
            for f, cap in (("file", 200_000), ("file_small", 80_000)):
                q = site / (im.get(f) or "")
                if not q.is_file(): E(f"missing image {im.get(f)}")
                elif q.stat().st_size > cap: warns.append(f"photos {cid}: {im.get(f)} is {q.stat().st_size // 1000} KB (target {cap // 1000} KB)")
    return errs, warns


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
