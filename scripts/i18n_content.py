"""Machine translations of published content into Arabic (UX phase 4b, part B).

    data/i18n/ar/<ISO3>.json            country records
    data/i18n/ar/regional/<CODE>.json   regional and international bodies
    data/i18n/ar/_global.json           change events not tied to a jurisdiction

Each file maps a record id to its translated fields:
    {"<record id>": {"<field>": {"ar": "...", "src": "<hash of the English source>"}}}
Record ids: "issuer:<ISO3>:<hash of the English name>" (field name: an issuing body or publisher as named in a record or lead), an instrument id (fields title, summary, status), a jurisdiction id (fields summary, lead_institutions,
review_notes, coverage_note), a change id (fields title; detail for government actions, kind "world") or "photo:<ISO3>:<role>" (fields caption, alt).
"ar" is null with a "skip" reason when a text could not be translated with confidence; the page then shows the English.

Rules (research/WEEKLY.md): use research/aigr_arabic_terms.csv terms; translate faithfully, never adding, softening or
strengthening legal effect; keep names, numbers and dates unchanged (Western digits); never translate an official title
that is already Arabic.

    python3 scripts/i18n_content.py status [ISO3 ...]      coverage per jurisdiction
    python3 scripts/i18n_content.py extract ISO3 ... > work.json
                                                           the missing or stale texts, ready to translate
    python3 scripts/i18n_content.py apply work.json        store translations (work.json items with "ar" filled in)
"""
import hashlib, json, re, sys
from common import ROOT, DATA, load, jurisdiction_files

BASE = DATA / "i18n" / "ar"
AR = re.compile(r"[؀-ۿ]")


def src_hash(text):
    if isinstance(text, list): text = "\n".join(text)
    return hashlib.sha1((text or "").strip().encode("utf-8")).hexdigest()[:12]


def path_for(jid, rec=None):
    if jid == "_global": return BASE / "_global.json"
    rec = rec or load(next(p for p in jurisdiction_files() if p.stem == jid))
    return BASE / ("regional" if rec["jurisdiction"].get("type") != "country" else "") / f"{jid}.json"


def issuer_id(name, jid):
    """Content id of an issuing body's name in one jurisdiction (the same English name can have a different Arabic name in
    another country, e.g. "Ministry of Education")."""
    return f"issuer:{jid}:{src_hash(name)}"


def is_arabic(text):
    """An official title counts as Arabic when most of its letters are Arabic."""
    letters = re.findall(r"[^\W\d_]", text or "")
    return bool(letters) and sum(1 for c in letters if AR.match(c)) / len(letters) > .5


def items(rec, photos=None):
    """(record id, field, English text) for every text of one jurisdiction that the Arabic pages show translated."""
    jid = rec["jurisdiction"]["id"]
    out = []
    by_id = {}
    for i in rec.get("instruments", []):
        by_id[i["id"]] = i
        if i.get("english_title") and not is_arabic(i.get("official_title")): out.append((i["id"], "title", i["english_title"]))
        if i.get("summary"): out.append((i["id"], "summary", i["summary"]))
        if i.get("current_status"): out.append((i["id"], "status", i["current_status"]))
    n = rec.get("narrative") or {}
    if n.get("summary"): out.append((jid, "summary", n["summary"]))
    if n.get("lead_institutions"): out.append((jid, "lead_institutions", list(n["lead_institutions"])))
    if n.get("review_notes"): out.append((jid, "review_notes", n["review_notes"]))
    a = rec.get("coverage_audit") or {}
    if a.get("no_material_found_note"): out.append((jid, "coverage_note", a["no_material_found_note"]))
    for c in rec.get("changes", []):
        if c.get("title") and not title_from_instrument(c, by_id): out.append((c["id"], "title", c["title"]))
        if c.get("kind") == "world" and c.get("detail"): out.append((c["id"], "detail", c["detail"]))
    seen = set()
    for i in rec.get("instruments", []) + rec.get("leads", []):
        for f in ("issuing_authority", "publisher_name"):
            name = (i.get(f) or "").strip()
            if name and name not in seen and not is_arabic(name):
                seen.add(name); out.append((issuer_id(name, jid), "name", name))
    for ph in ((photos or {}).get(jid) or {}).get("photos", []):
        for f in ("caption", "alt"):
            if ph.get(f): out.append((f"photo:{jid}:{ph['role']}", f, ph[f]))
    return out


def title_from_instrument(c, by_id):
    """A change whose title is its instrument's title reuses that title's translation (or the Arabic official title)."""
    i = by_id.get(c.get("instrument_id"))
    return bool(i) and c["title"] in (i.get("english_title"), i.get("official_title"))


def global_items():
    p = DATA / "changes-global.json"
    cs = load(p) if p.exists() else []
    return ([(c["id"], "title", c["title"]) for c in cs if c.get("title")]
            + [(c["id"], "detail", c["detail"]) for c in cs if c.get("kind") == "world" and c.get("detail")])


def stored(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def check(rid, field, en, entry):
    """'' if the stored translation is current, else 'missing', 'stale' or 'skipped'."""
    if not entry: return "missing"
    if entry.get("src") != src_hash(en): return "stale"
    if entry.get("ar") in (None, "", []): return "skipped"
    return ""


def audit(only=None):
    """{jid: {"total": n, "missing": [...], "stale": [...], "skipped": [...]}}"""
    photos = load(DATA / "photos.json")["countries"] if (DATA / "photos.json").exists() else {}
    res = {}
    for p in jurisdiction_files():
        jid = p.stem
        if only and jid not in only: continue
        rec = load(p)
        res[jid] = _audit(items(rec, photos), stored(path_for(jid, rec)))
    if not only or "_global" in only:
        res["_global"] = _audit(global_items(), stored(path_for("_global")))
    return res


def _audit(its, st):
    r = {"total": len(its), "missing": [], "stale": [], "skipped": []}
    for rid, f, en in its:
        k = check(rid, f, en, (st.get(rid) or {}).get(f))
        if k: r[k].append(f"{rid}.{f}")
    return r


# ---------------------------------------------------------------- quality checks on a translation
_NUM = re.compile(r"[0-9]+(?:[.,][0-9]+)*")
_ACR = re.compile(r"\b[A-Z][A-Z0-9&]{2,}\b")


_GA = None


def _glossary_acronyms():
    """Acronyms that the approved terms already render in Arabic (ASEAN, UNESCO, OECD, GCC ...): no Latin copy needed."""
    global _GA
    if _GA is None:
        import i18n
        _GA = {a for k in i18n.terms() for a in _ACR.findall(k)}
    return _GA


def _strip_glossary(en):
    """Drop glossary terms whose Arabic carries no digits (G7, G20) before the number check: their Arabic replaces them."""
    import i18n
    for k, v in i18n.terms().items():
        if re.search(r"\d", k) and not re.search(r"\d", v): en = re.sub(r"\b" + re.escape(k) + r"\b", " ", en)
    return en


def problems(en, ar):
    """Mechanical checks: numbers kept (Western digits), no «», no Eastern Arabic digits, Latin acronyms kept."""
    if isinstance(en, list):
        if not isinstance(ar, list) or len(ar) != len(en): return ["list length differs"]
        return [p for x, y in zip(en, ar) for p in problems(x, y)]
    out = []
    if not isinstance(ar, str) or not ar.strip(): return ["empty"]
    if re.search("[«»]", ar): out.append("uses «»")
    if re.search("[٠-٩۰-۹]", ar) and not re.search("[٠-٩۰-۹]", en): out.append("Eastern Arabic digits")   # unless quoting a source
    if not AR.search(ar): out.append("no Arabic text")
    en = _strip_glossary(en)
    miss = [n for n in _NUM.findall(en) if n not in ar and n.replace(",", "") not in ar.replace(",", "").replace("،", "")]
    if miss: out.append(f"numbers missing: {miss[:5]}")
    acr = [a for a in set(_ACR.findall(en)) if a not in ar and a not in _glossary_acronyms()]
    if acr: out.append(f"acronyms missing: {sorted(acr)[:5]}")
    return out


# ---------------------------------------------------------------- commands
def extract(jids):
    photos = load(DATA / "photos.json")["countries"]
    work = []
    for jid in jids:
        if jid == "_global": its, st = global_items(), stored(path_for("_global"))
        else:
            rec = load(next(p for p in jurisdiction_files() if p.stem == jid))
            its, st = items(rec, photos), stored(path_for(jid, rec))
        for rid, f, en in its:
            if check(rid, f, en, (st.get(rid) or {}).get(f)) in ("missing", "stale"):
                work.append({"jid": jid, "id": rid, "field": f, "en": en, "ar": None})
    return work


def apply(work, force=False):
    """Store translations from work items. Items failing the checks are reported and not stored unless force."""
    by_file, bad, n = {}, [], 0
    for w in work:
        ar, skip = w.get("ar"), w.get("skip")
        if ar in (None, "", []) and not skip: continue
        pr = [] if skip else problems(w["en"], ar)
        if pr and not force: bad.append((w["id"], w["field"], pr)); continue
        p = path_for(w["jid"])
        d = by_file.setdefault(p, stored(p))
        e = {"ar": None if skip else ar, "src": src_hash(w["en"])}
        if skip: e["skip"] = skip
        d.setdefault(w["id"], {})[w["field"]] = e
        n += 1
    for p, d in by_file.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        d = {k: d[k] for k in sorted(d, key=lambda k: (k.startswith("_"), k))}
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return n, bad


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "status":
        res = audit(set(args) or None)
        tot = sum(r["total"] for r in res.values()); miss = sum(len(r["missing"]) + len(r["stale"]) for r in res.values())
        for jid, r in res.items():
            if args or r["missing"] or r["stale"]: print(f"{jid}: {r['total']} texts, {len(r['missing'])} missing, {len(r['stale'])} stale, {len(r['skipped'])} skipped")
        print(f"total {tot} texts, {tot - miss} translated or skipped, {miss} missing or stale")
    elif cmd == "extract":
        json.dump(extract(args), sys.stdout, ensure_ascii=False, indent=1)
    elif cmd == "apply":
        n, bad = apply(json.loads(open(args[0], encoding="utf-8").read()), force="--force" in args)
        for rid, f, pr in bad: print(f"NOT STORED {rid}.{f}: {'; '.join(pr)}")
        print(f"stored {n}, rejected {len(bad)}")
        sys.exit(1 if bad else 0)
