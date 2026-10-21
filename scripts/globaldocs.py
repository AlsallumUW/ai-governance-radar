"""Global and regional documents page (/global/, /ar/global/).

Every instrument of a regional or international body (data/regional/*.json) on one page: headline counts, the bodies
grouped by kind (jurisdiction.group) and one filterable list of their documents with a CSV of the filtered rows.
Built in the analysis page loop (analysis.write), so it gets the same shell, Arabic build and cache-busting.
site/global.js does the filtering, sorting, URL state and CSV in the browser. Nothing here edits data.
"""
import json
import i18n
from pages import (ar_issuer, ar_title, body_group, body_name, body_name_ar, date_key, e, fmt_date, inst_item, kind,
                   year, GROUP_LABEL, GROUP_ORDER, LIFE, SITE_URL, STATUS_LABEL, WEIGHT)

LEDE = ("AI governance documents adopted by international and regional organisations whose members are governments. "
        "They are listed here and on each organisation's page, and are not counted in country totals.")
SORTS = [("newest", "Newest"), ("oldest", "Oldest"), ("org", "Organisation"), ("weight", "Legal weight")]
CSV_HEAD = ["Organisation", "Title", "Official title", "Issuer", "Date", "Legal status", "Lifecycle", "Categories", "Summary", "Official source", "Radar page"]


def _status(k):
    return STATUS_LABEL.get(k) or (k or "Not recorded").replace("_", " ").capitalize()


def _arabic(i):
    """Arabic title, issuer and summary of a record whatever the page language (both pages search English and Arabic)."""
    lang, i18n.LANG = i18n.LANG, "ar"
    try:
        iss = (i.get("issuing_authority") or i.get("publisher_name") or "").strip()
        return {"title": ar_title(i) or "", "issuer": (ar_issuer(iss, i["jurisdiction_id"]) if iss else "") or "",
                "summary": i18n.content(i["id"], "summary", i.get("summary")) or ""}
    finally:
        i18n.LANG = lang


def org_cards(bodies, rows_by, ctx):
    out = []
    for g in GROUP_ORDER:
        js = [j for j in bodies if body_group(j) == g]
        if not js: continue
        cards = []
        for j in js:
            docs = rows_by.get(j["id"], [])
            n_mem = len(ctx["members"].get(j["id"], ()))
            mem = i18n.T("Signatories vary by document") if j.get("members_rule") == "none" or not n_mem else (
                i18n.T("1 member state") if n_mem == 1 else i18n.T("{n} member states", n=n_mem))
            nd = i18n.T("No documents yet") if not docs else i18n.T("1 document") if len(docs) == 1 else i18n.T("{n} documents", n=len(docs))
            dates = [i["publication_date"] for i in docs if i.get("publication_date")]
            last = max(dates, key=date_key) if dates else None
            meta = [mem, nd] + ([i18n.T("Latest: {date}", date=fmt_date(last))] if last else [])
            cards.append(f'<li class="gd-org"><a class="gd-oname" href="../body/{e(j["id"])}/">{e(body_name(j))}</a>'
                         + "".join(f'<span class="gd-om">{e(m)}</span>' for m in meta) + '</li>')
        out.append(f'<section class="gd-group" aria-labelledby="gd-g-{g}"><h3 class="gd-gh" id="gd-g-{g}">{e(i18n.tr(GROUP_LABEL[g]))} <span class="count">{len(js)}</span></h3>'
                   f'<ul class="gd-orgs">{"".join(cards)}</ul></section>')
    return "".join(out)


def doc_row(i, j, cats, ctx, n):
    """One document, rendered by the country pages' item component (pages.inst_item) with the organisation above the title;
    data attributes for the filters in global.js."""
    ar = _arabic(i)
    d = i.get("publication_date")
    text = " ".join(x for x in (i.get("english_title"), i.get("official_title"), ar["title"], (i.get("issuing_authority") or i.get("publisher_name") or "").strip(),
                                ar["issuer"], i.get("summary"), ar["summary"], j.get("name"), j.get("short_name"), body_name_ar(j)) if x).lower()
    attrs = (f' data-org="{e(j["id"])}" data-oname="{e(body_name(j))}" data-year="{year(d) or ""}" data-status="{e(i.get("legal_status") or "")}" data-n="{n}"')
    label = f'<p class="gd-on"><a href="../body/{e(j["id"])}/">{e(body_name(j))}</a></p>'
    return inst_item(i, ctx["orgs"], ctx["srcs"], cats, jur=ctx["jur"], up="../", label=label, cls="gd-row", attrs=attrs, text=text)


def csv_rows(rows, jur, cats):
    """The CSV, in the page language: Arabic headers and, on the Arabic page, the Arabic organisation name and summary too."""
    isar = i18n.LANG == "ar"
    head = [i18n.tr(h) for h in CSV_HEAD]
    if isar:
        head.insert(1, i18n.T("Arabic organisation name")); head.insert(10, i18n.T("Arabic summary"))
    base = SITE_URL + ("ar/" if isar else "")
    out = {}
    for i in rows:
        j = jur[i["jurisdiction_id"]]; ar = _arabic(i) if isar else {}
        r = [j.get("name") or j["id"], i.get("english_title") or i.get("official_title") or "", i.get("official_title") or "",
             (i.get("issuing_authority") or i.get("publisher_name") or "").strip(), i.get("publication_date") or "",
             i18n.tr(_status(i.get("legal_status"))), i18n.tr(LIFE.get(i.get("lifecycle"), i.get("lifecycle") or "")),
             "; ".join(i18n.tr(cats.get(c, c)) for c in i.get("categories", [])), i.get("summary") or "",
             i.get("source_url") or i.get("official_webpage_url") or "", f'{base}body/{j["id"]}/#{i["id"]}']
        if isar:
            r.insert(1, body_name_ar(j) or ""); r.insert(10, ar.get("summary") or "")
        out[i["id"]] = r
    return {"head": head, "rows": out}


def global_page(D, ctx, head1, nav, foot):
    jur, cats, today = ctx["jur"], D["categories"], ctx["today"]
    bodies = [jur[b] for b in ctx["body_order"]]
    rows = [i for i in D["instruments"] if jur.get(i["jurisdiction_id"], {}).get("type") not in (None, "country")]
    rows.sort(key=lambda i: (date_key(i.get("publication_date")), i.get("english_title") or ""), reverse=True)
    by = {}
    for i in rows: by.setdefault(i["jurisdiction_id"], []).append(i)
    n_bind = sum(1 for i in rows if kind(i) == "binding")
    n_24 = sum(1 for i in rows if (year(i.get("publication_date")) or 0) >= 2024)
    stats = [("Organisations", len(bodies)), ("Documents", len(rows)), ("Treaties and binding acts", n_bind), ("Since 2024", n_24)]
    canon = f"{SITE_URL}global/"
    title = "Global and regional documents | AI Governance Radar"
    H = [head1(title, LEDE, canon), '<body class="cp gd">', nav("global"), '<main class="page gd-page">']
    H.append(f'<header class="hero gd-hero" id="top"><p class="eyebrow">{e(i18n.T("Data as of {date}", date=fmt_date(today)))}</p>'
             '<h1>Global and regional documents</h1>'
             f'<p class="section-lede gd-lede">{e(LEDE)}</p>'
             '<dl class="stats stats4">' + "".join(f'<div><dt>{e(k)}</dt><dd>{v:,}</dd></div>' for k, v in stats) + '</dl></header>')
    H.append('<nav class="chart-index" aria-label="On this page"><a href="#organisations">Organisations</a><a href="#documents">Documents</a></nav>')
    H.append(f'<section id="organisations" class="block"><h2>Organisations <span class="count">{len(bodies)}</span></h2>'
             f'{org_cards(bodies, by, ctx)}</section>')
    # controls: only values that occur in the list
    with_docs = [j for j in bodies if by.get(j["id"])]
    org_opts, last = [], None
    for j in with_docs:
        g = body_group(j)
        if g != last: org_opts.append(("</optgroup>" if last else "") + f'<optgroup label="{e(GROUP_LABEL[g])}">'); last = g
        org_opts.append(f'<option value="{e(j["id"])}">{e(body_name(j))}</option>')
    if last: org_opts.append("</optgroup>")
    sts = sorted({i.get("legal_status") or "" for i in rows}, key=lambda k: (WEIGHT.get(k, 9), _status(k)))
    years = sorted({year(i.get("publication_date")) for i in rows} - {None})
    yopts = "".join(f'<option value="{y}">{y}</option>' for y in years)
    present_cats = [(k, v) for k, v in cats.items() if any(k in i.get("categories", []) for i in rows)]
    sel = lambda f, label, opts, cls="": f'<label{cls}>{e(label)} <select data-f="{f}">{opts}</select></label>'
    controls = ('<div class="list-controls gd-controls" role="group" aria-label="Filter the documents">'
                + sel("org", "Organisation", '<option value="">All organisations</option>' + "".join(org_opts), ' class="gd-org-f"')
                + sel("type", "Type", '<option value="">All types</option>' + "".join(f'<option value="{e(k)}">{e(_status(k))}</option>' for k in sts))
                + sel("cat", "Category", '<option value="">All categories</option>' + "".join(f'<option value="{k}">{e(v)}</option>' for k, v in present_cats))
                + sel("from", "From", '<option value="">Any year</option>' + yopts, ' class="gd-y"')
                + sel("to", "To", '<option value="">Any year</option>' + yopts, ' class="gd-y"')
                + '<label class="grow">Search <input type="search" data-f="q" placeholder="Title, issuer or summary" autocomplete="off"></label>'
                + sel("sort", "Sort", "".join(f'<option value="{k}">{e(v)}</option>' for k, v in SORTS))
                + f'<p class="gd-actions"><button type="button" class="btn" id="gdCsv">Download CSV ({len(rows)})</button>'
                '<button type="button" class="btn" id="gdClear">Clear filters</button></p></div>')
    csv = json.dumps({"file": f"AI-Governance-Radar-global-and-regional-{today}.csv", **csv_rows(rows, jur, cats)},
                     ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    H.append(f'<section id="documents" class="block list-block gd-docs"><h2>Documents <span class="count">{len(rows)}</span></h2>{controls}'
             '<p class="list-status" id="gdStatus" aria-live="polite"></p>'
             '<div class="inst-list gd-list" id="gdList">' + "".join(doc_row(i, jur[i["jurisdiction_id"]], cats, ctx, n) for n, i in enumerate(rows)) + '</div>'
             '<p class="gd-none muted" id="gdNone" hidden>No documents match these filters.</p>'
             f'<script type="application/json" id="gd-csv">{csv}</script></section>')
    H.append('</main>' + foot(D) + '<script src="../assets/global.js" defer></script></body></html>')
    return "".join(H)
