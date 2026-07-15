---
name: job-fit
description: Score the workspace master CV against a single job description using a deterministic 0–100 fit score (skills coverage + experience/title relevance + seniority alignment). Read-only and offline; the Python computes the score, the skill explains it. A low fit is an honest signal to focus elsewhere or upskill, never a reason to fabricate. Use when the user wants to know how well they match a role before investing in it.
---

# Job Fit Score

Tell the user how well their master CV fits one job description, so they can decide
where to invest. The scoring is **deterministic Python** (`scoring/fit.py`); this
skill runs it and explains the result. The score is a diagnostic — it is **never** a
reason to invent skills or experience.

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- Run the CLI as `python -m scoring.scoring_cli fit` from that scripts dir, using the
  venv Python from the repo README (stdlib only). Do not hardcode paths; the JD comes
  from the user (`--jd-text` or `--jd-file`).

## Steps

1. **Get the JD.** Accept either pasted text or a file path. If a file, pass
   `--jd-file <path>`; otherwise `--jd-text "<text>"`.

2. **Score.** Run
   `python -m scoring.scoring_cli fit --jd-text "<the JD>"` (or `--jd-file <path>`).
   It prints one JSON object:
   `{"ok": true, "fit_score": N, "components": {"skills", "experience", "seniority"}, "reasons": [...]}`.
   If `ok` is false, show the error and stop — never invent a score. (A missing
   `cv_master.json` means the user should run `/job-setup` first.)

3. **Present.** Show the overall `fit_score` (0–100), then the three components with a
   one-line gloss each (skills = JD keyword coverage; experience = role-title/summary
   relevance; seniority = level alignment), then the `reasons` verbatim.

4. **Be honest about low fit.** If the fit is low, say so plainly: a low score means
   this role is a weaker match — focus your energy on better-fitting roles, or close a
   genuine gap via `/job-upskill`. Do NOT suggest padding the CV, and never present a
   higher number than the tool returned. A strong-fit role is where a tailored
   application (`/job-tailor`) pays off most.

## Rules

- Diagnostic only: report the score the CLI returned; never inflate or fabricate.
- Read-only and offline: never modifies the workspace, never calls the network.
- A low fit routes to focus/upskill, never to inventing experience the master lacks.
