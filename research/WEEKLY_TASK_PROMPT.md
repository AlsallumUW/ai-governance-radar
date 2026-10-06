# Prompt for the weekly Claude scheduled task

You are updating the AI Governance Radar repository: github.com/<OWNER>/<REPO>.

1. Clone the repository and read `research/WEEKLY.md` and `research/PROTOCOL.md` in full. Follow them exactly.
2. Deep-review the next `batch_size` countries from `research/queue.json` that are not in `done`.
3. Sweep the countries already in `done` for new government actions since their last review.
4. Run `python3 scripts/validate.py` (0 errors required), then `python3 scripts/log_changes.py`, then `python3 scripts/build.py`.
5. Push a branch `update/<YYYY-MM-DD>` and open one pull request with the changelog body described in WEEKLY.md. Do not merge it.

Constraints:
- Official sources only.
- Never infer legal effect.
- If an official site blocks automated access, verify through another official channel (national news agency, gazette, consultation portal). Otherwise leave the field null and list it under "Could not verify".
- Finish with a short summary: countries done, the number of government actions found, the number of items needing review, and the PR link.
