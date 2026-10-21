"""Document search page (/search/, /ar/search/).

    <out>/search/index.html        the page shell (same head, nav and footer as the timeline)
    dist/assets/search.json        one row per instrument (countries and bodies): the public text the country pages show
    dist/assets/search_terms.json  synonym groups (site/search_terms.json), also the "Suggested topics" chips

Both data files are shared by the English and Arabic pages and carry a content hash in their URL. site/search.js does
the matching, filtering and CSV export in the browser. Nothing here edits data.
"""
import hashlib, json
import i18n
from common import ROOT
from pages import (ar_issuer, ar_title, e, fmt_date, BODY_ORDER, EVENT, LIFE, SITE_URL, STATUS_LABEL, TYPES, TYPE_OF)
from subregions import SUBREGION

ACTIONS = ("published", "revised", "adopted", "applied", "consultation")   # dated government actions kept per instrument
REGIONS = ["Africa", "Americas", "Asia", "Europe", "Oceania"]
_CACHE = {}


def _ar(en):
    """Arabic label for interface text (the site dictionary); English if there is none."""
    return i18n.translate(en)


def _status_label(k):
    return STATUS_LABEL.get(k) or (k.replace("_", " ").capitalize() if k else "Not recorded")


def index(D, ctx):
    """The search index. Built once per build: the Arabic texts are read with LANG = "ar" whichever pass asks first."""
    if "index" in _CACHE: return _CACHE["index"]
    lang, i18n.LANG = i18n.LANG, "ar"
    try:
        jur, orgs = ctx["jur"], ctx["orgs"]
        cat_keys = list(D["categories"])
        acts = {}
        for c in D["changes"]:
            if c.get("kind") == "world" and c.get("type") in ACTIONS and c.get("instrument_id") and c.get("date"):
                acts.setdefault(c["instrument_id"], set()).add((c["date"], c["type"]))
        rows = []
        for i in D["instruments"]:
            t = i.get("english_title") or i.get("official_title") or ""
            ot = i.get("official_title") or ""
            at = ar_title(i) or ""
            iss = (i.get("issuing_authority") or orgs.get(i.get("organization_id"), {}).get("name") or i.get("publisher_name") or "").strip()
            issa = ar_issuer(iss, i.get("jurisdiction_id")) if iss else ""
            sa = i18n.content(i["id"], "summary", i.get("summary")) or ""
            sta = i18n.content(i["id"], "status", i.get("current_status")) or ""
            rows.append([i["id"], i["jurisdiction_id"], t, "" if ot == t else ot, "" if at in (ot, t) else at,
                         iss, "" if issa == iss else issa, i.get("publication_date") or "", i.get("legal_status") or "", i.get("lifecycle") or "",
                         [cat_keys.index(c) for c in i.get("categories", []) if c in cat_keys],
                         i.get("summary") or "", i.get("current_status") or "", sa, sta,
                         i.get("source_url") or i.get("official_webpage_url") or "", sorted(acts.get(i["id"], ()))])
        J = {}
        for j in D["jurisdictions"]:
            ar = i18n.D["countries"].get(j["id"]) or i18n.D["bodies"].get(j["id"]) or _ar(j["name"])
            J[j["id"]] = [j["name"], ar, "c" if j["type"] == "country" else "b", SUBREGION.get(j["id"], "") if j["type"] == "country" else "",
                          (j.get("region") or "") if j["type"] == "country" else ""]
        subs = {}
        for v in J.values():
            if v[2] == "c" and v[3]: subs.setdefault(v[4], set()).add(v[3])
        st_keys = sorted({i.get("legal_status") or "" for i in D["instruments"]}, key=lambda s: (s == "", s))
        idx = {"as_of": ctx["today"], "site": SITE_URL,
               "fields": ["id", "jurisdiction", "title", "official_title", "arabic_title", "issuer", "issuer_ar", "date", "legal_status", "lifecycle",
                          "categories", "summary", "status", "summary_ar", "status_ar", "source", "actions"],
               "jurisdictions": J,
               "regions": [[r, _ar(r), [[s, _ar(s)] for s in sorted(subs.get(r, ()))]] for r in REGIONS],
               "bodies": {b: sorted(ctx["members"].get(b, ())) for b in BODY_ORDER if b in jur},
               "categories": [[k, v, _ar(v)] for k, v in D["categories"].items()],
               "statuses": [[k, _status_label(k), _ar(_status_label(k))] for k in st_keys],
               "lifecycles": [[k, v, _ar(v)] for k, v in LIFE.items()],
               "types": [[k, v, _ar(v)] for k, v in TYPES], "type_of": TYPE_OF,
               "events": {k: [EVENT[k], _ar(EVENT[k])] for k in ACTIONS},
               "items": rows}
    finally:
        i18n.LANG = lang
    text = json.dumps(idx, ensure_ascii=False, separators=(",", ":"))
    terms = json.dumps({"groups": json.loads((ROOT / "site/search_terms.json").read_text(encoding="utf-8"))["groups"]}, ensure_ascii=False, separators=(",", ":"))
    _CACHE["index"] = idx
    _CACHE["files"] = {"search.json": text, "search_terms.json": terms}
    return idx


def write_assets(out):
    """dist/assets/search.json and search_terms.json (English pass only; the Arabic pages link to the same files)."""
    (out / "assets").mkdir(parents=True, exist_ok=True)
    for name, text in _CACHE["files"].items():
        (out / "assets" / name).write_text(text, encoding="utf-8")


def _url(name):
    return f"../assets/{name}?v={hashlib.sha1(_CACHE['files'][name].encode('utf-8')).hexdigest()[:8]}"


LEDE = ("Find recorded documents by keyword, date and country. The search covers each document's title, issuer, summary and status note, "
        "not the full text of the document.")
PRESETS = [("30", "Last 30 days"), ("60", "60 days"), ("90", "90 days"), ("12m", "12 months"), ("year", "Year"), ("custom", "Custom"), ("", "All time")]
SORTS = [("", "Relevance"), ("newest", "Newest"), ("oldest", "Oldest"), ("country", "Country")]


def search_page(D, ctx, head1, nav, foot):
    T = index(D, ctx)
    canon = f"{SITE_URL}search/"
    title = "Search documents | AI Governance Radar"
    asof = fmt_date(ctx["today"])
    pre = "".join(f'<link rel="preload" id="{i}" href="{_url(n)}" as="fetch" crossorigin="anonymous">'
                  for i, n in (("srData", "search.json"), ("srTerms", "search_terms.json")))
    H = [head1(title, LEDE, canon).replace("</head>", pre + "</head>", 1), '<body class="cp sr">', nav("search"), '<main class="page sr-page">']
    H.append('<header class="hero sr-hero"><h1>Search documents</h1>'
             f'<p class="stats-note sr-lede">{e(LEDE)}</p></header>')
    seg = "".join(f'<button type="button" class="seg-b" data-range="{k}" aria-pressed="{"true" if not k else "false"}">{e(v)}</button>' for k, v in PRESETS)
    types = "".join(f'<option value="{k}">{e(v)}</option>' for k, v in TYPES)
    cats = "".join(f'<option value="{k}">{e(v)}</option>' for k, v in D["categories"].items())
    sorts = "".join(f'<option value="{k}">{e(v)}</option>' for k, v in SORTS)
    H.append(
        '<form class="sr-form" id="srForm" role="search" aria-label="Search documents" onsubmit="return false">'
        # keywords
        '<div class="sr-sec sr-kw"><label class="sr-h" for="srQ">Keywords</label>'
        '<input type="search" id="srQ" name="q" autocomplete="off" spellcheck="false" placeholder="For example: deepfake, &quot;data sovereignty&quot;" aria-describedby="srHelp">'
        '<p class="sr-help" id="srHelp">Separate several terms with commas.</p>'
        '<div class="sr-opts"><fieldset class="sr-mode"><legend class="vh">How to combine terms</legend>'
        '<label class="sr-check"><input type="radio" name="mode" value="any" checked> Match any term</label>'
        '<label class="sr-check"><input type="radio" name="mode" value="all"> Match all terms</label></fieldset>'
        '<label class="sr-check"><input type="checkbox" id="srRel" checked> Include related terms</label></div>'
        '<p class="sr-also" id="srAlso" hidden><span>Also searching:</span> <span class="sr-also-list" id="srAlsoList" translate="no"></span><span id="srAlsoX" hidden></span></p>'
        '<div class="sr-topics"><span class="sr-sub" id="srTopicsH">Suggested topics</span><div class="sr-chips" id="srTopics" role="group" aria-labelledby="srTopicsH"></div>'
        '<button type="button" class="sr-moret" id="srMoreT" aria-controls="srTopics" aria-expanded="false" hidden>More topics</button></div></div>'
        # date
        '<fieldset class="sr-sec sr-date"><legend class="sr-h">Date</legend>'
        f'<div class="seg" role="group" aria-label="Date range">{seg}</div>'
        '<div class="sr-date-x"><label class="sr-inline" id="srYearL" hidden>Year <select id="srYear"></select></label>'
        '<span class="sr-custom" id="srCustom" hidden><label class="sr-inline">From <input type="date" id="srFrom"></label><label class="sr-inline">To <input type="date" id="srTo"></label></span></div>'
        f'<p class="sr-help" id="srAsof">{e(i18n.T("Data as of {date}", date=asof))}</p>'
        '<label class="sr-check"><input type="checkbox" id="srActions"> Include amendments and entry into force</label></fieldset>'
        # jurisdictions
        '<div class="sr-sec sr-jur"><label class="sr-h" for="srJ">Countries, regions and bodies</label>'
        '<div class="sr-picked" id="srPicked"><span class="sr-all" id="srAll">All countries</span></div>'
        '<div class="sr-combo"><input type="text" id="srJ" role="combobox" aria-expanded="false" aria-controls="srJList" aria-autocomplete="list" autocomplete="off" '
        'placeholder="Type a country, region or body" aria-describedby="srJHelp">'
        '<ul class="sr-list" id="srJList" role="listbox" aria-label="Countries, regions and bodies" hidden></ul></div>'
        '<p class="sr-help" id="srJHelp">You can pick more than one.</p></div>'
        # more
        '<details class="sr-sec sr-more" id="srMoreF"><summary>More filters</summary><div class="sr-more-in">'
        f'<label class="sr-inline">Document type <select id="srType"><option value="">All types</option>{types}</select></label>'
        f'<label class="sr-inline">Category <select id="srCat"><option value="">All categories</option>{cats}</select></label></div></details>'
        # bar
        f'<div class="sr-bar"><label class="sr-inline">Sort <select id="srSort">{sorts}</select></label>'
        '<button type="button" class="btn" id="srCsv" disabled>Download CSV</button><button type="button" class="btn" id="srClear">Clear all</button></div>'
        '</form>')
    H.append('<p class="sr-summary" id="srSummary" role="status" aria-live="polite">Loading…</p>'
             '<div class="sr-results" id="srResults"></div>'
             '<p class="sr-note" id="srNote" hidden></p>'
             '<p class="sr-morep"><span class="sr-shown" id="srShown"></span><button type="button" class="btn" id="srMore" hidden>Show more</button></p>'
             '<noscript><p>The search needs JavaScript. Every document is also listed on its country page and in the export on the map page.</p></noscript>')
    H.append('</main>' + foot(D) + '<script src="../assets/search.js" defer></script></body></html>')
    return "".join(H)
