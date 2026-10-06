#!/usr/bin/env python3
"""Check every official source link and update link_status / http_status / checked_date in data/.

    python3 scripts/check_links.py [SAU KEN ...]

Accessibility only — a reachable link says nothing about whether the document is current.
Runs weekly in GitHub Actions (.github/workflows/links.yml); log_changes.py then records any status flips.
"""
import concurrent.futures as cf, sys, urllib.request, ssl
from common import DATA, jurisdiction_files, load, save, today

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


if __name__ == "__main__":
    main(set(sys.argv[1:]))
