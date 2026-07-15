---
name: cv-tailor
description: Tailor the user's workspace master CV (cv_master.json) and write a cover letter for a specific job description. Claude authors the tailored CV and cover letter by reordering, rephrasing, and re-emphasising ONLY facts already in the master CV; the Python engine fabrication-checks it against the master, renders cv.pdf + cover_letter.pdf, computes an ATS match score, and packs the output. Surfaces the ATS score + missing keywords. Use when a user wants to tailor their CV/cover letter to a job.
---

# CV Tailor

Tailor the user's real master CV to one job. Nothing here is specific to any
person — every fact comes from the user's own `cv_master.json`. Use the CLI for
all writes so validation, fabrication checking, and rendering run; never
hand-edit workspace files.

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- Run the CLI as `python -m tailor.tailor_cli <subcommand>` from that scripts dir,
  using the venv Python described in the repo README (needs `pypdf`; `weasyprint`
  optional — the renderer falls back to reportlab/stdlib).
- Prompt assets ship with the plugin at
  `${CLAUDE_PLUGIN_ROOT}/scripts/tailor/prompts/` (recruiter_persona.md,
  humanizer_rules.md, tailor_prompt_template.md).
- The workspace is `$JOB_HUNT_HOME` (default `~/.job-hunt`). Do not hardcode paths.

## Steps

1. **Check setup.** Run `cd ${CLAUDE_PLUGIN_ROOT}/scripts && python -m tailor.tailor_cli check`.
   If `has_master` is false, stop and tell the user to run `/job-setup` first.

2. **Collect the job.** Ask for the company, the role title, and the job
   description (pasted text or a file path). Save it:
   `python -m tailor.tailor_cli save-jd --company "<C>" --role "<R>" (--jd-text "<JD>" | --jd-file <path>)`.
   Note the returned `jd_path` and `pack_slug`.

3. **Read the ground truth and the rules.** Read the user's master CV
   (`$JOB_HUNT_HOME/cv_master.json`) and the three prompt assets under
   `${CLAUDE_PLUGIN_ROOT}/scripts/tailor/prompts/`. (Optional: run
   `python -m tailor.tailor_cli build-prompt --company "<C>" --role "<R>" --jd-file <jd_path>`
   to get the fully assembled tailoring prompt.)

4. **Author `tailored_cv.json`.** Adopt the recruiter persona, obey EVERY
   humanizer rule (no banned phrases, no triadic lists, vary sentence rhythm,
   plain verbs, British/Dutch spelling, at most one em-dash per section), and
   build a JSON object matching the tailored_cv schema exactly:
   `schema_version` "1.0"; `meta{company,role,model_used:"",generated_at:""}`;
   `contact{...}` copied verbatim from the master; `summary` (2–4 tailored
   sentences); `skills_grouped[]{group,skills[]}` where every skill is an EXACT
   string from master `skills[].name`; `experience[]{company,title,dates,bullets[]}`
   where every `(company,title,dates)` triple matches a master entry verbatim and
   bullets are rephrasings of that entry's master bullets; `highlights[]` (0–5);
   `ats_keywords_used[]` (JD terms genuinely matched); and
   `fabrication_check{passed:true,issues:[]}` (the engine overwrites it).
   **INTEGRITY:** only reorder, rephrase, and re-emphasise. Never invent an
   employer, title, date, metric, or skill the master does not contain.
   Write this object to a temp file, e.g. `$JOB_HUNT_HOME/output/<pack_slug>/tailored_cv.draft.json`.

5. **Write the cover letter.** Create `cover_letter.md` in the pack dir
   `$JOB_HUNT_HOME/output/<pack_slug>/cover_letter.md`: a short, specific letter
   (salutation, 2–3 paragraphs, sign-off) grounded only in real master-CV facts,
   obeying the same humanizer rules. The renderer picks it up automatically.

6. **Finalize the pack.** Run:
   `python -m tailor.tailor_cli finalize --company "<C>" --role "<R>" --jd-file <jd_path> --tailored-file <draft path>`
   This fabrication-checks against the master, validates the schema, renders
   `cv.pdf`/`cv.html` and `cover_letter.pdf`, computes the ATS report, and writes
   `change_log.md`.
   - If it exits non-zero with `ok:false` and `fabrication_passed:false`, the
     tailored CV contains something not in the master. Read `fabrication_issues`,
     remove or correct those items (do NOT invent facts to satisfy the JD), and
     re-run finalize. Never present a pack that failed the fabrication check.
   - If `ok:false` with schema `issues`, fix the JSON shape and re-run.

7. **Report to the user (ATS shown before applying).** State the **ATS match
   score** (`ats_score`%), list the **top missing keywords** as honest gaps (the
   user should only add ones they genuinely have — re-tailor if so, never
   fabricate), confirm **fabrication_check PASSED — nothing fabricated**, note any
   advisory `humanizer_flags`, and give the pack path with its files
   (`cv.pdf`, `cover_letter.pdf` (or `cover_letter.html` if weasyprint is not
   installed), `ats_report.json`, `change_log.md`).

## Rules

- Never fabricate CV or cover-letter content. Only reorder/rephrase/re-emphasise
  facts already in the user's master CV.
- A missing ATS keyword the user genuinely lacks is a reported gap, never a reason
  to add an untrue claim.
- Always finalize through the CLI so the fabrication check and rendering run.
- Never store or ask for passwords.
