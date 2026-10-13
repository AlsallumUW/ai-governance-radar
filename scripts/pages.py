"""Static country and regional-body pages (UX phase 2).

Called from build.py: pages.write_all(D, recs, out_dir, flags) writes
    <out>/country/<ISO3>/index.html   for every country
    <out>/body/<CODE>/index.html      for every regional / international body
    <out>/assets/country.css, country.js
Charts are rendered here as static SVG (no JavaScript needed to read them); country.js adds
sorting, filters, chart/table toggles, tooltips and the per-country export.
"""
import datetime as dt, html, json, os, re
from common import ROOT

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
BODY_ORDER = ["EU", "GCC", "AU", "ASEAN", "COE", "UNESCO", "OECD", "ICESCO", "G7", "G20"]
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
        if len(d) == 7: return dt.date(int(d[:4]), int(d[5:7]), 1).strftime("%b %Y")
        x = dt.date.fromisoformat(d[:10]); return f"{x.day} {x.strftime('%b %Y')}"
    except ValueError:
        return d


def cets_text(jid, ctx):
    s = ctx["cets"].get(jid)
    if s: return {"ratified": "Ratified", "signed": "Signed"}.get(s, s.capitalize())
    eu = ctx.get("eu_cets")
    if eu and jid in ctx["members"].get("EU", ()):
        return f"Not signed nationally · EU signatory ({fmt_date(eu)})" if eu != "?" else "Not signed nationally · EU signatory"
    return "Not signed"


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
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Instruments per publication year: binding or mandatory, non-binding and drafts">']
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
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Instruments by legal status, ordered by legal weight">']
    for n, (k, v) in enumerate(items):
        y = 4 + n * rowh; w = max(2, (W - L - R) * v / mx); bh = 14; by = y + (rowh - bh) / 2
        r = min(4, w / 2)
        d = f"M{L},{by}H{L + w - r:.1f}Q{L + w:.1f},{by} {L + w:.1f},{by + r}V{by + bh - r}Q{L + w:.1f},{by + bh} {L + w - r:.1f},{by + bh}H{L}Z"
        lab = STATUS_LABEL.get(k) or k.replace('_', ' ').capitalize()
        out.append(f'<text class="cat" x="{L - 10}" y="{by + 11}" text-anchor="end">{e(lab)}</text>'
                   f'<path class="mark s-{KIND_CLASS[kind({"legal_status": k})]}" d="{d}" data-tip="{e(lab)}: {v} ({KIND_LABEL[kind({"legal_status": k})].lower()})"><title>{e(lab)}: {v}</title></path>'
                   f'<text class="val" x="{L + w + 6:.1f}" y="{by + 11}">{v}</text>')
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
def inst_item(i, orgs, srcs, cats, regional_from=None):
    title = i.get("english_title") or i.get("official_title")
    orig = i.get("official_title") if i.get("official_title") and i.get("official_title") != title else None
    issuer = i.get("issuing_authority") or orgs.get(i.get("organization_id"), {}).get("name") or i.get("publisher_name")
    st = i.get("legal_status"); src = srcs.get(i.get("source_id"), {})
    dates = []
    if i.get("publication_date"): dates.append(f'Published <time datetime="{e(i["publication_date"])}">{e(fmt_date(i["publication_date"]))}</time>')
    if i.get("effective_date"): dates.append(f'Effective <time datetime="{e(i["effective_date"])}">{e(fmt_date(i["effective_date"]))}</time>')
    if i.get("last_amended_date"): dates.append(f'Amended {e(fmt_date(i["last_amended_date"]))}')
    tags = [f'<span class="tag tag-{kind(i)}">{e(STATUS_LABEL.get(st) or (st or "Status not recorded").replace("_", " ").capitalize())}</span>']
    if i.get("lifecycle") in LIFE: tags.append(f'<span class="tag">{e(LIFE[i["lifecycle"]])}</span>')
    if i.get("government_level") in ("subnational", "local") and i.get("subnational_unit"): tags.append(f'<span class="tag">{e(i["subnational_unit"])}</span>')
    if regional_from: tags.append(f'<span class="tag tag-reg">{e(regional_from)} level · applies here</span>')
    vl = i.get("verification_level")
    links = [f'<a href="{e(i.get("source_url"))}" rel="noopener noreferrer" target="_blank">Official source</a>'] if i.get("source_url") else []
    if i.get("official_pdf_url") and i.get("official_pdf_url") != i.get("source_url"):
        links.append(f'<a href="{e(i["official_pdf_url"])}" rel="noopener noreferrer" target="_blank">PDF</a>')
    catnames = " · ".join(cats.get(c, c) for c in i.get("categories", []))
    return (f'<article class="inst" data-date="{e(date_key(i.get("publication_date")))}" data-weight="{WEIGHT.get(st, 9)}" data-type="{TYPE_OF.get(st, "guidance")}"'
            f' data-cats="{e(" ".join(i.get("categories", [])))}" data-cat="{e(i.get("category") or "")}" data-text="{e((title + " " + (orig or "") + " " + (issuer or "")).lower())}">'
            f'<h3 class="inst-title">{e(title)}</h3>' + (f'<p class="inst-orig" dir="auto" lang="{e(i.get("language") or "")}">{e(orig)}</p>' if orig else "")
            + f'<p class="inst-meta">{e(issuer)}{" · " if issuer and dates else ""}{" · ".join(dates)}</p>'
            + f'<p class="tags">{"".join(tags)}</p>'
            + (f'<p class="inst-sum">{e(i.get("summary"))}</p>' if i.get("summary") else "")
            + (f'<p class="inst-status">{e(i.get("current_status"))}</p>' if i.get("current_status") else "")
            + f'<p class="inst-foot">{" · ".join(links)}<span class="verify v-{e(vl)}">{e(VERIFY.get(vl, vl or "Verification not recorded"))}</span>'
            + (f'<span class="inst-cats">{e(catnames)}</span>' if catnames else "") + '</p></article>')


def figure(fid, title, desc, svg, table, note=""):
    return (f'<figure class="fig" id="{fid}"><figcaption><h3>{e(title)}</h3><p class="fig-desc">{e(desc)}</p></figcaption>'
            f'<div class="fig-chart">{svg}</div><div class="fig-table" hidden>{table}</div>'
            f'<p class="fig-tools"><button type="button" class="linkbtn" data-toggle-table="{fid}" aria-expanded="false">Show as table</button>{(" · " + note) if note else ""}</p></figure>')


def head(title, desc, canon, page_type="article"):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="color-scheme" content="light dark"><link rel="icon" href="data:,"><title>{e(title)}</title><meta name="description" content="{e(desc)}">'
            f'<link rel="canonical" href="{e(canon)}"><meta property="og:type" content="{page_type}"><meta property="og:site_name" content="AI Governance Radar">'
            f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{e(canon)}">'
            f'<meta name="twitter:card" content="summary"><meta name="twitter:title" content="{e(title)}"><meta name="twitter:description" content="{e(desc)}">'
            f'<link rel="stylesheet" href="../../assets/country.css"></head>')


def topbar(sections):
    return ('<header class="topnav"><a class="back" id="backToMap" href="../../">← World map</a><span class="site">AI Governance Radar</span>'
            '<nav class="toc" aria-label="On this page">' + "".join(f'<a href="#{k}">{e(v)}</a>' for k, v in sections) + '</nav></header>')


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
    cets = ctx["cets"].get(jid); c108 = jid in ctx["c108"]; c108_pending = jid in ctx["c108_pending"]
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
    future = sorted([c for c in D["changes"] if c.get("jurisdiction_id") == jid and c.get("kind") == "world" and (c.get("date") or "") > today],
                    key=lambda c: c.get("date") or "")
    secs.append(("charts", "Charts"))
    if nat: secs.append(("instruments", "Instruments"))
    if regional: secs.append(("regional", "Regional"))
    if sub: secs.append(("subnational", "Subnational"))
    if leads: secs.append(("leads", "Leads"))
    secs.append(("method", "Method"))
    H = [head(title, desc, canon), '<body class="cp">', topbar(secs), '<main class="page">']
    # a. header
    chips = "".join(f'<a class="chip" href="../../body/{b}/">{e(ctx["jur"][b].get("short_name") or b)}</a>' for b in memberships)
    treaty = []
    treaty.append(f'<li><span class="k">CETS 225 (CoE AI Convention)</span><span class="v">{e(cets_text(jid, ctx))}</span></li>')
    oa = ctx["oecd"].get(jid)
    if oa: treaty.append(f'<li><span class="k">OECD AI Recommendation</span><span class="v">Adherent{" (OECD member)" if oa.get("member") else " · non-member, since " + fmt_date(oa["date"]) if oa.get("date") else " · non-member"}</span></li>')
    treaty.append(f'<li><span class="k">Convention 108 (data protection)</span><span class="v">{"Party" if c108 else "Party; ratification act pending verification" if c108_pending else "Not recorded as a party"}</span></li>')
    stats = [("Instruments", len(rows_all)), ("Binding or mandatory", n_bind), ("Non-binding", n_soft), ("Drafts", n_draft), ("Leads", len(leads))]
    H.append('<header class="hero" id="top"><p class="eyebrow">' + e(j.get("region") or "") + (' · Country profile' if j.get("region") else 'Country profile') + '</p>'
             + f'<h1>{"<img class=flag src=" + chr(34) + flag + chr(34) + " alt=" + chr(34) + chr(34) + ">" if flag else ""}{e(j["name"])}</h1>'
             + (f'<p class="chips" aria-label="Memberships">{chips}</p>' if chips else "")
             + f'<ul class="facts">{"".join(treaty)}<li><span class="k">Last reviewed</span><span class="v">{e(fmt_date(narr.get("last_deep_review")) or "Not yet deep-reviewed")}</span></li></ul>'
             + '<dl class="stats">' + "".join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in stats) + '</dl>'
             + f'<p class="stats-note">{COUNT_NOTE} Leads: documents not yet verified as in-scope instruments. Counts include state, provincial and local instruments; regional instruments are listed separately.</p>'
             + f'<p class="hero-links"><a href="../../timeline/?country={e(jid)}">See this country on the timeline →</a><a href="../../analysis/">Global analysis →</a><a href="../../suggest/?country={e(jid)}">Suggest an update →</a></p></header>')
    # b. overview + c. charts in a two-column grid
    ov = ""
    zero = ""
    if not rows_all:
        zero = f'<p class="zero"><strong>No official AI-specific instruments found as of {e(fmt_date(narr.get("last_deep_review")) or "the latest review")}.</strong></p>'
        if audit.get("no_material_found_note"): zero += f'<p class="zero-note">{e(audit["no_material_found_note"])}</p>'
    if narr.get("summary") or narr.get("lead_institutions") or zero:
        ov = '<section id="overview" class="block prose"><h2>Overview</h2>' + zero + "".join(f'<p>{e(p)}</p>' for p in re.split(r"\n\s*\n", narr.get("summary") or "") if p.strip())
        if narr.get("lead_institutions"):
            ov += '<h3 class="minor">Lead institutions</h3><ul class="plain">' + "".join(f'<li>{e(x)}</li>' for x in narr["lead_institutions"]) + '</ul>'
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
            pl += f'<li data-date="{e(c["date"])}"><time datetime="{e(c["date"])}">{e(fmt_date(c["date"]))}</time><span class="pl-kind">{e(EVENT.get(c.get("type"), c.get("type")))}</span><span class="pl-title">{e(c.get("title"))}</span></li>'
        pl += '</ol><p class="pl-none muted" hidden>No upcoming dated actions.</p>' if future else '</ol><p class="pl-none muted">No upcoming dated actions recorded.</p>'
        pl += '<div class="pl-passed" hidden><h4>Date passed since this page was built</h4><ol class="pipeline"></ol></div>'
        if pipe_drafts: pl += '<h4>Drafts and documents open for comment</h4><ol class="pipeline">'
        for i in pipe_drafts[:12]:
            d = i.get("publication_date")
            pl += f'<li><time datetime="{e(d or "")}">{e(fmt_date(d) or "Undated")}</time><span class="pl-kind">{e(pipe_type(i))}</span><span class="pl-title">{e(i.get("english_title") or i.get("official_title"))}</span></li>'
        if pipe_drafts: pl += '</ol>'
        more = len(future) + len(pipe_drafts) - min(12, len(future)) - min(12, len(pipe_drafts))
        figs.append(f'<figure class="fig" id="fig-pipeline" data-asof="{e(today)}"><figcaption><h3>Open and upcoming <span class="asof">Upcoming as of {e(fmt_date(today))}</span></h3><p class="fig-desc">Dated government actions still ahead, then drafts and other documents still open for comment.</p></figcaption>{pl}'
                    + ('<p class="fig-tools">Includes non-draft documents still open for comment.</p>' if any(i.get("legal_status") != "consultation_draft" for i in pipe_drafts[:12]) else "")
                    + (f'<p class="fig-tools">{more} more in the instrument list.</p>' if more > 0 else "") + '</figure>')
    H.append('<div class="lede-grid">' + (ov or '<section id="overview" class="block prose"><h2>Overview</h2><p class="muted">No narrative summary has been written for this jurisdiction yet.</p></section>')
             + '<aside id="charts" class="panels" aria-label="Charts">' + "".join(figs) + '</aside></div>')
    # d. instruments
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
    if leads:
        H.append(f'<section id="leads" class="block"><details class="leads"><summary><h2>Leads — not yet verified as in-scope instruments <span class="count">{len(leads)}</span></h2></summary>'
                 '<p class="section-lede">Documents found during research that are not recorded as instruments: no official text could be read, no stated date, still pending, or outside the scope test.</p><ul class="lead-list">'
                 + "".join(f'<li><strong>{e(l.get("english_title") or l.get("title"))}</strong>' + (f'<span class="inst-orig" dir="auto">{e(l.get("title"))}</span>' if l.get("english_title") and l.get("english_title") != l.get("title") else "")
                           + (f'<span class="inst-meta">{e(l.get("issuing_authority"))}</span>' if l.get("issuing_authority") else "") + (f'<span class="lead-note">{e(l.get("note"))}</span>' if l.get("note") else "") + '</li>' for l in leads)
                 + '</ul></details></section>')
    # h. method
    m = '<section id="method" class="block prose method"><h2>Method note</h2>'
    if narr.get("review_notes"): m += f'<p>{e(narr["review_notes"])}</p>'
    m += f'<p>Coverage: {cov_counts["found"]} of the 18 governance categories have documents; {cov_counts["none"]} were searched with no material found; {cov_counts["na"]} were not assessed.' + (f' Review date {e(fmt_date(audit.get("review_date")))}.' if audit.get("review_date") else "") + '</p>'
    if audit.get("no_material_found_note"):
        m += f'<details class="tech"><summary>Technical coverage note</summary><p>{e(audit["no_material_found_note"])}</p></details>'
    m += ('<p>Only official government and official-body sources are recorded. Dates come from the document or the issuer\'s own page; empty fields mean not verified. '
          '<a href="../../?about=method" data-keep-query>Read the full methodology</a>.</p>'
          '<p class="export"><span>Download this profile:</span><button type="button" class="btn" data-export="csv">CSV</button><button type="button" class="btn" data-export="json">JSON</button></p></section>')
    H.append(m)
    bundle = {"meta": {"title": D["meta"].get("title"), "build_date": D["meta"].get("build_date"), "export": "single jurisdiction", "jurisdiction_id": jid, "url": canon},
              "jurisdiction": j, "narrative": narr or None, "instruments": rows_all,
              "regional_instruments_applying_here": [{"id": i["id"], "regional_jurisdiction_id": i["jurisdiction_id"], "english_title": i.get("english_title"), "legal_status": i.get("legal_status"), "source_url": i.get("source_url")} for i in regional],
              "leads": leads, "organizations": [o for o in D["organizations"] if o.get("jurisdiction_id") == jid],
              "sources": [s for s in D["sources"] if any(i.get("source_id") == s["id"] for i in rows_all)], "coverage_audit": audit or None,
              "changes": [c for c in D["changes"] if c.get("jurisdiction_id") == jid]}
    H.append('</main>' + footer(D) + '<script id="profile-data" type="application/json">' + json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
             + '</script><script src="../../assets/country.js" defer></script></body></html>')
    return "".join(H)


def body_page(b, D, rec, flags, ctx):
    bid = b["id"]; cats = D["categories"]
    rows = [i for i in D["instruments"] if i["jurisdiction_id"] == bid]
    narr = D["narratives"].get(bid) or {}
    members = sorted(ctx["members"].get(bid, ()), key=lambda c: ctx["jur"].get(c, {}).get("name", c))
    canon = f"{SITE_URL}body/{bid}/"
    title = f"{b['name']}: AI governance instruments | AI Governance Radar"
    desc = first_sentence(narr.get("summary")) or f"Instruments of the {b['name']} recorded on the AI Governance Radar, and the countries they apply to."
    secs = [("overview", "Overview"), ("charts", "Charts"), ("instruments", "Instruments")] + ([("members", "Members")] if members else []) + [("method", "Method")]
    H = [head(title, desc, canon), '<body class="cp">', topbar(secs), '<main class="page">']
    n_bind = sum(1 for i in rows if kind(i) == "binding"); n_draft = sum(1 for i in rows if kind(i) == "draft")
    stats = [("Instruments", len(rows)), ("Binding or mandatory", n_bind), ("Non-binding", len(rows) - n_bind - n_draft), ("Drafts", n_draft), ("Member states", len(members))]
    H.append(f'<header class="hero" id="top"><p class="eyebrow">Regional / international body</p><h1>{e(b["name"])}</h1>'
             + '<dl class="stats">' + "".join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in stats) + '</dl>'
             + f'<p class="stats-note">{COUNT_NOTE} Instruments are stored once for the body and listed on each country page they apply to.</p>'
             + f'<p class="hero-links"><a href="../../timeline/?body={e(bid)}">See this body and its members on the timeline →</a><a href="../../analysis/">Global analysis →</a><a href="../../suggest/?country={e(bid)}">Suggest an update →</a></p></header>')
    years_svg, years_tab, undated = chart_years(rows); status_svg, status_tab = chart_status(rows)
    figs = []
    if years_svg: figs.append(figure("fig-years", "Instruments per year", "By publication year: binding or mandatory, non-binding and drafts.",
                                      '<p class="legend"><span><i class="sw s-b"></i>Binding or mandatory</span><span><i class="sw s-n"></i>Non-binding</span><span><i class="sw s-d"></i>Drafts</span></p>' + years_svg, years_tab,
                                      f"{undated} undated not shown" if undated else ""))
    if status_svg: figs.append(figure("fig-status", "Legal-status mix", "Instruments by legal status, from most to least binding.", '<p class="legend"><span><i class="sw s-b"></i>Binding or mandatory</span><span><i class="sw s-n"></i>Non-binding</span><span><i class="sw s-d"></i>Drafts</span></p>' + status_svg, status_tab))
    ov = '<section id="overview" class="block prose"><h2>Overview</h2>' + ("".join(f'<p>{e(p)}</p>' for p in re.split(r"\n\s*\n", narr.get("summary") or "") if p.strip())
                                                                          or f'<p>{e(b.get("overview") or "")}</p>')
    if bid == "OECD" and ctx["oecd"]:
        adh = sorted(ctx["oecd"].items(), key=lambda kv: (kv[1].get("member") is not True, ctx["jur"].get(kv[0], {}).get("name", kv[0])))
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
    H.append('<section id="method" class="block prose method"><h2>Method note</h2>' + (f'<p>{e(narr.get("review_notes"))}</p>' if narr.get("review_notes") else "")
             + (f'<p>{e(rec.get("membership_note"))}</p>' if rec.get("membership_note") else "")
             + '<p>Only official sources are recorded. <a href="../../?about=method" data-keep-query>Read the full methodology</a>.</p>'
             '<p class="export"><span>Download this profile:</span><button type="button" class="btn" data-export="csv">CSV</button><button type="button" class="btn" data-export="json">JSON</button></p></section>')
    bundle = {"meta": {"title": D["meta"].get("title"), "build_date": D["meta"].get("build_date"), "export": "single jurisdiction", "jurisdiction_id": bid, "url": canon},
              "jurisdiction": b, "narrative": narr or None, "members": members, "instruments": rows,
              "organizations": [o for o in D["organizations"] if o.get("jurisdiction_id") == bid], "changes": [c for c in D["changes"] if c.get("jurisdiction_id") == bid]}
    H.append('</main>' + footer(D) + '<script id="profile-data" type="application/json">' + json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
             + '</script><script src="../../assets/country.js" defer></script></body></html>')
    return "".join(H)


def footer(D):
    return (f'<footer class="pagefoot"><p>AI Governance Radar · official government sources only · data as of {e(fmt_date(D["meta"].get("build_date")))}</p>'
            '<p><a href="../../" id="footMap">World map</a> · <a href="../../analysis/">Analysis</a> · <a href="../../timeline/">Timeline</a> · <a href="../../suggest/">Suggest an update</a> · <a href="../../?about=method">Methodology</a></p></footer>')


def write_all(D, recs, out, flags):
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
           "today": D["meta"].get("build_date") or dt.date.today().isoformat()}
    (out / "assets").mkdir(parents=True, exist_ok=True)
    for f in ("country.css", "country.js", "analysis.css", "analysis.js", "timeline.js", "suggest.js"):
        (out / "assets" / f).write_text((ROOT / "site" / f).read_text(encoding="utf-8"), encoding="utf-8")
    n = 0
    for rec in recs.values():
        j = rec["jurisdiction"]
        if j["type"] == "country":
            p = out / "country" / j["id"]; html_ = country_page(j, D, rec, flags, ctx)
        else:
            p = out / "body" / j["id"]; html_ = body_page(j, D, rec, flags, ctx)
        p.mkdir(parents=True, exist_ok=True); (p / "index.html").write_text(html_, encoding="utf-8"); n += 1
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
