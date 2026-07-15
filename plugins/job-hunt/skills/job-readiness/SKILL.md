---
name: job-readiness
description: Score an application pack's readiness to send using a deterministic 0–100 readiness score (ATS match + fit + completeness + advisory red flags) with a hard fabrication gate. Read-only and offline; the Python computes the score, the skill explains it and drives the honest re-tailor loop. Suggestions surface skills the user genuinely has but omitted, route real gaps to /job-upskill, and NEVER fabricate. Use before /job-apply to check and strengthen an application.
---

# Job Readiness

Tell the user whether a tailored application pack is ready to send — and exactly how
to strengthen it honestly — BEFORE `/job-apply`. The scoring is **deterministic
Python** (`scoring/readiness.py`); this skill runs it, explains it, and drives the
re-tailor loop. The score is a diagnostic and the fabrication gate is absolute — this
skill **never** invents skills or experience.

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- Run the CLI as `python -m scoring.scoring_cli readiness` from that scripts dir,
  using the venv Python from the repo README (stdlib only). Do not hardcode paths.

## Steps

1. **Identify the pack.** Take the pack slug or directory from the user
   (e.g. `northwind-bv-backend-engineer`). The JD is read from the pack's stored
   `jd_queue/<slug>.txt` automatically; if it isn't stored, ask the user to paste it
   and pass `--jd-text "<the JD>"` (or `--jd-file <path>`).

2. **Score.** Run
   `python -m scoring.scoring_cli readiness --pack "<slug>"` (add `--jd-text`/`--jd-file`
   only if the JD isn't stored). It prints one JSON object:
   `{"ok": true, "readiness_score": N, "blocking": bool, "factors": [...], "suggestions": [...]}`
   and writes `readiness.json` into the pack. If `ok` is false, show the error and stop
   — never invent a score.

3. **Fabrication gate first.** If `blocking` is true, say plainly: this pack is **not
   ready** — the tailored CV contains something not in the master CV. Do not proceed to
   `/job-apply`; tell the user to re-run `/job-tailor`. Never work around the gate.

4. **Present the checklist.** Show `readiness_score` (0–100), then each factor as
   pass/warn/fail with its detail: fabrication, ATS match, fit, completeness, and red
   flags (label the last as advisory — it's about the job, not the user).

5. **Drive the honest improve loop.** Read the `suggestions` verbatim and act on the
   split:
   - **"Re-tailor to surface X"** — the user genuinely has X; tell them to re-run
     `/job-tailor` so it appears in the CV. Then re-run this readiness check.
   - **"Learn-gap: X … /job-upskill"** — the user genuinely lacks X. Route to
     `/job-upskill`. **Never** suggest adding it to the CV.
   - **Missing pack pieces** (cover letter, contact, unrendered CV) — do the concrete
     fix and re-tailor.
   Loop: suggest → user re-runs `/job-tailor` → re-check readiness → repeat until strong,
   then `/job-apply`.

## Rules

- Fabrication is a hard gate: if `blocking` is true, the pack is not ready — full stop.
- Honest suggestions only: surface skills the user HAS; route genuine gaps to
  `/job-upskill`; never fabricate or "just add" a missing skill.
- Read-only and offline: never modifies the workspace beyond writing `readiness.json`,
  never calls the network. Report the score the CLI returned; never inflate it.
