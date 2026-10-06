# AI Governance Radar

An interactive map of what each country's government has **officially published** on AI governance: laws, strategies, frameworks, guidance and standards. It covers 193 UN member states, the State of Palestine and the Holy See, plus regional layers (EU, GCC, AU, ASEAN, Council of Europe, UNESCO).

Every record links to the original government source, and every change is logged with a date. Changes are either **government actions** (published, revised, adopted, applied, superseded, repealed) or **radar maintenance** (added, corrected, link changes).

## How it works

```
data/countries/XXX.json   one file per country: narrative, instruments, sources, coverage, change log
data/regional/XXX.json    EU, GCC, AU, ASEAN, COE, UNESCO
data/meta.json            categories and methodology
research/PROTOCOL.md      the record standard a country must meet to count as deep-reviewed
research/WEEKLY.md        the weekly update routine
research/queue.json       review order (GCC → MENA → G20 → EU → rest of world)
scripts/                  validate · log_changes · build · check_links · next_batch
site/                     page template, change-log UI, map assets
```

**Weekly cycle**

1. A Claude scheduled task deep-reviews the next batch of countries and sweeps already-reviewed ones for news.
2. It opens a pull request with a readable changelog.
3. GitHub Actions validates the data and builds the site on every pull request.
4. You review and merge. The site redeploys to GitHub Pages automatically.
5. A separate GitHub Action checks every source link on Mondays and opens its own pull request.

## Local use

```bash
python3 scripts/validate.py      # check data against the standard
python3 scripts/log_changes.py   # log changes since origin/main
python3 scripts/next_batch.py    # countries for the next deep-review run (--plan for all)
python3 scripts/build.py         # build dist/index.html
```

No dependencies beyond Python 3.10+.
