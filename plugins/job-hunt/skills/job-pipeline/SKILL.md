---
name: job-pipeline
description: Run the full auto-pipeline end to end — search the profile's platforms, fit-score new roles, select the top-N deterministically, auto-tailor each selected role, readiness-score each prepared pack, and present a ranked, review-ready shortlist (company, role, fit, ATS, readiness, top gaps, pack path). The user picks which roles to apply to; every apply still goes through assisted /job-apply and the user approves every send — this skill introduces no new auto-submit path. Never fabricates to raise fit/ATS/readiness; a role that fails the fabrication gate is surfaced as blocked, not hidden; genuine gaps route to /job-upskill; unavailable platform tools are skipped with a note, never faked.
---

# Job Pipeline

Orchestrate the whole discovery-to-shortlist chain in one run: search, fit-score,
select the top-N, auto-tailor, readiness-score, and present a ranked shortlist. This
skill is the conductor — the actual work is done by the existing deterministic CLIs
(`search.search_cli`, `scoring.scoring_cli`, `tailor.tailor_cli`) and by the
browser/MCP tools already used in `/job-search`, `/job-tailor`, and `/job-readiness`.
The pipeline never applies on the user's behalf: it prepares and ranks packs, the
user picks, and every send still goes through assisted `/job-apply`.

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- Run the CLIs as `python -m search.search_cli …`, `python -m scoring.scoring_cli …`,
  and `python -m tailor.tailor_cli …` from that scripts dir, using the venv Python
  from the repo README (stdlib only).
- Workspace: `$JOB_HUNT_HOME` (default `~/.job-hunt`). Do not hardcode paths.

## Modes

- `(none)` — full run against every platform in the profile.
- `--n <k>` / "top k" — override how many roles to auto-tailor (default 5).
- `<platform>` — restrict discovery to a single platform from the profile.

## Steps

1. **Read the profile.** Load `$JOB_HUNT_HOME/profile.json`. If it's missing, stop
   and tell the user to run `/job-setup` first. Note `platforms`, `target_locations`,
   `work_auth.scheme`, and `language_constraints`. Respect the profile's work-auth and
   language settings throughout the run.

2. **Discover (skill-driven, same as `/job-search`).** Run ONLY the profile's
   platforms with their tools. **If a required tool is unavailable in this session,
   skip that platform and say so explicitly — never fake or approximate its
   listings.** Build one combined raw-listing list, write it to
   `$JOB_HUNT_HOME/output/.pipeline_raw.json`, then run
   `python -m search.search_cli filter-dedupe-rank --listings-file <that file>`;
   read the ranked `new` roles and `counts`.

3. **Fit-score each new role.** For each role in `new`, fetch its JD (Indeed MCP
   `get_job_details` or Playwright on the listing URL; if the JD can't be fetched,
   skip that role with a note — never invent a JD), then run
   `python -m scoring.scoring_cli fit --jd-text "<JD>"` and attach the returned
   `fit_score`. Write the enriched array to
   `$JOB_HUNT_HOME/output/.pipeline_scored.json`.

4. **Select top-N.** Run
   `python -m scoring.scoring_cli select --scored-file $JOB_HUNT_HOME/output/.pipeline_scored.json --n <N>`
   (default 5, or the user's override). Use the returned `selected` list as the
   shortlist to auto-tailor. Note the counts at each stage (found → new → scored →
   selected).

5. **Auto-tailor each selected role (the `/job-tailor` flow).** For each selected
   role: `tailor_cli save-jd --company … --role … --jd-file …` → author
   `tailored_cv.json` by **reordering, rephrasing, and re-emphasising ONLY facts
   already in `cv_master.json`** (obey the humanizer rules; never invent an employer,
   title, date, metric, or skill) → run `python -m tailor.tailor_cli finalize …`.
   **If `finalize` returns `ok:false` with `fabrication_passed:false`, do NOT work
   around it: mark that role BLOCKED and surface it in the shortlist as blocked (not
   hidden), and never present a pack that failed the fabrication check.**

6. **Readiness-score each prepared pack.** Run
   `python -m scoring.scoring_cli readiness --pack "<slug>"`. If `blocking` is true,
   the pack is **not ready** — surface it as blocked with the reason; never inflate
   the score.

7. **Present the ranked, review-ready shortlist.** One row per selected role:
   **Company · Role · Fit · ATS · Readiness · Top gaps · Pack path**, ordered by the
   selection. Mark blocked packs clearly (fabrication-gate failures and
   readiness-blocking packs alike). State which platforms were skipped for lack of a
   tool.

8. **Hand off — user picks, `/job-apply` applies.** Ask which roles the user wants to
   apply to. **Every apply goes through assisted `/job-apply` — the user approves
   every send. The pipeline introduces NO new auto-submit path.** For honest gaps
   flagged in readiness (keywords the user genuinely lacks), route to
   `/job-upskill`; never suggest adding them to the CV.

## Rules

- Query only the profile's platforms; skip a platform whose tool is unavailable with
  an explicit note — never fake or approximate its listings or JDs.
- Never fabricate a job, JD, work-authorization status, fit/ATS/readiness score, or
  CV content — tailoring only reorders/rephrases/re-emphasises facts already in
  `cv_master.json`. Genuine gaps route to `/job-upskill`, never "just add it."
- A role that fails the fabrication gate is surfaced as **blocked**, not hidden or
  worked around.
- Fit, select, and readiness are diagnostics — report exactly what the CLIs
  returned, never inflate a score.
- **User approves every apply; no new auto-submit.** The pipeline prepares and ranks
  packs; it never sends an application itself. Every apply still goes through
  assisted `/job-apply`, where the user approves every send.
- Never store or ask for passwords. Respect the profile's work-auth and language
  settings throughout.
