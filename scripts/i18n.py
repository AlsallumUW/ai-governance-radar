"""Arabic interface (UX phase 4b).

One dictionary, site/i18n/ar.json, drives the Arabic pages:
  strings   English interface text -> Arabic (also English templates with {placeholders} for T())
  patterns  [regex, replacement] for interface text built from numbers, names and dates;
            in a replacement {1} is group 1 as is, {t1} group 1 translated, {d1} group 1 as an Arabic date
  countries ISO3 -> Arabic short name (Unicode CLDR via babel, with editorial overrides)
research/aigr_arabic_terms.csv is the authority for terminology: its terms are merged over ar.json and must be used as written.

The build generates every page a second time with LANG = "ar" (so T() and fmt_date give Arabic), then translate_html()
translates the remaining interface text. In the browser, assets/i18n-ar.js applies the same dictionary to text that
scripts add after load. Data (titles, summaries, names of bodies and people) never matches the dictionary and stays as
published.
"""
import csv, html, json, re
from common import ROOT

LANG = "en"
AR_JSON = ROOT / "site/i18n/ar.json"
TERMS_CSV = ROOT / "research/aigr_arabic_terms.csv"
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
EN_MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])}
EN_MONTHS.update({m[:3]: i for m, i in list(EN_MONTHS.items())}); EN_MONTHS["Sept"] = 8
_M = "|".join(sorted(EN_MONTHS, key=len, reverse=True))
DATE_RE = re.compile(rf"^(?:(\d{{1,2}}) )?({_M}) (\d{{4}})$")


def terms():
    """research/aigr_arabic_terms.csv -> {english: arabic}"""
    with open(TERMS_CSV, encoding="utf-8-sig") as f:
        return {r["english"].strip(): r["arabic"].strip() for r in csv.DictReader(f) if r.get("english")}


def load():
    d = json.loads(AR_JSON.read_text(encoding="utf-8"))
    s = dict(d.get("strings", {}))
    s.update(terms())                       # the CSV wins
    names = {}
    for p in sorted((ROOT / "data/countries").glob("*.json")) + sorted((ROOT / "data/regional").glob("*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))["jurisdiction"]
        ar = d.get("countries", {}).get(j["id"]) or d.get("bodies", {}).get(j["id"])
        if ar:
            names[j["name"]] = ar
            if j.get("short_name") and j["short_name"] != j["id"]: names[j["short_name"]] = ar
            if j["type"] != "country": names[j["id"]] = d.get("body_short", {}).get(j["id"], ar)
    for k, v in names.items(): s.setdefault(k, v)
    pats = [(re.compile(p), r) for p, r in d.get("patterns", [])]
    return d, s, pats


D, STR, PATS = load()
_LOWER = {k.lower(): v for k, v in STR.items()}


def ar_date(t):
    m = DATE_RE.match(t.strip())
    if not m: return None
    day, mon, yr = m.groups()
    return " ".join(x for x in (day, MONTHS[EN_MONTHS[mon]], yr) if x)


class _Miss(Exception): pass


def _render(rep, m):
    """A {tN} group must itself translate (or carry no English words), otherwise the pattern does not apply:
    "Germany flag" becomes "علم ألمانيا", but an English photo caption ending in "flag" is left alone."""
    def sub(x):
        k, i = x.group(1), int(x.group(2)); g = m.group(i) or ""
        if k == "t":
            u = translate(g)
            if u == g and re.search(r"[A-Za-z]{2}", g): raise _Miss
            return u
        return (ar_date(g) or g) if k == "d" else g
    return re.sub(r"\{([td]?)(\d)\}", sub, rep)


def translate(text):
    """Translate one piece of interface text; anything not in the dictionary comes back unchanged."""
    if not text or not text.strip(): return text
    lead = text[:len(text) - len(text.lstrip())]; trail = text[len(text.rstrip()):]
    core = re.sub(r"\s+", " ", text.strip())
    if core in STR: return lead + STR[core] + trail
    if core.isupper() and core.lower() in _LOWER: return lead + _LOWER[core.lower()] + trail   # "SAUDI ARABIA" in captions set in capitals
    for rx, rep in PATS:
        m = rx.match(core)
        if m:
            try: return lead + _render(rep, m) + trail
            except _Miss: continue
    if " · " in core:
        parts = [translate(p) for p in core.split(" · ")]
        if parts != core.split(" · "): return lead + " · ".join(parts) + trail
    d = ar_date(core)
    if d: return lead + d + trail
    return text


_RANK = {n: k for k, n in enumerate(D.get("sort_order", []))}


def name_key(name):
    """Sort key for a country or body name: English order on English pages, Arabic collation (ar.json sort_order) on Arabic pages."""
    if LANG != "ar": return (0, name)
    ar = translate(name)
    return (_RANK.get(ar, len(_RANK)), ar)


def T(en, **kw):
    """A sentence with {placeholders}: the Arabic template when LANG is "ar" (values are passed already formatted)."""
    t = STR.get(en, en) if LANG == "ar" else en
    return t.format(**kw)


def content(rid, field, en=None):
    """Machine translation of a published text (phase 4b part B, data/i18n/ar/) on Arabic pages; None on English pages, before
    it is translated, when it was skipped, or when the English has changed since (a stale translation is never shown)."""
    if LANG != "ar": return None
    entry = _CONTENT.get(rid, {}).get(field)
    if not isinstance(entry, dict) or entry.get("ar") in (None, "", []): return None
    if en is not None:
        from i18n_content import src_hash
        if entry.get("src") != src_hash(en): return None
    return entry["ar"]


def mt_note(anchor):
    """The machine-translation label with a link to the English original (localise() points EN_ORIGINAL at the English page)."""
    return (f'<p class="mt-note"><span class="mt-label">{T("Machine translation")}</span> '
            f'<a href="EN_ORIGINAL#{anchor}" hreflang="en">{T("English original")}</a></p>')


def change_title(c, instruments):
    """(Arabic title of a change event, True if it is a machine translation) or (None, False). A change that carries its
    instrument's title shows that instrument's Arabic official title, or the translation of its English title."""
    t = content(c.get("id"), "title", c.get("title"))
    if t: return t, True
    i = instruments.get(c.get("instrument_id"))
    if i and c.get("title") in (i.get("english_title"), i.get("official_title")):
        off = i.get("official_title") or ""
        if re.search(r"[\u0600-\u06FF]", off): return off, False
        t = content(i["id"], "title", i.get("english_title"))
        if t: return t, True
    return None, False


def _load_content():
    out = {}
    base = ROOT / "data/i18n/ar"
    if base.is_dir():
        for p in base.rglob("*.json"):
            out.update({k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")})
    return out


_CONTENT = _load_content()


def tr(s):
    return translate(s) if LANG == "ar" else s


# ---------------------------------------------------------------- HTML
_TOK = re.compile(r"(<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>|<[^>]+>)", re.S | re.I)
_ATTR = re.compile(r'(\s(?:placeholder|aria-label|title|alt|label|data-tip)=")([^"]*)(")')
_META = re.compile(r'(<meta\s+(?:name|property)="(?:description|og:title|og:description|twitter:title|twitter:description)"\s+content=")([^"]*)(")')


def _esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def _esca(s): return _esc(s).replace('"', "&quot;")


def translate_html(doc):
    out = []
    for part in _TOK.split(doc):
        if not part: continue
        if part.startswith("<"):
            low = part[:8].lower()
            if low.startswith(("<script", "<style", "<!--")): out.append(part); continue
            if low.startswith("<meta"):
                part = _META.sub(lambda m: m.group(1) + _esca(translate(html.unescape(m.group(2)))) + m.group(3), part)
            elif not low.startswith("<path"):
                part = _ATTR.sub(lambda m: m.group(1) + _esca(translate(html.unescape(m.group(2)))) + m.group(3), part)
            out.append(part)
        else:
            t = html.unescape(part)
            u = translate(t)
            out.append(part if u is t else _esc(u))
    return "".join(out)


def runtime_js():
    """assets/i18n-ar.js: the dictionary and the same matching rules, applied to text that scripts add to Arabic pages."""
    data = {"s": STR, "p": D.get("patterns", []), "m": MONTHS, "em": {k: v for k, v in EN_MONTHS.items()}}
    return ("(function(){'use strict';var I=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n" + (ROOT / "site/i18n/runtime.js").read_text(encoding="utf-8") + "})();")
