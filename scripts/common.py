"""Shared helpers for the AI Governance Radar repository."""
import datetime as dt, hashlib, json, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

WORLD_TYPES = ["published", "revised", "consultation", "adopted", "applied", "superseded", "repealed"]
RADAR_TYPES = ["added", "corrected", "removed", "link", "radar"]
LIFECYCLE = ["draft", "consultation", "published", "adopted", "in_force", "superseded", "repealed", "unverified"]
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
