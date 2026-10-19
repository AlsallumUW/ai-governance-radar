"""Low-detail world geometry for the moving globe: site/assets/world.topo.lo.json.

Same objects and arcs as site/assets/world.topo.json (countries + land), each arc simplified with Visvalingam's
algorithm. Arcs are shared between neighbouring countries, so simplifying arcs (never rings) keeps borders watertight;
arc end points are always kept. Targets: about 15,000 country points and 6,000 land points.
(site/vendor/make_topo.js writes the same file with topojson-simplify when Node is available.)

    python3 scripts/make_topo_lo.py
"""
import heapq, json
from common import ROOT

SRC, OUT = ROOT / "site/assets/world.topo.json", ROOT / "site/assets/world.topo.lo.json"
TARGET = {"countries": 15000, "land": 6000}


def decode(topo):
    """Absolute arc coordinates (undo quantisation and delta encoding when the topology has a transform)."""
    t = topo.get("transform")
    if not t: return [[list(p[:2]) for p in a] for a in topo["arcs"]]
    (sx, sy), (tx, ty) = t["scale"], t["translate"]
    out = []
    for a in topo["arcs"]:
        x = y = 0; pts = []
        for p in a:
            x += p[0]; y += p[1]; pts.append([x * sx + tx, y * sy + ty])
        out.append(pts)
    return out


def tri(a, b, c):
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2


def weights(pts):
    """Visvalingam effective area of each point (end points get infinity), made monotonic as in topojson-simplify."""
    n = len(pts); w = [float("inf")] * n
    if n < 3: return w
    prev = list(range(-1, n - 1)); nxt = list(range(1, n + 1)); area = [0.0] * n; heap = []
    for i in range(1, n - 1):
        area[i] = tri(pts[i - 1], pts[i], pts[i + 1]); heapq.heappush(heap, (area[i], i))
    alive = [True] * n; maxa = 0.0
    while heap:
        a, i = heapq.heappop(heap)
        if not alive[i] or a != area[i]: continue
        maxa = max(maxa, a); w[i] = maxa; alive[i] = False
        p, q = prev[i], nxt[i]; nxt[p] = q; prev[q] = p
        for j in (p, q):
            if 0 < j < n - 1 and alive[j]:
                area[j] = tri(pts[prev[j]], pts[j], pts[nxt[j]]); heapq.heappush(heap, (area[j], j))
    return w


def simplify(topo, target):
    arcs = decode(topo); ws = [weights(a) for a in arcs]
    finite = sorted(x for w in ws for x in w if x != float("inf"))
    fixed = sum(1 for w in ws for x in w if x == float("inf"))
    keep_n = max(0, target - fixed)
    thr = finite[-keep_n] if 0 < keep_n <= len(finite) else (0 if keep_n > len(finite) else float("inf"))
    out = []
    for a, w in zip(arcs, ws):
        pts = [p for p, x in zip(a, w) if x >= thr]
        closed = a[0] == a[-1]
        if closed and len(pts) < 4:      # a ring made of one arc needs at least 4 points
            mid = sorted(range(1, len(a) - 1), key=lambda i: -w[i])[:2]
            pts = [a[0]] + [a[i] for i in sorted(mid)] + [a[-1]]
        out.append([[round(x, 4), round(y, 4)] for x, y in pts])
    t = {k: v for k, v in topo.items() if k not in ("arcs", "transform")}
    t["arcs"] = out
    return t, sum(len(a) for a in out)


def main():
    T = json.loads(SRC.read_text(encoding="utf-8"))
    lo = {}
    for k in ("countries", "land"):
        lo[k], n = simplify(T[k], TARGET[k])
        print(f"{k}: {sum(len(a) for a in T[k]['arcs'])} -> {n} points")
    OUT.write_text(json.dumps(lo, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.name} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
