#!/usr/bin/env python3
"""Arabic page check: chart tooltips and legends on /ar/ pages must be fully Arabic.

Scans every dist/ar page for chart tooltips (data-tip attributes and <title> inside SVG charts), SVG chart text and
legends (elements whose class contains "legend"). Latin letters are allowed only inside parentheses that hold an
acronym or code, such as (SDAIA) or (CETS 225). Digits stay Western. Run after build.py (build.py runs it itself).

    python3 scripts/check_ar_charts.py           report and exit 1 on any failure
"""
import html, re, sys
from common import ROOT

AR = ROOT / "dist/ar"
ACRONYM = re.compile(r"\([A-Z][A-Z0-9&./\- ]*\)")
SCRIPT = re.compile(r"<script\b.*?</script>", re.S | re.I)
SVG = re.compile(r"<svg\b.*?</svg>", re.S)
LEGEND = re.compile(r'<(ul|ol|div|p|span|figcaption)\b[^>]*class="[^"]*\blegend\b[^"]*"[^>]*>(.*?)</\1>', re.S)


def _text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def latin(t):
    return bool(re.search(r"[A-Za-z]", ACRONYM.sub("", t)))


def items(doc):
    doc = SCRIPT.sub("", doc)
    for v in re.findall(r'data-tip="([^"]*)"', doc): yield "tooltip", html.unescape(v)
    for svg in SVG.findall(doc):
        for v in re.findall(r"<title>(.*?)</title>", svg, re.S): yield "tooltip", _text(v)
        for v in re.findall(r"<text\b[^>]*>(.*?)</text>", svg, re.S): yield "chart label", _text(v)
    for m in LEGEND.finditer(doc): yield "legend", _text(m.group(2))


def map_labels():
    """Living-map "What's new" panel and pulse legend: the labels app.js builds at run time (WN_L), filled with sample
    values and passed through the same dictionary the Arabic page uses (site/i18n/ar.json via scripts/i18n.py)."""
    import json
    import i18n
    src = (ROOT / "site/app.js").read_text(encoding="utf-8")
    m = re.search(r"/\*WN_L\*/(\{.*?\})/\*/WN_L\*/", src, re.S)
    if not m: yield "map panel", "WN_L labels not found in site/app.js"; return
    sample = {"c": "Saudi Arabia", "n": "5", "s": "2", "m": "4"}
    for key, tpl in json.loads(m.group(1)).items():
        for d in ("30", "60", "90"):
            en = re.sub(r"\{(\w)\}", lambda x: sample.get(x.group(1), d), tpl)
            yield ("pulse legend" if key == "legend" else "map panel"), i18n.translate(en)
            if "{d}" not in tpl: break


def check():
    bad = {}
    for p in sorted(AR.rglob("*.html")):
        for kind, t in items(p.read_text(encoding="utf-8")):
            if t and latin(t): bad.setdefault((kind, t), []).append(str(p.relative_to(AR)))
    for kind, t in map_labels():
        if t and latin(t): bad.setdefault((kind, t), []).append("index.html (site/app.js WN_L)")
    return bad


def main():
    if not AR.is_dir():
        print("check_ar_charts: dist/ar not built"); return 1
    bad = check()
    for (kind, t), where in sorted(bad.items(), key=lambda x: -len(x[1]))[:40]:
        print(f"ERROR /ar/{where[0]} ({len(where)} page(s)): {kind} has Latin text: {t[:160]}")
    print(f"check_ar_charts: {len(bad)} untranslated chart text(s)" if bad else "check_ar_charts: Arabic chart tooltips and legends OK")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
