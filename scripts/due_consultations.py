"""Consultations whose closing date has passed: lifecycle "consultation" -> "consultation_closed".

A record in consultation may carry `consultation_closes` (ISO date, the last day for comments as printed on the official
page). Every daily run calls this script for all jurisdictions, not only the day's group, so a consultation is shown as
closed the day after it closes. The record's text is left as it is; the "Consultation closed" label comes from the lifecycle.

    python3 scripts/due_consultations.py            list the records that are due
    python3 scripts/due_consultations.py --apply    flip them (and set last_changed to today)
"""
import datetime as dt, json, sys
from common import jurisdiction_files, load


def due(today):
    for p in jurisdiction_files():
        rec = load(p)
        for i in rec.get("instruments", []):
            c = i.get("consultation_closes")
            if i.get("lifecycle") == "consultation" and c and c < today:
                yield p, rec, i


def main():
    today = dt.date.today().isoformat()
    apply = "--apply" in sys.argv
    files = {}
    for p, rec, i in due(today):
        print(f"{rec['jurisdiction']['id']}  {i['id']}  closed {i['consultation_closes']}  {i.get('english_title') or i.get('official_title')}")
        if apply:
            i["lifecycle"] = "consultation_closed"; i["last_changed"] = today
            files[p] = rec
    for p, rec in files.items():
        raw = open(p, encoding="utf-8").read()
        ind = 2 if '\n  "' in raw[:200] else 1
        open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(rec, ensure_ascii=False, indent=ind) + "\n")
    if apply: print(f"{sum(1 for _ in files)} file(s) updated")


if __name__ == "__main__":
    main()
