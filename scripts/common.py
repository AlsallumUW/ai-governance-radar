"""Shared helpers for the AI Governance Radar repository."""
import datetime as dt, hashlib, json, pathlib, re, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

WORLD_TYPES = ["published", "revised", "consultation", "adopted", "applied", "superseded", "repealed", "event"]  # event: a dated government action that is not a change to an instrument (e.g. hosting an intergovernmental forum)
RADAR_TYPES = ["added", "corrected", "removed", "link", "radar"]
LIFECYCLE = ["draft", "consultation", "consultation_closed", "published", "adopted", "in_force", "superseded", "repealed", "unverified"]
LINK_STATUS = ["reachable", "redirected", "inaccessible", "broken", "not_checked"]


def today():
    """Today in Riyadh time (UTC+3)."""
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).date().isoformat()


def eid(*parts):
    return "c-" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


def event(date, kind, typ, jur, inst, title, detail="", frm=None, to=None, url=None, recorded=None, review=False):
    return {"id": eid(date, typ, jur, inst, title, frm, to), "date": date, "recorded": recorded or today(), "kind": kind,
            "type": typ, "jurisdiction_id": jur, "instrument_id": inst, "title": title, "detail": detail,
            "from": frm, "to": to, "source_url": url, "needs_review": review}


def jurisdiction_files(root=DATA):
    return sorted((root / "countries").glob("*.json")) + sorted((root / "regional").glob("*.json"))


def load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def save(p, obj):
    pathlib.Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_all(root=DATA):
    """Return {jurisdiction_id: record} from the working tree."""
    return {p.stem: load(p) for p in jurisdiction_files(root)}


def load_all_at(ref):
    """Return {jurisdiction_id: record} as of a git ref (e.g. origin/main). Empty dict if the ref is missing."""
    try:
        names = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref, "data/countries", "data/regional"],
                               cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    except subprocess.CalledProcessError:
        return {}
    out = {}
    for n in names:
        if n.endswith(".json"):
            txt = subprocess.run(["git", "show", f"{ref}:{n}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
            out[pathlib.Path(n).stem] = json.loads(txt)
    return out


def lifecycle_of(i):
    ls, cs = i.get("legal_status") or "", (i.get("current_status") or "").lower()
    if i.get("superseded_by"): return "superseded"
    if "repeal" in cs or "withdrawn" in cs: return "repealed"
    if "consultation" in ls or "consultation" in cs: return "consultation"
    if "drafts" in i.get("categories", []) or "draft" in ls: return "draft"
    if ls == "binding_regulation" and "in force" in cs: return "in_force"
    if cs.startswith(("approved", "adopted", "endorsed", "strategy approved")): return "adopted"
    if cs.startswith(("published", "normative", "mandatory", "opened")) or i.get("publication_date"): return "published"
    return "unverified"


# ---------------------------------------------------------------- public data
# Research-process fields stay in data/ (the repository) but never reach dist/: no notes on how a document was found,
# checked or fetched in anything published (embedded data, data.json, profile.json, CSV and download files).
INTERNAL_FIELDS = {"technical_note", "evidence_reference", "check_method", "search_queries", "needs_review", "final_url",
                   "page_title", "http_status", "error", "content_type", "checked_date", "date_reviewed", "passes",
                   "discovery_result_count", "focused_result_count", "categories_requiring_review", "categories_searched",
                   "source_role", "publisher_name_verified", "note", "metadata_gaps", "link_status"}
# link_status is a link-check result kept for research; pages and exports never say a link is broken or unreachable
# "note" is research text on leads and regional applicability rows; public notes have their own named fields


def link_check_event(x):
    """A change event that only records a link-check result ("Official link restored / no longer reachable"): research, not public."""
    return isinstance(x, dict) and x.get("type") == "link" and (x.get("detail") or "").startswith("Official link ")


def public(obj):
    """A copy of obj without INTERNAL_FIELDS, at any depth."""
    if isinstance(obj, dict): return {k: public(v) for k, v in obj.items() if k not in INTERNAL_FIELDS}
    if isinstance(obj, list): return [public(v) for v in obj if not link_check_event(v)]
    return obj


ADOPT_STATUSES = {"nonbinding_recommendation", "declaration", "international_treaty"}
ARABIC_NAME = re.compile(r"[\u0600-\u06FF]")


def short_issuer(name, sep=";", paren=r"\(([^()]*)\)"):
    """An issuer name as one short phrase: the part before ';' and without long parenthetical notes (acronyms kept)."""
    s = (name or "").strip().split(sep)[0]
    s = re.sub(r"\s*" + paren, lambda m: m.group(0) if len(m.group(1)) <= 24 and not re.match(r"(?:published|hosted|co-hosted|set up|with|convened)\b", m.group(1)) else "", s)
    return re.sub(r"\s+", " ", s).strip(" .,;")


PUB_DATE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")


def publication_event(rec, i, recorded=None):
    """The government action behind a record's publication date ("published", "adopted" or "consultation"), or None
    when the date is missing or gives only a year (a year alone cannot be placed in the Updates time windows).
    Month-only dates ("2026-09") are kept as they are; the Updates page shows them as the month."""
    d = str(i.get("publication_date") or "")
    if not PUB_DATE.match(d): return None
    life = i.get("lifecycle")
    if life in ("consultation", "consultation_closed") or i.get("legal_status") == "consultation_draft": typ, verb = "consultation", "Published for consultation by"
    elif life == "adopted" and i.get("legal_status") in ADOPT_STATUSES: typ, verb = "adopted", "Adopted by"
    else: typ, verb = "published", "Published by"
    iss = short_issuer(next((n for n in (i.get("issuing_authority"), i.get("publisher_name")) if n and not ARABIC_NAME.search(n)), None)
                       or rec["jurisdiction"]["name"])
    title = i.get("english_title") or i.get("official_title")
    return event(d, "world", typ, rec["jurisdiction"]["id"], i["id"], title, f"{verb} {iss}.", url=i.get("source_url"), recorded=recorded)
