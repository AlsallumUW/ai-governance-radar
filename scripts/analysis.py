"""Global analysis page and publication timeline (UX phase 3).

    <out>/analysis/index.html   static SVG charts, each with a table view and a CSV download
    <out>/timeline/index.html   every dated instrument on a time axis (site/timeline.js draws it from inline JSON)

Called from pages.write_all with the same context the country pages use. Nothing here edits data.
"""
import json, math, re, statistics
import i18n
from i18n import tr
from pages import (e, kind, KIND_LABEL, KIND_CLASS, COUNT_NOTE, STATUS_LABEL, BODY_ORDER, SITE_URL, fmt_date, year)

REGIONS = ["Africa", "Americas", "Asia", "Europe", "Oceania"]
GROUPS = ("soft", "binding", "draft")          # stack order, bottom to top (orange / blue / aqua: the weak pair is never adjacent)
LEGEND = ('<p class="legend"><span><i class="sw s-b"></i>Binding or mandatory</span><span><i class="sw s-n"></i>Non-binding</span>'
          '<span><i class="sw s-d"></i>Drafts</span></p>')
# issuer type: the record's authority_type, else its organisation's. Anything not listed here is reported as unclassified.
ISSUER = {
    "legislature": "Legislatures", "parliament": "Legislatures",
    "government": "Governments and ministries", "ministry": "Governments and ministries", "executive": "Governments and ministries",
    "executive_agency": "Governments and ministries", "agency": "Governments and ministries", "government_agency": "Governments and ministries",
    "government_department": "Governments and ministries", "government_council": "Governments and ministries", "head_of_state": "Governments and ministries",
    "subnational_government": "Governments and ministries", "local_government": "Governments and ministries", "municipal": "Governments and ministries",
    "regulator": "Regulators", "data_protection_authority": "Regulators", "central_bank": "Regulators", "cybersecurity_agency": "Regulators",
    "oversight_body": "Regulators",
    "judiciary": "Courts and judicial councils", "court": "Courts and judicial councils", "judicial_body": "Courts and judicial councils",
    "standards_body": "Other", "advisory_body": "Other", "independent_body": "Other", "audit": "Other", "audit_body": "Other",
    "attorney_general": "Other", "prosecution_service": "Other", "ethics_body": "Other", "sector_body": "Other", "public_body": "Other",
    "military_agency": "Other", "council": "Other",
}
ISSUER_ORDER = ["Legislatures", "Governments and ministries", "Regulators", "Courts and judicial councils", "Other"]
LEVELS = [("national", "National"), ("subnational", "State / provincial"), ("local", "Local"), ("regional", "Regional body")]
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]


def rn(r): return tr("the Americas" if r == "Americas" else r)
def _T(en, **kw): return i18n.T(en, **kw)
def LS(): return "، " if i18n.LANG == "ar" else ", "


def pct(n, d): return round(100 * n / d) if d else 0


def nice_step(mx):
    for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500):
        if mx / s <= 6: return s
    return 1000


def round_top(path_x, y, w, h, r):
    """Bar path with rounded top corners, flat on the baseline."""
    r = max(0, min(r, w / 2, h))
    return (f"M{path_x:.1f},{y + h:.1f}V{y + r:.1f}Q{path_x:.1f},{y:.1f} {path_x + r:.1f},{y:.1f}H{path_x + w - r:.1f}"
            f"Q{path_x + w:.1f},{y:.1f} {path_x + w:.1f},{y + r:.1f}V{y + h:.1f}Z")


def round_end(x, y, w, h, r):
    """Horizontal bar with rounded right end, flat on the left axis."""
    r = max(0, min(r, h / 2, w))
    return f"M{x:.1f},{y:.1f}H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{y + h - r:.1f}Q{x + w:.1f},{y + h:.1f} {x + w - r:.1f},{y + h:.1f}H{x:.1f}Z"


def table(head, rows, first_is_header=True):
    return ('<table class="data-table"><thead><tr>' + "".join(f'<th scope="col">{e(h)}</th>' for h in head) + '</tr></thead><tbody>'
            + "".join('<tr>' + "".join((f'<th scope="row">{e(c)}</th>' if n == 0 and first_is_header else f'<td>{e(c)}</td>') for n, c in enumerate(r)) + '</tr>' for r in rows)
            + '</tbody></table>')


def afig(fid, title, takeaway, desc, body, head, rows, note="", legend=""):
    """A chart figure: takeaway, chart, hidden table, table toggle and a CSV download of exactly the table's rows."""
    csv = json.dumps({"file": f"ai-governance-radar-{fid}.csv", "head": head, "rows": rows}, ensure_ascii=False).replace("</", "<\\/")
    return (f'<figure class="fig afig" id="{fid}"><figcaption><h3>{e(title)}</h3><p class="takeaway">{e(takeaway)}</p><p class="fig-desc">{e(desc)}</p></figcaption>'
            f'{legend}<div class="fig-chart">{body}</div><div class="fig-table" hidden>{table(head, rows)}</div>'
            f'<p class="fig-tools"><button type="button" class="linkbtn" data-toggle-table="{fid}" aria-expanded="false">Show as table</button> · '
            f'<button type="button" class="linkbtn" data-csv="{fid}">Download data (CSV)</button>{(" · " + e(note)) if note else ""}</p>'
            f'<script type="application/json" class="csv-data">{csv}</script></figure>')


# ---------------------------------------------------------------- AI-relevant dates for older binding laws
# Instruments first published before 2016 are mostly general binding laws (data protection, copyright, sector
# laws) recorded because a provision now applies to AI. On the adoption curve (the any-instrument and binding lines) they are dated by the AI-relevant provision,
# never by the original enactment: (1) a dated government action on the record whose text names the AI-relevant change, else
# (2) a dated amendment stated in the record's own current_status or summary, quoted below; the quote is checked against the
# record at every build, so a record edit that removes it drops the date. Records with neither are left off the line and
# listed in research/queue.json -> amendment_dates for a later data pass. No date here comes from outside the records.
AI_CUTOFF = "2016"
AI_TERMS = re.compile(r"artificial intelligence|\bAI\b|automated|deepfake|generative|algorithm|computer program|machine learning|synthetic|non-enjoyment", re.I)
AMEND_TEXT = {
    "i-15469f3cb73d": ("2023-09-22", "Section 12.1 (decisions based exclusively on automated processing) and s. 8.1 (identification, location and profiling technologies) were added by S.Q. 2021, c. 25 and apply from 22 September 2023"),
    "i-722b5be69283": ("2023-09-22", "Section 65.2 (decisions based exclusively on automated processing) was added by S.Q. 2021, c. 25 and applies from 22 September 2023"),
    "i-abaa8506db21": ("2018-12-12", "Article 47 (automated decisions) in its version in force since 1 June 2019 (Ordinance No. 2018-1125 of 12 December 2018)"),
    "i-92150e6be05d": ("2017-07-31", "issued 31 July 2017), which inserted § 41 (automated individual decision-making"),
    "i-c8f219c8d641": ("2025-11-17", "The AI-relevant Article 19-1 was added by Law No. 231-VIII of 17 November 2025"),
    "i-75c77177037a": ("2021-06-08", "Art. 18-2 inserted by Act No. 18207 of 8 June 2021"),
    "i-6c7857073ce0": ("2024", "Privacy and Other Legislation Amendment Act 2024 (automated-decision transparency"),
    "i-74baefb2c7ac": ("2001-06-12", "Section 6A was inserted by the Family and Community Services and Veterans' Affairs Legislation Amendment (Debt Recovery) Act 2000 (Royal Assent 12 June 2001)"),
    "i-f67bdefee4c0": ("2015", "Section 186.1 (Electronic Administration) was added by s.175 of the Economic Action Plan 2015 Act, No. 1"),
    "i-a1ead5c5c11d": ("2023-06-22", "Part VI.1 (Electronic Administration and Enforcement, ss.28.2-28.4) was added by s.305 of the Budget Implementation Act, 2023, No. 1 (S.C. 2023, c. 26, assented 22 June 2023)"),
    "i-8b82d0dfddc2": ("2011-07-25", "Art. 16 is in the wording of Law No. 261-FZ of 25.07.2011"),
}


def ai_dates(D, cids):
    """{id: (date, basis)} for country instruments first published before AI_CUTOFF that have an AI-relevant date; and the list without one."""
    ev = {}
    for c in D["changes"]:
        if c.get("kind") == "world" and c.get("instrument_id") and c.get("type") in ("revised", "adopted", "applied") and c.get("date"):
            if AI_TERMS.search((c.get("title") or "") + " " + (c.get("detail") or "")): ev.setdefault(c["instrument_id"], []).append(c)
    dated, missing = {}, []
    for i in D["instruments"]:
        if i["jurisdiction_id"] not in cids or not i.get("publication_date") or i["publication_date"][:4] >= AI_CUTOFF: continue
        later = sorted((c for c in ev.get(i["id"], []) if c["date"] > i["publication_date"]), key=lambda c: c["date"])
        if later:
            dated[i["id"]] = (later[0]["date"], f'government action: {later[0].get("title")}')
            continue
        t = AMEND_TEXT.get(i["id"])
        if t and t[1] in (i.get("current_status") or "") + " " + (i.get("summary") or ""):
            dated[i["id"]] = (t[0], f"record text: {t[1]}")
            continue
        missing.append(i)
    return dated, missing


def queue_amendment_dates(D, cids):
    _, missing = ai_dates(D, cids)
    return [{"jurisdiction_id": i["jurisdiction_id"], "instrument_id": i["id"], "title": i.get("english_title") or i.get("official_title"),
             "publication_date": i.get("publication_date"),
             "need": "date of the amendment that added the AI-relevant provision, or confirmation that it was in the original text"} for i in
            sorted(missing, key=lambda i: (i["jurisdiction_id"], i["publication_date"] or ""))]


# ---------------------------------------------------------------- the numbers
def compute(D, recs, ctx):
    jur = ctx["jur"]
    countries = [j for j in D["jurisdictions"] if j["type"] == "country"]
    cids = {j["id"] for j in countries}
    C = [i for i in D["instruments"] if i["jurisdiction_id"] in cids]          # national, subnational and local
    R = [i for i in D["instruments"] if i["jurisdiction_id"] not in cids]      # regional / international bodies
    orgs = ctx["orgs"]
    by_c = {c: [] for c in cids}
    for i in C: by_c[i["jurisdiction_id"]].append(i)
    leads = sum(len(r.get("leads") or []) for r in recs.values())
    ai_dated, ai_missing = ai_dates(D, cids)
    return {"ai_dated": ai_dated, "ai_missing": ai_missing, "ai_missing_ids": {i["id"] for i in ai_missing}, "countries": countries, "cids": cids, "C": C, "R": R, "by_c": by_c, "leads": leads, "orgs": orgs, "jur": jur}


# ---------------------------------------------------------------- a. instruments per year
def fig_years(N, today):
    C, R = N["C"], N["R"]
    first = 2016
    last = int(today[:4])
    keys = ["≤2015"] + [str(y) for y in range(first, last + 1)]
    bk = {k: {"binding": 0, "soft": 0, "draft": 0} for k in keys}
    reg = {k: 0 for k in keys}
    und_c = und_r = 0
    for i in C:
        y = year(i.get("publication_date"))
        if y is None: und_c += 1; continue
        bk["≤2015" if y < first else str(y)][kind(i)] += 1
    for i in R:
        y = year(i.get("publication_date"))
        if y is None: und_r += 1; continue
        reg["≤2015" if y < first else str(y)] += 1
    W, H, L, Rr, T, B = 720, 300, 40, 8, 12, 46
    pw, ph = W - L - Rr, H - T - B
    tot = {k: sum(v.values()) for k, v in bk.items()}
    mx = max(tot.values()) or 1; step = nice_step(mx); top = -(-mx // step) * step
    bw = pw / len(keys) * .62
    o = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Country instruments per publication year, stacked by binding or mandatory, non-binding and drafts">']
    for t in range(0, top + 1, step):
        y = T + ph - ph * t / top
        o.append(f'<line class="grid" x1="{L}" x2="{W - Rr}" y1="{y:.1f}" y2="{y:.1f}"/><text class="tick" x="{L - 6}" y="{y + 4:.1f}" text-anchor="end">{t}</text>')
    for n, k in enumerate(keys):
        cx = L + pw * (n + .5) / len(keys); x = cx - bw / 2; y0 = T + ph
        drawn = [(g, bk[k][g]) for g in GROUPS if bk[k][g]]
        for idx, (g, v) in enumerate(drawn):
            h = ph * v / top; gap = 2 if idx else 0; hh = max(.5, h - gap); yy = y0 - gap - hh
            tip = f"{k}: {v} {KIND_LABEL[g].lower()} (of {tot[k]})"
            if idx == len(drawn) - 1:
                o.append(f'<path class="mark s-{KIND_CLASS[g]}" d="{round_top(x, yy, bw, hh, 4)}" data-tip="{e(tip)}"><title>{e(tip)}</title></path>')
            else:
                o.append(f'<rect class="mark s-{KIND_CLASS[g]}" x="{x:.1f}" y="{yy:.1f}" width="{bw:.1f}" height="{hh:.1f}" data-tip="{e(tip)}"><title>{e(tip)}</title></rect>')
            y0 -= h
        if tot[k] and k in (max(tot, key=tot.get), keys[-1]):
            o.append(f'<text class="val" x="{cx:.1f}" y="{T + ph - ph * tot[k] / top - 6:.1f}" text-anchor="middle">{tot[k]}</text>')
        o.append(f'<text class="tick" x="{cx:.1f}" y="{T + ph + 16}" text-anchor="middle">{e(k if k != keys[-1] else k + "*")}</text>')
        if reg[k]:
            o.append(f'<text class="tick reg" x="{cx:.1f}" y="{T + ph + 36}" text-anchor="middle" data-tip="{e(k)}: {reg[k]} regional-body instrument{"s" if reg[k] != 1 else ""}">{reg[k]}</text>')
    o.append(f'<text class="tick" x="{L - 6}" y="{T + ph + 36}" text-anchor="end">Regional</text>')
    o.append(f'<line class="axis" x1="{L}" x2="{W - Rr}" y1="{T + ph}" y2="{T + ph}"/></svg>')
    rows = [[k, bk[k]["binding"], bk[k]["soft"], bk[k]["draft"], tot[k], reg[k]] for k in keys]
    rows.append(["Undated", "", "", "", und_c, und_r])
    rows.append(["Total", sum(r[1] for r in rows[:-1]), sum(r[2] for r in rows[:-1]), sum(r[3] for r in rows[:-1]), len(C), len(R)])
    peak = max((k for k in keys if k != "≤2015"), key=lambda k: tot[k])
    dated = len(C) - und_c
    since23 = sum(tot[k] for k in keys if k not in ("≤2015",) and int(k) >= 2023)
    soft = sum(bk[k]["soft"] for k in keys)
    take = _T("{peak} has the most country instruments ({n}). {p23}% of the {dated} dated country instruments were published in 2023 or later; "
              "{psoft}% of all dated country instruments are non-binding.", peak=peak, n=tot[peak], p23=pct(since23, dated), dated=f"{dated:,}", psoft=pct(soft, dated))
    desc = _T("National, state/provincial and local instruments by publication year. *{y} runs to {date} only. "
              "The row beneath the axis counts instruments of regional and international bodies (EU, GCC, AU, ASEAN, Council of Europe, UNESCO, OECD, ICESCO, ALECSO, G7, G20), not stacked.",
              y=keys[-1], date=fmt_date(today))
    note = _T("Undated: {c} country, {r} regional (not shown)", c=und_c, r=und_r)
    return afig("fig-years", "Instruments per year", take, desc, "".join(o), ["Year", "Binding or mandatory", "Non-binding", "Drafts", "Country total", "Regional bodies"], rows, note, LEGEND), {
        "years_total": sum(tot.values()), "undated_c": und_c, "undated_r": und_r, "regional_dated": sum(reg.values())}


# ---------------------------------------------------------------- b. adoption curve
def fig_adoption(N, today):
    first_any, first_strat, first_bind = {}, {}, {}
    for c, rows in N["by_c"].items():
        for i in rows:
            y = year(i.get("publication_date"))
            if y is None: continue
            if i.get("legal_status") == "national_strategy" and i.get("government_level") == "national":
                first_strat[c] = min(first_strat.get(c, 9999), y)
            # records first published before AI_CUTOFF count from their AI-relevant date, or not at all (both lines alike)
            if i["id"] in N["ai_dated"]: y = int(N["ai_dated"][i["id"]][0][:4])
            elif i["id"] in N["ai_missing_ids"]: continue
            first_any[c] = min(first_any.get(c, 9999), y)
            if kind(i) == "binding":
                first_bind[c] = min(first_bind.get(c, 9999), y)
    start, last = 2010, int(today[:4])
    ys = list(range(start, last + 1))
    series = [("any", "At least one instrument", first_any, "ln-a"), ("strat", "A national AI strategy", first_strat, "ln-s"),
              ("bind", "Binding or mandatory, incl. data protection and sector laws that apply to AI", first_bind, "ln-b")]
    cum = {k: [sum(1 for v in f.values() if v <= y) for y in ys] for k, _, f, _ in series}
    W, H, L, Rr, T, B = 720, 300, 40, 150, 14, 28
    pw, ph = W - L - Rr, H - T - B
    top = 200
    X = lambda n: L + pw * n / (len(ys) - 1)
    Y = lambda v: T + ph - ph * v / top
    o = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Cumulative number of countries by year: with at least one instrument, with a national AI strategy, with at least one binding-or-mandatory instrument">']
    for t in range(0, top + 1, 50):
        o.append(f'<line class="grid" x1="{L}" x2="{L + pw}" y1="{Y(t):.1f}" y2="{Y(t):.1f}"/><text class="tick" x="{L - 6}" y="{Y(t) + 4:.1f}" text-anchor="end">{t}</text>')
    o.append(f'<line class="grid ref" x1="{L}" x2="{L + pw}" y1="{Y(195):.1f}" y2="{Y(195):.1f}"/><text class="tick" x="{L + 4}" y="{Y(195) - 4:.1f}">195 countries</text>')
    for n, y in enumerate(ys):
        if n % 2 == 0 or n == len(ys) - 1:
            o.append(f'<text class="tick" x="{X(n):.1f}" y="{T + ph + 18}" text-anchor="middle">{y}{"*" if y == last else ""}</text>')
    lab_y = []
    for k, name, _, cls in series:
        pts = " ".join(f"{X(n):.1f},{Y(v):.1f}" for n, v in enumerate(cum[k]))
        o.append(f'<polyline class="line {cls}" points="{pts}"/>')
        for n, v in enumerate(cum[k]):
            tip = f"{ys[n]}: {v} countries — {name.lower()}"
            o.append(f'<circle class="pt {cls}" cx="{X(n):.1f}" cy="{Y(v):.1f}" r="4" data-tip="{e(tip)}"><title>{e(tip)}</title></circle>')
        lab_y.append([Y(cum[k][-1]), k, name, cls])
    lab_y.sort()
    for n in range(1, len(lab_y)):          # keep direct labels from colliding
        if lab_y[n][0] - lab_y[n - 1][0] < 28: lab_y[n][0] = lab_y[n - 1][0] + 28
    short = {"any": "Any instrument", "strat": "National AI strategy", "bind": "Binding or mandatory"}
    for yy, k, name, cls in lab_y:
        o.append(f'<text class="dlab {cls}-t" x="{L + pw + 10}" y="{yy + 4:.1f}">{e(short[k])} · {cum[k][-1]}</text>')
    o.append(f'<line class="axis" x1="{L}" x2="{L + pw}" y1="{T + ph}" y2="{T + ph}"/></svg>')
    legend = ('<p class="legend"><span><i class="sw ln-a"></i>At least one instrument</span><span><i class="sw ln-s"></i>National AI strategy</span>'
              '<span><i class="sw ln-b"></i>Binding or mandatory, incl. data protection and sector laws that apply to AI</span></p>')
    rows = [[y, cum["any"][n], cum["strat"][n], cum["bind"][n]] for n, y in enumerate(ys)]
    pre = {k: sum(1 for v in f.values() if v < start) for k, _, f, _ in series}
    s20 = cum["strat"][ys.index(2020)]
    moved = len(N["ai_dated"]); miss = len(N["ai_missing"])
    off = sorted(c for c, rows in N["by_c"].items() if rows and c not in first_any)
    take = _T("By {date}, {any} of 195 countries had at least one recorded instrument with an AI-relevant date, {strat} a national AI strategy and "
              "{bind} at least one binding-or-mandatory instrument with an AI-relevant date. Countries with a national AI strategy rose from {s20} at the end of 2020 to {strat}.",
              date=fmt_date(today), any=cum['any'][-1], strat=cum['strat'][-1], bind=cum['bind'][-1], s20=s20)
    desc = (_T("Cumulative countries, counted from the date of the earliest qualifying instrument found. The binding-or-mandatory line includes state, provincial and local "
               "instruments and general laws (data protection, copyright, sector laws) that apply to AI: the records do not reliably separate AI-specific laws from these, so "
               "one line is shown. On the any-instrument and binding lines, instruments first published before {cutoff} are dated by the AI-relevant amendment or provision "
               "where the record states it ({moved} instruments); {miss} with no such date in the record are left off both lines until a data pass finds it",
               cutoff=AI_CUTOFF, moved=moved, miss=miss)
            + (_T(", so {n} countries whose only records are among them ({names}) are not on the any-instrument line yet. ", n=len(off),
                  names=LS().join(tr(N['jur'][c]['name']) for c in off)) if off else ". ")
            + _T("The strategy line uses publication dates. Regional instruments (such as the EU AI Act) are not counted. *{y} runs to {date}.", y=last, date=fmt_date(today)))
    return afig("fig-adoption", "Adoption curve", take, desc, "".join(o), ["End of year", "Countries with at least one instrument (AI-relevant date)", "Countries with a national AI strategy",
                "Countries with at least one binding-or-mandatory instrument (AI-relevant date)"], rows,
                _T("Before {start}: {a} / {s} / {b} countries (included in the {start} values) · {moved} pre-{cutoff} instruments re-dated, {miss} awaiting an amendment date (research/queue.json)",
                   start=start, a=pre['any'], s=pre['strat'], b=pre['bind'], moved=moved, cutoff=AI_CUTOFF, miss=miss), legend), {
        "any": cum["any"][-1], "strat": cum["strat"][-1], "bind": cum["bind"][-1], "moved": moved, "missing": miss}


# ---------------------------------------------------------------- c. by region
def quart(v):
    v = sorted(v)
    if len(v) < 4: return v[0], statistics.median(v), v[-1]
    q = statistics.quantiles(v, n=4, method="inclusive")
    return q[0], q[1], q[2]


DEEP_SUB = ["USA", "CAN", "AUS", "BRA", "IND", "CHN"]
REGION_NOTE = ("Regional instruments (e.g. the EU AI Act) are counted once for the body, not for each member; this lowers counts for EU members. "
               "Subnational coverage is deeper for USA, CAN, AUS, BRA, IND, CHN (see Methodology).")
SCOPES = [("nat", "National-level instruments only"), ("all", "Including state/provincial and local instruments")]


def afig_variants(fid, title, desc, variants, note=""):
    """Like afig, with one block per scope; a page-wide checkbox switches them. Table view and CSV follow the visible block."""
    out = [f'<figure class="fig afig" id="{fid}"><figcaption><h3>{e(title)}</h3>'
           f'<label class="scope-toggle"><input type="checkbox" data-scope-toggle> Include state/provincial and local</label></figcaption>']
    for key, take, body, head, rows, legend in variants:
        csv = json.dumps({"file": f"ai-governance-radar-{fid}-{key}.csv", "head": head, "rows": rows}, ensure_ascii=False).replace("</", "<\\/")
        out.append(f'<div class="variant" data-scope="{key}"{" hidden" if key != "nat" else ""}><p class="takeaway">{e(take)}</p>'
                   f'<p class="fig-desc">{e(desc[key])}</p>{legend}<div class="fig-chart">{body}</div><div class="fig-table" hidden>{table(head, rows)}</div>'
                   f'<script type="application/json" class="csv-data">{csv}</script></div>')
    out.append(f'<p class="fig-tools"><button type="button" class="linkbtn" data-toggle-table="{fid}" aria-expanded="false">Show as table</button> · '
               f'<button type="button" class="linkbtn" data-csv="{fid}">Download data (CSV)</button></p><p class="fig-note">{e(note)}</p></figure>')
    return "".join(out)


def region_counts(N, scope):
    return {c: [i for i in rows if scope == "all" or i.get("government_level") == "national"] for c, rows in N["by_c"].items()}


def region_parts(N, by_c, scope):
    reg = {r: [j for j in N["countries"] if j.get("region") == r] for r in REGIONS}
    stats = {}
    for r, js in reg.items():
        counts = sorted(len(by_c[j["id"]]) for j in js)
        q1, med, q3 = quart(counts)
        top = max(js, key=lambda j: len(by_c[j["id"]]))
        stats[r] = {"n": len(js), "min": counts[0], "q1": q1, "med": med, "q3": q3, "max": counts[-1], "zero": sum(1 for c in counts if c == 0), "top": top["name"]}
    W, rowh, L, Rr, T = 720, 54, 92, 16, 26
    H = T + rowh * len(REGIONS) + 10
    gmax = max(s["max"] for s in stats.values())
    # square-root scale: the spread within each region stays readable while the largest count still fits
    ticks = [t for t in [0, 5, 10, 25, 50, 100, 200, 400] if t <= gmax * 1.05]
    if gmax > ticks[-1] * 1.25: ticks.append(gmax)
    S = lambda v: L + (W - L - Rr) * math.sqrt(v) / math.sqrt(max(gmax, 1))
    o = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Instruments per country by region ({e(dict(SCOPES)[scope].lower())}): every country as a dot, with the median and the middle half marked">']
    for t in ticks:
        o.append(f'<line class="grid" x1="{S(t):.1f}" x2="{S(t):.1f}" y1="{T - 6}" y2="{H - 6}"/><text class="tick" x="{S(t):.1f}" y="{T - 10}" text-anchor="middle">{t}</text>')
    for n, r in enumerate(REGIONS):
        s = stats[r]; cy = T + n * rowh + rowh / 2
        o.append(f'<text class="cat" x="{L - 12}" y="{cy + 4:.1f}" text-anchor="end">{e(r)}</text>')
        o.append(f'<line class="rng" x1="{S(s["min"]):.1f}" x2="{S(s["max"]):.1f}" y1="{cy:.1f}" y2="{cy:.1f}"/>')
        o.append(f'<rect class="iqr" x="{S(s["q1"]):.1f}" y="{cy - 9:.1f}" width="{max(2, S(s["q3"]) - S(s["q1"])):.1f}" height="18" rx="4"/>')
        for j in reg[r]:
            v = len(by_c[j["id"]])
            jit = (sum(map(ord, j["id"])) % 13 - 6) * 1.6   # stable jitter, independent of PYTHONHASHSEED
            o.append(f'<circle class="cdot" cx="{S(v):.1f}" cy="{cy + jit:.1f}" r="4" data-tip="{e(j["name"])}: {v}"><title>{e(j["name"])}: {v}</title></circle>')
        tip = f'{r}: median {s["med"]:g}, middle half {s["q1"]:g}–{s["q3"]:g}, range {s["min"]}–{s["max"]} ({s["n"]} countries)'
        o.append(f'<line class="med" x1="{S(s["med"]):.1f}" x2="{S(s["med"]):.1f}" y1="{cy - 13:.1f}" y2="{cy + 13:.1f}" data-tip="{e(tip)}"><title>{e(tip)}</title></line>')
    o.append('</svg>')
    legend = ('<p class="legend"><span><i class="sw cdot-sw"></i>One country</span><span><i class="sw iqr-sw"></i>Middle half of countries</span>'
              '<span><i class="sw med-sw"></i>Median</span></p>')
    rows = [[r, s["n"], f'{s["med"]:g}', f'{s["q1"]:g}', f'{s["q3"]:g}', s["min"], s["max"], s["zero"], s["top"]] for r, s in stats.items()]
    rows.append(["All countries", sum(s["n"] for s in stats.values()), "", "", "", "", "", sum(s["zero"] for s in stats.values()), f"Total instruments: {sum(len(v) for v in by_c.values())}"])
    part1 = (stats, "".join(o), ["Region", "Countries", "Median per country", "Lower quartile", "Upper quartile", "Minimum", "Maximum", "Countries with none", "Most instruments"], rows, legend)
    mix = {r: {"binding": 0, "soft": 0, "draft": 0} for r in REGIONS}
    for c, rows_c in by_c.items():
        for i in rows_c: mix[N["jur"][c].get("region")][kind(i)] += 1
    W2, rh, L2, R2 = 720, 34, 92, 46
    H2 = rh * len(REGIONS) + 8
    o = [f'<svg viewBox="0 0 {W2} {H2}" class="chart" role="img" aria-label="Share of each region\'s instruments that are binding or mandatory, non-binding and drafts ({e(dict(SCOPES)[scope].lower())})">']
    for n, r in enumerate(REGIONS):
        tot = sum(mix[r].values()) or 1; x = L2; y = 4 + n * rh; bh = 20
        o.append(f'<text class="cat" x="{L2 - 12}" y="{y + 15}" text-anchor="end">{e(r)}</text>')
        drawn = [(g, mix[r][g]) for g in GROUPS if mix[r][g]]
        for idx, (g, v) in enumerate(drawn):
            w = (W2 - L2 - R2) * v / tot; gap = 2 if idx else 0
            tip = f"{r}: {v} {KIND_LABEL[g].lower()} ({pct(v, tot)}% of {tot})"
            if idx == len(drawn) - 1:
                o.append(f'<path class="mark s-{KIND_CLASS[g]}" d="{round_end(x + gap, y, w - gap, bh, 4)}" data-tip="{e(tip)}"><title>{e(tip)}</title></path>')
            else:
                o.append(f'<rect class="mark s-{KIND_CLASS[g]}" x="{x + gap:.1f}" y="{y}" width="{max(.5, w - gap):.1f}" height="{bh}" data-tip="{e(tip)}"><title>{e(tip)}</title></rect>')
            if w > 34: o.append(f'<text class="inlab" x="{x + gap + 6:.1f}" y="{y + 14}">{pct(v, tot)}%</text>')
            x += w
        o.append(f'<text class="val" x="{W2 - R2 + 6}" y="{y + 15}">{sum(mix[r].values())}</text>')
    o.append(f'<line class="axis" x1="{L2}" x2="{L2}" y1="0" y2="{H2}"/></svg>')
    rows = [[r, mix[r]["binding"], mix[r]["soft"], mix[r]["draft"], sum(mix[r].values()), f'{pct(mix[r]["binding"], sum(mix[r].values()))}%'] for r in REGIONS]
    rows.append(["Total", *[sum(mix[r][g] for r in REGIONS) for g in ("binding", "soft", "draft")], sum(sum(m.values()) for m in mix.values()), ""])
    part2 = (mix, "".join(o), ["Region", "Binding or mandatory", "Non-binding", "Drafts", "Total", "Binding share"], rows, LEGEND)
    return part1, part2, reg


def fig_region(N):
    P = {k: region_parts(N, region_counts(N, k), k) for k, _ in SCOPES}
    reg = P["nat"][2]
    sn, sa = P["nat"][0][0], P["all"][0][0]
    hi = max(REGIONS, key=lambda r: sn[r]["med"]); lo = min(REGIONS, key=lambda r: sn[r]["med"])
    t_nat = _T("At national level the median country has {hm} recorded instruments in {hi} (the highest regional median) and {lm} in {lo} (the lowest). "
               "Ranges per country: {ranges}.", hm=f"{sn[hi]['med']:g}", hi=rn(hi), lm=f"{sn[lo]['med']:g}", lo=rn(lo),
               ranges=LS().join(f"{tr(r)} {sn[r]['min']}–{sn[r]['max']}" for r in REGIONS))
    nat_total = sum(len(v) for v in region_counts(N, "nat").values()); all_total = len(N["C"]); added = all_total - nat_total
    deep = sum(1 for i in N["C"] if i.get("government_level") != "national" and i["jurisdiction_id"] in DEEP_SUB)
    moved = max(abs(sa[r]["med"] - sn[r]["med"]) for r in REGIONS)
    t_all = (_T("State/provincial and local instruments add {added} to the {nat} national ones; {deep} of them ({p}%) come from the six countries with deeper "
                "subnational coverage (USA, CAN, AUS, BRA, IND, CHN). ", added=f"{added:,}", nat=f"{nat_total:,}", deep=f"{deep:,}", p=pct(deep, added))
             + (_T("No regional median changes.") if moved == 0 else _T("No regional median moves by more than {m}.", m=f"{moved:g}")))
    desc1 = {"nat": "Instruments per country issued at national level, on a square-root scale. Medians and ranges, not totals.",
             "all": "Instruments per country including state/provincial and local instruments, on a square-root scale. Medians and ranges, not totals."}
    f1 = afig_variants("fig-region", "Instruments per country, by region", desc1,
                       [(k, t_nat if k == "nat" else t_all, P[k][0][1], P[k][0][2], P[k][0][3], P[k][0][4]) for k, _ in SCOPES], REGION_NOTE)
    mn, ma = P["nat"][1][0], P["all"][1][0]
    bs = lambda m, r: pct(m[r]["binding"], sum(m[r].values()))
    hv, lv = max(bs(mn, r) for r in REGIONS), min(bs(mn, r) for r in REGIONS)
    join = lambda xs: xs[0] if len(xs) == 1 else LS().join(xs[:-1]) + (" و" if i18n.LANG == "ar" else " and ") + xs[-1]
    m_nat = _T("At national level, binding or mandatory instruments are {hv}% of recorded instruments in {a} and {lv}% in {b}.",
               hv=hv, a=join([rn(r) for r in REGIONS if bs(mn, r) == hv]), lv=lv, b=join([rn(r) for r in REGIONS if bs(mn, r) == lv]))
    natc = region_counts(N, "nat")
    for r in REGIONS:   # name a single country when it supplies most of a region's national instruments
        c = max(reg[r], key=lambda j: len(natc[j["id"]])); n = len(natc[c["id"]]); t = sum(mn[r].values())
        if t and n / t >= .4:
            nm = tr(c['name']) if i18n.LANG == "ar" else ('The ' if c['name'].startswith('United') else '') + c['name']
            m_nat += " " + _T("{name} supplies {n} of the {t} national instruments in {r} ({p}%).", name=nm, n=n, t=t, r=rn(r), p=pct(n, t))
    big = max(REGIONS, key=lambda r: abs(bs(ma, r) - bs(mn, r)))
    m_all = _T("Adding state/provincial and local instruments changes the binding-or-mandatory share most in {r}, from {a}% to {b}%; "
               "in the other regions it moves by at most {m} points.", r=rn(big), a=bs(mn, big), b=bs(ma, big), m=max(abs(bs(ma, r) - bs(mn, r)) for r in REGIONS if r != big))
    desc2 = {"nat": "Share of each region's national-level instruments in each group; the number at the end is the region's total.",
             "all": "Share of each region's instruments, including state/provincial and local, in each group; the number at the end is the region's total."}
    f2 = afig_variants("fig-mix", "Group mix, by region", desc2,
                       [(k, m_nat if k == "nat" else m_all, P[k][1][1], P[k][1][2], P[k][1][3], P[k][1][4]) for k, _ in SCOPES], REGION_NOTE)
    return f1, f2, {"mix_nat": sum(sum(m.values()) for m in mn.values()), "mix_all": sum(sum(m.values()) for m in ma.values()), "nat_total": nat_total,
                    "box_nat": sum(len(v) for v in region_counts(N, "nat").values()), "box_all": sum(len(v) for v in region_counts(N, "all").values())}


# ---------------------------------------------------------------- d. category heatmap
def fig_heat(N, cats):
    reg = {r: [j["id"] for j in N["countries"] if j.get("region") == r] for r in REGIONS}
    cols = REGIONS + ["All countries"]
    reg["All countries"] = [j["id"] for j in N["countries"]]
    has = {c: {k for i in N["by_c"][c] for k in i.get("categories", [])} for c in N["cids"]}
    share = {(k, r): (sum(1 for c in reg[r] if k in has[c]), len(reg[r])) for k in cats for r in cols}
    W, L, T, cw, chh = 720, 196, 34, 0, 24
    cw = (W - L - 12) / len(cols)
    H = T + chh * len(cats) + 6
    o = [f'<svg viewBox="0 0 {W} {H}" class="chart heat" role="img" aria-label="Share of countries in each region with at least one instrument in each category">']
    for n, r in enumerate(cols):
        x = L + n * cw + (8 if r == "All countries" else 0)
        o.append(f'<text class="cat" x="{x + cw / 2:.1f}" y="{T - 12}" text-anchor="middle">{e(r if r != "All countries" else "All")}</text>')
    for m, (k, name) in enumerate(cats.items()):
        y = T + m * chh
        o.append(f'<text class="cat" x="{L - 10}" y="{y + 16}" text-anchor="end">{e(name)}</text>')
        for n, r in enumerate(cols):
            hit, tot = share[(k, r)]; p = hit / tot if tot else 0
            step = 0 if hit == 0 else 1 + min(12, int(p * 12.999))
            x = L + n * cw + (8 if r == "All countries" else 0)
            tip = f"{name} · {r}: {hit} of {tot} countries ({pct(hit, tot)}%)"
            o.append(f'<rect class="hc h{step}" x="{x + 1:.1f}" y="{y + 1}" width="{cw - 2:.1f}" height="{chh - 2}" rx="3" data-tip="{e(tip)}"><title>{e(tip)}</title></rect>'
                     f'<text class="hv {"hv-d" if step >= 8 else ""}" x="{x + cw / 2:.1f}" y="{y + 16}" text-anchor="middle">{pct(hit, tot)}%</text>')
    o.append('</svg>')
    legend = ('<p class="legend heat-legend"><span>0%</span>' + "".join(f'<i class="hk h{s}"></i>' for s in range(0, 14)) + '<span>100% of countries in the region</span></p>')
    rows = [[name] + [f"{share[(k, r)][0]} of {share[(k, r)][1]}" for r in cols] for k, name in cats.items()]
    allc = {k: share[(k, "All countries")][0] for k in cats}
    top3 = sorted(cats, key=lambda k: -allc[k])[:3]; low = min(cats, key=lambda k: allc[k])
    take = _T("The most widely covered categories are {top} ({pcts} of countries); the least is {low} ({p}%).",
              top=LS().join(tr(cats[k]) for k in top3), pcts=LS().join(str(pct(allc[k], 195)) + '%' for k in top3), low=tr(cats[low]), p=pct(allc[low], 195))
    desc = "Share of countries in each region with at least one national, state/provincial or local instrument tagged with the category. One instrument can carry several categories."
    return afig("fig-heat", "Category coverage by region", take, desc, "".join(o), ["Category"] + cols, rows, "", legend)


# ---------------------------------------------------------------- e. treaties
def fig_treaty(N, ctx):
    cids = N["cids"]; jur = N["jur"]
    eu = set(ctx["members"].get("EU", ()))
    st = {}
    for c in sorted(cids, key=lambda c: jur[c]["name"]):
        s = ctx["cets"].get(c)
        st[c] = "Ratified" if s == "ratified" else "Signed" if s == "signed" else "EU signatory only" if c in eu else "None"
    order = ["Ratified", "Signed", "EU signatory only", "None"]
    cnt = {k: sum(1 for v in st.values() if v == k) for k in order}
    c108 = len(ctx["c108"] & cids); c108p = len(ctx["c108_pending"] & cids)
    bars = [("CETS 225: ratified", cnt["Ratified"], "t1"), ("CETS 225: signed, not ratified", cnt["Signed"], "t2"),
            ("CETS 225: EU signatory only", cnt["EU signatory only"], "t3"), ("CETS 225: none", cnt["None"], "t4"),
            ("Convention 108: parties verified from national ratification acts in this dataset", c108, "t1"), ("Convention 108: ratification act pending verification", c108p, "t3")]
    W, rh, L, Rr = 720, 30, 400, 40
    H = rh * len(bars) + 22
    o = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="CETS 225 status of the 195 countries, and Convention 108 parties">']
    for n, (lab, v, cls) in enumerate(bars):
        y = 4 + n * rh + (14 if n >= 4 else 0); w = max(2, (W - L - Rr) * v / 195)
        o.append(f'<text class="cat" x="{L - 12}" y="{y + 14}" text-anchor="end">{e(lab)}</text>'
                 f'<path class="mark tb {cls}" d="{round_end(L, y, w, 18, 4)}" data-tip="{e(lab)}: {v} of 195"><title>{e(lab)}: {v}</title></path>'
                 f'<text class="val" x="{L + w + 6:.1f}" y="{y + 14}">{v}</text>')
    o.append(f'<line class="axis" x1="{L}" x2="{L}" y1="0" y2="{H}"/></svg>')
    signers = [(jur[c]["name"], st[c]) for c in st if st[c] in ("Ratified", "Signed")]
    small = ('<table class="data-table plain-table small-table"><thead><tr><th scope="col">Signed or ratified CETS 225 in its own name</th><th scope="col">Status</th></tr></thead><tbody>'
             + "".join(f'<tr><th scope="row"><a href="../country/{c}/">{e(jur[c]["name"])}</a></th><td>{e(st[c])}</td></tr>' for c in st if st[c] in ("Ratified", "Signed"))
             + '</tbody></table>')
    rows = [[jur[c]["name"], c, st[c], "Party" if c in ctx["c108"] else "Pending verification" if c in ctx["c108_pending"] else "Not recorded"] for c in st]
    take = _T(("{r} country has" if cnt['Ratified'] == 1 else "{r} countries have") + " ratified CETS 225 and {s} more have signed it in their own name; {eu} EU members are covered "
              "only by the EU's signature. {c} Convention 108 parties are verified from national ratification acts in this dataset, with {p} more pending verification.",
              r=cnt['Ratified'], s=cnt['Signed'], eu=cnt['EU signatory only'], c=c108, p=c108p)
    desc = ("Out of 195 countries. CETS 225 status from the Council of Europe record in this dataset; 'ratified' needs the country's own ratification act. "
            "Convention 108 counts only parties whose ratification or accession act was found, so it is lower than the treaty office's own list.")
    c108_link = ('<p class="fig-note">The official list of Convention 108 parties is longer; see the Council of Europe Treaty Office '
                 '<a href="https://www.coe.int/en/web/conventions/full-list?module=signatures-by-treaty&amp;treatynum=108" rel="noopener">chart of signatures and ratifications of Treaty 108</a>.</p>')
    return afig("fig-treaty", "Treaty status", take, desc, "".join(o) + c108_link + small, ["Country", "ISO3", "CETS 225", "Convention 108"], rows, "Table and CSV list all 195 countries"), cnt


# ---------------------------------------------------------------- f. issuer types
def fig_issuer(N):
    cnt = {k: 0 for k in ISSUER_ORDER}; unc = 0; unc_types = {}
    for i in N["C"]:
        t = i.get("authority_type") or (N["orgs"].get(i.get("organization_id")) or {}).get("authority_type")
        g = ISSUER.get(t)
        if g: cnt[g] += 1
        else:
            unc += 1; unc_types[t or "missing"] = unc_types.get(t or "missing", 0) + 1
    tot = len(N["C"])
    bars = [(k, cnt[k]) for k in ISSUER_ORDER] + [("Unclassified", unc)]
    W, rh, L, Rr = 720, 30, 220, 80
    H = rh * len(bars) + 8
    mx = max(v for _, v in bars)
    o = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Country instruments by issuer type">']
    for n, (k, v) in enumerate(bars):
        y = 4 + n * rh; w = max(2, (W - L - Rr) * v / mx)
        o.append(f'<text class="cat" x="{L - 12}" y="{y + 14}" text-anchor="end">{e(k)}</text>'
                 f'<path class="mark {"tb t4" if k == "Unclassified" else "tb t1"}" d="{round_end(L, y, w, 18, 4)}" data-tip="{e(k)}: {v} ({pct(v, tot)}%)"><title>{e(k)}: {v}</title></path>'
                 f'<text class="val" x="{L + w + 6:.1f}" y="{y + 14}">{v} · {pct(v, tot)}%</text>')
    o.append(f'<line class="axis" x1="{L}" x2="{L}" y1="0" y2="{H}"/></svg>')
    rows = [[k, v, f"{pct(v, tot)}%"] for k, v in bars] + [["Total", tot, "100%"]]
    big = max(ISSUER_ORDER, key=lambda k: cnt[k])
    take = _T("{big} issued {pb}% of country instruments, legislatures {pl}% and regulators {pr}%. "
              "{unc} instruments ({pu}%) have no issuer type recorded and are left unclassified.",
              big=tr(big), pb=pct(cnt[big], tot), pl=pct(cnt['Legislatures'], tot), pr=pct(cnt['Regulators'], tot), unc=unc, pu=pct(unc, tot))
    desc = ("National, state/provincial and local instruments by the type of body that issued them: the record's authority type, else that of its issuing organisation. "
            "Governments and ministries include executive agencies, heads of state and local governments; regulators include data-protection authorities and central banks; "
            "other covers standards bodies, advisory and independent bodies, auditors and prosecutors.")
    return afig("fig-issuer", "Issuer types", take, desc, "".join(o), ["Issuer type", "Instruments", "Share"], rows,
                "Unclassified: " + ", ".join(f"{k} {v}" for k, v in sorted(unc_types.items(), key=lambda kv: -kv[1]))), {"issuer_total": sum(cnt.values()) + unc, "unclassified": unc}


# ---------------------------------------------------------------- pages
def head1(title, desc, canon):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="color-scheme" content="light dark"><link rel="icon" href="data:,"><title>{e(title)}</title><meta name="description" content="{e(desc)}">'
            f'<link rel="canonical" href="{e(canon)}"><meta property="og:type" content="website"><meta property="og:site_name" content="AI Governance Radar">'
            f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{e(canon)}">'
            f'<link rel="stylesheet" href="../assets/country.css"><link rel="stylesheet" href="../assets/analysis.css"></head>')


def nav(active):
    links = [("analysis", "Analysis"), ("timeline", "Timeline"), ("suggest", "Suggest an update")]
    return ('<header class="topnav"><a class="back" id="backToMap" href="../">← World map</a><span class="site">AI Governance Radar</span>'
            '<nav class="toc sitenav" aria-label="Site">' + "".join(f'<a href="../{k}/"{" aria-current=page" if k == active else ""}>{v}</a>' for k, v in links)
            + '<a href="../?about=method">Methodology</a></nav></header>')


def foot(D):
    return (f'<footer class="pagefoot"><p>AI Governance Radar · official government sources only · data as of {e(fmt_date(D["meta"].get("build_date")))}</p>'
            '<p><a href="../">World map</a> · <a href="../analysis/">Analysis</a> · <a href="../timeline/">Timeline</a> · <a href="../suggest/">Suggest an update</a> · <a href="../?about=method">Methodology</a></p></footer>')


DISCOVERY = "Recent years are better represented: newer documents are more often online, so growth since 2023 is partly a discovery effect."
CAUTION = ("Counts reflect officially published documents found by this radar. "
           "They do not measure the quality or strength of a country's AI governance.")


def analysis_page(D, recs, ctx):
    N = compute(D, recs, ctx); today = ctx["today"]
    fa, ka = fig_years(N, today)
    fb, kb = fig_adoption(N, today)
    fc1, fc2, kc = fig_region(N)
    fd = fig_heat(N, D["categories"])
    fe, ke = fig_treaty(N, ctx)
    ff, kf = fig_issuer(N)
    n_all = len(D["instruments"]); nC, nR = len(N["C"]), len(N["R"])
    lvl = {k: sum(1 for i in N["C"] if i.get("government_level") == k) for k in ("national", "subnational", "local")}
    grp = {g: sum(1 for i in N["C"] if kind(i) == g) for g in GROUPS}
    zero = sum(1 for c in N["cids"] if not N["by_c"][c])
    stats = [("Countries", len(N["countries"])), ("Instruments", f"{n_all:,}"), ("Leads", f"{N['leads']:,}"), ("Countries with none found", zero)]
    recon = [
        ("Instruments in the full export (CSV / JSON)", n_all),
        ("· national", lvl["national"]), ("· state / provincial", lvl["subnational"]), ("· local", lvl["local"]), ("· regional bodies", nR),
        ("Chart a: dated country instruments + undated country instruments", f'{ka["years_total"]} + {ka["undated_c"]} = {ka["years_total"] + ka["undated_c"]}'),
        ("Chart a: dated regional instruments + undated regional instruments", f'{ka["regional_dated"]} + {ka["undated_r"]} = {ka["regional_dated"] + ka["undated_r"]}'),
        ("Chart c, national-level only (default): per-country counts and group mix", f'{kc["box_nat"]} and {kc["mix_nat"]} (= national {lvl["national"]})'),
        ("Chart c, including state/provincial and local: per-country counts and group mix", f'{kc["box_all"]} and {kc["mix_all"]} (= country instruments {nC})'),
        ("Chart f (issuer types): country instruments", f'{kf["issuer_total"]}'),
        ("Group totals for country instruments (binding or mandatory / non-binding / drafts)", f'{grp["binding"]} / {grp["soft"]} / {grp["draft"]}'),
    ]
    assert ka["years_total"] + ka["undated_c"] == nC and ka["regional_dated"] + ka["undated_r"] == nR and kf["issuer_total"] == nC
    assert kc["box_nat"] == kc["mix_nat"] == lvl["national"] and kc["box_all"] == kc["mix_all"] == nC
    assert lvl["national"] + lvl["subnational"] + lvl["local"] == nC and nC + nR == n_all
    canon = f"{SITE_URL}analysis/"
    title = "Global analysis | AI Governance Radar"
    desc = _T("Charts across all 195 countries: AI governance instruments per year, adoption, regions, categories, treaties and issuers. Data as of {date}.", date=fmt_date(today))
    H = [head1(title, desc, canon), '<body class="cp an">', nav("analysis"), '<main class="page">']
    H.append(f'<header class="hero" id="top"><p class="eyebrow">{e(_T("Global analysis · data snapshot {date}", date=fmt_date(today)))}</p><h1>AI governance in 195 countries</h1>'
             + '<dl class="stats stats4">' + "".join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in stats) + '</dl>'
             + f'<p class="stats-note">{e(tr(COUNT_NOTE))} ' + e(_T("Instruments: {c} national, state/provincial and local, plus {r} of regional bodies. ", c=f"{nC:,}", r=nR))
             + e(_T("Leads: documents found but not yet verified as in-scope instruments; they are not counted in any chart.")) + '</p>'
             + f'<aside class="caution" role="note"><strong>Read with care.</strong> {e(CAUTION)} <a href="../?about=method">Methodology</a></aside>'
             + f'<p class="discovery">{e(DISCOVERY)}</p></header>')
    H.append('<nav class="chart-index" aria-label="Charts"><a href="#fig-years">Per year</a><a href="#fig-adoption">Adoption</a><a href="#fig-region">Regions</a>'
             '<a href="#fig-heat">Categories</a><a href="#fig-treaty">Treaties</a><a href="#fig-issuer">Issuers</a><a href="#recon">How the numbers add up</a></nav>')
    H.append('<div class="an-grid">' + fa + fb + fc1 + fc2 + fd + fe + ff + '</div>')
    H.append('<section id="recon" class="block"><h2>How the numbers add up</h2><p class="section-lede">Every chart is built from the same snapshot as the export on the map page. '
             'Charts use instruments issued in each country; the region charts (c) default to national-level instruments, with a switch to add state/provincial and local ones, '
             'and the other charts include all three levels. Regional-body instruments are shown separately in chart a and left out of the others, '
             'so a regional instrument is never counted once per member state. Totals below are checked at every build for both settings of the switch.</p>'
             + table(["Check", "Count"], recon) + '</section>')
    H.append('</main>' + foot(D) + '<script src="../assets/analysis.js" defer></script></body></html>')
    return "".join(H)


# ---------------------------------------------------------------- timeline
def timeline_data(D, ctx):
    jur = ctx["jur"]
    st_keys = sorted({i.get("legal_status") or "" for i in D["instruments"]}, key=lambda s: (s == "", s))
    cat_keys = list(D["categories"])
    lv = [k for k, _ in LEVELS]
    J = {}
    for j in D["jurisdictions"]:
        J[j["id"]] = [j["name"], j.get("region") or "", 1 if j["type"] == "country" else 0]
    app = {}
    for a in D["regional_applicability"]: app.setdefault(a["instrument_id"], []).append(a["jurisdiction_id"])
    rows = []
    for i in D["instruments"]:
        d = i.get("publication_date") or ""
        iss = (i.get("issuing_authority") or i.get("publisher_name") or "")
        if len(iss) > 140: iss = iss[:139].rsplit(" ", 1)[0] + "…"
        rows.append([i["id"], i["jurisdiction_id"], d, ["binding", "soft", "draft"].index(kind(i)),
                     i.get("english_title") or i.get("official_title") or "", iss, st_keys.index(i.get("legal_status") or ""),
                     [cat_keys.index(c) for c in i.get("categories", []) if c in cat_keys], lv.index(i.get("government_level")) if i.get("government_level") in lv else 0,
                     i.get("source_url") or i.get("official_webpage_url") or "", app.get(i["id"], [])])
    bodies = {b: [jur[b]["name"] if b in jur else b, sorted(ctx["members"].get(b, ()))] for b in BODY_ORDER if b in jur}
    return {"asof": ctx["today"], "fields": ["id", "jurisdiction", "date", "group", "title", "issuer", "status", "categories", "level", "source", "applies_to"],
            "groups": [KIND_LABEL[g] for g in ("binding", "soft", "draft")], "statuses": [[k, STATUS_LABEL.get(k) or (k.replace("_", " ").capitalize() if k else "Not recorded")] for k in st_keys],
            "categories": [[k, v] for k, v in D["categories"].items()], "levels": [[k, v] for k, v in LEVELS], "regions": REGIONS,
            "jurisdictions": J, "bodies": bodies, "items": rows}


def timeline_page(D, ctx):
    T = timeline_data(D, ctx)
    canon = f"{SITE_URL}timeline/"
    title = "Publication timeline | AI Governance Radar"
    desc = _T("Every dated AI-governance instrument recorded by the radar on one time axis, filterable by country, region, body, category, status and level. Data as of {date}.", date=fmt_date(ctx['today']))
    sel = lambda name, label, opts: (f'<label>{e(label)}<select name="{name}" data-f="{name}"><option value="">All</option>' + opts + '</select></label>')
    countries = sorted(((k, v[0]) for k, v in T["jurisdictions"].items() if v[2]), key=lambda kv: kv[1])
    st_opts = ('<optgroup label="Group">' + "".join(f'<option value="{g}">{e(KIND_LABEL[g])}</option>' for g in ("binding", "soft", "draft")) + '</optgroup>'
               '<optgroup label="Legal status">' + "".join(f'<option value="{k}">{e(v)}</option>' for k, v in T["statuses"] if k) + '</optgroup>')
    filters = ('<form class="tl-filters" id="tlFilters" role="search" aria-label="Filter the timeline" onsubmit="return false">'
               + sel("country", "Country", "".join(f'<option value="{k}">{e(v)}</option>' for k, v in countries))
               + sel("region", "Region", "".join(f'<option>{r}</option>' for r in REGIONS))
               + sel("body", "International body (members)", "".join(f'<option value="{k}">{e(v[0])}</option>' for k, v in T["bodies"].items()))
               + sel("cat", "Category", "".join(f'<option value="{k}">{e(v)}</option>' for k, v in T["categories"]))
               + sel("status", "Legal status", st_opts)
               + sel("level", "Government level", "".join(f'<option value="{k}">{e(v)}</option>' for k, v in LEVELS))
               + '<label>From<select name="from" data-f="from"></select></label><label>To<select name="to" data-f="to"></select></label>'
               + '<button type="button" class="btn" id="tlReset">Clear filters</button></form>')
    H = [head1(title, desc, canon), '<body class="cp tl">', nav("timeline"), '<main class="page tl-page">']
    H.append(f'<header class="hero tl-hero"><p class="eyebrow">{e(_T("Publication timeline · data snapshot {date}", date=fmt_date(ctx["today"])))}</p><h1>Publication timeline</h1>'
             '<p class="stats-note">Every dated instrument (national, state/provincial, local and regional) placed at its publication date, newest at the right. '
             'Dates given only as a year or a month are placed mid-year or mid-month. ' + e(CAUTION) + ' <a href="../?about=method">Methodology</a></p>'
             f'<p class="discovery">{e(DISCOVERY)}</p></header>')
    H.append(filters)
    H.append('<p class="tl-status" id="tlStatus" aria-live="polite"></p>' + LEGEND.replace('class="legend"', 'class="legend tl-legend"'))
    H.append('<div class="tl-chart" id="tlChart"><svg id="tlSvg" class="chart" role="img" aria-label="Instruments by publication date"></svg>'
             '<div class="tl-brush-wrap"><p class="tl-brush-h">Drag across the years below to zoom; click a year to show only that year.</p><svg id="tlBrush" class="chart" aria-label="Year range selector" role="slider"></svg></div>'
             '<div class="tl-card" id="tlCard" hidden role="dialog" aria-label="Instrument details"></div></div>')
    H.append('<div class="tl-list" id="tlList"></div>')
    H.append('<noscript><p>The timeline needs JavaScript. Every instrument is also listed on its country page and in the export on the map page.</p></noscript>')
    H.append('</main>' + foot(D) + '<script id="tl-data" type="application/json">' + json.dumps(T, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
             + '</script><script src="../assets/timeline.js" defer></script></body></html>')
    return "".join(H)


# ---------------------------------------------------------------- update requests
REPO_URL = "https://github.com/AlsallumUW/ai-governance-radar"
SUGGEST_NOTE = "Suggestions are checked against official sources before anything is added. Submitting requires a free GitHub account."


def suggest_page(D, ctx):
    """A static form that opens a prefilled GitHub issue (template update-request.yml). No server, no e-mail."""
    canon = f"{SITE_URL}suggest/"
    title = "Suggest an update | AI Governance Radar"
    desc = "Suggest a new AI-governance document, a correction, a status change or a broken link. Suggestions are checked against official sources."
    juris = sorted(D["jurisdictions"], key=lambda j: (j["type"] != "country", j["name"]))
    opts = ('<optgroup label="Countries">' + "".join(f'<option value="{e(j["id"])}">{e(j["name"])}</option>' for j in juris if j["type"] == "country") + '</optgroup>'
            '<optgroup label="International bodies">' + "".join(f'<option value="{e(j["id"])}">{e(j["name"])}</option>' for j in juris if j["type"] != "country") + '</optgroup>')
    kinds = ["New instrument", "Correction", "Status change", "Broken link"]
    H = [head1(title, desc, canon), '<body class="cp sg">', nav("suggest"), '<main class="page">']
    H.append('<header class="hero sg-hero"><p class="eyebrow">Update requests</p><h1>Suggest an update</h1>'
             '<p class="stats-note">Found a new official AI-governance document, an error, a change of status or a broken link? Send it here. '
             'Please give the official source: the document itself or the issuing body\'s own page. News articles, aggregators and social media cannot be used.</p></header>')
    H.append(f'<form class="sg-form" id="sgForm" data-repo="{e(REPO_URL)}" novalidate>'
             f'<label>Country or body<select name="country" id="sgCountry" required><option value="">Choose…</option>{opts}</select></label>'
             '<fieldset><legend>What is new or wrong?</legend>' + "".join(
                 f'<label class="radio"><input type="radio" name="change_type" value="{e(k)}"{" checked" if n == 0 else ""}> {e(k)}</label>' for n, k in enumerate(kinds)) + '</fieldset>'
             '<label>Official source URL <span class="req">(required)</span><input type="url" name="source_url" id="sgUrl" required placeholder="https://" inputmode="url" autocomplete="off"></label>'
             '<label>Notes<textarea name="notes" rows="5" placeholder="What should change, and where on the site (instrument title or page)."></textarea></label>'
             '<p class="sg-error" id="sgError" role="alert" hidden></p>'
             '<p class="sg-actions"><button type="submit" class="btn btn-primary">Open a GitHub issue</button></p>'
             f'<p class="sg-note">{e(SUGGEST_NOTE)}</p></form>')
    H.append('</main>' + foot(D) + '<script src="../assets/suggest.js" defer></script></body></html>')
    return "".join(H)


def write(D, recs, out, ctx):
    for p, html_ in (("analysis", analysis_page(D, recs, ctx)), ("timeline", timeline_page(D, ctx)), ("suggest", suggest_page(D, ctx))):
        (out / p).mkdir(parents=True, exist_ok=True)
        (out / p / "index.html").write_text(html_, encoding="utf-8")


if __name__ == "__main__":
    # python3 scripts/analysis.py --queue : refresh research/queue.json -> amendment_dates from the current data
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
    from common import ROOT
    import build
    if "--queue" in sys.argv:
        D = build.assemble()
        cids = {j["id"] for j in D["jurisdictions"] if j["type"] == "country"}
        qp = ROOT / "research/queue.json"
        q = json.loads(qp.read_text(encoding="utf-8"))
        q["amendment_dates"] = queue_amendment_dates(D, cids)
        qp.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"amendment_dates: {len(q['amendment_dates'])} records")
