#!/usr/bin/env python3
"""Detect what changed in data/ since a git ref and write dated change events into each country file.

    python3 scripts/log_changes.py                  compare with origin/main (default)
    python3 scripts/log_changes.py --base HEAD~1    compare with another ref
    python3 scripts/log_changes.py --dry-run        print, don't write

Government actions (adopted, applied, revised, superseded, ...) that are inferred from field changes are
marked needs_review=true. Filling in a field that was previously unknown (e.g. lifecycle 'unverified' -> 'adopted')
is logged as a radar correction, not as a government action. The researcher should also add world events by hand when the source gives a
precise date (see research/PROTOCOL.md, section 5).
"""
import datetime as dt, sys
from common import DATA, event, lifecycle_of, load_all, load_all_at, save, today

TRACKED = {"official_title": "title", "english_title": "title", "issuing_authority": "issuing authority",
           "publication_date": "publication date", "legal_status": "legal status", "scope": "scope",
           "summary": "summary", "categories": "categories",
           "lifecycle": "lifecycle", "last_amended_date": "amendment date", "effective_date": "effective date"}
LIFE_TO_TYPE = {"adopted": "adopted", "published": "adopted", "in_force": "applied", "superseded": "superseded",
                "repealed": "repealed", "consultation": "consultation", "draft": "consultation"}


def detect(old, new, date):
    evs = []
    o = {i["id"]: i for i in old.get("instruments", [])}
    n = {i["id"]: i for i in new.get("instruments", [])}
    jid = new["jurisdiction"]["id"]
    for k, i in n.items():
        title = i.get("english_title") or i.get("official_title")
        i.setdefault("lifecycle", lifecycle_of(i))
        if k not in o:
            i.setdefault("first_recorded", date)
            pub = i.get("publication_date")
            recent = pub and len(pub) == 10 and pub >= (dt.date.fromisoformat(date) - dt.timedelta(days=60)).isoformat()
            if recent:
                evs.append(event(pub, "world", "published", jid, k, title, "Newly published document.", url=i.get("source_url"), recorded=date, review=True))
            evs.append(event(date, "radar", "added", jid, k, title, "Added to the radar" + (f" (published {pub})." if pub else "."), url=i.get("source_url"), recorded=date))
            continue
        p = o[k]
        known = p.get("lifecycle") not in (None, "unverified")
        if known and p.get("lifecycle") != i["lifecycle"]:
            typ = LIFE_TO_TYPE.get(i["lifecycle"], "revised")
            when = i.get("effective_date") if typ == "applied" and i.get("effective_date") else date
            evs.append(event(when, "world", typ, jid, k, title, "Status changed.", p.get("lifecycle"), i["lifecycle"], i.get("source_url"), date, True))
        if i.get("last_amended_date") and p.get("last_amended_date") and i["last_amended_date"] != p.get("last_amended_date"):
            evs.append(event(i["last_amended_date"], "world", "revised", jid, k, title, "Amended / new version.", p.get("last_amended_date"), i["last_amended_date"], i.get("source_url"), date, True))
        if known and i.get("effective_date") and not p.get("effective_date") and p.get("lifecycle") == i["lifecycle"]:
            evs.append(event(i["effective_date"], "world", "applied", jid, k, title, "Effective / application date recorded.", None, i["effective_date"], i.get("source_url"), date, True))
        if i.get("source_url") != p.get("source_url"):
            evs.append(event(date, "radar", "link", jid, k, title, "Official source moved.", p.get("source_url"), i.get("source_url"), i.get("source_url"), date))
        fixed = sorted({lbl for f, lbl in TRACKED.items() if (p.get(f) or None) != (i.get(f) or None)})
        if fixed:
            evs.append(event(date, "radar", "corrected", jid, k, title, "Record updated: " + ", ".join(fixed) + ".", recorded=date))
    for k, p in o.items():
        if k not in n:
            evs.append(event(date, "radar", "removed", jid, k, p.get("english_title") or p.get("official_title"),
                             "Removed from the radar (not an official source, duplicate, or out of scope).", recorded=date))
    so = {s["id"]: s for s in old.get("sources", [])}
    for s in new.get("sources", []):
        prev = so.get(s["id"])
        if prev and prev.get("link_status") != s.get("link_status") and s.get("link_status") in ("inaccessible", "broken", "reachable"):
            for iid in s.get("instrument_ids", []):
                if iid in n:
                    evs.append(event(date, "radar", "link", jid, iid, n[iid].get("english_title") or n[iid].get("official_title"),
                                     "Official link " + ("restored." if s["link_status"] == "reachable" else "no longer reachable."),
                                     prev.get("link_status"), s.get("link_status"), s.get("url"), date))
    on, nn = (old.get("narrative") or {}), (new.get("narrative") or {})
    if nn.get("last_deep_review") and nn.get("last_deep_review") != on.get("last_deep_review"):
        evs.append(event(nn["last_deep_review"], "radar", "radar", jid, None, "Deep review completed",
                         f"Country reviewed to the full record standard; {len(n)} documents recorded.", recorded=date))
    return evs


def main():
    a = sys.argv[1:]
    base = a[a.index("--base") + 1] if "--base" in a else "origin/main"
    dry, date = "--dry-run" in a, today()
    old_all, new_all = load_all_at(base), load_all()
    if not old_all:
        print(f"base ref '{base}' not found — nothing to compare"); return 0
    total = 0
    for jid, rec in new_all.items():
        old = old_all.get(jid, {"jurisdiction": rec["jurisdiction"], "instruments": [], "sources": []})
        evs = detect(old, rec, date)
        have = {c["id"] for c in rec.get("changes", [])}
        hand = {(c.get("instrument_id"), c.get("type"), c.get("date")) for c in rec.get("changes", []) if c.get("kind") == "world"}
        evs = [e for e in evs if e["id"] not in have and not (e["kind"] == "world" and (e["instrument_id"], e["type"], e["date"]) in hand)]
        if not evs: continue
        total += len(evs)
        for e in evs:
            print(f"  {e['date']}  {e['kind']:<5} {e['type']:<12} {jid:<6} {e['title'][:70]}")
        if not dry:
            rec.setdefault("changes", []).extend(evs)
            rec["changes"].sort(key=lambda c: (c.get("date") or "", c.get("recorded") or ""), reverse=True)
            sub = "countries" if rec["jurisdiction"]["type"] == "country" else "regional"
            save(DATA / sub / f"{jid}.json", rec)
    print(f"{total} change events {'found' if dry else 'logged'} since {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
