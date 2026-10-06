#!/usr/bin/env python3
"""Assemble data/ into one database and build the static site.

    python3 scripts/build.py            -> dist/index.html, dist/data.json, dist/changes.csv
"""
import csv, io, json, sys
from common import ROOT, DATA, load, load_all

OUT = ROOT / "dist"


def assemble():
    meta = load(DATA / "meta.json")
    recs = load_all()
    D = {"meta": meta["meta"], "categories": meta["categories"], "jurisdictions": [], "instruments": [],
         "organizations": [], "sources": [], "regional_applicability": [], "instrument_relationships": load(DATA / "relationships.json"),
         "coverage_audit": [], "changes": list(load(DATA / "changes-global.json")), "narratives": {}}
    order = sorted(recs.values(), key=lambda r: (r["jurisdiction"]["type"] != "country", r["jurisdiction"]["name"]))
    for r in order:
        j = r["jurisdiction"]
        D["jurisdictions"].append(j)
        D["instruments"] += r.get("instruments", [])
        D["organizations"] += r.get("organizations", [])
        D["sources"] += r.get("sources", [])
        if r.get("coverage_audit"): D["coverage_audit"].append(r["coverage_audit"])
        D["changes"] += r.get("changes", [])
        if r.get("narrative"): D["narratives"][j["id"]] = r["narrative"]
    # regional / international instruments apply to each member country (EU AI Act -> all 27, etc.)
    D["regional_applicability"] = []
    for r in order:
        j = r["jurisdiction"]
        if j["type"] == "country": continue
        for i in r.get("instruments", []):
            rule = i.get("applies_to", "members")
            targets = r.get("members", []) if rule == "members" else (rule if isinstance(rule, list) else [])
            i["regional_applicability"] = targets
            for cid in targets:
                D["regional_applicability"].append({"jurisdiction_id": cid, "instrument_id": i["id"], "regional_jurisdiction_id": j["id"],
                    "applicability_type": f"{j['id']}_member_layer",
                    "note": r.get("membership_note") or "Applies through membership; instrument-specific scope remains controlling."})
    D["changes"].sort(key=lambda c: (c.get("date") or "", c.get("recorded") or ""), reverse=True)
    last = {}
    for c in D["changes"]:
        if c.get("instrument_id") and c.get("kind") == "world":
            last[c["instrument_id"]] = max(last.get(c["instrument_id"], ""), c.get("date") or "")
    for i in D["instruments"]:
        i["last_changed"] = last.get(i["id"]) or None
    D["meta"]["deeply_reviewed_country_count"] = sum(
        1 for r in recs.values() if r["jurisdiction"]["type"] == "country" and (r.get("narrative") or {}).get("last_deep_review"))
    D["meta"]["build_date"] = max([D["meta"].get("research_date", "")] + [c.get("recorded") or "" for c in D["changes"]])
    return D


def build():
    D = assemble()
    t = (ROOT / "site/template.html").read_text(encoding="utf-8")
    payload = json.dumps(D, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    for key in ["geometry", "basemap", "flags"]:
        t = t.replace(f"__{key.upper()}__", (ROOT / f"site/assets/{key}.json").read_text(encoding="utf-8"), 1)
    t = t.replace("__CHANGELOG_CSS__", (ROOT / "site/changelog.css").read_text(encoding="utf-8"), 1)
    t = t.replace("__CHANGELOG_JS__", (ROOT / "site/changelog.js").read_text(encoding="utf-8"), 1)
    t = t.replace("__DATABASE__", payload, 1)  # last, so data text can never be mistaken for a placeholder
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(t, encoding="utf-8")
    (OUT / "data.json").write_text(json.dumps(D, ensure_ascii=False, indent=1), encoding="utf-8")
    f = ["date", "recorded", "kind", "type", "jurisdiction_id", "instrument_id", "title", "detail", "from", "to", "source_url", "needs_review"]
    buf = io.StringIO(); w = csv.DictWriter(buf, f, extrasaction="ignore"); w.writeheader(); w.writerows(D["changes"])
    (OUT / "changes.csv").write_text("﻿" + buf.getvalue(), encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    print(f"built dist/index.html ({len(t)/1e6:.1f} MB): {len(D['jurisdictions'])} jurisdictions, "
          f"{len(D['instruments'])} instruments, {len(D['changes'])} change events, "
          f"{D['meta']['deeply_reviewed_country_count']} deep-reviewed countries")


if __name__ == "__main__":
    sys.exit(build())
