#!/usr/bin/env python3
"""Assemble data/ into one database and build the static site.

    python3 scripts/build.py            -> dist/index.html, dist/data.json, dist/changes.csv
"""
import csv, hashlib, html, io, json, re, sys
from common import ROOT, DATA, load, load_all, public
import pages
import i18n

OUT = ROOT / "dist"


def assemble():
    meta = load(DATA / "meta.json")
    recs = load_all()
    D = {"meta": meta["meta"], "categories": meta["categories"], "jurisdictions": [], "instruments": [],
         "organizations": [], "sources": [], "regional_applicability": [], "instrument_relationships": load(DATA / "relationships.json"),
         "coverage_audit": [], "changes": list(load(DATA / "changes-global.json")), "narratives": {}, "regional_members": {}}
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
        if j["type"] != "country" and r.get("members"): D["regional_members"][j["id"]] = r["members"]
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


# Cache-busting: every local image, CSS and JS URL in the built HTML gets ?v=<first 8 hex chars of the file's sha1>,
# so a changed file gets a new URL and browsers and the CDN cannot keep serving the old copy after a deploy.
BUST_EXT = (".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".avif", ".css", ".js")
BUST_ATTR = re.compile(r'\b(src|href|srcset|imagesrcset|content)="([^"]+)"')


def bust_urls(out):
    hashes, n = {}, 0

    def tag(url, base):
        if "?" in url or "#" in url:
            return url
        if url.startswith(pages.SITE_URL):
            f = out / url[len(pages.SITE_URL):]
        elif "://" in url or url.startswith(("data:", "mailto:", "/")):
            return url
        else:
            f = (base / url).resolve()
        if f.suffix.lower() not in BUST_EXT or not f.is_file():
            return url
        if f not in hashes:
            hashes[f] = hashlib.sha1(f.read_bytes()).hexdigest()[:8]
        return f"{url}?v={hashes[f]}"

    for page in out.rglob("*.html"):
        base, t = page.parent, page.read_text(encoding="utf-8")

        def attr(m):
            name, val = m.group(1), m.group(2)
            if name in ("srcset", "imagesrcset"):
                val = ", ".join(" ".join([tag(p.split()[0], base)] + p.split()[1:]) for p in val.split(",") if p.strip())
            else:
                val = tag(val, base)
            return f'{name}="{val}"'

        new = BUST_ATTR.sub(attr, t)
        if new != t:
            page.write_text(new, encoding="utf-8"); n += 1
    return n, len(hashes)


# ---------------------------------------------------------------- Arabic mirror (UX phase 4b)
AR = OUT / "ar"
FONT = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap">')


# summaries and status notes are published text in their own language: dir="auto" lets an English one sit and align left
DATA_DIR = re.compile(r'(<p class="(?:inst-sum|inst-status)")(?=>)')     # English text only; translations carry lang/dir


def map_photos():
    """Hero photo and caption per country for the map's hover card (the 800-px hero file)."""
    p = ROOT / "data/photos.json"
    if not p.exists(): return {}
    out = {}
    for cid, c in json.loads(p.read_text(encoding="utf-8")).get("countries", {}).items():
        h = next((im for im in c.get("photos") or [] if im.get("role") == "hero"), None)
        if h: out[cid] = {"file": h.get("file_small") or h["file"], "caption": h.get("caption") or ""}
    return out


def issuer_names(D):
    """Arabic names of issuing bodies for the issuer line in the map panel and the Updates rows: the content pipeline's
    translated issuer names (data/i18n/ar, "issuer:<hash>"), then each country's translated lead institutions, matched by
    position to the English list."""
    from i18n_content import issuer_id
    out = {}
    for i in D["instruments"]:
        for f in ("issuing_authority", "publisher_name"):
            n = (i.get(f) or "").strip()
            k = f"{i['jurisdiction_id']}|{n}"   # per country: the same English name can differ in Arabic
            if n and k not in out and (t := i18n.content(issuer_id(n, i["jurisdiction_id"]), "name", n)): out[k] = t
    for jid, n in (D.get("narratives") or {}).items():
        en = list((n or {}).get("lead_institutions") or [])
        ar = i18n.content(jid, "lead_institutions", en) if en else None
        if isinstance(ar, list) and len(ar) == len(en):
            for e, a in zip(en, ar):
                if e and a:
                    out.setdefault(e.strip(), a.strip()); out.setdefault(re.sub(r"\s*\([^()]*\)\s*$", "", e).strip(), a.strip())
    return out


def build_ar(D, map_html, flags):
    """dist/ar/: every page again, generated with Arabic templates and dates, then the remaining interface text translated.
    Photos, data files and assets are shared with the English site (links are pointed back to them in localise())."""
    i18n.LANG = "ar"
    try:
        AR.mkdir(exist_ok=True)
        inst = {i["id"]: i for i in D["instruments"]}
        ct = {c["id"]: t for c in D["changes"] if c.get("id") for t, _ in [i18n.change_title(c, inst)] if t and t != c.get("title")}
        # Updates rows: Arabic one-line event details (government actions)
        cd = {c["id"]: t for c in D["changes"] if c.get("kind") == "world" and c.get("detail") and (t := i18n.content(c["id"], "detail", c["detail"]))}
        # living map card on the Arabic page: translated hero captions and document titles
        arm = {"captions": {cid: t for cid, ph in map_photos().items() if (t := i18n.content(f"photo:{cid}:hero", "caption", ph["caption"]))},
               "titles": {i["id"]: t for i in D["instruments"] if (t := i18n.content(i["id"], "title", i.get("english_title")))},
               "issuers": issuer_names(D)}
        # Arabic tables for the home page (change titles and details, map captions, titles, issuers): one shared, cached file
        ar_url = shared_asset("home-ar.json", json.dumps({"CT": ct, "CD": cd, "MAP": arm}, ensure_ascii=False, separators=(",", ":")))
        ct_js = '<link rel="preload" href="' + ar_url + '" as="fetch" crossorigin="anonymous"><script>window.RADAR_ASSETS.ar=' + json.dumps(ar_url) + '</script>'
        method = f'<p class="ar-note">{i18n.T("Arabic texts of documents not published in Arabic are translations; the original text is authoritative.")}</p>'
        ar_map = i18n.translate_html(map_html).replace("</head>", ct_js + "</head>", 1)
        k = ar_map.index("</p>", ar_map.index('id="methodDialog"')) + 4      # after the dialog's first paragraph
        (AR / "index.html").write_text(ar_map[:k] + method + ar_map[k:], encoding="utf-8")
        n = pages.write_all(D, load_all(), AR, flags, mirror=True)
        for page in AR.rglob("*.html"):
            if page.name == "index.html" and page.parent == AR: continue
            page.write_text(DATA_DIR.sub(r'\1 dir="auto"', i18n.translate_html(page.read_text(encoding="utf-8"))), encoding="utf-8")
    finally:
        i18n.LANG = "en"
    if (AR / "assets").is_dir() and not any((AR / "assets").iterdir()): (AR / "assets").rmdir()
    (OUT / "assets").mkdir(exist_ok=True)
    (OUT / "assets" / "i18n-ar.js").write_text(i18n.runtime_js(), encoding="utf-8")
    (OUT / "assets" / "ar.css").write_text((ROOT / "site/i18n/ar.css").read_text(encoding="utf-8"), encoding="utf-8")
    return n


def localise(out):
    """Both languages: lang/dir, hreflang alternates and the language switch; Arabic pages also get the font, the runtime
    translator, and links to shared files (photos, assets, data) pointed back at the main site."""
    import os
    for page in out.rglob("*.html"):
        rel = page.relative_to(out).as_posix()
        ar = rel.startswith("ar/")
        path = rel[3:] if ar else rel                      # page path within its language, e.g. country/SAU/index.html
        url = path[:-len("index.html")] if path.endswith("index.html") else path
        depth = url.count("/")
        up = "../" * (depth + (1 if ar else 0))           # from this page to the site root
        other = (up + url) if ar else (up + "ar/" + url)   # same page in the other language
        t = page.read_text(encoding="utf-8")
        if '<html lang="en">' not in t: continue
        alt = (f'<link rel="alternate" hreflang="en" href="{pages.SITE_URL}{url}"><link rel="alternate" hreflang="ar" href="{pages.SITE_URL}ar/{url}">'
               f'<link rel="alternate" hreflang="x-default" href="{pages.SITE_URL}{url}">')
        # language switch: always the last item of the top bar, so it sits in the corner (top-right in English,
        # top-left in Arabic), as on most government sites
        globe = ('<svg class="ls-ico" viewBox="0 0 16 16" width="15" height="15" aria-hidden="true"><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.3"/>'
                 '<path d="M1.5 8h13M8 1.5c2 2 2.8 4.2 2.8 6.5S10 12.5 8 14.5M8 1.5C6 3.5 5.2 5.7 5.2 8S6 12.5 8 14.5" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>')
        switch = (f'<a class="lang-switch" href="{other or "./"}" hreflang="en" lang="en" aria-label="English version">{globe}<span>English</span></a>' if ar else
                  f'<a class="lang-switch" href="{other}" hreflang="ar" lang="ar" aria-label="النسخة العربية">{globe}<span>العربية</span></a>')
        if ar:
            t = t.replace('<html lang="en">', '<html lang="ar" dir="rtl">', 1)
            t = t.replace("</head>", FONT + f'<link rel="stylesheet" href="{up}assets/ar.css">' + alt + f'<script src="{up}assets/i18n-ar.js"></script></head>', 1)
            # shared files: a relative link that resolves outside dist/ar/ content is pointed at the main site
            base = page.parent
            def link(u):
                if "://" in u or u.startswith(("#", "data:", "mailto:", "/", "?")): return u
                path_ = re.split(r"[?#]", u, maxsplit=1)[0]
                tgt = os.path.normpath(base / path_)
                if os.path.exists(tgt): return u
                rest = os.path.relpath(tgt, AR)
                if rest.startswith("..") or not os.path.exists(out / rest): return u
                return os.path.relpath(out / rest, base).replace(os.sep, "/") + ("/" if path_.endswith("/") else "") + u[len(path_):]
            t = re.sub(r'(\b(?:src|href)=")([^"]+)(")', lambda m: m.group(1) + link(m.group(2)) + m.group(3), t)
            t = t.replace('href="EN_ORIGINAL#', f'href="{other or "./"}#')      # machine-translation notes link the English page
            t = re.sub(r'((?:srcset|imagesrcset)=")([^"]+)(")', lambda m: m.group(1) + ", ".join(
                " ".join([link(q.split()[0])] + q.split()[1:]) for q in m.group(2).split(",") if q.strip()) + m.group(3), t)
        else:
            t = t.replace("</head>", alt + "</head>", 1)
        if '<header class="topnav">' in t:
            a = t.index('<header class="topnav">'); b = t.index('</header>', a)
            p_ = t.find('<div class="progress"', a, b)
            at = p_ if p_ > 0 else b
            t = t[:at] + switch + t[at:]
        elif '<header class="topbar">' in t:
            a = t.index('<header class="topbar">'); b = t.index('</header>', a)
            t = t[:b] + switch.replace('class="lang-switch"', 'class="button lang-switch"') + t[b:]
        else:
            t = t.replace("<body>", "<body>" + switch, 1) if "<body>" in t else t
        page.write_text(t, encoding="utf-8")


# The home page loads its data from shared, cacheable files instead of embedding them (EN and AR pages use the same
# files; each URL carries a content hash so a new build is never served from an old cache):
#   assets/data.min.json     the fields the map, panel and Updates tab use
#   assets/world.topo.json   full country and land geometry; assets/world.topo.lo.json: low detail for the moving globe
#   assets/flags.json        flag images
#   data.json                the full public dataset, fetched only for downloads
MIN_FIELDS = {
    "instruments": ["id", "jurisdiction_id", "official_title", "english_title", "legal_status", "lifecycle", "categories",
                    "issuing_authority", "publisher_name", "authority_type", "organization_id", "source_id", "source_url",
                    "publication_date", "verification_level", "government_level", "subnational_unit", "party_status",
                    "adherents", "regional_applicability"],
    "jurisdictions": ["id", "iso2", "name", "short_name", "type", "aliases"],
    "organizations": ["id", "jurisdiction_id", "name", "authority_type", "government_level", "subnational_unit"],
    "regional_applicability": ["instrument_id", "jurisdiction_id", "regional_jurisdiction_id"],
}


def min_data(P):
    m = {k: P[k] for k in ("meta", "categories", "changes", "regional_members")}
    for k, fields in MIN_FIELDS.items():
        m[k] = [{f: x[f] for f in fields if f in x} for x in P[k]]
    return m


def shared_asset(name, text):
    """Write dist/assets/<name> and return its URL with a content hash."""
    (OUT / "assets").mkdir(parents=True, exist_ok=True)
    (OUT / "assets" / name).write_text(text, encoding="utf-8")
    return f"assets/{name}?v={hashlib.sha1(text.encode('utf-8')).hexdigest()[:8]}"


FORBIDDEN = re.compile(r"\bcurl\b|local-retry|WebFetch|maintainer|confirmed by Faisal", re.I)
# visible page text only (scripts, styles and tags removed): repository paths, internal notes and raw field values
VISIBLE_FORBIDDEN = re.compile(r"\bresearch/(?:queue|PROTOCOL|WEEKLY|BACKFILL|TRANSLATION)|\.json\)|data pass")
VISIBLE_OK = re.compile(r"[\w.+-]+@[\w.-]+|https?://\S+|www\.\S+")   # e-mail addresses and URLs quoted in text


def schema_vocab(D):
    """Field names and coded values of the dataset (legal_status, lifecycle, binding_law, ...): never visible on a page."""
    v = set()
    for k in ("instruments", "sources", "organizations", "changes", "jurisdictions"):
        for x in D[k]:
            v.update(f for f in x if "_" in f)
            for f in ("legal_status", "lifecycle", "authority_type", "verification_level", "link_status", "government_level", "kind", "type"):
                if isinstance(x.get(f), str) and "_" in x[f]: v.add(x[f])
    return frozenset(v)


def check_public(out, vocab=frozenset()):
    """Fail the build if research-process wording reaches anything published (pages, data files, downloads)."""
    bad = []
    for f in out.rglob("*"):
        if f.suffix.lower() not in (".html", ".json", ".csv", ".js", ".txt", ".xml") or not f.is_file(): continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        for m in FORBIDDEN.finditer(t):
            bad.append(f"{f.relative_to(out).as_posix()}: '{m.group(0)}' ...{t[max(0, m.start() - 60):m.end() + 40]!r}")
    for f in out.rglob("*.html"):
        t = f.read_text(encoding="utf-8", errors="ignore")
        t = re.sub(r"<(script|style)\b.*?</\1>", " ", t, flags=re.S); t = html.unescape(re.sub(r"<[^>]+>", " ", t)); t = VISIBLE_OK.sub(" ", t)
        for m in list(VISIBLE_FORBIDDEN.finditer(t)) + [m for m in re.finditer(r"\b[a-z]+(?:_[a-z0-9]+)+\b", t) if m.group(0) in vocab]:
            bad.append(f"{f.relative_to(out).as_posix()} (visible): '{m.group(0)}' ...{t[max(0, m.start() - 60):m.end() + 40]!r}")
    for b in bad[:25]: print("PUBLIC DATA CHECK:", b)
    if bad: print(f"PUBLIC DATA CHECK FAILED: {len(bad)} occurrence(s) of research-process wording in dist/")
    return 1 if bad else 0


def build():
    D = assemble()
    P = public(D)                       # what may be published: no research-process fields
    t = (ROOT / "site/template.html").read_text(encoding="utf-8")
    t = t.replace("__VENDOR_JS__", (ROOT / "site/vendor/d3-bundle.min.js").read_text(encoding="utf-8").replace("</", "<\\/"), 1)
    full_json = json.dumps(P, ensure_ascii=False, separators=(",", ":"))
    OUT.mkdir(exist_ok=True)
    (OUT / "data.json").write_text(full_json, encoding="utf-8")
    assets = {"data": shared_asset("data.min.json", json.dumps(min_data(P), ensure_ascii=False, separators=(",", ":"))),
              "geo": shared_asset("world.topo.json", (ROOT / "site/assets/world.topo.json").read_text(encoding="utf-8")),
              "geoLo": shared_asset("world.topo.lo.json", (ROOT / "site/assets/world.topo.lo.json").read_text(encoding="utf-8")),
              "flags": shared_asset("flags.json", (ROOT / "site/assets/flags.json").read_text(encoding="utf-8")),
              "full": f"data.json?v={hashlib.sha1(full_json.encode('utf-8')).hexdigest()[:8]}"}
    t = t.replace("__ASSET_PRELOADS__", "".join(f'<link rel="preload" href="{u}" as="fetch" crossorigin="anonymous">' for k, u in assets.items() if k != "full"), 1)
    t = t.replace("__ASSETS__", json.dumps(assets), 1)
    # SDAIA symbol (the official logo file from Faisal, 21 Oct 2026, with the wordmark removed and the view cropped to the symbol)
    t = t.replace("__SDAIA_LOGO__", shared_asset("sdaia-symbol.svg", (ROOT / "site/assets/sdaia-symbol.svg").read_text(encoding="utf-8")), 1)
    t = t.replace("__PHOTOS__", json.dumps(map_photos(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"), 1)
    t = t.replace("__APP_JS__", (ROOT / "site/app.js").read_text(encoding="utf-8"), 1)
    t = t.replace("__CHANGELOG_CSS__", (ROOT / "site/changelog.css").read_text(encoding="utf-8"), 1)
    t = t.replace("__CHANGELOG_JS__", (ROOT / "site/changelog.js").read_text(encoding="utf-8"), 1)
    t = t.replace("__BUILD_DATE__", pages.fmt_date(D["meta"].get("build_date")))
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(t, encoding="utf-8")
    f = ["date", "recorded", "kind", "type", "jurisdiction_id", "instrument_id", "title", "detail", "from", "to", "source_url"]
    buf = io.StringIO(); w = csv.DictWriter(buf, f, extrasaction="ignore"); w.writeheader(); w.writerows(P["changes"])
    (OUT / "changes.csv").write_text("﻿" + buf.getvalue(), encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    flags = json.loads((ROOT / "site/assets/flags.json").read_text(encoding="utf-8"))
    n_pages = pages.write_all(D, load_all(), OUT, flags)
    n_ar = build_ar(D, t, flags)
    localise(OUT)
    n_busted, n_files = bust_urls(OUT)
    print(f"built dist/index.html ({len(t)/1e6:.1f} MB): {len(D['jurisdictions'])} jurisdictions, "
          f"{len(D['instruments'])} instruments, {len(D['changes'])} change events, "
          f"{D['meta']['deeply_reviewed_country_count']} deep-reviewed countries; {n_pages} country/body pages ({n_ar} in Arabic); cache-busted {n_files} asset URLs in {n_busted} pages")
    import check_ar_charts
    rc = check_ar_charts.main()   # fails the build if an Arabic chart tooltip or legend is left in English
    return rc or check_public(OUT, schema_vocab(D))


if __name__ == "__main__":
    sys.exit(build())
