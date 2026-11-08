#!/usr/bin/env python3
"""Check every official source link and update link_status / http_status / checked_date in data/.

    python3 scripts/check_links.py [SAU KEN ...]        check all (or some) jurisdictions and save
    python3 scripts/check_links.py --dry-run [...]      check and print, save nothing
    python3 scripts/check_links.py --probe FILE.json    check a list of URLs (JSON list of strings or of
                                                        {"url": ...} objects) and print one JSON line each

Accessibility only — a reachable link says nothing about whether the document is current.
Runs weekly in GitHub Actions (.github/workflows/links.yml); log_changes.py then records any status flips.

Noise rules (a weekly run should flag real problems, not bot blocking):
- Requests look like a browser (headers, cookies), follow 301/302/303/307/308, and percent-encode non-ASCII URLs.
- A certificate the runner cannot verify is retried without verification: the check is about reachability only.
- Hosts in research/bot_protected_hosts.json block automated clients but open in a normal browser. For them,
  401/403/406/429/503 and timeouts never change the recorded status; only 404/410 do. Hosts listed under
  "fake_404_hosts" (e.g. ftc.gov) also answer bots with 404 for live pages, so for them 404 is ignored too.
- Timeouts, connection errors and 5xx elsewhere change the status only after two consecutive failing runs
  (fail_streak, an internal field).
- A redirect that only changes scheme, "www.", host case, a trailing slash or the .htm/.html suffix is "reachable".
  A redirect to the site's home page or a maintenance/login page is "redirected" with a note in "error".
"""
import concurrent.futures as cf, http.cookiejar, json, pathlib, re, ssl, sys, urllib.error, urllib.parse, urllib.request
from common import ROOT, jurisdiction_files, load, save, today

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA,
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9,ar;q=0.8,fr;q=0.7"}
METHOD = "GET; browser headers; first 1 KiB; 25-second timeout"
BOT_FILE = ROOT / "research" / "bot_protected_hosts.json"
BLOCK_CODES = {401, 403, 406, 429, 503}
GONE_CODES = {404, 410}
HOME_HINT = re.compile(r"(maintenance|manutencao|manutencion|mantenimiento|wartung|/login|signin|sign-in|/error|/404|notfound|not-found)", re.I)

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()
LOOSE = ssl.create_default_context()
LOOSE.check_hostname, LOOSE.verify_mode = False, ssl.CERT_NONE


def bot_hosts():
    """(hosts that block bots, hosts that also answer bots with false 404s)."""
    try:
        d = json.loads(BOT_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set(), set()
    clean = lambda xs: {h.lower().removeprefix("www.") for h in xs}
    return clean(d.get("hosts", [])), clean(d.get("fake_404_hosts", []))


def host(url):
    return (urllib.parse.urlsplit(url).hostname or "").lower().removeprefix("www.")


def encode(url):
    """Percent-encode spaces and non-ASCII characters; leave existing escapes alone."""
    p = urllib.parse.urlsplit(url.strip())
    netloc = p.netloc.encode("idna").decode() if not p.netloc.isascii() else p.netloc
    q = lambda s, safe: urllib.parse.quote(s, safe=safe + "%")
    return urllib.parse.urlunsplit((p.scheme, netloc, q(p.path, "/:@!$&'()*+,;=~-._"),
                                    q(p.query, "=&/:@!$'()*+,;?~-._"), q(p.fragment, "")))


def norm(url):
    p = urllib.parse.urlsplit(urllib.parse.unquote(url))
    path = re.sub(r"\.html?$", "", p.path.rstrip("/"))
    return (p.hostname or "").lower().removeprefix("www."), path, p.query


def is_home_or_error(final):
    p = urllib.parse.urlsplit(final)
    return p.path.strip("/") in ("", "index.html", "index.php", "en", "fr", "ar", "es") or bool(HOME_HINT.search(p.path + "?" + p.query))


def fetch(url, ctx):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                                         urllib.request.HTTPSHandler(context=ctx))
    with opener.open(urllib.request.Request(url, headers=HEADERS, method="GET"), timeout=25) as r:
        r.read(1024)
        return r.status, r.geturl(), r.headers.get("Content-Type")


def probe(url):
    """(status, http_code, final_url, error, content_type) for one URL."""
    try:
        target = encode(url)
    except Exception as e:
        return "broken", None, url, "Malformed URL: " + str(e)[:100], None
    note = None
    try:
        try:
            code, final, ctype = fetch(target, CTX)
        except urllib.error.URLError as e:
            if not isinstance(getattr(e, "reason", None), ssl.SSLError): raise
            code, final, ctype = fetch(target, LOOSE)
            note = "Certificate chain could not be verified by the checker"
    except urllib.error.HTTPError as e:
        return ("broken" if e.code in GONE_CODES else "inaccessible"), e.code, url, str(e)[:160], None
    except Exception as e:
        return "inaccessible", None, url, type(e).__name__ + ": " + str(e)[:120], None
    if norm(final) == norm(target) or norm(final) == norm(url):
        return "reachable", code, final, note, ctype
    if is_home_or_error(final):
        return "redirected", code, final, "Redirected to the site's home, maintenance or error page", ctype
    return "redirected", code, final, note, ctype


def settle(prev, result, protected, fake404=False):
    """The status to record, given the previous record, this run's result and whether the host blocks bots."""
    status, code = result[0], result[1]
    if fake404 and code in GONE_CODES:
        return prev.get("link_status") or "not_checked", (prev.get("fail_streak") or 0) + 1
    if status != "inaccessible" and not (status == "broken" and code not in GONE_CODES):
        return status, 0
    streak = (prev.get("fail_streak") or 0) + 1
    if protected and (code in BLOCK_CODES or code is None):
        return prev.get("link_status") or "not_checked", streak
    if code in BLOCK_CODES:
        return status, streak
    # timeouts, connection errors, 5xx: wait for a second failing run before changing the status
    return (status if streak >= 2 else prev.get("link_status") or "not_checked"), streak


def run_probe(path):
    items = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    urls = [x["url"] if isinstance(x, dict) else x for x in items]
    with cf.ThreadPoolExecutor(12) as ex:
        for u, (status, code, final, err, ctype) in zip(urls, ex.map(probe, urls)):
            print(json.dumps({"url": u, "status": status, "code": code, "final": final, "ctype": ctype, "error": err},
                             ensure_ascii=False), flush=True)


def main(only, dry):
    protected, fake404 = bot_hosts()
    files = [p for p in jurisdiction_files() if not only or p.stem in only]
    recs = {p: load(p) for p in files}
    jobs = {(p, s["id"]): s["url"] for p, r in recs.items() for s in r.get("sources", [])}
    print(f"checking {len(jobs)} links ({len(protected)} bot-protected hosts) …")
    with cf.ThreadPoolExecutor(16) as ex:
        results = dict(zip(jobs, ex.map(probe, jobs.values())))
    flips = 0
    for (p, sid), res in results.items():
        status, code, final, err, ctype = res
        for s in recs[p]["sources"]:
            if s["id"] != sid: continue
            h = host(s["url"])
            new, streak = settle(s, res, h in protected or h in fake404, h in fake404)
            if s.get("link_status") != new:
                flips += 1
                print(f"  {p.stem:<6} {s.get('link_status')} -> {new}  [{code}] {s['url'][:100]}")
            s.update(link_status=new, http_status=code, final_url=final, error=err, checked_date=today(),
                     check_method=METHOD, fail_streak=streak)
            for i in recs[p].get("instruments", []):
                if i.get("source_id") == sid: i["link_status"] = new
    if not dry:
        for p, r in recs.items(): save(p, r)
    print(f"done — {flips} status changes" + (" (dry run, nothing saved)" if dry else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--probe" in a:
        run_probe(a[a.index("--probe") + 1])
    else:
        main({x for x in a if not x.startswith("--")}, "--dry-run" in a)
