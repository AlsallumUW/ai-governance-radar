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
            if c.get("instrument_id") and c["instrument_id"] not in inst_ids and c.get("type") != "removed":
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
    return errs, warns


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    errs, warns = check(set(args) or None)
    for w in warns: print("WARN ", w)
    for e in errs: print("ERROR", e)
    print(f"\n{len(errs)} errors, {len(warns)} warnings")
    sys.exit(1 if errs or ("--strict" in sys.argv and warns) else 0)
