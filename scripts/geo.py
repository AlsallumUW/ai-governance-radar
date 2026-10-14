"""Small static SVG maps for the country and body pages (UX phase 2b), drawn from site/assets/world.topo.json.

    locator(iso)          small regional map with the country highlighted (side rail)
    silhouette(iso)       large outline of the country (fallback hero when no photo is available)
    world(highlight)      world map with a set of countries highlighted (body page hero)

No dependencies: TopoJSON arcs are decoded here, projected, simplified (Douglas-Peucker in screen space)
and written as compact path data.
"""
import json, math
from functools import lru_cache
from common import ROOT


@lru_cache(maxsize=1)
def _shapes():
    """{ISO3: [ring, ...]} in lon/lat; each ring is a list of (lon, lat)."""
    t = json.loads((ROOT / "site/assets/world.topo.json").read_text(encoding="utf-8"))["countries"]
    arcs = t["arcs"]; tr = t.get("transform")

    def arc(i):
        a = arcs[i if i >= 0 else ~i]
        if tr:  # quantized, delta-encoded
            (sx, sy), (dx, dy) = tr["scale"], tr["translate"]; x = y = 0; pts = []
            for p in a:
                x += p[0]; y += p[1]; pts.append((x * sx + dx, y * sy + dy))
        else:
            pts = [tuple(p) for p in a]
        return pts if i >= 0 else pts[::-1]

    def ring(ids):
        out = []
        for k, i in enumerate(ids):
            pts = arc(i); out.extend(pts if k == 0 else pts[1:])
        return out

    S = {}
    for g in t["objects"]["countries"]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]] if g["type"] == "Polygon" else []
        S[g["id"]] = [ring(r) for poly in polys for r in poly]
    return S


def _area(r):
    return abs(sum(r[i][0] * r[i - 1][1] - r[i - 1][0] * r[i][1] for i in range(len(r)))) / 2


def _dp(pts, tol):
    """Douglas-Peucker simplification of a closed ring (iterative)."""
    if len(pts) < 5: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]; t2 = tol * tol
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]; dx, dy = x2 - x1, y2 - y1; L = dx * dx + dy * dy
        best, bi = -1, -1
        for i in range(a + 1, b):
            x, y = pts[i]
            if L == 0: d = (x - x1) ** 2 + (y - y1) ** 2
            else:
                u = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / L)); d = (x - x1 - u * dx) ** 2 + (y - y1 - u * dy) ** 2
            if d > best: best, bi = d, i
        if best > t2:
            keep[bi] = True; stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def _clip(r, W, H, m=4):
    """Sutherland-Hodgman clip of a ring to the rectangle [-m, W+m] x [-m, H+m]."""
    for edge in range(4):
        if not r: break
        inside = [lambda p: p[0] >= -m, lambda p: p[0] <= W + m, lambda p: p[1] >= -m, lambda p: p[1] <= H + m][edge]
        val = [-m, W + m, -m, H + m][edge]; ax = 0 if edge < 2 else 1
        out = []
        for i, p in enumerate(r):
            q = r[i - 1]
            if inside(p):
                if not inside(q): out.append(_cut(q, p, ax, val))
                out.append(p)
            elif inside(q): out.append(_cut(q, p, ax, val))
        r = out
    return r


def _cut(a, b, ax, v):
    t = (v - a[ax]) / ((b[ax] - a[ax]) or 1e-12)
    return (v, a[1] + t * (b[1] - a[1])) if ax == 0 else (a[0] + t * (b[0] - a[0]), v)


def _path(rings, tol, min_area, nd=1, win=None):
    out = []
    f = (lambda v: f"{v:.{nd}f}".rstrip("0").rstrip(".")) if nd else (lambda v: str(round(v)))
    for r in rings:
        if len(r) < 3 or _area(r) < min_area: continue
        if win:
            bx = _bbox([r])
            if bx[2] < -2 or bx[0] > win[0] + 2 or bx[3] < -2 or bx[1] > win[1] + 2: continue
            r = _clip(r, *win)
            if len(r) < 3: continue
        s = _dp(r, tol)
        if len(s) < 3: continue
        d = "M" + "L".join(f"{f(x)},{f(y)}" for x, y in s) + "Z"
        out.append(d)
    return "".join(out)


def _unwrap(rings, center_lon):
    """Shift whole rings by 360° so they sit within ±180° of center_lon (countries near the antimeridian)."""
    out = []
    for r in rings:
        if not r: continue
        m = sum(p[0] for p in r) / len(r); k = 0
        while m + k - center_lon > 180: k -= 360
        while m + k - center_lon < -180: k += 360
        out.append([(x + k, y) for x, y in r] if k else r)
    return out


def _center(rings):
    """Longitude/latitude centre of a country's largest ring, robust across the antimeridian."""
    big = max(rings, key=lambda r: _area(r) if r else 0)
    xs = [p[0] for p in big]; ys = [p[1] for p in big]
    c = sum(xs) / len(xs)
    if max(xs) - min(xs) > 180:  # ring itself straddles ±180
        c = sum(x % 360 for x in xs) / len(xs)
        c = c - 360 if c > 180 else c
    return c, (min(ys) + max(ys)) / 2


def _bbox(rings):
    xs = [p[0] for r in rings for p in r]; ys = [p[1] for r in rings for p in r]
    return min(xs), min(ys), max(xs), max(ys)


def _country_rings(iso, center_lon):
    rings = _unwrap(_shapes().get(iso, []), center_lon)
    # drop far-flung overseas parts (e.g. French Guiana for France) when one part clearly dominates
    if len(rings) > 1:
        big = max(rings, key=_area); bx = _bbox([big]); A = _area(big)
        far = lambda r: (min(abs(p[0] - (bx[0] + bx[2]) / 2) for p in r) > 25 or min(abs(p[1] - (bx[1] + bx[3]) / 2) for p in r) > 25)
        main = [r for r in rings if not (far(r) and _area(r) < A * 0.5)]
        if main: return main, rings
    return rings, rings


def locator(iso, name="", W=200, H=150):
    """Regional map, country highlighted. Small countries get a ring marker."""
    S = _shapes()
    if iso not in S: return ""
    clon, clat = _center(S[iso])
    main, _ = _country_rings(iso, clon)
    x0, y0, x1, y1 = _bbox(main)
    k = math.cos(math.radians(max(-70, min(70, (y0 + y1) / 2))))
    # window: country plus context, at least 28° of longitude, keeping the W:H ratio
    tiny = max(x1 - x0, y1 - y0) < 3  # small island states: show more ocean so neighbours give context
    span_x = max((x1 - x0) * k * 2.2, (y1 - y0) * 2.2 * W / H, (60 if tiny else 28) * k)
    span_y = span_x * H / W
    cx, cy = ((x0 + x1) / 2) * k, (y0 + y1) / 2
    sx = W / span_x
    px = lambda lon, lat: ((lon * k - cx) * sx + W / 2, (cy - lat) * sx + H / 2)
    tol = 0.45
    others = []
    for cid, rings in S.items():
        if cid == iso: continue
        rr = _unwrap(rings, clon)
        bx = _bbox(rr)
        if bx[2] * k < cx - span_x / 2 - 1 or bx[0] * k > cx + span_x / 2 + 1 or bx[3] < cy - span_y / 2 - 1 or bx[1] > cy + span_y / 2 + 1: continue
        d = _path([[px(*p) for p in r] for r in rr], 0.8, 2.5, nd=0, win=(W, H))
        if d: others.append(d)
    pr = [[px(*p) for p in r] for r in main]
    me = _path(pr, tol * .6, 0.05)
    dots = [r[0] for r in pr if len({(round(x, 1), round(y, 1)) for x, y in r}) < 3]
    me += "".join(f"M{x - 1.6:.1f},{y:.1f}a1.6,1.6 0 1,0 3.2,0a1.6,1.6 0 1,0 -3.2,0Z" for x, y in dots)
    bx = _bbox(pr); size = max(bx[2] - bx[0], bx[3] - bx[1])
    mark = ""
    if size < 10 or len(dots) == len(pr):
        mx, my = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        mark = f'<circle class="loc-ring" cx="{mx:.1f}" cy="{my:.1f}" r="{max(7, size / 2 + 4):.1f}"/>'
    label = f"Locator map: {name} highlighted" if name else "Locator map"
    return (f'<svg class="locator" viewBox="0 0 {W} {H}" role="img" aria-label="{label}"><rect class="loc-sea" width="{W}" height="{H}"/>'
            f'<path class="loc-land" d="{"".join(others)}"/><path class="loc-me" d="{me}"/>{mark}</svg>')


def silhouette(iso, name="", W=1200, H=640):
    """Large outline of the country for the fallback hero (no photo available)."""
    S = _shapes()
    if iso not in S: return ""
    clon, _ = _center(S[iso])
    main, allr = _country_rings(iso, clon)
    x0, y0, x1, y1 = _bbox(main)
    k = math.cos(math.radians(max(-70, min(70, (y0 + y1) / 2))))
    w, h = max((x1 - x0) * k, 1e-6), max(y1 - y0, 1e-6)
    pad = 0.08
    s = min(W * (1 - 2 * pad) / w, H * (1 - 2 * pad) / h)
    ox = (W - w * s) / 2 - x0 * k * s; oy = (H - h * s) / 2 + y1 * s
    px = lambda lon, lat: (lon * k * s + ox, oy - lat * s)
    d = _path([[px(*p) for p in r] for r in main], 0.8, 1.5)
    if not d:  # very small islands: keep everything
        d = _path([[px(*p) for p in r] for r in main], 0.3, 0)
    # islands too small for the source map (stored as single points) are drawn as dots
    pts = [px(*r[0]) for r in main if len({(round(x, 4), round(y, 4)) for x, y in r}) < 3]
    if pts and sum(_area(r) for r in [[px(*p) for p in r] for r in main]) < W * H * 0.02:
        d += "".join(f"M{x - 12:.1f},{y:.1f}a12,12 0 1,0 24,0a12,12 0 1,0 -24,0Z" for x, y in pts)
    return (f'<svg class="silhouette" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Outline of {name}">'
            f'<path d="{d}"/></svg>')


# Territory rules for the body maps: one list. Each entry names a part of a member's outline in world.topo.json
# (matched by the ring's centre falling in `box` = lon0, lat0, lon1, lat1).
#   "overseas_region": legally part of the state but overseas; highlighted only for the bodies in `included_in`
#                      (EU outermost regions, TFEU art. 349/355(1)); every other body shows main territory only.
#   "dependency":      not part of the member's main territory and outside these bodies; never highlighted.
# Greenland, Faroe Islands, New Caledonia, French Polynesia, Wallis and Futuna, Saint Pierre and Miquelon,
# Saint Barthélemy, Aruba, Curaçao, Sint Maarten and UK overseas territories are not drawn as part of any
# member in world.topo.json, so they can never be highlighted; Caribbean Netherlands and Clipperton are, hence listed.
TERRITORIES = [
    {"iso": "FRA", "name": "French Guiana", "box": (-55, 1, -51, 6.5), "status": "overseas_region", "included_in": ["EU"]},
    {"iso": "FRA", "name": "Guadeloupe", "box": (-62, 15.8, -60.9, 16.6), "status": "overseas_region", "included_in": ["EU"]},
    {"iso": "FRA", "name": "Martinique", "box": (-61.3, 14.3, -60.7, 15), "status": "overseas_region", "included_in": ["EU"]},
    {"iso": "FRA", "name": "Saint-Martin", "box": (-63.2, 18, -62.9, 18.2), "status": "overseas_region", "included_in": ["EU"]},
    {"iso": "FRA", "name": "Mayotte", "box": (44.9, -13.1, 45.4, -12.5), "status": "overseas_region", "included_in": ["EU"]},
    {"iso": "FRA", "name": "Réunion", "box": (55.1, -21.5, 56, -20.8), "status": "overseas_region", "included_in": ["EU"]},
    {"iso": "PRT", "name": "Azores", "box": (-32, 36.5, -24.5, 40), "status": "overseas_region", "included_in": ["EU"]},
    {"iso": "PRT", "name": "Madeira", "box": (-17.5, 32.3, -16, 33.2), "status": "overseas_region", "included_in": ["EU"]},
    {"iso": "ESP", "name": "Canary Islands", "box": (-18.5, 27.5, -13, 29.6), "status": "overseas_region", "included_in": ["EU"]},
    {"iso": "FRA", "name": "Clipperton Island", "box": (-110, 9.5, -108.5, 11), "status": "dependency"},
    {"iso": "NLD", "name": "Caribbean Netherlands (Bonaire, Sint Eustatius, Saba)", "box": (-69, 11.8, -62.8, 18), "status": "dependency"},
    {"iso": "NOR", "name": "Bouvet Island", "box": (2.5, -55, 4.5, -54), "status": "dependency"},
    {"iso": "NZL", "name": "Tokelau", "box": (-173, -10, -171, -8), "status": "dependency"},
]


def _member_part(cid, ring, body):
    """True if this ring of member `cid` is highlighted on `body`'s map (see TERRITORIES)."""
    if not ring: return False
    x = sum(p[0] for p in ring) / len(ring); y = sum(p[1] for p in ring) / len(ring)
    for t in TERRITORIES:
        b = t["box"]
        if t["iso"] == cid and b[0] <= x <= b[2] and b[1] <= y <= b[3]:
            return t["status"] == "overseas_region" and body in t.get("included_in", [])
    return True


def world(highlight, name="", W=960, H=470, body=None):
    """Equal Earth world map, members highlighted (body pages). Overseas parts follow TERRITORIES."""
    S = _shapes(); hl = set(highlight)
    # Equal Earth projection (Šavrič, Patterson, Jenny 2018)
    A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796; M = math.sqrt(3) / 2

    def ee(lon, lat):
        l, p = math.radians(lon), math.radians(lat)
        t = math.asin(M * math.sin(p)); t2 = t * t; t6 = t2 * t2 * t2
        x = l * math.cos(t) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
        y = t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
        return x, y
    xmax = ee(180, 0)[0]
    s = W / (2 * xmax)
    top = ee(0, 84)[1] * s; bot = -ee(0, -58)[1] * s
    Hc = top + bot
    px = lambda lon, lat: (W / 2 + ee(lon, lat)[0] * s, top - ee(lon, lat)[1] * s)
    land, mem = [], []
    for cid, rings in S.items():
        if cid in hl:
            on = [r for r in rings if _member_part(cid, r, body)]; off = [r for r in rings if not _member_part(cid, r, body)]
        else:
            on, off = [], rings
        d = _path([[px(*p) for p in r] for r in off], 0.6, 0.4, nd=1)
        if d: land.append(d)
        d = _path([[px(*p) for p in r] for r in on], 0.6, 0.05, nd=1)  # keep small member islands visible
        if d: mem.append(d)
    label = f"World map: member states of {name} highlighted" if name else "World map"
    return (f'<svg class="worldmap" viewBox="0 0 {W} {Hc:.0f}" role="img" aria-label="{label}">'
            f'<path class="wm-land" d="{"".join(land)}"/><path class="wm-me" d="{"".join(mem)}"/></svg>')
