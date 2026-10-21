"""Hero visuals for the Analysis, Timeline, Global and Search pages (built as static HTML/SVG; no runtime dependency).

    world_map(D, ctx)       Analysis: Equal Earth choropleth of national-level instruments per country (links to country pages)
    rise_band(D, ctx)       Timeline: monthly count of instruments dated to the month or day, stacked by group, with annotations
    org_mosaic(D, ctx)      Global: photo mosaic of the organisations with the most documents (links to their pages)
    org_thumb(bid, ctx)     Global: small hero-photo thumbnail for an organisation card
    topic_cloud(D, ctx)     Search: suggested topics sized by the number of documents each one finds

Every label goes through i18n.T / i18n.tr, so the Arabic pass (i18n.LANG = "ar") renders Arabic directly.
"""
import json, math, re
import i18n
from common import ROOT
from pages import e, fmt_date, kind

T = i18n.T


# ---------------------------------------------------------------- world map (Analysis)
TOPO = ROOT / "site/assets/world.topo.lo.json"
# national-level instruments per country: 0, then six bins (close to sextiles of the non-zero counts, rounded to plain numbers)
BINS = [(1, 2), (3, 5), (6, 10), (11, 20), (21, 50), (51, None)]
MAP_W = 800
LAT_MIN, LAT_MAX = -56.0, 84.0


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
    # the separator is only needed where the next number does not start with "-"
    out = steps[0]
    for s in steps[1:]: out += s if s.startswith("-") else " " + s
    return d + out + "z"


def _geometry():
    """{ISO3: [rings in pixels]} and the map height, cached per build."""
    if "_geo" in _CACHE: return _CACHE["_geo"]
    topo = json.loads(TOPO.read_text(encoding="utf-8"))["countries"]
    arcs = _decode(topo)
    x0, _ = equal_earth(-180, 0); x1, _ = equal_earth(180, 0)
    _, ytop = equal_earth(0, LAT_MAX); _, ybot = equal_earth(0, LAT_MIN)
    s = MAP_W / (x1 - x0)
    H = round((ytop - ybot) * s, 1)

    def proj(p):
        x, y = equal_earth(p[0], max(LAT_MIN, min(LAT_MAX, p[1])))
        return ((x - x0) * s, (ytop - y) * s)

    parcs = [_simplify([proj(p) for p in a], 0.9) for a in arcs]

    def ring(idx):
        out = []
        for k in idx:
            a = parcs[k] if k >= 0 else parcs[~k][::-1]
            out.extend(a if not out else a[1:])
        return out

    geo = {}
    for g in topo["objects"]["countries"]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]] if g["type"] == "Polygon" else []
        geo[g["id"]] = [ring(r) for p in polys for r in p]
    _CACHE["_geo"] = (geo, H)
    return geo, H


def bin_of(n):
    if not n: return 0
    for k, (lo, hi) in enumerate(BINS, 1):
        if hi is None or n <= hi: return k
    return len(BINS)


def bin_label(k):
    lo, hi = BINS[k - 1]
    return f"{lo}+" if hi is None else f"{lo}–{hi}"


def world_map(D, ctx):
    jur = ctx["jur"]
    counts = {j["id"]: 0 for j in D["jurisdictions"] if j["type"] == "country"}
    for i in D["instruments"]:
        if i["jurisdiction_id"] in counts and i.get("government_level") == "national": counts[i["jurisdiction_id"]] += 1
    geo, H = _geometry()
    body, dots = [], []
    for cid in sorted(geo, key=lambda c: -abs(sum(_area(r) for r in geo[c]))):   # large countries first: small ones stay on top
        if cid not in counts: continue
        rings = geo[cid]
        areas = [abs(_area(r)) for r in rings]
        big = max(range(len(rings)), key=lambda k: areas[k]) if rings else None
        d = "".join(_ring_d(r) for k, r in enumerate(rings) if areas[k] >= .6 or k == big)
        n = counts[cid]; name = i18n.tr(jur[cid]["name"])
        tip = (T("{country}: no instruments found at national level", country=name) if n == 0 else
               T("{country}: 1 instrument", country=name) if n == 1 else T("{country}: {n} instruments", country=name, n=n))
        mark = f'<path d="{d}"/>'
        if sum(areas) < 10 and big is not None:     # small states: a dot, so they can be seen and clicked
            r = rings[big]; cx = sum(p[0] for p in r) / len(r); cy = sum(p[1] for p in r) / len(r)
            dots.append(f'<a href="../country/{cid}/" class="m{bin_of(n)}" tabindex="-1"><title>{e(tip)}</title><circle cx="{_num(cx)}" cy="{_num(cy)}" r="2.6"/></a>')
            continue
        body.append(f'<a href="../country/{cid}/" class="m{bin_of(n)}" tabindex="-1"><title>{e(tip)}</title>{mark}</a>')
    nat = sum(counts.values()); zero = sum(1 for v in counts.values() if not v)
    label = T("World map: national-level instruments recorded in each of the 195 countries ({n} in all; {z} countries with none found). The same counts are in the country ranking below.",
              n=f"{nat:,}", z=zero)
    svg = (f'<svg class="wm" viewBox="0 0 {MAP_W} {_num(H)}" role="img" aria-label="{e(label)}">' + "".join(body) + "".join(dots) + '</svg>')
    sw = ([f'<span><i class="wk m0"></i>{e(T("None found"))}</span>']
          + [f'<span><i class="wk m{k}"></i><bdi dir="ltr">{bin_label(k)}</bdi></span>' for k in range(1, len(BINS) + 1)])
    legend = (f'<div class="wm-legend legend"><span class="wm-lh">{e(T("Instruments recorded (national level)"))}</span>'
              f'<span class="wm-keys">{"".join(sw)}</span></div>')
    return f'<figure class="hero-vis wm-fig">{svg}{legend}</figure>'


# ---------------------------------------------------------------- the rise (Timeline)
GROUP_ORDER = ("soft", "binding", "draft")     # bottom to top, as in the analysis charts
GROUP_CLASS = {"soft": "n", "binding": "b", "draft": "d"}


def _monotone(xs, ys):
    """Monotone cubic (Fritsch-Carlson) path segments through the points: no overshoot below zero or above a peak."""
    n = len(xs)
    if n < 3: return "".join(f"L{_num(x)} {_num(y)}" for x, y in zip(xs[1:], ys[1:]))
    dx = [xs[i + 1] - xs[i] for i in range(n - 1)]
    m = [(ys[i + 1] - ys[i]) / dx[i] for i in range(n - 1)]
    t = [m[0]] + [0 if m[i - 1] * m[i] <= 0 else (m[i - 1] + m[i]) / 2 for i in range(1, n - 1)] + [m[-1]]
    for i in range(n - 1):
        if m[i] == 0: t[i] = t[i + 1] = 0; continue
        a, b = t[i] / m[i], t[i + 1] / m[i]
        h = a * a + b * b
        if h > 9: k = 3 / math.sqrt(h); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]
    out = []
    for i in range(n - 1):
        h = dx[i] / 3
        out.append(f"C{_num(xs[i] + h)} {_num(ys[i] + t[i] * h)} {_num(xs[i + 1] - h)} {_num(ys[i + 1] - t[i + 1] * h)} {_num(xs[i + 1])} {_num(ys[i + 1])}")
    return "".join(out)


def rise_band(D, ctx):
    today = ctx["today"]
    y0, ylast, mlast = 2016, int(today[:4]), int(today[5:7])
    months = [f"{y}-{m:02d}" for y in range(y0, ylast + 1) for m in range(1, 13) if (y, m) <= (ylast, mlast)]
    cnt = {k: {g: 0 for g in GROUP_ORDER} for k in months}
    cum_all, year_only = [], 0
    for i in D["instruments"]:
        d = i.get("publication_date") or ""
        if len(d) == 4: year_only += 1; continue
        if len(d) < 7: continue
        cum_all.append(d[:7])
        if d[:7] in cnt: cnt[d[:7]][kind(i)] += 1
    cum_all.sort()
    tot = [sum(cnt[k].values()) for k in months]
    W, H, L, R, TOP, B = 600, 236, 6, 6, 74, 24
    pw, ph = W - L - R, H - TOP - B
    top = max(tot) * 1.04 or 1
    X = lambda n: L + pw * n / (len(months) - 1)
    Y = lambda v: TOP + ph - ph * v / top
    xs = [X(n) for n in range(len(months))]
    o = [f'<svg class="rise" viewBox="0 0 {W} {H}" role="img" aria-label="{e(T("Instruments dated to the month or day, per month since January 2016, stacked by binding or mandatory, non-binding and drafts"))}">']
    for yr in range(y0, ylast + 1):
        n = months.index(f"{yr}-01")
        o.append(f'<line class="yr" x1="{_num(X(n))}" x2="{_num(X(n))}" y1="{TOP - 4}" y2="{TOP + ph}"/>'
                 f'<text class="tick{" odd" if (yr - y0) % 2 else ""}" x="{_num(X(n) + 3)}" y="{H - 7}">{yr}</text>')
    base = [0] * len(months)
    for g in GROUP_ORDER:
        upper = [b + cnt[k][g] for b, k in zip(base, months)]
        yt = [Y(v) for v in upper]; yb = [Y(v) for v in base]
        d = (f"M{_num(xs[0])} {_num(yt[0])}" + _monotone(xs, yt) + f"L{_num(xs[-1])} {_num(yb[-1])}"
             + _monotone(xs[::-1], yb[::-1]) + "Z")
        o.append(f'<path class="ar s-{GROUP_CLASS[g]}" d="{d}"/>')
        base = upper
    o.append(f'<path class="tot" d="M{_num(xs[0])} {_num(Y(tot[0]))}{_monotone(xs, [Y(v) for v in tot])}"/>')
    o.append(f'<line class="base" x1="{L}" x2="{W - R}" y1="{TOP + ph}" y2="{TOP + ph}"/>')
    # annotations, in priority order: the total since 2016, the busiest month, the months the 1,000th and the 100th dated
    # instruments (any date to the month or day, earlier ones included) were reached
    total = sum(tot)
    pk = max(range(len(months)), key=lambda n: (tot[n], n))
    notes = [(len(months) - 1, tot[-1], T("{n} since 2016", n=f"{total:,}"), "nt-total"),
             (pk, tot[pk], T("Busiest month: {month}, {n}", month=fmt_date(months[pk]), n=tot[pk]), "")]
    for mile in (1000, 100):
        if len(cum_all) >= mile and cum_all[mile - 1] in cnt:
            n = months.index(cum_all[mile - 1])
            notes.append((n, tot[n], T("{n}th dated instrument: {month}", n=f"{mile:,}", month=fmt_date(months[n])), ""))
    rows = [14, 37, 60]                 # label rows above the plot

    def place(scale):
        """Greedy rows: a label may not overlap another label in its row, nor cross the leader line of a note placed above it
        (and its own leader line may not cross a label below it). Returns {note index: row} for the notes that fit."""
        boxes, out = [], {}
        for k, (n, v, text, _) in enumerate(notes):
            x = X(n); w = len(text) * 5.4 * scale + 6
            a, b = (x - w, x) if x > W * .6 else (x, x + w)
            for r in range(len(rows)):
                if any(r == r2 and a < b2 + 10 and b2 > a and a2 < b + 10 for r2, a2, b2, _ in boxes): continue
                if any(r2 < r and a - 4 <= x2 <= b + 4 for r2, _, _, x2 in boxes): continue
                if any(r2 > r and a2 - 4 <= x <= b2 + 4 for r2, a2, b2, _ in boxes): continue
                boxes.append((r, a, b, x)); out[k] = r; break
        return out

    wide, narrow = place(1), place(1.75)        # phones show the labels larger (analysis.css); notes that do not fit are hidden there
    for k, (n, v, text, cls) in enumerate(notes):
        if k not in wide: continue
        x = X(n); ly = rows[wide[k]]; end = x > W * .6
        hide = " nm" if narrow.get(k) != wide[k] else ""
        o.append(f'<g class="note{" " + cls if cls else ""}{hide}"><line x1="{_num(x)}" x2="{_num(x)}" y1="{ly + 4}" y2="{_num(Y(v) - 4)}"/>'
                 f'<circle cx="{_num(x)}" cy="{_num(Y(v))}" r="3"/><text x="{_num(x + (-5 if end else 5))}" y="{ly}" text-anchor="{"end" if end else "start"}">{e(text)}</text></g>')
    caption = T("{n} instruments dated to the month or day since January 2016, by month. {y} dated only by year are not included. {m} is incomplete.",
                n=f"{total:,}", y=year_only, m=fmt_date(months[-1]))
    legend = ('<p class="legend rise-legend"><span><i class="sw s-b"></i>' + e(T("Binding or mandatory")) + '</span><span><i class="sw s-n"></i>'
              + e(T("Non-binding")) + '</span><span><i class="sw s-d"></i>' + e(T("Drafts")) + '</span></p>')
    return f'<figure class="hero-vis rise-fig">{"".join(o)}</svg>{legend}<figcaption class="vis-cap">{e(caption)}</figcaption></figure>'


# ---------------------------------------------------------------- organisation photos (Global)
# 5 columns x 4 rows; [column, row, column span, row span] for the tiles in rank order (most documents first)
MOSAIC = [(1, 1, 2, 2), (3, 1, 1, 2), (4, 1, 2, 1), (4, 2, 1, 2), (5, 2, 1, 1), (1, 3, 1, 2), (2, 3, 2, 1), (5, 3, 1, 1),
          (2, 4, 1, 1), (3, 4, 2, 1), (5, 4, 1, 1)]


def _alt(im):
    return (im.get("alt_ar") or im["alt"]) if i18n.LANG == "ar" else im["alt"]


def org_mosaic(D, ctx):
    from pages import body_name
    jur, photos = ctx["jur"], ctx["photos"]
    n_docs = {}
    for i in D["instruments"]:
        if jur.get(i["jurisdiction_id"], {}).get("type") not in (None, "country"): n_docs[i["jurisdiction_id"]] = n_docs.get(i["jurisdiction_id"], 0) + 1
    order = {b: k for k, b in enumerate(ctx["body_order"])}
    pick = sorted((b for b in ctx["body_order"] if (photos.get(b) or {}).get("hero")), key=lambda b: (-n_docs.get(b, 0), order[b]))[:len(MOSAIC)]
    tiles = []
    for k, (b, (c, r, cs, rs)) in enumerate(zip(pick, MOSAIC)):
        im = photos[b]["hero"]
        n = n_docs.get(b, 0)
        docs = T("1 document") if n == 1 else T("{n} documents", n=n)
        # the big tile takes the 1600-px file on wide screens; the others the 800-px one
        srcset = f'../{e(im["file_small"])} {im["width_small"]}w' + (f', ../{e(im["file"])} {im["width"]}w' if k == 0 else "")
        sizes = "(min-width: 1000px) 260px, 60vw" if k == 0 else "(min-width: 1000px) 130px, 33vw"
        tiles.append(f'<li class="mo-t{" mo-big" if k == 0 else ""}{" mo-pw" if k == 9 else ""}" style="--c:{c};--r:{r};--cs:{cs};--rs:{rs}">'
                     f'<a href="../body/{e(b)}/"><img src="../{e(im["file_small"])}" srcset="{srcset}" sizes="{sizes}" width="{im["width_small"]}" height="{round(im["width_small"] * im["height"] / im["width"])}" '
                     f'alt="{e(_alt(im))}" loading="lazy" decoding="async"><span class="mo-l"><b>{e(body_name(jur[b], short=True))}</b><span>{e(docs)}</span></span></a></li>')
    credit = (f'<p class="vis-cap mo-credit">{e(T("Photos: Wikimedia Commons"))} — <a href="../credits/#organisations">{e(T("see Credits"))}</a></p>')
    return (f'<figure class="hero-vis mo-fig"><ul class="mosaic" aria-label="{e(T("Organisations with the most documents"))}">{"".join(tiles)}</ul>'
            f'{credit}</figure>')


def org_thumb(bid, ctx):
    im = (ctx["photos"].get(bid) or {}).get("hero")
    if not im: return '<span class="gd-th gd-th-none" aria-hidden="true"></span>'
    return (f'<img class="gd-th" src="../{e(im["file_small"])}" width="{im["width_small"]}" height="{round(im["width_small"] * im["height"] / im["width"])}" '
            f'alt="" loading="lazy" decoding="async">')


# ---------------------------------------------------------------- suggested topics (Search)
# the same matching as site/search.js: text and terms normalised alike; Latin related terms match whole words (plural allowed),
# the typed term (the topic's first term) matches as a word prefix when longer than 3 letters; Arabic terms match anywhere
_DIAC = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭـ]")
_SEP = re.compile(r"[\s\-_/‐-―­]+")
_AR = re.compile(r"[؀-ۿ]")
_LATIN = re.compile(r"^[a-z0-9 ]+$")
B0, B1 = r"(?<![^\W_])", r"(?![^\W_])"
_CACHE = {}


def _norm(s):
    s = _DIAC.sub("", str(s or "").lower())
    s = re.sub("[أإآٱ]", "ا", s).replace("ة", "ه").replace("ى", "ي")
    return _SEP.sub(" ", s)


def _alt_src(a, typed):
    s = " ?".join(re.escape(w) for w in a.strip().split(" ") if w)
    if _AR.search(a): return s
    if typed and len(a.replace(" ", "")) > 3: return B0 + s
    return B0 + s + r"(?:e?s)?" + B1


def topic_counts(D, ctx, groups, lang):
    """{group key: number of documents the topic's chip finds} for the page language: the chip searches its first term in
    that language with related terms on, over the documents the search shows by default (all countries, all dates)."""
    key = ("topics", lang)
    if key in _CACHE: return _CACHE[key]
    import search
    idx = search.index(D, ctx)
    f = idx["fields"]
    cols = [f.index(k) for k in ("title", "official_title", "arabic_title", "issuer", "issuer_ar", "summary", "status", "summary_ar", "status_ar")]
    jc = f.index("jurisdiction")
    # the search starts on "All countries": documents of international and regional bodies are left out until a body is picked
    rows = [r for r in idx["items"] if idx["jurisdictions"].get(r[jc], [None, None, ""])[2] == "c"]
    fields = [[_norm(r[c]) for c in cols if r[c]] for r in rows]
    mem = [[(_norm(x).strip(), x) for x in g["en"] + g["ar"]] for g in groups]
    can_contain = lambda ns: len(ns) >= 4 or (len(ns) >= 3 and not _LATIN.match(ns))
    out = {}
    for g in groups:
        term = g["ar"][0] if lang == "ar" else g["en"][0]
        n = _norm(term).strip(); ns = n.replace(" ", "")
        alts = {n: (term, True)}
        for gg, mm in zip(groups, mem):
            if any(x.replace(" ", "") == ns or (can_contain(ns) and ns in x.replace(" ", "")) for x, _ in mm):
                for x, raw in mm: alts.setdefault(x, (raw, False))
        src = "|".join(_alt_src(k, typed) for k, (raw, typed) in sorted(alts.items(), key=lambda kv: -len(kv[0])))
        rx = re.compile(src)
        out[g["key"]] = sum(1 for fs in fields if any(rx.search(v) for v in fs))
    _CACHE[key] = out
    return out


def topic_cloud(D, ctx):
    groups = json.loads((ROOT / "site/search_terms.json").read_text(encoding="utf-8"))["groups"]
    lang = "ar" if i18n.LANG == "ar" else "en"
    cnt = topic_counts(D, ctx, groups, lang)
    gs = [g for g in groups if cnt.get(g["key"])]
    if not gs: return ""
    mx = max(cnt[g["key"]] for g in gs); mn = min(cnt[g["key"]] for g in gs)
    # largest topics towards the middle of the flow, smaller ones at both ends, so the cloud has a centre of gravity
    ranked = sorted(gs, key=lambda g: (-cnt[g["key"]], g["key"]))
    left, right = [], []
    for k, g in enumerate(ranked): (left if k % 2 else right).append(g)
    flow = left[::-1] + right
    bs = []
    for g in flow:
        n = cnt[g["key"]]
        t = (math.sqrt(n) - math.sqrt(mn)) / ((math.sqrt(mx) - math.sqrt(mn)) or 1)      # 0..1 on a square-root scale
        lvl = 1 + min(4, int(t * 5))
        label = g["label_ar"] if lang == "ar" else g["label_en"]
        tip = T("{topic}: {n} documents", topic=label, n=f"{n:,}")
        bs.append(f'<button type="button" class="tb-b tb-{lvl}" data-key="{e(g["key"])}" aria-pressed="false" style="--t:{t:.3f}" title="{e(tip)}">'
                  f'<span class="tb-l">{e(label)}</span><span class="tb-n">{n:,}</span></button>')
    cap = T("Suggested topics, sized by the number of recorded documents each one finds. Select a topic to search for it.")
    return (f'<figure class="hero-vis tc-fig"><div class="tcloud" id="srCloud" role="group" aria-label="{e(T("Suggested topics"))}">{"".join(bs)}</div>'
            f'<figcaption class="vis-cap">{e(cap)}</figcaption></figure>')
