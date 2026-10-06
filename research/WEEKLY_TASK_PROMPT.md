# Prompt for the weekly Claude scheduled task

You are updating the AI Governance Radar repository: github.com/AlsallumUW/ai-governance-radar.

1. Clone the repository and read `research/WEEKLY.md` and `research/PROTOCOL.md` in full. Follow them exactly.
2. Run `python3 scripts/next_batch.py` and deep-review the countries it prints (PROTOCOL §6 explains tiers and run size; research countries in parallel sub-agents when there are several).
3. Sweep all 195 countries and the regional bodies for new government actions (WEEKLY.md step 3: one sub-agent per wave, in parallel).
4. Run `python3 scripts/validate.py` (0 errors required), then `python3 scripts/log_changes.py`, then `python3 scripts/build.py`.
5. Push a branch `update/<YYYY-MM-DD>` and open one pull request with the changelog body described in WEEKLY.md. Do not merge it.

Constraints:
- Official sources only.
- Never infer legal effect.
- If an official site blocks automated access, verify through another official document channel (official gazette, consultation portal, the issuing body's other official pages). News agencies, including state agencies such as SPA and WAM, are never sources. Otherwise leave the field null and list it under "Could not verify".
- Finish with a short summary: countries done, the number of government actions found, the number of items needing review, and the PR link.
