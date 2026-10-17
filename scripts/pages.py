"""Static country and regional-body pages (UX phase 2).

Called from build.py: pages.write_all(D, recs, out_dir, flags) writes
    <out>/country/<ISO3>/index.html   for every country
    <out>/body/<CODE>/index.html      for every regional / international body
    <out>/assets/country.css, country.js
Charts are rendered here as static SVG (no JavaScript needed to read them); country.js adds
sorting, filters, chart/table toggles, tooltips and the per-country export.
"""
import collections, datetime as dt, html, json, os, re, shutil
from common import ROOT
import geo
import i18n
from subregions import SUBREGION

SITE_URL = os.environ.get("RADAR_SITE_URL", "https://alsallumuw.github.io/ai-governance-radar/").rstrip("/") + "/"
BINDING = {"binding_law", "binding_regulation", "international_treaty", "administrative_policy_mandatory_in_scope"}
WEIGHT = {"binding_law": 0, "international_treaty": 1, "binding_regulation": 2, "administrative_policy_mandatory_in_scope": 3,
          "administrative_guideline": 4, "regulatory_opinion": 4, "nonbinding_guidance": 5, "voluntary_code": 5,
          "national_strategy": 6, "consultation_draft": 7}
STATUS_LABEL = {"binding_law": "Law (binding)", "international_treaty": "International treaty", "binding_regulation": "Regulation (binding)",
                "administrative_policy_mandatory_in_scope": "Mandatory policy (in scope)", "administrative_guideline": "Administrative guideline",
                "regulatory_opinion": "Regulatory opinion", "nonbinding_guidance": "Non-binding guidance", "voluntary_code": "Voluntary code",
                "national_strategy": "National strategy", "consultation_draft": "Draft / consultation"}
TYPE_OF = {"binding_law": "law", "binding_regulation": "regulation", "international_treaty": "treaty",
           "administrative_policy_mandatory_in_scope": "mandatory", "administrative_guideline": "guidance", "nonbinding_guidance": "guidance",
           "regulatory_opinion": "guidance", "voluntary_code": "guidance", "national_strategy": "strategy", "consultation_draft": "draft"}
TYPES = [("law", "Law"), ("regulation", "Regulation"), ("treaty", "Treaty"), ("mandatory", "Mandatory policy"), ("guidance", "Guidance & opinions"),
         ("strategy", "Strategy"), ("draft", "Draft / consultation")]
LIFE = {"draft": "Draft", "consultation": "In consultation", "published": "Published", "adopted": "Adopted", "in_force": "In force",
        "superseded": "Superseded", "repealed": "Repealed"}
VERIFY = {"reviewed_primary_metadata": "Reviewed against the official text", "primary_source_located": "Official source located; text not fully reviewed"}
EVENT = {"published": "Published", "revised": "Revised", "consultation": "Consultation", "adopted": "Adopted", "applied": "Applies / in force",
         "superseded": "Superseded", "repealed": "Repealed"}
BODY_ORDER = ["EU", "GCC", "AU", "ASEAN", "COE", "UNESCO", "OECD", "ICESCO", "ALECSO", "G7", "G20"]
# old body codes: a redirect page is kept at /body/<old>/ and links with ?body=<old> are read as the new code
BODY_REDIRECTS = {"ISESCO": "ICESCO"}

e = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def kind(i):
    if i.get("legal_status") == "consultation_draft": return "draft"
    return "binding" if i.get("legal_status") in BINDING else "soft"


PIPE_TYPE = {"binding_law": "Law", "binding_regulation": "Regulation", "international_treaty": "Treaty",
             "administrative_policy_mandatory_in_scope": "Mandatory policy", "administrative_guideline": "Guideline", "regulatory_opinion": "Opinion",
             "nonbinding_guidance": "Guidance", "voluntary_code": "Code", "national_strategy": "Strategy"}


def pipe_type(i):
    """Type label for an item in the "Open and upcoming" list: drafts say Draft; anything else in consultation says what it is."""
    if i.get("legal_status") == "consultation_draft": return "Draft"
    t = PIPE_TYPE.get(i.get("legal_status"), "Document")
    return f"{t} — open for comment" if i.get("lifecycle") == "consultation" else f"{t} — {LIFE.get(i.get('lifecycle'), 'draft').lower()}"


KIND_LABEL = {"binding": "Binding or mandatory", "soft": "Non-binding", "draft": "Drafts"}
KIND_CLASS = {"binding": "b", "soft": "n", "draft": "d"}
COUNT_NOTE = ("Binding or mandatory: laws, regulations, treaties and policies mandatory within their scope · Non-binding: strategies, guidelines, "
              "guidance, codes and opinions · Drafts: consultation drafts.")


def year(d):
    return int(d[:4]) if d and re.match(r"^\d{4}", d) else None


def date_key(d):
    if not d: return ""
    return d + "-00-00" if len(d) == 4 else d + "-00" if len(d) == 7 else d


def fmt_date(d):
    if not d: return ""
    try:
        if len(d) == 4: return d
        if len(d) == 7:
            x = dt.date(int(d[:4]), int(d[5:7]), 1)
            return f"{i18n.MONTHS[x.month - 1]} {x.year}" if i18n.LANG == "ar" else x.strftime("%b %Y")
        x = dt.date.fromisoformat(d[:10])
        return f"{x.day} {i18n.MONTHS[x.month - 1]} {x.year}" if i18n.LANG == "ar" else f"{x.day} {x.strftime('%b %Y')}"
    except ValueError:
        return d


def cets_text(jid, ctx):
    s = ctx["cets"].get(jid)
    if s: return {"ratified": "Ratified", "signed": "Signed"}.get(s, s.capitalize())
    eu = ctx.get("eu_cets")
    if eu and jid in ctx["members"].get("EU", ()):
        return f"Not signed nationally · EU signatory ({fmt_date(eu)})" if eu != "?" else "Not signed nationally · EU signatory"
    return "Not signed"


def cets_positive(jid, ctx):
    """Header line for CETS 225 on a country page: ratified, signed or covered by the EU's signature; None otherwise."""
    s = ctx["cets"].get(jid)
    if s: return {"ratified": "Ratified", "signed": "Signed"}.get(s, s.capitalize())
    eu = ctx.get("eu_cets")
    if eu and jid in ctx["members"].get("EU", ()):
        return f"EU signatory ({fmt_date(eu)})" if eu != "?" else "EU signatory"
    return None


COUNT_DEFS = ["Binding or mandatory: laws, regulations, treaties and policies mandatory within their scope",
              "Non-binding: strategies, guidelines, guidance, codes and opinions", "Drafts: consultation drafts.",
              "Leads: documents not yet verified as in-scope instruments.",
              "Counts include state, provincial and local instruments; regional instruments are listed separately."]


def count_info():
    """Small (i) button beside the header counts; the definitions open in a popover (country.js)."""
    return ('<div class="count-info"><button type="button" class="info-btn" aria-expanded="false" aria-controls="countDefs" aria-label="About the counts">'
            '<span aria-hidden="true">i</span></button><div class="info-pop" id="countDefs" role="region" aria-label="About the counts" hidden>'
            '<p class="info-h">How the counts are defined</p><ul>' + "".join(f"<li>{e(t)}</li>" for t in COUNT_DEFS) + '</ul></div></div>')


def first_sentence(t, n=158):
    t = re.sub(r"\s+", " ", t or "").strip()
    s = re.split(r"(?<=[.!?])\s", t)[0]
    s = s if len(s) <= n else s[:n - 1].rsplit(" ", 1)[0] + "…"
    return s


# ---------------------------------------------------------------- charts (static SVG)
def chart_years(rows):
    """Stacked columns per publication year: non-binding, binding or mandatory, drafts. Returns (svg, table, undated)."""
    dated = [(year(i.get("publication_date")), kind(i)) for i in rows]
    undated = sum(1 for y, _ in dated if y is None)
    ys = [y for y, _ in dated if y]
    if not ys: return None, None, undated
    lo, hi = min(ys), max(ys)
    earlier = None
    if hi - lo > 15:
        earlier = hi - 15; lo = earlier
    buckets = {}
    for y, b in dated:
        if y is None: continue
        k = max(y, lo) if earlier else y
        buckets.setdefault(k, {"binding": 0, "soft": 0, "draft": 0})[b] += 1
    keys = list(range(lo, hi + 1))
    W, H, L, R, T, B = 360, 190, 26, 4, 10, 26
    pw, ph = W - L - R, H - T - B
    Z = {"binding": 0, "soft": 0, "draft": 0}
    mx = max(sum(buckets.get(k, Z).values()) for k in keys) or 1
    step = 1 if mx <= 6 else 2 if mx <= 12 else 5 if mx <= 30 else 10 if mx <= 60 else 20 if mx <= 120 else 50
    top = ((mx + step - 1) // step) * step
    bw = min(22, pw / len(keys) * .66)
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart grow-y" role="img" aria-label="Instruments per publication year: binding or mandatory, non-binding and drafts">']
    for t in range(0, top + 1, step):
        y = T + ph - ph * t / top
        out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}"/><text class="tick" x="{L - 6}" y="{y + 3:.1f}" text-anchor="end">{t}</text>')
    lab_every = 1 if len(keys) <= 6 else 2 if len(keys) <= 12 else 4
    for n, k in enumerate(keys):
        bk = buckets.get(k, Z)
        cx = L + pw * (n + .5) / len(keys); x = cx - bw / 2; base = T + ph
        label = (f"≤{k}" if earlier and k == lo else str(k))
        segs = [(KIND_CLASS[x], bk[x], KIND_LABEL[x]) for x in ("soft", "binding", "draft")]
        y0 = base
        drawn = [(c, v, nm) for c, v, nm in segs if v]
        out.append(f'<g class="col" style="--i:{n};transform-origin:0 {base:.1f}px">')
        for idx, (c, v, nm) in enumerate(drawn):
            h = ph * v / top; y1 = y0 - h
            gap = 2 if idx > 0 else 0
            hh = max(0.5, h - gap)
            topmost = idx == len(drawn) - 1
            r = min(4, hh, bw / 2) if topmost else 0
            yy = y0 - gap - hh
            if r:
                d = (f"M{x:.1f},{y0 - gap:.1f}V{yy + r:.1f}Q{x:.1f},{yy:.1f} {x + r:.1f},{yy:.1f}H{x + bw - r:.1f}"
                     f"Q{x + bw:.1f},{yy:.1f} {x + bw:.1f},{yy + r:.1f}V{y0 - gap:.1f}Z")
                out.append(f'<path class="mark s-{c}" d="{d}" data-tip="{e(label)}: {v} {nm.lower()}"><title>{e(label)}: {v} {nm.lower()}</title></path>')
            else:
                out.append(f'<rect class="mark s-{c}" x="{x:.1f}" y="{yy:.1f}" width="{bw:.1f}" height="{hh:.1f}" data-tip="{e(label)}: {v} {nm.lower()}"><title>{e(label)}: {v} {nm.lower()}</title></rect>')
            y0 = y1
        out.append('</g>')
        if n % lab_every == 0 or n == len(keys) - 1:
            out.append(f'<text class="tick" x="{cx:.1f}" y="{H - B + 16}" text-anchor="middle">{e(label)}</text>')
    out.append(f'<line class="axis" x1="{L}" x2="{W - R}" y1="{T + ph}" y2="{T + ph}"/></svg>')
    table = ('<table class="data-table"><thead><tr><th scope="col">Year</th><th scope="col">Binding or mandatory</th><th scope="col">Non-binding</th><th scope="col">Drafts</th><th scope="col">Total</th></tr></thead><tbody>'
             + "".join(f'<tr><th scope="row">{"≤"+str(k) if earlier and k == lo else k}</th><td>{buckets[k]["binding"]}</td><td>{buckets[k]["soft"]}</td><td>{buckets[k]["draft"]}</td><td>{sum(buckets[k].values())}</td></tr>' for k in keys if k in buckets)
             + "</tbody></table>")
    return "".join(out), table, undated


def chart_status(rows):
    c = {}
    for i in rows: c[i.get("legal_status")] = c.get(i.get("legal_status"), 0) + 1
    items = sorted([(k, v) for k, v in c.items() if k], key=lambda kv: WEIGHT.get(kv[0], 9))
    if not items: return None, None
    W, rowh, L, R = 360, 26, 158, 30
    H = rowh * len(items) + 8
    mx = max(v for _, v in items)
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart grow-x" role="img" aria-label="Instruments by legal status, ordered by legal weight">']
    for n, (k, v) in enumerate(items):
        y = 4 + n * rowh; w = max(2, (W - L - R) * v / mx); bh = 14; by = y + (rowh - bh) / 2
        r = min(4, w / 2)
        d = f"M{L},{by}H{L + w - r:.1f}Q{L + w:.1f},{by} {L + w:.1f},{by + r}V{by + bh - r}Q{L + w:.1f},{by + bh} {L + w - r:.1f},{by + bh}H{L}Z"
        lab = STATUS_LABEL.get(k) or k.replace('_', ' ').capitalize()
        out.append(f'<text class="cat" x="{L - 10}" y="{by + 11}" text-anchor="end">{e(lab)}</text>'
                   f'<path class="mark s-{KIND_CLASS[kind({"legal_status": k})]}" style="--i:{n};transform-origin:{L}px 0" d="{d}" data-tip="{e(lab)}: {v} ({KIND_LABEL[kind({"legal_status": k})].lower()})"><title>{e(lab)}: {v}</title></path>'
                   f'<text class="val" style="--i:{n}" x="{L + w + 6:.1f}" y="{by + 11}">{v}</text>')
    out.append(f'<line class="axis" x1="{L}" x2="{L}" y1="0" y2="{H}"/></svg>')
    table = ('<table class="data-table"><thead><tr><th scope="col">Legal status</th><th scope="col">Instruments</th></tr></thead><tbody>'
             + "".join(f'<tr><th scope="row">{e(STATUS_LABEL.get(k) or k.replace('_', ' ').capitalize())}</th><td>{v}</td></tr>' for k, v in items) + "</tbody></table>")
    return "".join(out), table


def coverage_grid(cats, audit, rows):
    found = set(audit.get("categories_with_findings") or []) | {c for i in rows for c in i.get("categories", [])}
    none = set(audit.get("categories_where_no_material_was_found") or []) - found
    cells, counts = [], {"found": 0, "none": 0, "na": 0}
    for k, label in cats.items():
        st = "found" if k in found else "none" if k in none else "na"
        counts[st] += 1
        txt = {"found": "Documents found", "none": "Searched, none found", "na": "Not assessed"}[st]
        n = sum(1 for i in rows if k in i.get("categories", []))
        cells.append(f'<li class="cov cov-{st}" data-tip="{e(label)}: {txt}{f" ({n})" if n else ""}"><span class="cov-mark" aria-hidden="true"></span>'
                     f'<span class="cov-label">{e(label)}</span><span class="cov-state">{txt}{f" · {n}" if n else ""}</span></li>')
    return f'<ul class="cov-grid" aria-label="Coverage of the 18 governance categories">{"".join(cells)}</ul>', counts


# ---------------------------------------------------------------- page fragments
AR_SCRIPT = re.compile(r"[\u0600-\u06FF]")


def inst_titles(i, title, orig):
    """English pages: the English title, then the official title if it differs. Arabic pages: the official title as
    published; if it is not in Arabic, the English title below it and, once translated (phase 4b part B), an Arabic
    machine translation marked as such."""
    if i18n.LANG != "ar":
        return f'<h3 class="inst-title">{e(title)}</h3>' + (f'<p class="inst-orig" dir="auto" lang="{e(i.get("language") or "")}">{e(orig)}</p>' if orig else "")
    official = i.get("official_title") or title
    h = f'<h3 class="inst-title" dir="auto" lang="{e(i.get("language") or "")}">{e(official)}</h3>'
    if not AR_SCRIPT.search(official or ""):
        if i.get("english_title") and i["english_title"] != official: h += f'<p class="inst-orig" dir="ltr" lang="en">{e(i["english_title"])}</p>'
        mt = i18n.content(i["id"], "title", i.get("english_title"))
        if mt: h += f'<p class="inst-mt" lang="ar">{e(mt)}{i18n.orig_link(i["id"])}</p>'
    return h


def inst_item(i, orgs, srcs, cats, regional_from=None):
    title = i.get("english_title") or i.get("official_title")
    orig = i.get("official_title") if i.get("official_title") and i.get("official_title") != title else None
    issuer = i.get("issuing_authority") or orgs.get(i.get("organization_id"), {}).get("name") or i.get("publisher_name")
    st = i.get("legal_status"); src = srcs.get(i.get("source_id"), {})
    dates = []
    if i.get("publication_date"): dates.append(i18n.T("Published {date}", date=f'<time datetime="{e(i["publication_date"])}">{e(fmt_date(i["publication_date"]))}</time>'))
    if i.get("effective_date"): dates.append(i18n.T("Effective {date}", date=f'<time datetime="{e(i["effective_date"])}">{e(fmt_date(i["effective_date"]))}</time>'))
    if i.get("last_amended_date"): dates.append(i18n.T("Amended {date}", date=e(fmt_date(i["last_amended_date"]))))
    tags = [f'<span class="tag tag-{kind(i)}">{e(STATUS_LABEL.get(st) or (st or "Status not recorded").replace("_", " ").capitalize())}</span>']
    if i.get("lifecycle") in LIFE: tags.append(f'<span class="tag">{e(LIFE[i["lifecycle"]])}</span>')
    if i.get("government_level") in ("subnational", "local") and i.get("subnational_unit"): tags.append(f'<span class="tag">{e(i["subnational_unit"])}</span>')
    if regional_from: tags.append(f'<span class="tag tag-reg">{e(regional_from)} level · applies here</span>')
    vl = i.get("verification_level")
    links = [f'<a href="{e(i.get("source_url"))}" rel="noopener noreferrer" target="_blank">Official source</a>'] if i.get("source_url") else []
    if i.get("official_pdf_url") and i.get("official_pdf_url") != i.get("source_url"):
        links.append(f'<a href="{e(i["official_pdf_url"])}" rel="noopener noreferrer" target="_blank">PDF</a>')
    catnames = " · ".join(cats.get(c, c) for c in i.get("categories", []))
    title_ar = i18n.content(i["id"], "title", i.get("english_title"))
    sum_ar = i18n.content(i["id"], "summary", i.get("summary"))
    st_ar = i18n.content(i["id"], "status", i.get("current_status"))
    return (f'<article class="inst" id="{e(i["id"])}" data-date="{e(date_key(i.get("publication_date")))}" data-weight="{WEIGHT.get(st, 9)}" data-type="{TYPE_OF.get(st, "guidance")}"'
            f' data-cats="{e(" ".join(i.get("categories", [])))}" data-cat="{e(i.get("category") or "")}" data-text="{e((title + " " + (orig or "") + " " + (title_ar or "") + " " + (issuer or "")).lower())}">'
            + inst_titles(i, title, orig)
            + f'<p class="inst-meta">{e(issuer)}{" · " if issuer and dates else ""}{" · ".join(dates)}</p>'
            + f'<p class="tags">{"".join(tags)}</p>'
            + (f'<p class="inst-sum"{ar_attr(sum_ar)}>{e(sum_ar or i.get("summary"))}{i18n.orig_link(i["id"]) if sum_ar else ""}</p>' if i.get("summary") else "")
            + (f'<p class="inst-status"{ar_attr(st_ar)}>{e(st_ar or i.get("current_status"))}</p>' if i.get("current_status") else "")
            + f'<p class="inst-foot">{" · ".join(links)}<span class="verify v-{e(vl)}">{e(VERIFY.get(vl, vl or "Verification not recorded"))}</span>'
            + (f'<span class="inst-cats">{e(catnames)}</span>' if catnames else "") + '</p>'
            + (f'<details class="src-notes"><summary>Source notes</summary><p lang="en" dir="ltr">{e(i["evidence_reference"])}</p></details>' if i.get("evidence_reference") else "")
            + '</article>')


def figure(fid, title, desc, svg, table, note=""):
    return (f'<figure class="fig" id="{fid}"><figcaption><h3>{e(title)}</h3><p class="fig-desc">{e(desc)}</p></figcaption>'
            f'<div class="fig-chart">{svg}</div><div class="fig-table" hidden>{table}</div>'
            f'<p class="fig-tools"><button type="button" class="linkbtn" data-toggle-table="{fid}" aria-expanded="false">Show as table</button>{(" · " + note) if note else ""}</p></figure>')


def head(title, desc, canon, page_type="article", preload=None):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="color-scheme" content="light dark"><link rel="icon" href="data:,"><title>{e(title)}</title><meta name="description" content="{e(desc)}">'
            f'<link rel="canonical" href="{e(canon)}"><meta property="og:type" content="{page_type}"><meta property="og:site_name" content="AI Governance Radar">'
            f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{e(canon)}">'
            f'<meta name="twitter:card" content="summary"><meta name="twitter:title" content="{e(title)}"><meta name="twitter:description" content="{e(desc)}">'
            + (f'<meta property="og:image" content="{e(SITE_URL + preload["file"])}">' if preload else "")
            + (f'<link rel="preload" as="image" href="../../{e(preload["file_small"])}" imagesrcset="../../{e(preload["file_small"])} 800w, ../../{e(preload["file"])} 1600w" imagesizes="100vw" fetchpriority="high">' if preload else "")
            + '<link rel="stylesheet" href="../../assets/country.css"></head>')


def hero(eyebrow, h1, stats, photo=None, art=None, kind=None, info=""):
    """Full-width page header. With a photo: the photo under a scrim, name and counts over it, credit line below.
    Without one: a country silhouette (kind None) or the member map of a body (kind "map") on a tinted background."""
    k = "photo" if photo else (kind or "shape")
    body = (f'<div class="hero-body"><p class="eyebrow">{eyebrow}</p>{h1}'
            '<div class="stats-row"><dl class="stats">' + "".join(f'<div><dt>{a}</dt><dd data-count="{v}">{v}</dd></div>' for a, v in stats) + f'</dl>{info}</div></div>')
    if photo:
        media = f'<div class="hero-media">{img_tag(photo, "hero-img")}</div><div class="hero-scrim" aria-hidden="true"></div>'
        foot = f'<p class="hero-credit"><span class="hero-cap">{cap(photo)}</span>{credit(photo)}</p>'
    else:
        media = f'<div class="hero-art">{art or ""}</div>'; foot = ""
    return f'<header class="hero hero--{k}" id="top">{media}{body}{foot}</header>'


def topbar(sections, ident=""):
    """Sticky top bar. Once the hero has scrolled away (country.js adds .stuck) it also shows the page's name and counts.
    On narrow screens the section links collapse into a menu (a plain <details>, so it works without JavaScript)."""
    links = "".join(f'<a href="#{k}">{e(v)}</a>' for k, v in sections)
    return ('<header class="topnav"><a class="back" id="backToMap" href="../../">← World map</a><span class="site">AI Governance Radar</span>'
            + (f'<span class="bar-id" aria-hidden="true">{ident}</span>' if ident else "")
            + f'<nav class="toc" aria-label="On this page">{links}</nav>'
            + f'<details class="secmenu"><summary>Sections</summary><nav aria-label="On this page (menu)">{links}</nav></details>'
            + '<div class="progress" aria-hidden="true"><i></i></div></header>')


def bar_ident(name, stats):
    return f'<b>{e(name)}</b>' + "".join(f'<span><em>{v}</em> {e(k.lower() if n else k)}</span>' for n, (k, v) in enumerate(stats[:4]))


# ---------------------------------------------------------------- photos (UX phase 2b)
def img_tag(im, cls="", lazy=False, sizes="100vw", alt=None):
    """<img> for a stored photo (two widths, WebP), paths relative to a country/body page. alt="" for decorative use."""
    big, small = "../../" + im["file"], "../../" + im["file_small"]
    attrs = 'loading="lazy" decoding="async"' if lazy else 'fetchpriority="high" decoding="async"'
    return (f'<img class="{cls}" src="{e(big if not lazy else small)}" srcset="{e(small)} {im["width_small"]}w, {e(big)} {im["width"]}w" sizes="{sizes}" '
            f'width="{im["width"]}" height="{im["height"]}" alt="{e((im.get("alt_ar") or im["alt"]) if alt is None else alt)}" {attrs}>')


def credit(im):
    """Credit line. CC BY / CC BY-SA credits name the changes made ("cropped and resized"), as the licences require."""
    lic = e(im["license"])
    if im.get("license_url"): lic = f'<a href="{e(im["license_url"])}" rel="license noopener" target="_blank">{lic}</a>'
    if im.get("changes"): lic += f' ({e(im["changes"])})'
    return (f'<span class="photo-credit">Photo: <a href="{e(im["commons_url"])}" rel="noopener" target="_blank">{e(im["author"])}</a>, '
            f'{lic}, via Wikimedia Commons</span>')


def photo_band(im):
    """Full-bleed 21:9 heritage / landscape strip before the instrument lists, caption over the image, credit below (gentle parallax in country.js)."""
    return (f'<figure class="photo-break"><div class="pb-media">{img_tag(im, lazy=True)}<p class="pb-cap"><span>{cap(im)}</span></p></div>'
            f'<figcaption>{credit(im)}</figcaption></figure>')


def feature_photo(im):
    """Portrait (4:5) photo beside the overview text; sticky on wide screens while the text scrolls, full width above the text on phones."""
    return (f'<figure class="ov-photo"><div class="ov-media">{img_tag(im, lazy=True, sizes="(min-width: 900px) 420px, 100vw")}</div>'
            f'<figcaption><span class="pp-cap">{cap(im)}</span>{credit(im)}</figcaption></figure>')


def backdrop(im):
    """City photo behind the charts section: fixed (sticky), dimmed and blurred on wide screens; a plain image band above the charts on phones."""
    return (f'<div class="cs-bg" aria-hidden="true"><div class="cs-bg-in">{img_tag(im, lazy=True, sizes="100vw", alt="")}</div></div>'
            f'<p class="cs-cap"><span class="pp-cap">{cap(im)}</span>{credit(im)}</p>')


def closing_strip(jid, j, ctx, hero_img):
    """End of page: the hero photo, faded and desaturated, behind links to four other countries and back to the map.
    Candidates come from groups the country belongs to, in this order: GCC, ALECSO, ASEAN, AU, EU, its UN subregion, then
    ICESCO, COE, OECD, G20, G7. The first group fills the four places and later groups top it up. Within a group countries
    are ranked by number of recorded instruments; countries with none are used only if four cannot be found otherwise."""
    jur, n, mem = ctx["jur"], ctx["n_inst"], ctx["members"]
    sub = SUBREGION.get(jid)
    # never link Israel and GCC / ALECSO member pages to each other in the automatic choice
    arab = set(mem.get("GCC", ())) | set(mem.get("ALECSO", ()))
    blocked = arab if jid == "ISR" else ({"ISR"} if jid in arab else set())
    groups = [(b, jur[b].get("short_name") or b, set(mem.get(b, ()))) for b in ("GCC", "ALECSO", "ASEAN", "AU", "EU") if jid in mem.get(b, ())]
    if sub: groups.append(("sub", sub, {c for c, r in SUBREGION.items() if r == sub}))
    groups += [(b, jur[b].get("short_name") or b, set(mem.get(b, ()))) for b in ("ICESCO", "COE", "OECD", "G20", "G7") if jid in mem.get(b, ())]
    peers, used = [], []
    for allow_zero in (False, True):
        for key, name, cs in groups:
            if len(peers) == 4: break
            cand = sorted((c for c in cs if c != jid and c not in peers and c not in blocked and jur.get(c, {}).get("type") == "country" and (allow_zero or n.get(c, 0) > 0)),
                          key=lambda c: (-n.get(c, 0), jur[c]["name"]))[:4 - len(peers)]
            if cand: peers += cand; used.append(name) if name not in used else None
    label = "From " + ", then ".join(f"{u} (UN subregion)" if u == sub else f"{u} members" for u in used) if used else ""
    ov = ctx["explore_overrides"].get(jid)
    if ov: peers, label = ov["countries"], f'From {ov["group"]}'
    links = "".join(f'<li><a href="../../country/{c}/">{e(jur[c]["name"])}' + (f' <span class="cl-n" title="instruments recorded">{n[c]}</span>' if n.get(c) else "") + '</a></li>' for c in peers)
    bg = f'<div class="closing-bg" aria-hidden="true"><img src="../../{e(hero_img["file_small"])}" alt="" loading="lazy" decoding="async" width="{hero_img["width_small"]}" height="{round(hero_img["width_small"] * 9 / 16)}"></div>' if hero_img else ""
    return (f'<section class="closing" aria-label="Explore other countries">{bg}<div class="closing-in"><h2>Explore other countries</h2>'
            + (f'<p class="closing-sub">{e(label)} · ranked by instruments recorded</p><ul class="closing-links">{links}</ul>' if links else "")
            + '<p class="closing-map"><a href="../../" data-keep-query>← Back to the world map</a></p></div></section>')


def rail(sections, locator_svg=""):
    """Desktop side rail: locator map, section links (current one highlighted by country.js) and a reading-progress line."""
    return ('<aside class="rail" aria-label="Page navigation"><div class="rail-in">'
            + (f'<div class="rail-map">{locator_svg}</div>' if locator_svg else "")
            + '<nav class="rail-nav" aria-label="Sections"><span class="rail-track" aria-hidden="true"><i></i></span><ol>'
            + "".join(f'<li><a href="#{k}">{e(v)}</a></li>' for k, v in sections) + '</ol></nav>'
            + '<p class="rail-top"><a href="#top">Back to top ↑</a></p></div></aside>')


def instruments_section(rows, orgs, srcs, cats, sid="instruments", heading="Instruments", lead=""):
    present_types = [t for t in TYPES if any(TYPE_OF.get(i.get("legal_status")) == t[0] for i in rows)]
    present_cats = [(k, v) for k, v in cats.items() if any(k in i.get("categories", []) for i in rows)]
    rows = sorted(rows, key=lambda i: (date_key(i.get("publication_date")), i.get("english_title") or ""), reverse=True)
    controls = ('<div class="list-controls" role="group" aria-label="Sort and filter">'
                '<label>Sort <select data-sort><option value="newest">Newest first</option><option value="weight">Legal weight</option><option value="category">By category</option></select></label>'
                '<label>Type <select data-ftype><option value="">All types</option>' + "".join(f'<option value="{k}">{e(v)}</option>' for k, v in present_types) + '</select></label>'
                '<label>Category <select data-fcat><option value="">All categories</option>' + "".join(f'<option value="{k}">{e(v)}</option>' for k, v in present_cats) + '</select></label>'
                '<label class="grow">Search <input type="search" data-fq placeholder="Title or issuer"></label></div>')
    return (f'<section id="{sid}" class="block list-block"><h2>{e(heading)} <span class="count">{len(rows)}</span></h2>{lead}{controls}'
            f'<p class="list-status" aria-live="polite"></p><div class="inst-list" data-list>' + "".join(inst_item(i, orgs, srcs, cats) for i in rows) + '</div></section>')


# ---------------------------------------------------------------- pages
def country_page(j, D, rec, flags, ctx):
    jid = j["id"]; cats = D["categories"]
    rows_all = [i for i in D["instruments"] if i["jurisdiction_id"] == jid]
    nat = [i for i in rows_all if i.get("government_level") not in ("subnational", "local")]
    sub = [i for i in rows_all if i.get("government_level") in ("subnational", "local")]
    regional = ctx["inherited"].get(jid, [])
    leads = rec.get("leads") or []
    narr = D["narratives"].get(jid) or {}
    audit = next((a for a in D["coverage_audit"] if a.get("jurisdiction_id") == jid), {}) or {}
    orgs, srcs = ctx["orgs"], ctx["srcs"]
    canon = f"{SITE_URL}country/{jid}/"
    memberships = [b for b in BODY_ORDER if jid in ctx["members"].get(b, ())]
    cets = ctx["cets"].get(jid); c108 = jid in ctx["c108"]
    n_bind = sum(1 for i in rows_all if kind(i) == "binding"); n_draft = sum(1 for i in rows_all if kind(i) == "draft"); n_soft = len(rows_all) - n_bind - n_draft
    title = f"{j['name']}: AI governance profile | AI Governance Radar"
    desc = first_sentence(narr.get("summary")) or f"Official AI-governance laws, strategies and guidance recorded for {j['name']}."
    flag = flags.get((j.get("iso2") or "").lower())
    # sections
    secs = [("overview", "Overview")]
    years_svg, years_tab, undated = chart_years(rows_all)
    status_svg, status_tab = chart_status(rows_all)
    cov_html, cov_counts = coverage_grid(cats, audit, rows_all)
    today = ctx["today"]
    pipe_drafts = sorted([i for i in rows_all if i.get("legal_status") == "consultation_draft" or i.get("lifecycle") in ("consultation", "draft")],
                         key=lambda i: date_key(i.get("publication_date")), reverse=True)
    inst_by_id = {i["id"]: i for i in rows_all}
    future = sorted([c for c in D["changes"] if c.get("jurisdiction_id") == jid and c.get("kind") == "world" and (c.get("date") or "") > today],
                    key=lambda c: c.get("date") or "")
    secs.append(("charts", "Charts"))
    if nat: secs.append(("instruments", "Instruments"))
    if regional: secs.append(("regional", "Regional"))
    if sub: secs.append(("subnational", "Subnational"))
    if leads: secs.append(("leads", "Leads"))
    secs.append(("method", "Method"))
    # a. header
    chips = "".join(f'<a class="chip" href="../../body/{b}/">{e(ctx["jur"][b].get("short_name") or b)}</a>' for b in memberships)
    treaty = []
    cets_line = cets_positive(jid, ctx)
    if cets_line: treaty.append(f'<li><span class="k">CETS 225 (CoE AI Convention)</span><span class="v">{e(cets_line)}</span></li>')
    oa = ctx["oecd"].get(jid)
    if oa: treaty.append(f'<li><span class="k">OECD AI Recommendation</span><span class="v">Adherent{" (OECD member)" if oa.get("member") else " · non-member, since " + fmt_date(oa["date"]) if oa.get("date") else " · non-member"}</span></li>')
    # countries in pending_c108 show no line here; the analysis page note explains them
    if c108: treaty.append('<li><span class="k">Convention 108 (data protection)</span><span class="v">Party</span></li>')
    stats = [("Instruments", len(rows_all)), ("Binding or mandatory", n_bind), ("Non-binding", n_soft), ("Drafts", n_draft), ("Leads", len(leads))]
    ph = ctx["photos"].get(jid) or {}
    hero_img = ph.get("hero")
    H = [head(title, desc, canon, preload=hero_img), f'<body class="cp" data-jid="{e(jid)}" data-build="{e(D["meta"].get("build_date") or "")}">',
         topbar(secs, bar_ident(j["name"], stats)), '<main id="main">']
    eyebrow = e(j.get("region") or "") + (' · Country profile' if j.get("region") else 'Country profile')
    h1 = f'<h1>{"<img class=flag src=" + chr(34) + flag + chr(34) + " alt=" + chr(34) + chr(34) + ">" if flag else ""}{e(j["name"])}</h1>'
    H.append(hero(eyebrow, h1, stats, photo=hero_img, art=None if hero_img else geo.silhouette(jid, j["name"]), info=count_info()))
    H.append('<div class="page layout">' + rail(secs, geo.locator(jid, j["name"])) + '<div class="content">')
    H.append('<section class="intro" aria-label="Memberships and treaty status">'
             + (f'<p class="chips" aria-label="Memberships">{chips}</p>' if chips else "")
             + f'<ul class="facts">{"".join(treaty)}<li><span class="k">Last reviewed</span><span class="v">{e(fmt_date(narr.get("last_deep_review")) or "Not yet deep-reviewed")}</span></li></ul>'
             + f'<p class="hero-links"><a href="../../timeline/?country={e(jid)}">See this country on the timeline →</a><a href="../../analysis/">Global analysis →</a><a href="../../suggest/?country={e(jid)}">Suggest an update →</a></p></section>')
    # b. overview + c. charts in a two-column grid
    ov = ""
    zero = ""
    sum_ar = i18n.content(jid, "summary", narr.get("summary"))
    lead_ar = i18n.content(jid, "lead_institutions", narr.get("lead_institutions"))
    cov_ar = i18n.content(jid, "coverage_note", audit.get("no_material_found_note"))
    notes_ar = i18n.content(jid, "review_notes", narr.get("review_notes"))
    if not rows_all:
        zero = f'<p class="zero"><strong>No official AI-specific instruments found as of {e(fmt_date(narr.get("last_deep_review")) or "the latest review")}.</strong></p>'
        if audit.get("no_material_found_note"): zero += f'<p class="zero-note"{ar_attr(cov_ar)}>{e(cov_ar or audit["no_material_found_note"])}{i18n.orig_link("overview") if cov_ar else ""}</p>'
    if narr.get("summary") or narr.get("lead_institutions") or zero:
        ov = '<section id="overview" class="block prose"><h2>Overview</h2>' + zero + paras(sum_ar or narr.get("summary"), sum_ar, "overview")
        if narr.get("lead_institutions"):
            ov += '<h3 class="minor">Lead institutions</h3><ul class="plain">' + "".join(f'<li{ar_attr(lead_ar)}>{e(x)}</li>' for x in (lead_ar or narr["lead_institutions"])) + '</ul>'
        ov += '</section>'
    figs = []
    if years_svg:
        figs.append(figure("fig-years", "Instruments per year", "By publication year: binding or mandatory, non-binding and drafts. Undated instruments are left out.",
                           '<p class="legend"><span><i class="sw s-b"></i>Binding or mandatory</span><span><i class="sw s-n"></i>Non-binding</span><span><i class="sw s-d"></i>Drafts</span></p>' + years_svg, years_tab,
                           f"{undated} undated instrument{'s' if undated != 1 else ''} not shown" if undated else ""))
    if status_svg:
        figs.append(figure("fig-status", "Legal-status mix", "Instruments by legal status, from most to least binding.", '<p class="legend"><span><i class="sw s-b"></i>Binding or mandatory</span><span><i class="sw s-n"></i>Non-binding</span><span><i class="sw s-d"></i>Drafts</span></p>' + status_svg, status_tab))
    figs.append(f'<figure class="fig" id="fig-coverage"><figcaption><h3>Category coverage</h3><p class="fig-desc">{cov_counts["found"]} of 18 categories with documents · {cov_counts["none"]} searched with none found · {cov_counts["na"]} not assessed.</p></figcaption>{cov_html}</figure>')
    if pipe_drafts or future:
        pl = '<ol class="pipeline" data-upcoming>'
        for c in future[:12]:
            pl += f'<li data-date="{e(c["date"])}"><time datetime="{e(c["date"])}">{e(fmt_date(c["date"]))}</time><span class="pl-kind">{e(EVENT.get(c.get("type"), c.get("type")))}</span><span class="pl-title"{ar_attr(i18n.change_title(c, inst_by_id)[0])}>{e(i18n.change_title(c, inst_by_id)[0] or c.get("title"))}</span></li>'
        pl += '</ol><p class="pl-none muted" hidden>No upcoming dated actions.</p>' if future else '</ol><p class="pl-none muted">No upcoming dated actions recorded.</p>'
        pl += '<div class="pl-passed" hidden><h4>Date passed since this page was built</h4><ol class="pipeline"></ol></div>'
        if pipe_drafts: pl += '<h4>Drafts and documents open for comment</h4><ol class="pipeline">'
        for i in pipe_drafts[:12]:
            d = i.get("publication_date")
            pl += f'<li><time datetime="{e(d or "")}">{e(fmt_date(d) or "Undated")}</time><span class="pl-kind">{e(pipe_type(i))}</span><span class="pl-title"{ar_attr(ar_title(i))}>{e(ar_title(i) or i.get("english_title") or i.get("official_title"))}</span></li>'
        if pipe_drafts: pl += '</ol>'
        more = len(future) + len(pipe_drafts) - min(12, len(future)) - min(12, len(pipe_drafts))
        figs.append(f'<figure class="fig" id="fig-pipeline" data-asof="{e(today)}"><figcaption><h3>Open and upcoming <span class="asof">Upcoming as of {e(fmt_date(today))}</span></h3><p class="fig-desc">Dated government actions still ahead, then drafts and other documents still open for comment.</p></figcaption>{pl}'
                    + ('<p class="fig-tools">Includes non-draft documents still open for comment.</p>' if any(i.get("legal_status") != "consultation_draft" for i in pipe_drafts[:12]) else "")
                    + (f'<p class="fig-tools">{more} more in the instrument list.</p>' if more > 0 else "") + '</figure>')
    feat, bdrop, band = ph.get("feature"), ph.get("backdrop"), ph.get("band")
    ov = ov or '<section id="overview" class="block prose"><h2>Overview</h2><p class="muted">No narrative summary has been written for this jurisdiction yet.</p></section>'
    H.append(f'<div class="ov-grid{" has-photo" if feat else ""}">' + ov + (feature_photo(feat) if feat else "") + '</div>')
    H.append(f'<section id="charts" class="charts-sec{" has-bg" if bdrop else ""}" aria-label="Charts">' + (backdrop(bdrop) if bdrop else "")
             + '<h2 class="charts-h">Charts</h2><div class="panels">' + "".join(figs) + '</div></section>')
    # d. instruments (a full-width 21:9 heritage / landscape band before the first list, else before the method note)
    if band and (nat or regional or sub): H.append(photo_band(band)); band = None
    if nat: H.append(instruments_section(nat, orgs, srcs, cats, lead='<p class="section-lede">National instruments. Sort and filter below; the list prints in full.</p>'))
    # e. regional
    if regional:
        byb = {}
        for i in regional: byb.setdefault(i["jurisdiction_id"], []).append(i)
        H.append(f'<section id="regional" class="block"><h2>Regional and international instruments <span class="count">{len(regional)}</span></h2>'
                 '<p class="section-lede">Instruments of bodies this country belongs to, or treaties it has signed or ratified. Their legal effect follows each instrument\'s own scope.</p>'
                 + "".join(f'<h3 class="minor"><a href="../../body/{b}/">{e(ctx["jur"][b]["name"])}</a></h3><div class="inst-list">'
                           + "".join(inst_item(i, orgs, srcs, cats, regional_from=ctx["jur"][b].get("short_name") or b) for i in rs) + '</div>'
                           for b, rs in sorted(byb.items(), key=lambda kv: BODY_ORDER.index(kv[0]) if kv[0] in BODY_ORDER else 99)) + '</section>')
    # f. subnational
    if sub:
        byu = {}
        for i in sub: byu.setdefault(i.get("subnational_unit") or "Unspecified", []).append(i)
        H.append(f'<section id="subnational" class="block"><h2>State, provincial and local <span class="count">{len(sub)}</span></h2>'
                 + "".join(f'<details class="unit"><summary><span>{e(u)}</span><span class="count">{len(rs)}</span></summary><div class="inst-list">'
                           + "".join(inst_item(i, orgs, srcs, cats) for i in sorted(rs, key=lambda i: date_key(i.get("publication_date")), reverse=True)) + '</div></details>'
                           for u, rs in sorted(byu.items())) + '</section>')
    # g. leads
    if band: H.append(photo_band(band))
    if leads:
        H.append(f'<section id="leads" class="block"><details class="leads"><summary><h2>Leads — not yet verified as in-scope instruments <span class="count">{len(leads)}</span></h2></summary>'
                 '<p class="section-lede">Documents found during research that are not recorded as instruments: no official text could be read, no stated date, still pending, or outside the scope test.</p><ul class="lead-list">'
                 + "".join(f'<li><strong>{e(l.get("english_title") or l.get("title"))}</strong>' + (f'<span class="inst-orig" dir="auto">{e(l.get("title"))}</span>' if l.get("english_title") and l.get("english_title") != l.get("title") else "")
                           + (f'<span class="inst-meta">{e(l.get("issuing_authority"))}</span>' if l.get("issuing_authority") else "") + (f'<span class="lead-note">{e(l.get("note"))}</span>' if l.get("note") else "") + '</li>' for l in leads)
                 + '</ul></details></section>')
    # h. method
    m = '<section id="method" class="block prose method"><h2>Method note</h2>'
    if narr.get("review_notes"): m += f'<p{ar_attr(notes_ar)}>{e(notes_ar or narr["review_notes"])}{i18n.orig_link("method") if notes_ar else ""}</p>'
    m += f'<p>Coverage: {cov_counts["found"]} of the 18 governance categories have documents; {cov_counts["none"]} were searched with no material found; {cov_counts["na"]} were not assessed.' + (f' Review date {e(fmt_date(audit.get("review_date")))}.' if audit.get("review_date") else "") + '</p>'
    if audit.get("no_material_found_note"):
        m += f'<p class="cov-note"{ar_attr(cov_ar)}>{e(cov_ar or audit["no_material_found_note"])}{i18n.orig_link("method") if cov_ar else ""}</p>'
    if audit.get("technical_note"):
        m += f'<details class="tech"><summary>Technical coverage note</summary><p lang="en" dir="ltr">{e(audit["technical_note"])}</p></details>'
    m += ('<p>Only official government and official-body sources are recorded. Dates come from the document or the issuer\'s own page; empty fields mean not verified. '
          '<a href="../../?about=method" data-keep-query>Read the full methodology</a>.</p>'
          '<p class="export"><span>Download this profile:</span><button type="button" class="btn" data-export="csv">CSV</button><button type="button" class="btn" data-export="json">JSON</button></p></section>')
    H.append(m)
    H.append(closing_strip(jid, j, ctx, hero_img))
    bundle = {"meta": {"title": D["meta"].get("title"), "build_date": D["meta"].get("build_date"), "export": "single jurisdiction", "jurisdiction_id": jid, "url": canon},
              "jurisdiction": j, "narrative": narr or None, "instruments": rows_all,
              "regional_instruments_applying_here": [{"id": i["id"], "regional_jurisdiction_id": i["jurisdiction_id"], "english_title": i.get("english_title"), "legal_status": i.get("legal_status"), "source_url": i.get("source_url")} for i in regional],
              "leads": leads, "organizations": [o for o in D["organizations"] if o.get("jurisdiction_id") == jid],
              "sources": [s for s in D["sources"] if any(i.get("source_id") == s["id"] for i in rows_all)], "coverage_audit": audit or None,
              "changes": [c for c in D["changes"] if c.get("jurisdiction_id") == jid]}
    H.append('</div></div></main>' + footer(D) + '<script src="../../assets/country.js" defer></script></body></html>')
    return "".join(H), bundle


def body_page(b, D, rec, flags, ctx):
    bid = b["id"]; cats = D["categories"]
    rows = [i for i in D["instruments"] if i["jurisdiction_id"] == bid]
    narr = D["narratives"].get(bid) or {}
    members = sorted(ctx["members"].get(bid, ()), key=lambda c: i18n.name_key(ctx["jur"].get(c, {}).get("name", c)))
    canon = f"{SITE_URL}body/{bid}/"
    title = f"{b['name']}: AI governance instruments | AI Governance Radar"
    desc = first_sentence(narr.get("summary")) or f"Instruments of the {b['name']} recorded on the AI Governance Radar, and the countries they apply to."
    secs = [("overview", "Overview"), ("charts", "Charts"), ("instruments", "Instruments")] + ([("members", "Members")] if members else []) + [("method", "Method")]
    n_bind = sum(1 for i in rows if kind(i) == "binding"); n_draft = sum(1 for i in rows if kind(i) == "draft")
    stats = [("Instruments", len(rows)), ("Binding or mandatory", n_bind), ("Non-binding", len(rows) - n_bind - n_draft), ("Drafts", n_draft), ("Member states", len(members))]
    H = [head(title, desc, canon), f'<body class="cp" data-jid="{e(bid)}" data-build="{e(D["meta"].get("build_date") or "")}">',
         topbar(secs, bar_ident(b.get("short_name") or b["name"], stats)), '<main id="main">']
    # no logos (trademarks): the hero shows the member states on a world map
    H.append(hero("Regional / international body", f'<h1>{e(b["name"])}</h1>', stats, art=geo.world(members, b["name"], body=bid) if members else None, kind="map"))
    H.append('<div class="page layout">' + rail(secs) + '<div class="content">')
    H.append(f'<section class="intro" aria-label="About the counts"><p class="stats-note">{COUNT_NOTE} Instruments are stored once for the body and listed on each country page they apply to.</p>'
             + f'<p class="hero-links"><a href="../../timeline/?body={e(bid)}">See this body and its members on the timeline →</a><a href="../../analysis/">Global analysis →</a><a href="../../suggest/?country={e(bid)}">Suggest an update →</a></p></section>')
    years_svg, years_tab, undated = chart_years(rows); status_svg, status_tab = chart_status(rows)
    figs = []
    if years_svg: figs.append(figure("fig-years", "Instruments per year", "By publication year: binding or mandatory, non-binding and drafts.",
                                      '<p class="legend"><span><i class="sw s-b"></i>Binding or mandatory</span><span><i class="sw s-n"></i>Non-binding</span><span><i class="sw s-d"></i>Drafts</span></p>' + years_svg, years_tab,
                                      f"{undated} undated not shown" if undated else ""))
    if status_svg: figs.append(figure("fig-status", "Legal-status mix", "Instruments by legal status, from most to least binding.", '<p class="legend"><span><i class="sw s-b"></i>Binding or mandatory</span><span><i class="sw s-n"></i>Non-binding</span><span><i class="sw s-d"></i>Drafts</span></p>' + status_svg, status_tab))
    bsum_ar = i18n.content(bid, "summary", narr.get("summary")); bnotes_ar = i18n.content(bid, "review_notes", narr.get("review_notes"))
    ov = '<section id="overview" class="block prose"><h2>Overview</h2>' + (paras(bsum_ar or narr.get("summary"), bsum_ar, "overview") or f'<p>{e(b.get("overview") or "")}</p>')
    if bid == "OECD" and ctx["oecd"]:
        adh = sorted(ctx["oecd"].items(), key=lambda kv: (kv[1].get("member") is not True, i18n.name_key(ctx["jur"].get(kv[0], {}).get("name", kv[0]))))
        link = lambda c: f'<a href="../../{"body" if ctx["jur"].get(c, {}).get("type") != "country" else "country"}/{c}/">{e(ctx["jur"].get(c, {}).get("name", c))}</a>'
        ov += ('<h3 class="minor">Adherents to the AI Recommendation</h3><table class="data-table plain-table"><thead><tr><th scope="col">Adherent</th><th scope="col">Status</th><th scope="col">Adhered</th></tr></thead><tbody>'
               + "".join(f'<tr><th scope="row">{link(c)}</th><td>{"OECD member" if a.get("member") else "Non-member"}</td><td>{e(fmt_date(a.get("date")) or "Date not listed")}</td></tr>' for c, a in adh)
               + '</tbody></table>')
    if bid == "COE" and ctx["cets"]:
        rows_c = [(c, cets_text(c, ctx)) for c in ctx["cets"]] + [(c, cets_text(c, ctx)) for c in ctx["members"].get("EU", ()) if c not in ctx["cets"]]
        order = lambda r: ({"Ratified": 0, "Signed": 1}.get(r[1], 2), ctx["jur"].get(r[0], {}).get("name", r[0]))
        link = lambda c: (f'<a href="../../{"body" if ctx["jur"].get(c, {}).get("type") != "country" else "country"}/{c}/">{e(ctx["jur"].get(c, {}).get("name", c))}</a>')
        ov += ('<h3 class="minor">CETS 225: Framework Convention on AI</h3><table class="data-table plain-table"><thead><tr><th scope="col">Signatory</th><th scope="col">Status</th></tr></thead><tbody>'
               + "".join(f'<tr><th scope="row">{link(c)}</th><td>{e(s)}</td></tr>' for c, s in sorted(rows_c, key=order)) + '</tbody></table>')
    ov += '</section>'
    H.append('<div class="lede-grid">' + ov + '<aside id="charts" class="panels" aria-label="Charts">' + "".join(figs) + '</aside></div>')
    if rows: H.append(instruments_section(rows, ctx["orgs"], ctx["srcs"], cats))
    if members:
        H.append(f'<section id="members" class="block"><h2>Member states <span class="count">{len(members)}</span></h2><p class="member-grid">'
                 + "".join(f'<a class="chip" href="../../country/{c}/">{e(ctx["jur"].get(c, {}).get("name", c))}</a>' for c in members) + '</p>'
                 + (f'<p class="section-lede">{e((rec.get("members_source") or {}).get("comment"))}</p>' if rec.get("members_source") else "") + '</section>')
    H.append('<section id="method" class="block prose method"><h2>Method note</h2>' + (f'<p{ar_attr(bnotes_ar)}>{e(bnotes_ar or narr.get("review_notes"))}{i18n.orig_link("method") if bnotes_ar else ""}</p>' if narr.get("review_notes") else "")
             + (f'<p>{e(rec.get("membership_note"))}</p>' if rec.get("membership_note") else "")
             + '<p>Only official sources are recorded. <a href="../../?about=method" data-keep-query>Read the full methodology</a>.</p>'
             '<p class="export"><span>Download this profile:</span><button type="button" class="btn" data-export="csv">CSV</button><button type="button" class="btn" data-export="json">JSON</button></p></section>')
    bundle = {"meta": {"title": D["meta"].get("title"), "build_date": D["meta"].get("build_date"), "export": "single jurisdiction", "jurisdiction_id": bid, "url": canon},
              "jurisdiction": b, "narrative": narr or None, "members": members, "instruments": rows,
              "organizations": [o for o in D["organizations"] if o.get("jurisdiction_id") == bid], "changes": [c for c in D["changes"] if c.get("jurisdiction_id") == bid]}
    H.append('</div></div></main>' + footer(D) + '<script src="../../assets/country.js" defer></script></body></html>')
    return "".join(H), bundle


def footer(D, up="../../"):
    return (f'<footer class="pagefoot"><p>AI Governance Radar · official government sources only · data as of {e(fmt_date(D["meta"].get("build_date")))}</p>'
            f'<p><a href="{up}" id="footMap">World map</a> · <a href="{up}analysis/">Analysis</a> · <a href="{up}timeline/">Timeline</a> · <a href="{up}suggest/">Suggest an update</a> · <a href="{up}?about=method">Methodology</a> · <a href="{up}credits/">Photo credits</a></p></footer>')


ROLE_LABEL = {"hero": "Header", "feature": "Beside the overview", "backdrop": "Behind the charts", "band": "Before the instruments"}


def cap(im):
    """Photo caption; on Arabic pages its machine translation, marked as such."""
    if im.get("caption_ar"): return f'<span lang="ar">{e(im["caption_ar"])}</span>'
    return e(im["caption"])


def ar_attr(t):
    return ' lang="ar" dir="rtl"' if t else ""


def ar_title(i):
    """Arabic pages: an Arabic official title, else the machine translation of the English title."""
    if i18n.LANG != "ar": return None
    if AR_SCRIPT.search(i.get("official_title") or ""): return i["official_title"]
    return i18n.content(i["id"], "title", i.get("english_title"))


def paras(text, is_ar=False, anchor=None):
    """Paragraphs of a narrative; a translated one ends with the small link to the original text."""
    ps = [p for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    return "".join(f'<p{ar_attr(is_ar)}>{e(p)}{i18n.orig_link(anchor) if is_ar and anchor and n == len(ps) - 1 else ""}</p>' for n, p in enumerate(ps))


def load_photos():
    """data/photos.json -> {ISO3: {role: image}} with roles hero, feature, backdrop, band"""
    p = ROOT / "data/photos.json"
    if not p.exists(): return {}
    out = {cid: {im["role"]: dict(im) for im in ph.get("photos") or []}
           for cid, ph in json.loads(p.read_text(encoding="utf-8")).get("countries", {}).items()}
    for cid, ims in out.items():          # Arabic pages: machine-translated caption and alt text (credits stay as published)
        for role, im in ims.items():
            for f in ("caption", "alt"):
                t = i18n.content(f"photo:{cid}:{role}", f, im.get(f))
                if t: im[f + "_ar"] = t
    return out


def credits_page(D, ctx):
    """/credits/: every photo used on the site, with author, licence and a link to its Commons page."""
    photos = ctx["photos"]; jur = ctx["jur"]
    rows, fallback = [], []
    for cid in sorted((c for c, j in jur.items() if j.get("type") == "country"), key=lambda c: i18n.name_key(jur[c].get("name", c))):
        ph = photos.get(cid) or {}
        ims = [(ROLE_LABEL[r], ph[r]) for r in ROLE_LABEL if ph.get(r)]
        if not ph.get("hero"): fallback.append(cid)
        for role, im in ims:
            lic = f'<a href="{e(im["license_url"])}" rel="license noopener">{e(im["license"])}</a>' if im.get("license_url") else e(im["license"])
            rows.append(f'<tr><th scope="row"><a href="../country/{cid}/">{e(jur.get(cid, {}).get("name", cid))}</a></th><td>{role}</td><td>{e(im["subject"])}</td>'
                        f'<td>{e(im["author"])}</td><td>{lic}</td><td><a href="{e(im["commons_url"])}" rel="noopener">{e(im["title"])}</a></td></tr>')
    n_img = len(rows)
    title = "Photo credits | AI Governance Radar"
    H = [head(title, "Authors and licences of the photos used on the AI Governance Radar country pages.", f"{SITE_URL}credits/").replace('href="../../assets/', 'href="../assets/'),
         '<body class="cp credits"><header class="topnav"><a class="back" id="backToMap" href="../">← World map</a><span class="site">AI Governance Radar</span></header>',
         '<main class="page"><header class="hero"><p class="eyebrow">About the photos</p><h1>Photo credits</h1>'
         f'<p class="section-lede">{n_img} photos on {sum(1 for c in photos.values() if c.get("hero"))} country pages. All come from Wikimedia Commons under a public-domain, CC0, CC BY or CC BY-SA licence, '
         'were cropped (landscape, portrait or panoramic), resized and converted to WebP for this site, and are served from this site (not hotlinked). Each photo carries a caption and its own credit line where it appears. '
         'Images under CC BY-SA are shared here under the same licence; changes: cropped and resized to WebP. '
         'Regional and international bodies are shown with a map of their members rather than a logo.</p></header>'
         '<div class="table-wrap"><table class="data-table plain-table credits-table"><thead><tr><th scope="col">Country</th><th scope="col">Used as</th><th scope="col">What it shows</th>'
         '<th scope="col">Author</th><th scope="col">Licence</th><th scope="col">Commons file</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>']
    if fallback:
        H.append('<p class="section-lede">No suitable freely licensed photo was found for: ' + ", ".join(f'<a href="../country/{c}/">{e(jur.get(c, {}).get("name", c))}</a>' for c in fallback)
                 + '. These pages show an outline of the country instead.</p>')
    H.append('</main>' + footer(D, "../") + '</body></html>')
    return "".join(H)


def write_all(D, recs, out, flags, mirror=False):
    """mirror=True: a language mirror (dist/ar/) that shares the photos and assets of the main site instead of copying them."""
    jur = {j["id"]: j for j in D["jurisdictions"]}
    inst = {i["id"]: i for i in D["instruments"]}
    inherited = {}
    for a in D["regional_applicability"]:
        i = inst.get(a["instrument_id"])
        if i: inherited.setdefault(a["jurisdiction_id"], []).append(i)
    members = {k: set(v) for k, v in (D.get("regional_members") or {}).items()}
    cets, c108, eu_cets, oecd = {}, set(), None, {}
    for i in D["instruments"]:
        if i["jurisdiction_id"] == "OECD" and i.get("adherents"): oecd = i["adherents"]
        if i["jurisdiction_id"] == "COE" and i.get("party_status"):
            cets = {k: v.get("status") for k, v in i["party_status"].items()}
            eu_cets = (i["party_status"].get("EU") or {}).get("date") or ("?" if "EU" in i["party_status"] else None)
        if i["jurisdiction_id"] == "COE" and "Convention for the Protection of Individuals" in (i.get("english_title") or ""):
            c108 = set(i.get("regional_applicability") or [])
    try:
        q = json.loads((ROOT / "research/queue.json").read_text(encoding="utf-8")); c108_pending = set(q.get("pending_c108") or [])
    except Exception:
        c108_pending = set()
    ctx = {"jur": jur, "inherited": inherited, "members": members, "cets": cets, "eu_cets": eu_cets, "c108": c108, "c108_pending": c108_pending, "oecd": oecd,
           "orgs": {o["id"]: o for o in D["organizations"]}, "srcs": {s["id"]: s for s in D["sources"]},
           "today": D["meta"].get("build_date") or dt.date.today().isoformat(), "photos": load_photos(),
           "explore_overrides": {k: v for k, v in json.loads((ROOT / "data/explore_overrides.json").read_text(encoding="utf-8")).items() if not k.startswith("_")} if (ROOT / "data/explore_overrides.json").exists() else {},
           "n_inst": collections.Counter(i["jurisdiction_id"] for i in D["instruments"])}
    (out / "assets").mkdir(parents=True, exist_ok=True)
    for f in () if mirror else ("country.css", "country.js", "analysis.css", "analysis.js", "timeline.js", "suggest.js"):
        (out / "assets" / f).write_text((ROOT / "site" / f).read_text(encoding="utf-8"), encoding="utf-8")
    # photos (site/img) are copied as they are; never hotlinked
    if (ROOT / "site/img").is_dir() and not mirror:
        shutil.copytree(ROOT / "site/img", out / "img", dirs_exist_ok=True)
    n = 0
    for rec in recs.values():
        j = rec["jurisdiction"]
        if j["type"] == "country":
            p = out / "country" / j["id"]; html_, bundle = country_page(j, D, rec, flags, ctx)
        else:
            p = out / "body" / j["id"]; html_, bundle = body_page(j, D, rec, flags, ctx)
        p.mkdir(parents=True, exist_ok=True); (p / "index.html").write_text(html_, encoding="utf-8"); n += 1
        # the export bundle is fetched only when someone downloads the profile, so it stays out of the first page load
        (p / "profile.json").write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out / "credits").mkdir(exist_ok=True)
    (out / "credits" / "index.html").write_text(credits_page(D, ctx), encoding="utf-8")
    for old_code, new_code in BODY_REDIRECTS.items():
        p = out / "body" / old_code; p.mkdir(parents=True, exist_ok=True)
        to = f"../{new_code}/"; name = ctx["jur"].get(new_code, {}).get("name", new_code)
        (p / "index.html").write_text(
            f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">'
            f'<title>{e(old_code)} is now {e(new_code)} | AI Governance Radar</title><link rel="canonical" href="{SITE_URL}body/{new_code}/"><meta name="robots" content="noindex">'
            f'<meta http-equiv="refresh" content="0; url={to}"><script>location.replace("{to}"+location.search+location.hash)</script></head>'
            f'<body><p>{e(old_code)} is now {e(new_code)}. Continue to <a href="{to}">{e(name)}</a>.</p></body></html>', encoding="utf-8")
    import analysis
    analysis.write(D, recs, out, ctx)
    return n
