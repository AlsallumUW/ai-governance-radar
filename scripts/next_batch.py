#!/usr/bin/env python3
"""Print the countries for the next deep-review run, from research/queue.json.

    python3 scripts/next_batch.py          one line of country codes, e.g. "KWT OMN EGY JOR MAR TUN"
    python3 scripts/next_batch.py --plan   every remaining run, in order (for planning)

Rule (PROTOCOL §6): a tier A country is a run on its own. Otherwise the run takes tier B and C
countries in wave order until run_budget points are used (B=1, C=0.5); A countries are skipped
over (they get their own runs) so B/C batches stay full.
"""
import sys
from common import ROOT, load

QUEUE = ROOT / "research" / "queue.json"


def tier_of(q):
    return {c: t for t, cs in q["tiers"].items() for c in cs}


def runs(q):
    tier, cost, budget = tier_of(q), q["tier_cost"], q["run_budget"]
    todo = [c for w in q["waves"] for c in w["countries"] if c not in q.get("done", {})]
    out, cur, used = [], [], 0.0
    for c in todo:
        t = tier[c]
        if t == "A":
            out.append([c]); continue  # its own run; the open B/C batch carries on past it
        if cur and used + cost[t] > budget:
            out.append(cur); cur, used = [], 0.0
        cur.append(c); used += cost[t]
    if cur: out.append(cur)
    return out


def check_queue(q, countries):
    """Errors if a country is missing from, or duplicated across, the waves or the tiers."""
    errs = []
    for name, lists in (("waves", [w["countries"] for w in q["waves"]]), ("tiers", list(q["tiers"].values()))):
        seen = [c for l in lists for c in l]
        dup = sorted({c for c in seen if seen.count(c) > 1})
        missing = sorted(set(countries) - set(seen))
        extra = sorted(set(seen) - set(countries))
        if dup: errs.append(f"queue.json {name}: listed more than once: {dup}")
        if missing: errs.append(f"queue.json {name}: missing: {missing}")
        if extra: errs.append(f"queue.json {name}: unknown codes: {extra}")
    return errs


if __name__ == "__main__":
    q = load(QUEUE)
    rs = runs(q)
    if "--plan" in sys.argv:
        tier = tier_of(q)
        for i, r in enumerate(rs, 1):
            print(f"{i:3}. " + " ".join(f"{c}({tier[c]})" for c in r))
        print(f"\n{len(rs)} runs remaining, {sum(map(len, rs))} countries")
    else:
        print(" ".join(rs[0]) if rs else "")
