#!/usr/bin/env python3
"""Backfill: add the publication event (published / adopted / put to consultation) for every record whose publication
date gives at least the month and that has no world event yet. Safe to run again (adds nothing twice).

    python3 scripts/add_publication_events.py            write
    python3 scripts/add_publication_events.py --dry-run  count only

Afterwards translate the new event details: python3 scripts/i18n_content.py extract <ids> / apply.
"""
import sys
from collections import Counter
from common import jurisdiction_files, load, publication_event, save

dry = "--dry-run" in sys.argv
per, kinds = Counter(), Counter()
for p in jurisdiction_files():
    r = load(p)
    have = {c.get("instrument_id") for c in r.get("changes", []) if c.get("kind") == "world"}
    ids = {c["id"] for c in r.get("changes", [])}
    new = [e for i in r.get("instruments", []) if i["id"] not in have for e in [publication_event(r, i)] if e and e["id"] not in ids]
    if not new: continue
    per[r["jurisdiction"]["id"]] += len(new)
    kinds.update(("month" if len(e["date"]) == 7 else "day", e["type"]) for e in new)
    if not dry:
        r["changes"] = sorted(r.get("changes", []) + new, key=lambda c: (c.get("date") or "", c.get("recorded") or ""), reverse=True)
        save(p, r)
print(f"{sum(per.values())} events {'to add' if dry else 'added'} in {len(per)} jurisdictions: {dict(kinds)}")
