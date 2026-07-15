---
name: interview-prep
description: Generate likely interview questions and structured talking points for one role, from the job description plus the user's master CV. Talking points are grounded ONLY in facts present in the master CV — the same anti-fabrication ethos as /job-tailor — and thin areas are flagged honestly rather than papered over. Minimal Python (load the JD + master CV); the structured prep is the skill's value. Use when the user wants to prepare for an interview.
---

# Interview Prep

Produce interview questions and grounded talking points for one role. The value
is the structured prep in this skill; the Python is minimal (loading the JD and
the master CV). The binding rule: **every talking point is grounded only in real
facts from the user's master CV — never invent experience, achievements,
metrics, or skills.**

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- The master CV lives in the workspace `$JOB_HUNT_HOME` (default `~/.job-hunt`)
  as `cv_master.json`; the tailor engine resolves it via
  `python -m tailor.tailor_engine` helpers. Do not hardcode paths. The JD comes
  from the user (paste or file path).

## Steps

1. **Load the facts.** Read the user's master CV from the workspace (the same
   `cv_master.json` `/job-tailor` uses) and take the JD from the user. Both
   loaders (`load_master_cv`, `load_job_description`) live in
   `tailor/tailor_engine.py`. If the master CV is missing, tell the user to run
   `/job-setup` first — do not proceed from nothing.

2. **Derive likely questions.** From the JD's responsibilities and requirements,
   list the questions this role is likely to ask: role-specific technical
   questions, behavioural questions, and questions probing the JD's emphasis.

3. **Draft grounded talking points.** For each question, draft talking points
   that cite REAL experience from the master CV — specific roles, projects,
   skills, and outcomes that actually appear there. Do NOT invent a project, a
   metric, or a skill the master CV does not contain.

4. **Flag the gaps honestly.** Where the master CV does not support a strong
   answer, say so plainly and suggest an honest framing (transferable
   experience, genuine eagerness to learn) rather than fabricating a claim.

## Rules

- Talking points are grounded ONLY in the master CV; never invent experience,
  achievements, metrics, or skills.
- Flag thin areas honestly instead of papering over them.
- Read-only: this skill does not modify the workspace.
