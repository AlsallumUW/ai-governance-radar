#!/usr/bin/env python3
"""Assemble data/ into one database and build the static site.

    python3 scripts/build.py            -> dist/index.html, dist/data.json, dist/changes.csv
"""
import csv, hashlib, io, json, re, sys
from common import ROOT, DATA, load, load_all
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


def build_ar(D, map_html, flags):
    """dist/ar/: every page again, generated with Arabic templates and dates, then the remaining interface text translated.
    Photos, data files and assets are shared with the English site (links are pointed back to them in localise())."""
    i18n.LANG = "ar"
    try:
        AR.mkdir(exist_ok=True)
        inst = {i["id"]: i for i in D["instruments"]}
        ct = {c["id"]: t for c in D["changes"] if c.get("id") for t, _ in [i18n.change_title(c, inst)] if t and t != c.get("title")}
        ct_js = ('<script>window.AR_CT=' + json.dumps(ct, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ';</script>') if ct else ""
        # living map card on the Arabic page: translated hero captions and document titles
        arm = {"captions": {cid: t for cid, ph in map_photos().items() if (t := i18n.content(f"photo:{cid}:hero", "caption", ph["caption"]))},
               "titles": {i["id"]: t for i in D["instruments"] if (t := i18n.content(i["id"], "title", i.get("english_title")))}}
        ct_js += '<script>window.AR_MAP=' + json.dumps(arm, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ';</script>'
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
        switch = (f'<a class="lang-switch" href="{other or "./"}" hreflang="en" lang="en">English</a>' if ar else
                  f'<a class="lang-switch" href="{other}" hreflang="ar" lang="ar">العربية</a>')
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
        if '<span class="site">' in t:
            t = re.sub(r'(<span class="site">[^<]*</span>)', lambda m: m.group(1) + switch, t, count=1)
        elif '<div class="actions">' in t:
            t = t.replace('<div class="actions">', '<div class="actions">' + switch.replace('class="lang-switch"', 'class="button lang-switch"'), 1)
        else:
            t = t.replace("<body>", "<body>" + switch, 1) if "<body>" in t else t
        page.write_text(t, encoding="utf-8")


def build():
    D = assemble()
    t = (ROOT / "site/template.html").read_text(encoding="utf-8")
    payload = json.dumps(D, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    t = t.replace("__VENDOR_JS__", (ROOT / "site/vendor/d3-bundle.min.js").read_text(encoding="utf-8").replace("</", "<\\/"), 1)
    t = t.replace("__GEOMETRY__", (ROOT / "site/assets/world.topo.json").read_text(encoding="utf-8"), 1)
    t = t.replace("__FLAGS__", (ROOT / "site/assets/flags.json").read_text(encoding="utf-8"), 1)
    t = t.replace("__PHOTOS__", json.dumps(map_photos(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"), 1)
    t = t.replace("__APP_JS__", (ROOT / "site/app.js").read_text(encoding="utf-8"), 1)
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
    flags = json.loads((ROOT / "site/assets/flags.json").read_text(encoding="utf-8"))
    n_pages = pages.write_all(D, load_all(), OUT, flags)
    n_ar = build_ar(D, t, flags)
    localise(OUT)
    n_busted, n_files = bust_urls(OUT)
    print(f"built dist/index.html ({len(t)/1e6:.1f} MB): {len(D['jurisdictions'])} jurisdictions, "
          f"{len(D['instruments'])} instruments, {len(D['changes'])} change events, "
          f"{D['meta']['deeply_reviewed_country_count']} deep-reviewed countries; {n_pages} country/body pages ({n_ar} in Arabic); cache-busted {n_files} asset URLs in {n_busted} pages")


if __name__ == "__main__":
    sys.exit(build())
