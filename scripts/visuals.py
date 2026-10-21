"""Page banners and world maps for the Analysis, Timeline, Global and Search pages (static HTML/SVG built here;
site/maps.js adds the hover card, keyboard focus and the page's live behaviour).

    banner(page, ctx, ...)      full-bleed photo header (data/photos.json "pages"), styled like the country pages' hero
    world(...)                  the shared Equal Earth map: sphere, graticule, land, one <a data-iso3> per country, small-state dots
    map_card(...)               the map in a card with its title, legend and an info card
    analysis_map(D, ctx)        national-level instruments per country (the page's scope switch re-shades it)
    timeline_map(D, ctx)        year of each country's earliest dated instrument, with a year slider and Play
    global_map(D, ctx)          number of organisations each country belongs to, with headquarters markers
    search_map(D, ctx)          documents in the current search results (shaded in the browser by search.js)
    org_thumb(bid, ctx)         small photo thumbnail for an organisation card on /global/

Every label goes through i18n.T / i18n.tr, so the Arabic pass (i18n.LANG = "ar") renders Arabic directly; data-* text
(the info card) is written in the page language here because translate_html does not touch data attributes.
"""
import json, math
import i18n
from common import ROOT
from pages import cap, credit, e, kind

T = i18n.T


def TT(en):
    """A template with {placeholders} left for site/maps.js to fill, in the page language."""
    return i18n.STR.get(en, en) if i18n.LANG == "ar" else en
_CACHE = {}


# ---------------------------------------------------------------- page banner
def banner(page, ctx, eyebrow, h1, lede="", stats=None, info=""):
    """The country-page hero for a site page: photo under a scrim, eyebrow, title and lede in white over it, the counts
    (if any) along its bottom edge and the photo's caption and credit in the corner. Paths are relative to /<page>/."""
    im = (ctx.get("page_photos", {}).get(page) or {}).get("hero")
    st = ""
    if stats:
        st = (f'<div class="stats-row"><dl class="stats pg-stats" style="--n:{len(stats)}">' + "".join(f'<div><dt>{e(k)}</dt><dd>{v}</dd></div>' for k, v in stats)
              + f'</dl>{info}</div>')
    body = (f'<div class="hero-body">' + (f'<p class="eyebrow">{e(eyebrow)}</p>' if eyebrow else "") + f'<h1>{h1}</h1>'
            + (f'<p class="pg-lede">{e(lede)}</p>' if lede else "") + st + '</div>')
    if not im:
        return f'<header class="hero pg-hero" id="top">{body}</header>'
    alt = im.get("alt_ar") or im["alt"]
    img = (f'<img class="hero-img" src="../{e(im["file"])}" srcset="../{e(im["file_small"])} {im["width_small"]}w, ../{e(im["file"])} {im["width"]}w" '
           f'sizes="100vw" width="{im["width"]}" height="{im["height"]}" alt="{e(alt)}" fetchpriority="high" decoding="async">')
    return (f'<header class="hero hero--photo pg-hero" id="top"><div class="hero-media">{img}</div><div class="hero-scrim" aria-hidden="true"></div>'
            f'{body}<p class="hero-credit"><span class="hero-cap">{cap(im)}</span>{credit(im)}</p></header>')


def banner_preload(page, ctx):
    """<link rel=preload> for the banner photo (both widths), placed in the page's <head>."""
    im = (ctx.get("page_photos", {}).get(page) or {}).get("hero")
    if not im: return ""
    return (f'<link rel="preload" as="image" href="../{e(im["file_small"])}" imagesrcset="../{e(im["file_small"])} {im["width_small"]}w, '
            f'../{e(im["file"])} {im["width"]}w" imagesizes="100vw" fetchpriority="high">')


# ---------------------------------------------------------------- projection and geometry
TOPO = ROOT / "site/assets/world.topo.lo.json"
MAP_W = 800
LAT_MIN, LAT_MAX = -58.0, 85.0


def equal_earth(lon, lat):
    """Equal Earth projection (Šavrič, Patterson and Jenny 2018), unit sphere; y grows northwards."""
    A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
    M = math.sqrt(3) / 2
    lam, phi = math.radians(lon), math.radians(lat)
    th = math.asin(M * math.sin(phi))
    t2 = th * th; t6 = t2 * t2 * t2
    x = lam * math.cos(th) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = th * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y


def _frame():
    x0, _ = equal_earth(-180, 0); x1, _ = equal_earth(180, 0)
    _, ytop = equal_earth(0, LAT_MAX); _, ybot = equal_earth(0, LAT_MIN)
    s = MAP_W / (x1 - x0)
    return x0, ytop, s, round((ytop - ybot) * s, 1)


def proj(lon, lat):
    x0, ytop, s, _ = _frame()
    x, y = equal_earth(lon, max(LAT_MIN, min(LAT_MAX, lat)))
    return ((x - x0) * s, (ytop - y) * s)


def _decode(topo):
    """Absolute arc coordinates: undo quantisation and delta encoding when the topology has a transform."""
    t = topo.get("transform")
    if not t: return [[tuple(p[:2]) for p in a] for a in topo["arcs"]]
    (sx, sy), (tx, ty) = t["scale"], t["translate"]
    out = []
    for a in topo["arcs"]:
        x = y = 0; pts = []
        for p in a:
            x += p[0]; y += p[1]; pts.append((x * sx + tx, y * sy + ty))
        out.append(pts)
    return out


def _simplify(pts, tol):
    """Radial-distance thinning in projected pixels; the end points (shared with the neighbouring arc) are always kept."""
    if len(pts) < 3: return pts
    out = [pts[0]]; t2 = tol * tol
    for p in pts[1:-1]:
        q = out[-1]
        if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= t2: out.append(p)
    out.append(pts[-1])
    return out


def _area(r):
    return sum(r[i][0] * r[i - 1][1] - r[i - 1][0] * r[i][1] for i in range(len(r))) / 2


def _num(v):
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    if s.startswith("0."): s = s[1:]
    elif s.startswith("-0."): s = "-" + s[2:]
    return "0" if s in ("", "-0", "-") else s


def _ring_d(r):
    """Path data for one ring: absolute start, then relative steps (tenths of a pixel, so no rounding drift)."""
    q = [(round(x * 10), round(y * 10)) for x, y in r]
    pts = [q[0]] + [p for a, p in zip(q, q[1:]) if p != a]
    if len(pts) > 1 and pts[-1] == pts[0]: pts = pts[:-1]
    if len(pts) < 3: return ""
    d = f"M{_num(pts[0][0] / 10)} {_num(pts[0][1] / 10)}l"
    steps = []
    for a, b in zip(pts, pts[1:]):
        dx, dy = _num((b[0] - a[0]) / 10), _num((b[1] - a[1]) / 10)
        steps.append(dx + ("" if dy.startswith("-") else " ") + dy)
    out = steps[0]       # the separator is only needed where the next number does not start with "-"
    for s in steps[1:]: out += s if s.startswith("-") else " " + s
    return d + out + "z"


def _rings(topo, obj):
    """{id: [rings in pixels]} for one object of a topology (rings entirely south of the map's edge are dropped)."""
    arcs = _decode(topo)
    keep = [any(p[1] > LAT_MIN + .5 for p in a) for a in arcs]
    parcs = [_simplify([proj(*p) for p in a], 0.9) for a in arcs]

    def ring(idx):
        out = []
        for k in idx:
            a = parcs[k] if k >= 0 else parcs[~k][::-1]
            out.extend(a if not out else a[1:])
        return out

    res = {}
    for n, g in enumerate(topo["objects"][obj]["geometries"]):
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]] if g["type"] == "Polygon" else []
        res[g.get("id", n)] = [ring(r) for p in polys for r in p if any(keep[k if k >= 0 else ~k] for k in r)]
    return res


def _geometry():
    """(countries {ISO3: rings}, land path data, map height), cached per build."""
    if "geo" in _CACHE: return _CACHE["geo"]
    t = json.loads(TOPO.read_text(encoding="utf-8"))
    geo = _rings(t["countries"], "countries")
    land = "".join(_ring_d(r) for rs in _rings(t["land"], "land").values() for r in rs if abs(_area(r)) >= .6)
    _CACHE["geo"] = (geo, land, _frame()[3])
    return _CACHE["geo"]


def _backdrop():
    """Sphere outline (the map's edge, flat at the cut latitudes) and a 30° graticule."""
    if "bd" in _CACHE: return _CACHE["bd"]
    P = lambda lo, la: "%s %s" % (_num(proj(lo, la)[0]), _num(proj(lo, la)[1]))
    edge = [P(-180, la) for la in range(int(LAT_MAX), int(LAT_MIN) - 1, -1)] + [P(180, la) for la in range(int(LAT_MIN), int(LAT_MAX) + 1)]
    sph = "M" + "L".join(edge) + "Z"
    g = []
    for lo in range(-150, 180, 30):
        g.append("M" + "L".join(P(lo, la) for la in range(int(LAT_MIN), int(LAT_MAX) + 1, 4)))
    for la in (-30, 0, 30, 60):
        g.append("M" + "L".join(P(lo, la) for lo in range(-180, 181, 10)))
    _CACHE["bd"] = (sph, "".join(g))
    return _CACHE["bd"]


def world(items, label, extra=""):
    """The shared map SVG. items: {ISO3: {"cls": "m3", "attrs": {name: value}, "tip": text}}; every country of the
    topology is drawn, linked to its country page and carrying data-iso3 and data-name (the page language)."""
    geo, land, H = _geometry()
    sph, grat = _backdrop()
    jur = _CACHE.get("jur") or {}
    body, dots = [], []
    for cid in sorted(geo, key=lambda c: -abs(sum(_area(r) for r in geo[c]))):   # large countries first: small ones stay on top
        it = items.get(cid)
        if it is None: continue
        rings = geo[cid]
        if not rings: continue
        areas = [abs(_area(r)) for r in rings]
        big = max(range(len(rings)), key=lambda k: areas[k])
        name = i18n.tr(jur[cid]["name"]) if cid in jur else cid
        attrs = "".join(f' data-{k}="{e(str(v))}"' for k, v in (it.get("attrs") or {}).items())
        a = f'<a href="../country/{cid}/" class="{it["cls"]}" data-iso3="{cid}" data-name="{e(name)}"{attrs} tabindex="-1"><title>{e(it["tip"])}</title>'
        if sum(areas) < 10:      # small states: a dot, so they can be seen and pointed at
            r = rings[big]; cx = sum(p[0] for p in r) / len(r); cy = sum(p[1] for p in r) / len(r)
            dots.append(f'{a}<circle cx="{_num(cx)}" cy="{_num(cy)}" r="2.4"/></a>')
            continue
        d = "".join(_ring_d(r) for k, r in enumerate(rings) if areas[k] >= .6 or k == big)
        body.append(f'{a}<path d="{d}"/></a>')
    return (f'<svg class="wm" viewBox="0 0 {MAP_W} {_num(H)}" role="img" aria-label="{e(label)}">'
            f'<path class="wm-sph" d="{sph}"/><path class="wm-grat" d="{grat}"/><path class="wm-land" d="{land}"/>'
            f'<g class="wm-c">{"".join(body)}</g><g class="wm-dots">{"".join(dots)}</g>{extra}</svg>')


def legend(title, keys, title_alt=None):
    """Shared legend: a title and one swatch per bin. keys: [(bin, label)], bin 0 = none."""
    sw = "".join(f'<span{" class=k0" if not k else ""}><i class="wk m{k}"></i><bdi dir="ltr">{e(t)}</bdi></span>' for k, t in keys)
    alt = f' data-alt="{e(title_alt)}"' if title_alt else ""
    return (f'<div class="wm-legend"><span class="wm-lh"{alt}>{e(title)}</span><span class="wm-keys">{sw}</span></div>')


def map_card(kind_, fid, title, desc, svg, leg, below="", note="", data=None, above="", keep_note=False, side=""):
    """The map in a card: title and description, legend, controls above, the map with its info card, controls below and a note
    (keep_note: an empty note is kept, hidden, for a script to fill; side: a panel beside the map on wide screens, under it on narrow ones)."""
    data = {"t-open": T("Open the country page"), **(data or {})}
    attrs = "".join(f' data-{k}="{e(str(v))}"' for k, v in data.items())
    return (f'<figure class="wmap" id="{fid}" data-map="{kind_}"{attrs} aria-labelledby="{fid}-h">'
            f'<div class="wm-head"><div class="wm-tt"><h2 id="{fid}-h">{e(title)}</h2><p class="wm-desc">{e(desc)}</p></div>{leg}</div>'
            + above + ('<div class="wm-split"><div class="wm-main">' if side else "")
            + f'<div class="wm-stage">{svg}<div class="wm-card" hidden></div></div>{below}' + (f'</div>{side}</div>' if side else "")
            + (f'<figcaption class="wm-note"{"" if note else " hidden"}>{note}</figcaption>' if note or keep_note else "") + '</figure>')


def _countries(D, ctx):
    _CACHE["jur"] = ctx["jur"]
    return [j["id"] for j in D["jurisdictions"] if j["type"] == "country"]


def _bin(n, bins):
    if not n: return 0
    for k, (lo, hi) in enumerate(bins, 1):
        if hi is None or n <= hi: return k
    return len(bins)


def _range(lo, hi):
    return f"{lo}+" if hi is None else (str(lo) if lo == hi else f"{lo}–{hi}")


# ---------------------------------------------------------------- Analysis
# instruments per country: 0, then six bins (close to sextiles of the non-zero national counts, rounded to plain numbers)
SEQ = [(1, 2), (3, 5), (6, 10), (11, 20), (21, 50), (51, None)]


def _inst_line(c):
    """"33 instruments (11 binding or mandatory, 20 non-binding, 2 drafts)" in the page language."""
    n = sum(c.values())
    if not n: return None
    parts = []
    for g, one, many in (("binding", "1 binding or mandatory", "{n} binding or mandatory"), ("soft", "1 non-binding", "{n} non-binding"),
                         ("draft", "1 draft", "{n} drafts")):
        if c[g]: parts.append(T(one) if c[g] == 1 else T(many, n=c[g]))
    head = T("1 instrument") if n == 1 else T("{n} instruments", n=n)
    return T("{total} ({parts})", total=head, parts=("، " if i18n.LANG == "ar" else ", ").join(parts))


# lenses: each recolours the same map (site/maps.js) from one compact JSON blob; bins are fixed here so the legend is static
LENSES = ["docs", "strategy", "binding", "topic", "recent"]
STRAT_BINS = [(None, 2018), (2019, 2019), (2020, 2021), (2022, 2023), (2024, 2024), (2025, None)]   # darkest = earliest
SHARE_BINS = [(0, 14), (15, 24), (25, 34), (35, 49), (50, 64), (65, 100)]
RECENT_FROM = "2024-01-01"
RECENT_BINS = [(1, 1), (2, 3), (4, 6), (7, 12), (13, 30), (31, None)]
MIN_SHARE = 3          # fewer national instruments than this: no share is shown (hatched)
MIN_SHARE_TOP = 10     # ...and the top five of that lens only ranks countries with at least this many (100% of 3 says little)


def _sbin(y):
    for k, (lo, hi) in enumerate(STRAT_BINS, 1):
        if (lo is None or y >= lo) and (hi is None or y <= hi): return len(STRAT_BINS) + 1 - k
    return 1


def _pbin(p):
    for k, (lo, hi) in enumerate(SHARE_BINS, 1):
        if p <= hi: return k
    return len(SHARE_BINS)


def _first_strategies(D, cids):
    """{country: instrument} the earliest dated national-level national strategy: the rule of chart b (fig_adoption), so the counts agree."""
    from pages import date_key
    out = {}
    for i in D["instruments"]:
        c = i["jurisdiction_id"]
        if c not in cids or i.get("legal_status") != "national_strategy" or i.get("government_level") != "national": continue
        d = i.get("publication_date") or ""
        if not d[:4].isdigit(): continue
        if c not in out or date_key(d) < date_key(out[c]["publication_date"]): out[c] = i
    return out


def analysis_map(D, ctx):
    from pages import ar_title, fmt_date
    cids = _countries(D, ctx)
    jur = ctx["jur"]
    cset = set(cids)
    cat_keys = list(D["categories"])
    nat = {c: {"binding": 0, "soft": 0, "draft": 0} for c in cids}
    allv = {c: {"binding": 0, "soft": 0, "draft": 0} for c in cids}
    recent = {c: 0 for c in cids}
    topic = {c: [0] * len(cat_keys) for c in cids}
    for i in D["instruments"]:
        c = i["jurisdiction_id"]
        if c not in nat: continue
        allv[c][kind(i)] += 1
        if i.get("government_level") != "national": continue
        nat[c][kind(i)] += 1
        d = i.get("publication_date") or ""
        if d[:4].isdigit() and (d + "-01-01"[len(d) - 4:] if len(d) in (4, 7) else d) >= RECENT_FROM: recent[c] += 1      # a year alone counts from 1 January
        for k in i.get("categories", []):
            if k in cat_keys: topic[c][cat_keys.index(k)] += 1
    strat = _first_strategies(D, cset)
    sep = "، " if i18n.LANG == "ar" else ", "
    items, blob = {}, {}
    for c in cids:
        a, b = sum(nat[c].values()), sum(allv[c].values())
        i0 = _inst_line(nat[c]) or T("No instruments found at national level")
        i1 = _inst_line(allv[c]) or T("No instruments found")
        items[c] = {"cls": f"m{_bin(a, SEQ)}", "tip": f"{i18n.tr(jur[c]['name'])}: {i0}",
                    "attrs": {"i": i0, "b": _bin(a, SEQ), "i-all": i1, "b-all": _bin(b, SEQ)}}
        s = strat.get(c)
        st = 0 if not s else [s["publication_date"], ar_title(s) or s.get("english_title") or s.get("official_title") or "", fmt_date(s["publication_date"][:7]),
                              _sbin(int(s["publication_date"][:4]))]
        # [iso2, national, all levels, binding (national), first strategy [date, title, month, shade] or 0, since 2024, instruments per category (comma-separated, zeros empty)]
        blob[c] = [(jur[c].get("iso2") or "").lower(), a, b, nat[c]["binding"], st, recent[c], ",".join(str(x) if x else "" for x in topic[c]).rstrip(",")]
    tot = sum(sum(v.values()) for v in nat.values()); zero = sum(1 for v in nat.values() if not sum(v.values()))
    label = T("World map: national-level instruments recorded in each of the 195 countries ({n} in all; {z} countries with none found). The same counts are in the country ranking below.",
              n=f"{tot:,}", z=zero)
    cats = [[k, i18n.tr(v)] for k, v in D["categories"].items()]
    n_strat, n_share = len(strat), sum(1 for c in cids if sum(nat[c].values()) >= MIN_SHARE)
    # one legend per lens (the topic legend's steps are filled in by maps.js for the chosen category)
    legs = {
        "docs": legend(T("Instruments recorded (national level)"), [(0, T("None found"))] + [(k, _range(*b)) for k, b in enumerate(SEQ, 1)],
                       title_alt=T("Instruments recorded (all levels)")),
        "strategy": legend(T("First national AI strategy"), [(0, T("None recorded"))] + [
            (len(STRAT_BINS) + 1 - k, T("Before {y}", y=hi + 1) if lo is None else (str(lo) if lo == (hi or int(ctx["today"][:4])) else f"{lo}–{str(hi or int(ctx['today'][:4]))[2:]}"))
            for k, (lo, hi) in enumerate(STRAT_BINS, 1)]),
        "binding": legend(T("Binding or mandatory, share of national instruments"), [("h", T("Fewer than 3"))] + [
            (k, (f"{lo}%+" if hi == 100 else f"{lo}–{hi}%")) for k, (lo, hi) in enumerate(SHARE_BINS, 1)]),
        "topic": legend(T("Instruments recorded (national level)"), [(0, T("None found"))]),
        "recent": legend(T("Instruments published since 1 Jan 2024 (national level)"), [(0, T("None found"))] + [(k, _range(*b)) for k, b in enumerate(RECENT_BINS, 1)]),
    }
    leg = "".join(l.replace('<div class="wm-legend"', f'<div class="wm-legend" data-lens="{k}"' + ("" if k == "docs" else " hidden"), 1) for k, l in legs.items())
    L = {
        "docs": {"tab": T("Documents recorded"), "h": T("Where AI governance documents have been recorded"),
                 "d": T("National-level instruments recorded in each country. Select a country to open its page."),
                 "top": T("Most instruments recorded"), "note": ""},
        "strategy": {"tab": T("National AI strategy"), "h": T("When countries adopted their first national AI strategy"),
                     "d": T("{n} of 195 countries have a national AI strategy recorded. Darker shades adopted earlier.", n=n_strat),
                     "top": T("Earliest national AI strategies"),
                     "note": T("Year of the earliest dated national-level instrument recorded as a national strategy: the same rule as the adoption chart (b), so the counts agree.")},
        "binding": {"tab": T("Binding or mandatory"), "h": T("How much of each country's recorded AI governance is binding"),
                    "d": T("Share of each country's national-level instruments that are binding or mandatory. {n} countries have at least 3 instruments; the rest are hatched.", n=n_share),
                    "top": T("Highest share binding or mandatory (countries with at least 10 instruments)"),
                    "note": T("Binding or mandatory includes data protection, copyright and sector laws that apply to AI. A share says how a country's recorded instruments divide, not how strongly AI is regulated.")},
        "topic": {"tab": T("Topic"), "h": T("Where instruments on a topic have been recorded"),
                  "d": T("National-level instruments tagged with the chosen category. One instrument can carry several categories."),
                  "top": T("Most instruments on this topic"), "note": ""},
        "recent": {"tab": T("New since 2024"), "h": T("Who has been most active since 2024"),
                   "d": T("National-level instruments published from 1 January 2024. Instruments with only a year count from that year."),
                   "top": T("Most instruments published since 1 Jan 2024"), "note": ""},
    }
    data = {"lens": L, "cats": cats, "c": blob, "sep": sep, "min": MIN_SHARE, "topmin": MIN_SHARE_TOP, "sb": [hi for _, hi in SHARE_BINS], "rb": [hi for _, hi in RECENT_BINS],
            "t": {"strat0": T("No national AI strategy recorded"), "share": TT("{p}% binding or mandatory ({b} of {n} national instruments)"),
                  "share0": TT("Too few national instruments to compare ({n})"), "topic1": TT("1 instrument on {topic}"), "topicn": TT("{n} instruments on {topic}"),
                  "topic0": TT("No instruments on {topic}"), "rec1": TT("1 instrument published since 1 Jan 2024"), "recn": TT("{n} instruments published since 1 Jan 2024"),
                  "rec0": T("None published since 1 Jan 2024"), "topich": TT("Where instruments on {topic} have been recorded"),
                  "toplh": TT("Instruments on {topic} (national level)"), "toptop": TT("Most instruments on {topic}"), "pct": TT("{p}%")}}
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tabs = "".join(f'<button type="button" class="seg-b" data-lens="{k}" aria-pressed="{"true" if k == "docs" else "false"}">{e(L[k]["tab"])}</button>' for k in LENSES)
    copts = "".join(f'<option value="{e(k)}"{" selected" if k == "generative-ai" else ""}>{e(v)}</option>' for k, v in cats)
    lensbar = (f'<div class="wm-lens"><span class="wm-lens-l" id="map-lens-l">{e(T("Show:"))}</span><div class="seg" role="group" aria-labelledby="map-lens-l">{tabs}</div>'
               f'<label class="wm-topic" hidden><span class="vh">{e(T("Topic"))}</span><select data-topic>{copts}</select></label></div>')
    tog = f'<label class="scope-toggle wm-scope"><input type="checkbox" data-scope-toggle> {e(T("Include state/provincial and local"))}</label>'
    top = (f'<section class="wm-top" aria-labelledby="map-top-h"><h3 class="wm-top-h" id="map-top-h">{e(L["docs"]["top"])}</h3><ol class="wm-top-l"></ol></section>')
    hatch = ('<defs><pattern id="wmHatch" width="3.2" height="3.2" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             '<rect width="3.2" height="3.2" class="wm-hb"/><line x1="0" y1="0" x2="0" y2="3.2" class="wm-hl"/></pattern></defs>')
    return map_card("analysis", "map", L["docs"]["h"], L["docs"]["d"], world(items, label, extra=hatch), leg,
                    above=lensbar, below=f'<div class="wm-ctl">{tog}</div>{top}',
                    note="", keep_note=True) + f'<script type="application/json" id="map-lens">{js}</script>'


# ---------------------------------------------------------------- Timeline
YEAR_BINS = [(None, 2017), (2018, 2019), (2020, 2021), (2022, 2023), (2024, 2024), (2025, 2026)]
YEAR_FROM = 2014


def _ybin(y):
    for k, (lo, hi) in enumerate(YEAR_BINS, 1):
        if (lo is None or y >= lo) and y <= hi: return k
    return len(YEAR_BINS)


def timeline_map(D, ctx):
    cids = _countries(D, ctx)
    first = {}
    for i in D["instruments"]:
        c, d = i["jurisdiction_id"], i.get("publication_date") or ""
        if c in ctx["jur"] and ctx["jur"][c]["type"] == "country" and len(d) >= 4:
            first[c] = min(first.get(c, 9999), int(d[:4]))
    last = int(ctx["today"][:4])
    # the darkest shade goes to the earliest adopters
    nb = len(YEAR_BINS)
    items = {}
    for c in cids:
        y = first.get(c)
        info = T("First dated document: {year}", year=y) if y else T("No dated document recorded")
        b = nb + 1 - _ybin(y) if y else 0
        items[c] = {"cls": f"m{b}", "tip": f"{i18n.tr(ctx['jur'][c]['name'])}: {info}", "attrs": {"i": info, "b": b, **({"y": y} if y else {})}}
    keys = [(0, T("None recorded"))]
    for k, (lo, hi) in enumerate(YEAR_BINS, 1):
        hi = min(hi, last)
        keys.append((nb + 1 - k, T("Before {y}", y=hi + 1) if lo is None else (str(lo) if lo == hi else f"{lo}–{hi}")))
    label = T("World map: the year of each country's earliest dated AI governance document ({n} of 195 countries have one).", n=len(first))
    n_last = len(first)
    ctl = (f'<div class="wm-ctl wm-play"><button type="button" class="btn wm-pb" aria-pressed="false" data-play="{e(T("Play"))}" data-pause="{e(T("Pause"))}">'
           f'<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path class="i-play" d="M3 1.5v9l7.5-4.5z"/><path class="i-pause" d="M2.5 1.5h2.6v9H2.5zM6.9 1.5h2.6v9H6.9z"/></svg>'
           f'<span>{e(T("Play"))}</span></button>'
           f'<label class="wm-yr"><span aria-hidden="true">{YEAR_FROM}</span><span class="vh">{e(T("Year"))}</span><input type="range" min="{YEAR_FROM}" max="{last}" step="1" value="{last}" '
           f'aria-valuetext="{last}"><span aria-hidden="true">{last}</span></label>'
           f'<output class="wm-count" aria-live="polite">{e(T("{n} countries by {y}", n=n_last, y=last))}</output></div>')
    note = e(T("Year of the earliest instrument with a publication date, at any level of government. At the slider's first year, every earlier first document is included."))
    return map_card("timeline", "map", T("When countries published their first AI governance document"),
                    T("Each country is shaded by the year of its earliest dated instrument. Move the slider, or press Play, to follow adoption year by year."),
                    world(items, label), legend(T("First dated document"), keys), below=ctl, note=note,
                    data={"t-one": TT("1 country by {y}"), "t-many": TT("{n} countries by {y}")})


# ---------------------------------------------------------------- Global
MEM_BINS = [(1, 7), (8, 9), (10, 11), (12, 13), (14, 15), (16, None)]
# headquarters (lon, lat); G7, G20, BRICS and the AI summits have no seat
SEATS = {"UN": ("New York", -73.968, 40.749), "UNESCO": ("Paris", 2.306, 48.849), "ITU": ("Geneva", 6.137, 46.210), "WHO": ("Geneva", 6.134, 46.233),
         "ILO": ("Geneva", 6.137, 46.226), "UNICEF": ("New York", -73.971, 40.751), "WIPO": ("Geneva", 6.139, 46.224), "CCW": ("Geneva", 6.140, 46.227),
         "OECD": ("Paris", 2.269, 48.861), "EU": ("Brussels", 4.383, 50.844), "COE": ("Strasbourg", 7.774, 48.594), "NATO": ("Brussels", 4.425, 50.879),
         "AU": ("Addis Ababa", 38.746, 9.003), "ASEAN": ("Jakarta", 106.800, -6.237), "APEC": ("Singapore", 103.851, 1.290), "GCC": ("Riyadh", 46.712, 24.690),
         "LAS": ("Cairo", 31.236, 30.045), "ALECSO": ("Tunis", 10.181, 36.806), "ICESCO": ("Rabat", -6.849, 33.971), "OIC": ("Jeddah", 39.172, 21.543),
         "OAS": ("Washington", -77.040, 38.893), "FSB": ("Basel", 7.592, 47.548), "BIS": ("Basel", 7.592, 47.548), "IOSCO": ("Madrid", -3.688, 40.432),
         "WBG": ("Washington", -77.042, 38.899)}


def global_map(D, ctx):
    """Organisation explorer: by default the membership-count choropleth; pick an organisation (select or headquarters marker) to
    see its member states and latest documents, or a country (select or click) to see the organisations it belongs to.
    site/maps.js draws the selections from the JSON blob written here, in the page language."""
    from pages import ar_title, body_group, body_name, date_key, fmt_date, GROUP_LABEL, GROUP_ORDER
    cids = _countries(D, ctx)
    jur = ctx["jur"]
    cset = set(cids)
    orgs = [b for b in ctx["body_order"] if jur[b].get("members_rule") != "none" and ctx["members"].get(b)]
    sep = "، " if i18n.LANG == "ar" else ", "
    of = {c: [] for c in cids}
    for b in orgs:
        for c in ctx["members"][b]:
            if c in of: of[c].append(body_name(jur[b], short=True))
    items = {}
    for c in cids:
        n = len(of[c])
        info = T("Member of 1 organisation") if n == 1 else T("Member of {n} organisations", n=n) if n else T("Not a member of any of these organisations")
        items[c] = {"cls": f"m{_bin(n, MEM_BINS)}", "tip": f"{i18n.tr(jur[c]['name'])}: {info}",
                    "attrs": {"i": info, "b": _bin(n, MEM_BINS), "l": sep.join(of[c])}}
    # documents of each organisation, newest first
    docs = {}
    for i in D["instruments"]:
        if i["jurisdiction_id"] in jur and jur[i["jurisdiction_id"]]["type"] != "country": docs.setdefault(i["jurisdiction_id"], []).append(i)
    for v in docs.values(): v.sort(key=lambda i: (date_key(i.get("publication_date")), i.get("english_title") or ""), reverse=True)
    title = lambda i: ar_title(i) or i.get("english_title") or i.get("official_title") or ""
    doc = lambda b, i, sig=False: [i["id"], title(i), fmt_date(i.get("publication_date"))] + (["".join(c for c in (i.get("signatories") or []) if c in cset)] if sig else [])
    blob_o = {}
    for b in ctx["body_order"]:
        j = jur[b]; none = j.get("members_rule") == "none"
        mem = sorted(c for c in ctx["members"].get(b, ()) if c in cset)
        if not mem and not none: continue
        ds = docs.get(b, [])
        # [name, short name, group, member states (0: signatories vary by document), documents, newest 3 (all, with signatories, when membership varies)]
        # member states as one string of ISO3 codes; "!" + the countries left out when that is shorter (the UN system)
        out = sorted(cset - set(mem))
        mem_s = ("!" + "".join(out)) if len(out) < len(mem) else "".join(mem)
        blob_o[b] = [body_name(j), body_name(j, short=True), body_group(j), 0 if none else mem_s, len(ds), [doc(b, i, none) for i in (ds if none else ds[:3])]]
    groups = [[g, i18n.tr(GROUP_LABEL[g])] for g in GROUP_ORDER if any(v[2] == g for v in blob_o.values())]
    # headquarters: seats within a few pixels of each other (Geneva, Basel, Brussels, Paris, New York, Washington) share a marker
    marks = []
    for b in ctx["body_order"]:
        if b not in SEATS: continue
        city, lon, lat = SEATS[b]; x, y = proj(lon, lat)
        m = next((m for m in marks if m["city"] == city or (m["x"] - x) ** 2 + (m["y"] - y) ** 2 < 25), None)
        if m: m["orgs"].append(b); m["pts"].append((x, y))
        else: marks.append({"city": city, "x": x, "y": y, "orgs": [b], "pts": [(x, y)]})
    hq = []
    for m in sorted(marks, key=lambda m: -len(m["orgs"])):
        x = sum(p[0] for p in m["pts"]) / len(m["pts"]); y = sum(p[1] for p in m["pts"]) / len(m["pts"])
        names = sep.join(body_name(jur[b], short=True) for b in m["orgs"])
        r = 1.7 + .75 * math.sqrt(len(m["orgs"]))
        city = i18n.tr(m["city"])
        hq.append(f'<g class="hq" data-name="{e(city)}" data-i="{e(names)}" data-orgs="{" ".join(m["orgs"])}" tabindex="-1"><title>{e(city + ": " + names)}</title>'
                  f'<circle class="hq-h" cx="{_num(x)}" cy="{_num(y)}" r="{_num(r + 3)}"/><circle class="hq-d" cx="{_num(x)}" cy="{_num(y)}" r="{_num(r)}"/></g>')
    label = T("World map: the number of international and regional organisations each country belongs to, of the {n} recorded here with a membership list, and the organisations' headquarters.", n=len(orgs))
    key = (f'<span class="wm-hqkey"><svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4"/></svg>'
           f'{e(T("Headquarters"))}</span>')
    leg0 = legend(T("Organisations a country belongs to"), [(k, _range(*b)) for k, b in enumerate(MEM_BINS, 1)])
    leg0 = leg0.replace('<div class="wm-legend"', '<div class="wm-legend" data-mode=""', 1)[:-len("</div>")] + key + "</div>"
    sel_key = lambda cls, text, attr="": f'<span><i class="wk {cls}"></i><bdi{attr}>{e(text)}</bdi></span>'
    leg_org = (f'<div class="wm-legend wm-legend-sel" data-mode="org" hidden><span class="wm-lh" data-org-title></span><span class="wm-keys">'
               + sel_key("m4", T("Member states"), " data-org-key") + sel_key("m0", T("Other countries"))
               + f'</span><span class="wm-hqkey wm-hqkey-on"><svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4"/></svg>{e(T("Headquarters"))}</span></div>')
    leg_c = (f'<div class="wm-legend wm-legend-sel wm-legend-c" data-mode="country" hidden><span class="wm-lh" data-country-title></span><span class="wm-keys">'
             + sel_key("msel", T("Selected country")) + f'<span class="k0 wm-k"><i class="wk m0"></i><bdi>{e(T("None"))}</bdi></span>'
             + f'</span><span class="wm-hqkey wm-hqkey-on"><svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><circle cx="6" cy="6" r="4"/></svg>{e(T("Headquarters of its organisations"))}</span></div>')
    no_seat = [b for b in orgs if b not in SEATS]
    note = e(T("Membership lists as recorded on each organisation's page; the AI Action Summits are left out of the shading because participation varies by declaration. {list} have no permanent seat and no marker.",
               list=sep.join(body_name(jur[b], short=True) for b in no_seat)))
    # pickers
    oopts, last = [], None
    for b, v in blob_o.items():
        if v[2] != last:
            oopts.append(("</optgroup>" if last else "") + f'<optgroup label="{e(i18n.tr(GROUP_LABEL[v[2]]))}">'); last = v[2]
        oopts.append(f'<option value="{e(b)}">{e(v[0])}</option>')
    oopts.append("</optgroup>")
    # the countries are listed by site/maps.js from the map itself (their names are on it already, in the page language)
    copts = ""
    x_icon = '<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true"><path d="M2.5 2.5l7 7M9.5 2.5l-7 7"/></svg>'
    pickers = (f'<div class="wm-pickers" role="group" aria-label="{e(T("Explore the map"))}">'
               f'<label class="wm-pk"><span>{e(T("Organisation"))}</span><select data-pick="org"><option value="">{e(T("Choose an organisation"))}</option>{"".join(oopts)}</select></label>'
               f'<span class="wm-or" aria-hidden="true">{e(T("or"))}</span>'
               f'<label class="wm-pk"><span>{e(T("Country"))}</span><select data-pick="country"><option value="">{e(T("Choose a country"))}</option>{copts}</select></label>'
               f'<button type="button" class="wm-clear" hidden>{x_icon}<span>{e(T("Clear selection"))}</span></button></div>')
    ex = [("org", b) for b in ("EU", "AU", "GCC") if b in blob_o] + [("country", c) for c in ("SAU",) if c in cset]
    exs = "".join(f'<button type="button" class="wm-ex" data-{k}="{v}">{e(blob_o[v][0] if k == "org" else i18n.tr(jur[v]["name"]))}</button>' for k, v in ex)
    panel = (f'<aside class="wm-panel" aria-live="polite" aria-label="{e(T("Selection details"))}"><div class="wm-p0">'
             f'<p class="wm-p-h">{e(T("Select an organisation or a country"))}</p>'
             f'<p class="wm-p-t">{e(T("Pick an organisation to see its member states and latest documents, or a country to see which international documents apply to it through its memberships."))}</p>'
             f'<p class="wm-p-ex"><span>{e(T("For example:"))}</span>{exs}</p></div><div class="wm-p1" hidden></div></aside>')
    data = {"o": blob_o, "g": groups, "f": {c: (jur[c].get("iso2") or "").lower() for c in cids},
            "t": {"members": TT("{n} member states"), "members1": T("1 member state"), "docs": TT("{n} documents"), "docs1": T("1 document"), "docs0": T("No documents yet"),
                  "sigvary": T("Signatories vary by document"), "latest": T("Latest"), "recent": T("Most recent documents"), "all": TT("All {n} documents"),
                  "lmem": T("Member states"), "ldocs": T("Documents"), "ldecl": T("Declarations"),
                  "orgpage": T("Open the organisation page"), "cpage": T("Open the country page"),
                  "cline": TT("{c} is a member of {n} organisations recorded here, which have adopted {m} AI governance documents."),
                  "cline1": TT("{c} is a member of 1 organisation recorded here, which has adopted {m} AI governance documents."),
                  "cline0": TT("{c} is not a member of any organisation recorded here with a membership list."),
                  "csum": TT("{c} also signed {k} of the {n} AI summit declarations recorded here."),
                  "signed": T("Signatories"), "decl": T("Declaration"), "nosig": T("Signatories are not recorded for this document."),

                  "choose": T("Choose an organisation at this headquarters"),
                  "shared": TT("{n} organisations shared with {c}"), "shared1": TT("1 organisation shared with {c}"), "sharedh": TT("Organisations shared with {c}"), "date": T("Date not recorded")}}
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    svg = world(items, label, extra=f'<g class="wm-hq">{"".join(hq)}</g>')
    return map_card("global", "map", T("International and regional organisations: members and documents"),
                    T("Countries are shaded by how many of the {n} organisations recorded here they belong to. Pick an organisation or a country to explore; dots mark headquarters.", n=len(orgs)),
                    svg, leg0 + leg_org + leg_c, above=pickers, side=panel, note=note) + f'<script type="application/json" id="map-orgs">{js}</script>'


# ---------------------------------------------------------------- Search
def qbins(vals, k=6):
    """Upper bounds of up to k bins for the non-zero values (quantiles, whole numbers, strictly increasing); the same rule as
    shade() in site/maps.js, which recomputes them for every result set."""
    v = sorted(x for x in vals if x > 0)
    if not v: return []
    u = sorted(set(v))
    if len(u) <= k: return u
    out = []
    for i in range(1, k + 1):
        q = v[min(len(v) - 1, math.ceil(i * len(v) / k) - 1)]
        if not out or q > out[-1]: out.append(q)
    if out[-1] != v[-1]: out.append(v[-1])
    return out


def spread(k, m):
    """Shade (1-6) of bin k of m: fewer bins than shades are spread over the whole ramp (one bin takes the middle)."""
    return 4 if m == 1 else round(1 + (k - 1) * 5 / (m - 1))


def _qbin(n, ups):
    if not n: return 0
    for k, u in enumerate(ups, 1):
        if n <= u: return spread(k, len(ups))
    return 6


def search_map(D, ctx):
    cids = _countries(D, ctx)
    n_all = {c: 0 for c in cids}
    for i in D["instruments"]:
        if i["jurisdiction_id"] in n_all: n_all[i["jurisdiction_id"]] += 1
    # before the search data loads (and without JavaScript) the map shows what the search starts with: every country document
    ups = qbins(list(n_all.values()))
    items = {c: {"cls": f"m{_qbin(n_all[c], ups)}", "tip": i18n.tr(ctx["jur"][c]["name"]), "attrs": {"i": ""}} for c in cids}
    label = T("World map: the number of documents in the current search results from each country.")
    lo = [1] + [u + 1 for u in ups[:-1]]
    leg = legend(T("Documents in the results"), [(0, T("None"))] + [(spread(k, len(ups)), _range(a, b)) for k, (a, b) in enumerate(zip(lo, ups), 1)])
    return map_card("search", "map", T("Where matching documents come from"),
                    T("Countries are shaded by the number of documents in the current results, and update with every search. Select a country to show only its documents; select it again to show all."),
                    world(items, label), leg, above='<div class="wm-sel" hidden></div>',
                    data={"t-chip": TT("Country: {name}"), "t-rm": TT("Remove {name} from the search"), "t-all": T("Show all countries"),
                          "t-none": T("No documents in the results"), "t-one": TT("1 document"), "t-many": TT("{n} documents"),
                          "t-pick": T("Select to show only this country's documents"), "t-lnone": T("None")})


# ---------------------------------------------------------------- organisation thumbnails (Global)
def org_thumb(bid, ctx):
    im = (ctx["photos"].get(bid) or {}).get("hero")
    if not im: return '<span class="gd-th gd-th-none" aria-hidden="true"></span>'
    return (f'<img class="gd-th" src="../{e(im["file_small"])}" width="{im["width_small"]}" height="{round(im["width_small"] * im["height"] / im["width"])}" '
            f'alt="" loading="lazy" decoding="async">')
