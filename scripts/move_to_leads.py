#!/usr/bin/env python3
"""Move records to leads (owner rules: bills are leads; a record whose official document cannot be confirmed
at a working official link is a lead until it can be).

    python3 scripts/move_to_leads.py PLAN.json [--date YYYY-MM-DD]

PLAN.json: {"<instrument id>": {"note": "why, and what was found", "detail": "public change-log detail"}, ...}

For each instrument: a lead is added to its jurisdiction file (official title, English title, issuer, URL, note,
date first found); the record, its world events and its Arabic texts are removed; sources and organisations cited
only by it are removed; references from other records (supersedes, superseded_by, related_instruments) are
dropped; remaining radar events keep an Arabic title; a radar "removed" event is logged; research/verify_queue.json
entries for it are dropped.
"""
import json, sys
from common import DATA, ROOT, eid, jurisdiction_files, load, save, today
from i18n_content import src_hash

AR = DATA / "i18n" / "ar"


def ar_path(p):
    return AR / ("regional/" if p.parent.name == "regional" else "") / p.name


def main(plan_path, date):
    plan = json.loads(open(plan_path, encoding="utf-8").read())
    left = set(plan)
    for p in jurisdiction_files():
        d = load(p)
        ids = [i["id"] for i in d.get("instruments", []) if i["id"] in left]
        if not ids: continue
        ap = ar_path(p)
        ar = load(ap) if ap.exists() else {}
        for iid in ids:
            i = next(x for x in d["instruments"] if x["id"] == iid)
            jid = i["jurisdiction_id"]
            ar_title = (ar.get(iid, {}).get("title") or {}).get("ar") or (
                i["official_title"] if any("؀" <= ch <= "ۿ" for ch in i["official_title"]) else None)
            d.setdefault("leads", []).append({
                "title": i["official_title"], "english_title": i.get("english_title"),
                "issuing_authority": i.get("issuing_authority"),
                "url": i.get("official_pdf_url") or i.get("source_url"),
                "note": plan[iid]["note"], "found": i.get("first_recorded") or date})
            d["instruments"] = [x for x in d["instruments"] if x["id"] != iid]
            # world events of the record go; radar events stay and keep an Arabic title
            gone = [c["id"] for c in d.get("changes", []) if c.get("instrument_id") == iid and c.get("kind") == "world"]
            d["changes"] = [c for c in d.get("changes", []) if c["id"] not in gone]
            for cid in gone: ar.pop(cid, None)
            title = i.get("english_title") or i["official_title"]
            for c in d["changes"]:
                if c.get("instrument_id") == iid and ar_title and c.get("title") in (i.get("english_title"), i["official_title"]):
                    ar.setdefault(c["id"], {})["title"] = {"ar": ar_title, "src": src_hash(c["title"])}
            ev = {"id": eid(date, "removed", jid, iid, title, None, None), "date": date, "recorded": date, "kind": "radar",
                  "type": "removed", "jurisdiction_id": jid, "instrument_id": iid, "title": title,
                  "detail": plan[iid]["detail"], "from": None, "to": None, "source_url": None, "needs_review": False}
            d["changes"].insert(0, ev)
            if ar_title: ar[ev["id"]] = {"title": {"ar": ar_title, "src": src_hash(title)}}
            ar.pop(iid, None)
            # sources and organisations cited only by this record
            for s in d.get("sources", []):
                if iid in s.get("instrument_ids", []): s["instrument_ids"].remove(iid)
            d["sources"] = [s for s in d.get("sources", []) if s.get("instrument_ids") or s["id"] != i.get("source_id")]
            used = {x.get("organization_id") for x in d["instruments"]}
            d["organizations"] = [o for o in d.get("organizations", []) if o["id"] != i.get("organization_id") or o["id"] in used]
            left.discard(iid)
        save(p, d)
        if ar: save(ap, ar)
    # references from any record
    gone_ids = set(plan) - left
    for p in jurisdiction_files():
        d, ch = load(p), False
        for x in d.get("instruments", []):
            for f in ("supersedes", "superseded_by", "related_instruments"):
                v = x.get(f) or []
                nv = [r for r in v if (r.get("id") if isinstance(r, dict) else r) not in gone_ids]
                if nv != v: x[f], ch = nv, True
        if ch: save(p, d)
    q = ROOT / "research" / "verify_queue.json"
    if q.exists():
        vq = load(q)
        lists = [k for k, v in vq.items() if isinstance(v, list)] if isinstance(vq, dict) else [None]
        changed = False
        for k in lists:
            rows = vq[k] if k else vq
            kept = [r for r in rows if not (isinstance(r, dict) and r.get("instrument_id") in gone_ids)]
            if len(kept) != len(rows):
                changed = True
                if k: vq[k] = kept
                else: vq = kept
        if changed: save(q, vq)
    print(f"moved {len(gone_ids)} records to leads" + (f"; not found: {sorted(left)}" if left else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[a.index("--date") + 1] if "--date" in a else today())
