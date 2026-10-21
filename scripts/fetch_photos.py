#!/usr/bin/env python3
"""Fetch photos from Wikimedia Commons into data/photos.json and site/img/ (countries and international / regional bodies).

    python3 scripts/fetch_photos.py photos-todo.json             fetch, crop, write images and photos.json entries
    python3 scripts/fetch_photos.py photos-todo.json --dry-run   read the Commons metadata and check the licences only
    python3 scripts/fetch_photos.py photos-todo.json --force     replace an entry that already exists for that role

photos-todo.json is a list of objects:
    {"jurisdiction": "FSB",            ISO3 of a country (data/countries/) or code of a body (data/regional/)
     "kind": "bodies",                 "countries" or "bodies"
     "role": "hero",                   hero (16:9), feature (4:5), backdrop (3:2) or band (21:9)
     "commons_title": "File:....jpg",  the Commons file ("File:" is added if missing)
     "subject": "...", "caption": "...", "why": "...", "alt": "...",
     "crop_focus": "0.5"}              optional: "x" or "x,y" as fractions (0 = left/top, 1 = right/bottom). A single value
                                       applies to the axis that is cropped; default 0.5 (centre)

For each item the script reads the file's Commons metadata (imageinfo + extmetadata: Artist, LicenseShortName,
LicenseUrl; url, size), refuses licences that scripts/validate.py does not allow (PHOTO_LICENCES: public domain, CC0,
CC BY, CC BY-SA) and non-free files, downloads the original (or a 2560 px rendering of very large or non-JPEG/PNG
originals), crops it to the role's shape around crop_focus, writes the two WebP sizes used by the pages
(site/img/<kind>/<code>/<role>-<big>.webp and -<small>.webp, as small as needed to stay within PHOTO_CAPS) and writes the
entry in data/photos.json (author as plain text, licence normalised, license_url, commons_url, title "File:...",
source_width, bytes, changes "cropped and resized"). photos.json is saved after every successful item, so an
interrupted run can be resumed. Afterwards: translate the new captions and alt texts
(python3 scripts/i18n_content.py extract <code>; apply) and run python3 scripts/validate.py.

Needs Pillow (with WebP) and network access to commons.wikimedia.org / upload.wikimedia.org. requests is used when
installed, else urllib.
"""
import argparse, html, io, json, pathlib, re, sys, time, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from validate import PHOTO_CAPS, PHOTO_LICENCES, PHOTO_ROLES  # noqa: E402  the same rules the build enforces

API = "https://commons.wikimedia.org/w/api.php"
UA = "AIGovernanceRadar-photo-fetch/1.0 (https://github.com/AlsallumUW/ai-governance-radar; photo credits page)"
# role -> (aspect width/height, big width, small width, file name stem); file names are fixed, sizes as on country pages
ROLES = {"hero": (16 / 9, 1600, 800), "feature": (4 / 5, 960, 480), "backdrop": (3 / 2, 1280, 640), "band": (21 / 9, 1600, 800)}
THUMB_WIDTH = 2560          # rendering requested when the original is not used (>= 2000 px, as the brief asks)
MAX_ORIGINAL = 6000         # originals wider than this are fetched as a THUMB_WIDTH rendering
FIELD_ORDER = ["role", "file", "file_small", "width", "height", "width_small", "subject", "caption", "why", "alt", "title", "author",
               "license", "license_url", "commons_url", "source_width", "crop_focus", "bytes", "changes"]
KINDS = {"countries": "countries", "bodies": "regional"}

try:
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = 400_000_000
except ImportError:          # the metadata check (--dry-run) still works
    Image = ImageOps = None


# ---------------------------------------------------------------- network
class FetchError(RuntimeError):
    """An HTTP 4xx answer (other than 429): the request is wrong, retrying will not help."""


def http_get(url, params=None, binary=False, tries=4):
    """GET with a descriptive User-Agent (Wikimedia policy) and retries with backoff on errors and 429/5xx."""
    if params: url = url + "?" + urllib.parse.urlencode(params)
    last = None
    for n in range(tries):
        try:
            try:
                import requests
                r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise IOError(f"HTTP {r.status_code}", r.headers.get("Retry-After"))
                if 400 <= r.status_code < 500: raise FetchError(f"HTTP {r.status_code} for {url[:120]}")   # not worth retrying
                r.raise_for_status()
                return r.content if binary else r.text
            except ImportError:
                import urllib.request
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
                return data if binary else data.decode("utf-8")
        except FetchError:
            raise
        except Exception as ex:          # network errors, HTTP errors
            last = ex
            wait = 2 ** n * 3
            ra = ex.args[1] if isinstance(ex, IOError) and len(ex.args) > 1 else None
            if ra and str(ra).isdigit(): wait = max(wait, int(ra))
            if n < tries - 1: time.sleep(wait)
    raise RuntimeError(f"could not fetch {url[:120]}: {last}")


def commons_info(title):
    """imageinfo for one Commons file: url, descriptionurl, width, height, mime, thumburl and extmetadata."""
    q = {"action": "query", "format": "json", "formatversion": "2", "titles": title, "prop": "imageinfo",
         "iiprop": "url|size|mime|extmetadata", "iiurlwidth": str(THUMB_WIDTH), "redirects": "1"}
    d = json.loads(http_get(API, q))
    pages = (d.get("query") or {}).get("pages") or []
    if not pages or pages[0].get("missing") or not pages[0].get("imageinfo"):
        raise ValueError(f"not found on Commons: {title}")
    ii = pages[0]["imageinfo"][0]
    ii["title"] = pages[0]["title"]
    return ii


# ---------------------------------------------------------------- metadata
def plain(s):
    """extmetadata values are HTML: tags removed, entities decoded, whitespace collapsed."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip(" ,;")


def norm_licence(short, url=""):
    """Commons LicenseShortName -> the form validate.py accepts ("CC BY-SA 4.0", "CC BY 3.0 de", "CC0 1.0", "Public domain"),
    or None when it is not an allowed licence."""
    s = plain(short)
    low = s.lower()
    if re.match(r"^(public domain|pd\b|pd-)", low) or "publicdomain/mark" in (url or ""): return "Public domain"
    if re.match(r"^cc0\b|^cc-zero", low) or "publicdomain/zero" in (url or ""): return "CC0 1.0"
    m = re.match(r"^cc[\s-]+(by(?:[\s-]+sa)?)[\s-]+(\d\.\d)(?:[\s-]+([a-z]{2,3}))?$", low)
    if not m: return None
    kind = "BY-SA" if "sa" in m.group(1) else "BY"
    out = f"CC {kind} {m.group(2)}" + (f" {m.group(3)}" if m.group(3) else "")
    return out if PHOTO_LICENCES.match(out) else None


def credit_fields(ii):
    """(author, licence, license_url) from extmetadata; raises ValueError when the file may not be used."""
    md = ii.get("extmetadata") or {}
    v = lambda k: (md.get(k) or {}).get("value") or ""
    if str(v("NonFree")).lower() == "true": raise ValueError("Commons marks this file as non-free")
    lic = norm_licence(v("LicenseShortName"), v("LicenseUrl"))
    if not lic: raise ValueError(f"licence not allowed: {plain(v('LicenseShortName')) or 'none stated'}")
    author = plain(v("Artist")) or plain(v("Attribution")) or plain(v("Credit"))
    if not author:
        if lic in ("Public domain", "CC0 1.0"): author = "Unknown author"
        else: raise ValueError(f"{lic} needs an author credit, and Commons lists none")
    author = re.sub(r"\s*(You are free to use|Photo portfolio|\(\s*Flickr\s*\)).*$", "", author).strip()
    author = re.sub(r"^(Fotograf|Photographer|Photo|Author):\s*", "", author, flags=re.I)
    if len(author) > 160: author = author[:159].rsplit(" ", 1)[0] + "…"
    url = v("LicenseUrl").strip()
    if not url and lic == "CC0 1.0": url = "https://creativecommons.org/publicdomain/zero/1.0/"
    if url.startswith("//"): url = "https:" + url
    return author, lic, url, plain(v("Restrictions"))


# ---------------------------------------------------------------- image
def parse_focus(s):
    """"0.5" -> (0.5, None): applies to the cropped axis; "0.5,0.3" -> (0.5, 0.3)."""
    parts = [p.strip() for p in str(s if s not in (None, "") else "0.5").split(",")]
    vals = [min(1.0, max(0.0, float(p))) for p in parts[:2]]
    return (vals[0], vals[1]) if len(vals) == 2 else (vals[0], None)


def crop_box(w, h, aspect, focus):
    """Largest box of the given aspect inside w x h, centred on the focus point (clamped to the image)."""
    fx, fy = focus
    if w / h > aspect:          # too wide: crop the sides
        cw, ch = round(h * aspect), h
        fy = 0.5 if fy is None else fy
    else:                        # too tall: crop top and bottom
        cw, ch = w, round(w / aspect)
        fx, fy = (0.5, fx) if fy is None else (fx, fy)
    left = min(max(0, round(fx * w - cw / 2)), w - cw)
    top = min(max(0, round(fy * h - ch / 2)), h - ch)
    return left, top, left + cw, top + ch


def encode(im, cap):
    """WebP bytes under the size cap: quality from 82 down to 40; the smallest result if none fits."""
    best = None
    for q in (82, 78, 74, 70, 65, 60, 55, 50, 45, 40):
        buf = io.BytesIO(); im.save(buf, "WEBP", quality=q, method=6)
        b = buf.getvalue()
        if best is None or len(b) < len(best): best = b
        if len(b) <= cap: return b, q
    return best, None


def render(src, role, focus, out_dir):
    """Crop the source image (bytes or a path) to the role's shape and write <role>-<big>.webp and <role>-<small>.webp.
    Returns (width, height, width_small, height_small, [bytes_big, bytes_small], warnings)."""
    if Image is None: raise RuntimeError("Pillow is not installed (pip install Pillow)")
    aspect, big_w, small_w = ROLES[role]
    im = Image.open(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else src)
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB",):
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA"); bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
        else:
            im = im.convert("RGB")
    box = crop_box(im.width, im.height, aspect, focus)
    im = im.crop(box)
    warns = []
    w = min(big_w, im.width)                     # never upscale: a small source gives a smaller image (same file names)
    if w < big_w: warns.append(f"source crop is only {im.width} px wide; image written at {w} px (target {big_w})")
    h = round(w / aspect)
    sw = round(w * small_w / big_w); shh = round(sw / aspect)
    caps = PHOTO_CAPS["hero" if role == "hero" else "other"]
    out_dir.mkdir(parents=True, exist_ok=True)
    sizes = []
    for width, height, cap, name in ((w, h, caps[0], f"{role}-{big_w}.webp"), (sw, shh, caps[1], f"{role}-{small_w}.webp")):
        b, q = encode(im.resize((width, height), Image.LANCZOS), cap)
        if q is None: warns.append(f"{name} is {len(b) // 1000} KB even at quality 40 (cap {cap // 1000} KB)")
        (out_dir / name).write_bytes(b); sizes.append(len(b))
    return w, h, sw, shh, sizes, warns


# ---------------------------------------------------------------- photos.json
def make_entry(item, kind, code, role, dims, meta):
    w, h, sw, _, sizes = dims
    big_w, small_w = ROLES[role][1], ROLES[role][2]
    e = {"role": role, "file": f"img/{kind}/{code}/{role}-{big_w}.webp", "file_small": f"img/{kind}/{code}/{role}-{small_w}.webp",
         "width": w, "height": h, "width_small": sw, "subject": item["subject"], "caption": item["caption"], "why": item["why"],
         "alt": item["alt"], "title": meta["title"], "author": meta["author"], "license": meta["license"], "license_url": meta["license_url"],
         "commons_url": meta["commons_url"], "source_width": meta["source_width"], "crop_focus": str(item.get("crop_focus") or "0.5"),
         "bytes": sizes, "changes": "cropped and resized"}
    return {k: e[k] for k in FIELD_ORDER}


def put_entry(photos, kind, code, entry, force=False):
    """Insert or replace (force) the entry for that role; returns False if one exists and force is off."""
    ph = photos.setdefault(kind, {}).setdefault(code, {"photos": []})
    ims = ph.setdefault("photos", [])
    old = [n for n, im in enumerate(ims) if im.get("role") == entry["role"]]
    if old and not force: return False
    if old: ims[old[0]] = entry
    else: ims.append(entry)
    ims.sort(key=lambda im: PHOTO_ROLES.index(im["role"]) if im.get("role") in PHOTO_ROLES else 9)
    photos[kind] = dict(sorted(photos[kind].items()))
    return True


def save_photos(path, photos):
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(photos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")   # the file's existing format
    tmp.replace(path)


def check_item(item):
    """Problems with one input item (before any network call)."""
    out = []
    for f in ("jurisdiction", "kind", "role", "commons_title", "subject", "caption", "why", "alt"):
        if not str(item.get(f) or "").strip(): out.append(f"missing {f}")
    if item.get("kind") not in KINDS: out.append(f"kind must be one of {sorted(KINDS)}")
    elif item.get("jurisdiction") and not (ROOT / "data" / KINDS[item["kind"]] / f"{item['jurisdiction']}.json").is_file():
        out.append(f"no data/{KINDS[item['kind']]}/{item['jurisdiction']}.json")
    if item.get("role") not in ROLES: out.append(f"role must be one of {list(ROLES)}")
    try: parse_focus(item.get("crop_focus"))
    except ValueError: out.append(f"crop_focus not understood: {item.get('crop_focus')!r}")
    return out


def run(items, dry=False, force=False, photos_path=ROOT / "data/photos.json", img_root=ROOT / "site/img"):
    photos = json.loads(photos_path.read_text(encoding="utf-8")) if photos_path.exists() else {}
    results = []
    for n, item in enumerate(items, 1):
        code, kind, role = item.get("jurisdiction"), item.get("kind"), item.get("role")
        tag = f"[{n}/{len(items)}] {kind}/{code}/{role}"
        bad = check_item(item)
        if bad: results.append((tag, "INVALID", "; ".join(bad))); print(tag, "INVALID:", "; ".join(bad)); continue
        exists = any(im.get("role") == role for im in ((photos.get(kind) or {}).get(code) or {}).get("photos", []))
        if exists and not force and not dry:
            results.append((tag, "SKIPPED", "entry exists (use --force to replace)")); print(tag, "skipped: entry exists"); continue
        title = item["commons_title"].strip()
        if not title.lower().startswith("file:"): title = "File:" + title
        try:
            ii = commons_info(title)
            author, lic, lic_url, restr = credit_fields(ii)
        except Exception as ex:
            results.append((tag, "REFUSED" if isinstance(ex, ValueError) else "FAILED", str(ex))); print(tag, "refused:" if isinstance(ex, ValueError) else "failed:", ex); continue
        note = f"{lic}, {author[:40]}" + (f"; restrictions: {restr}" if restr else "")
        if dry:
            results.append((tag, "OK (dry run)", note)); print(tag, "ok (dry run):", note); continue
        try:
            use_orig = ii.get("mime") in ("image/jpeg", "image/png", "image/webp") and (ii.get("width") or 0) <= MAX_ORIGINAL
            src = http_get(ii["url"] if use_orig or not ii.get("thumburl") else ii["thumburl"], binary=True)
            w, h, sw, shh, sizes, warns = render(src, role, parse_focus(item.get("crop_focus")), img_root / kind / code)
        except Exception as ex:
            results.append((tag, "FAILED", str(ex))); print(tag, "failed:", ex); continue
        meta = {"title": ii["title"], "author": author, "license": lic, "license_url": lic_url,
                "commons_url": ii.get("descriptionurl") or "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(ii["title"].replace(" ", "_")),
                "source_width": ii.get("width")}
        put_entry(photos, kind, code, make_entry(item, kind, code, role, (w, h, sw, shh, sizes), meta), force=True)
        save_photos(photos_path, photos)
        msg = note + f"; {w}x{h}, {sizes[0] // 1000}+{sizes[1] // 1000} KB" + ("; " + "; ".join(warns) if warns else "")
        results.append((tag, "WRITTEN", msg)); print(tag, "written:", msg)
        time.sleep(0.5)          # be gentle with the API
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("todo", help="JSON list of photos to fetch")
    ap.add_argument("--dry-run", action="store_true", help="read metadata and check licences only; write nothing")
    ap.add_argument("--force", action="store_true", help="replace existing entries for the same role")
    a = ap.parse_args()
    items = json.loads(pathlib.Path(a.todo).read_text(encoding="utf-8"))
    if not isinstance(items, list): sys.exit("the input must be a JSON list")
    res = run(items, dry=a.dry_run, force=a.force)
    print("\nSummary")
    width = max((len(t) for t, _, _ in res), default=10)
    for t, st, msg in res: print(f"  {t:<{width}}  {st:<13} {msg}")
    counts = {}
    for _, st, _ in res: counts[st] = counts.get(st, 0) + 1
    print("  " + ", ".join(f"{v} {k.lower()}" for k, v in counts.items()))
    if any(st == "WRITTEN" for _, st, _ in res):
        codes = sorted({t.split("/")[1] for t, st, _ in res if st == "WRITTEN"})
        print(f"\nNext: python3 scripts/i18n_content.py extract {' '.join(codes)} > work.json  (translate the captions and alt texts), "
              "python3 scripts/i18n_content.py apply work.json, then python3 scripts/validate.py")
    sys.exit(1 if any(st in ("FAILED", "INVALID", "REFUSED") for _, st, _ in res) else 0)


if __name__ == "__main__":
    main()
