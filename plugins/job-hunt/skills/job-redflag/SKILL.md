---
name: job-redflag
description: Scan a job description for advisory red flags using a deterministic, curated pattern set (vague compensation, culture cliches like "rockstar"/"we are a family", "fast-paced"/"wear many hats", unlimited PTO, unpaid assessments, equity-only pay, uncompensated on-call, unrealistic seniority ranges). Read-only and offline; the Python does the detection, the skill explains and contextualises. Use when the user wants to sanity-check a JD before applying.
---

# Job Red-Flag Scan

Surface advisory red flags in a single job description so the user can read the
worrying lines carefully before spending time on an application. The detection
is **deterministic Python** (`insights/redflags.py`); this skill runs it and
explains the results. It is **advisory, not a verdict** — never tell the user to
apply or skip; surface the evidence and let them decide.

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- Run the CLI as `python -m insights.insights_cli <subcommand>` from that scripts
  dir, using the venv Python from the repo README (stdlib only). Do not hardcode
  paths; the JD comes from the user (`--jd-text` or `--jd-file`).

## Steps

1. **Get the JD.** Accept either pasted text or a file path from the user. If a
   file, pass `--jd-file <path>`; otherwise `--jd-text "<text>"`.

2. **Scan.** Run
   `python -m insights.insights_cli red-flags --jd-text "<the JD>"`
   (or `--jd-file <path>`). It prints one JSON object:
   `{"ok": true, "count": N, "red_flags": [{"flag", "category", "evidence", "severity"}, ...]}`.
   If `ok` is false, show the error and stop — never invent flags.

3. **Present.** Group the flags by `category` (compensation, culture, workload,
   benefits, hiring-process, seniority). For each, show the `flag`, its
   `severity` (low / medium / high), and the exact `evidence` line from the JD.
   If `count` is 0, say plainly that no red flags were detected — that is a
   real, clean result, not a reason to keep digging.

4. **Contextualise, don't judge.** Briefly explain why each flag can matter and
   what to ask about it, then hand the decision back to the user.

## Rules

- Advisory only: never render a verdict ("skip this job" / "apply now").
- Read-only and offline: never modifies the workspace, never calls the network.
- Never fabricate a flag or an evidence line — show only what the CLI returned.
