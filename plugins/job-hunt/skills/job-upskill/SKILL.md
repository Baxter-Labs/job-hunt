---
name: job-upskill
description: Aggregate the MISSING ATS keywords across the user's tailored packs (all, or one named role) into a ranked list of skill gaps with frequency and the roles that wanted each, using the deterministic insights CLI. The skill then turns the real gaps into a focused learning plan with resources. Read-only and offline for the Python part. Use when the user wants to know what to learn next to be more competitive.
---

# Job Upskill

Turn the user's own tailoring history into a focused upskilling plan. The gap
data is **deterministic** — it reuses each pack's already-computed
`ats_report.json` `missing_keywords` (via `insights/upskill.py`), so the gaps
shown are exactly the ones `/job-tailor` reported. The ranked gaps are facts;
the "what to learn and how" is this skill's contribution.

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- Run the CLI as `python -m insights.insights_cli <subcommand>` from that scripts
  dir, using the venv Python from the repo README. The workspace is
  `$JOB_HUNT_HOME` (default `~/.job-hunt`); packs live under `output/`. Do not
  hardcode paths.

## Steps

1. **Aggregate the gaps.** For every tailored role, run
   `python -m insights.insights_cli upskill --all`. For a single role, run
   `python -m insights.insights_cli upskill --pack "<company-slug>-<role-slug>"`.
   It prints one JSON object:
   `{"ok": true, "packs_scanned": N, "gaps": [{"keyword", "count", "roles"}, ...]}`.
   If `packs_scanned` is 0, tell the user there are no tailored packs yet and to
   run `/job-tailor` first — do not invent gaps.

2. **Show the ranked gaps.** Present the top gaps as a short table: `keyword`,
   `count` (how many of their roles wanted it), and the `roles` list. This is
   the honest signal of where they are least competitive.

3. **Make a learning plan.** From the real gaps, propose a focused plan:
   prioritise the highest-frequency, highest-leverage gaps; suggest credible
   learning resources; sequence them realistically. Keep it grounded in the
   actual gaps — no generic "learn everything" advice.

## Rules

- Ground the plan in the CLI's real gaps; never inflate or invent skills the
  data doesn't show.
- The Python step is read-only and offline; it never modifies the workspace.
- If there are no packs, say so honestly rather than producing a plan from
  nothing.
