#!/usr/bin/env python3
"""Check every official source link and update link_status / http_status / checked_date in data/.
Also checks the links that change events carry (the Updates panel shows an event's own source_url when it has one)
and writes those results to research/link_check_events.json, which is never published.

    python3 scripts/check_links.py [SAU KEN ...]

Accessibility only — a reachable link says nothing about whether the document is current.
Runs weekly in GitHub Actions (.github/workflows/links.yml); log_changes.py then records any status flips.
"""
import concurrent.futures as cf, json, sys, urllib.request, ssl
from common import DATA, ROOT, jurisdiction_files, link_check_event, load, save, today

EVENTS_OUT = ROOT / "research" / "link_check_events.json"

UA = "Mozilla/5.0 (compatible; AIGovernanceRadar-linkcheck/1.0; +https://github.com)"
CTX = ssl.create_default_context()


def probe(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            r.read(1024)
            final = r.geturl()
            status = "redirected" if final.rstrip("/") != url.rstrip("/") else "reachable"
            return status, r.status, final, None
    except urllib.error.HTTPError as e:
        # 401/403/429 are usually bot protection, not a dead document
        return ("inaccessible" if e.code in (401, 403, 429, 503) else "broken"), e.code, url, str(e)
    except Exception as e:
        return "inaccessible", None, url, type(e).__name__ + ": " + str(e)[:120]


def main(only):
    files = [p for p in jurisdiction_files() if not only or p.stem in only]
    jobs = {}
    recs = {p: load(p) for p in files}
    for p, r in recs.items():
        for s in r.get("sources", []):
            jobs[(p, s["id"])] = s["url"]
    print(f"checking {len(jobs)} links …")
    with cf.ThreadPoolExecutor(16) as ex:
        results = dict(zip(jobs, ex.map(probe, jobs.values())))
    flips = 0
    for (p, sid), (status, code, final, err) in results.items():
        for s in recs[p]["sources"]:
            if s["id"] == sid:
                if s.get("link_status") != status: flips += 1
                s.update(link_status=status, http_status=code, final_url=final, error=err, checked_date=today(),
                         check_method="GET; first 1 KiB; 20-second timeout")
        for i in recs[p].get("instruments", []):
            if i.get("source_id") == sid: i["link_status"] = status
    for p, r in recs.items(): save(p, r)
    print(f"done — {flips} status changes")
    check_events(recs, only)


def check_events(recs, only):
    """Event links that are not a source of any record: results go to research/link_check_events.json (internal)."""
    known = {s["url"] for r in recs.values() for s in r.get("sources", [])}
    ev = {}
    glob_ev = load(DATA / "changes-global.json") if not only else []
    for c in [c for r in recs.values() for c in r.get("changes", [])] + list(glob_ev):
        u = c.get("source_url")
        if u and u not in known and not link_check_event(c):
            ev.setdefault(u, []).append(c["id"])
    print(f"checking {len(ev)} event links …")
    with cf.ThreadPoolExecutor(16) as ex:
        res = dict(zip(ev, ex.map(probe, ev)))
    old = json.loads(EVENTS_OUT.read_text(encoding="utf-8")) if EVENTS_OUT.exists() and only else {}
    old.update({u: {"link_status": s, "http_status": code, "final_url": final, "error": err, "checked_date": today(),
                    "events": ev[u]} for u, (s, code, final, err) in res.items()})
    EVENTS_OUT.write_text(json.dumps(dict(sorted(old.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    bad = sum(1 for s, *_ in res.values() if s == "broken")
    print(f"event links: {len(res)} checked, {bad} broken (see {EVENTS_OUT.relative_to(ROOT)})")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
