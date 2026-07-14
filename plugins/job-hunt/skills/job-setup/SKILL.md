---
name: job-setup
description: Guided one-time setup for the Job Hunt plugin. Creates the user's workspace, writes a validated profile.json (contact, target locations, selected platforms, work-authorisation scheme, apply preferences), and imports the user's existing CV PDFs into a validated cv_master.json. Use when a user first installs job-hunt or wants to reconfigure.
---

# Job Setup

Guide the user through one-time setup. Nothing here is specific to any person —
every fact comes from the user in this session. Use the setup CLI for all writes;
never edit files in the workspace by hand.

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- Run the CLI as: `python -m engine.setup_cli <subcommand>` from that scripts dir,
  using the user's Python (a venv with `pypdf` installed — see the repo README).
- The workspace lives at `$JOB_HUNT_HOME` (default `~/.job-hunt`). Do not hardcode paths.

## Steps

1. **Create the workspace.**
   Run: `cd ${CLAUDE_PLUGIN_ROOT}/scripts && python -m engine.setup_cli init-workspace`
   Report the `home` path to the user.

2. **Collect profile fields — ask, don't assume.** One topic at a time:
   - Full name and email (required); optional phone, location, links.
   - Target locations (free text list).
   - Platforms to search — offer the allowed set: `linkedin`, `indeed`, `naukri`,
     `career_pages`, `greenhouse_lever`. They may pick one or many.
   - Work authorisation: do they need visa sponsorship? If yes, which scheme —
     `nl-ind-hsm` (Dutch IND highly-skilled-migrant register), `eu-blue-card`, or
     `none` (domestic / no sponsorship needed, e.g. India).
   - English-only roles? (language constraint)
   - Auto-submit simple no-CAPTCHA apply forms? Default **no**.

3. **Write the profile.** Build the JSON matching `templates/profile.example.json`
   and run:
   `python -m engine.setup_cli write-profile --json '<profile json>'`
   If it returns `{"ok": false, "issues": [...]}`, fix the issues and retry. Never
   proceed on a failed write.

4. **Import the user's CV(s).** Ask for the path(s) to their existing CV PDF(s).
   Extract the text:
   `python -m engine.setup_cli extract-cv --pdf <path1> [--pdf <path2> ...]`
   Read the returned `text`.

5. **Structure the CV into the master schema.** From the extracted text, build a
   `cv_master.json` object matching `templates/cv_master.example.json` exactly
   (keys: `schema_version` "1.0", `contact{name,title,email,phone,location,links,
   work_authorization}`, `summary`, `skills[]{name,category,level}`,
   `experience[]{company,title,location,dates,bullets[]}`, `education[]`,
   `projects[]{name,details}`, `certifications[]`, `languages[]`).
   INTEGRITY: transcribe only facts actually present in the CV text. Do not invent
   employers, titles, dates, skills, or metrics. Preserve exact company names,
   titles, and date ranges (use an en-dash "–" in date ranges). This master is the
   single source of truth that a later fabrication check enforces against.

6. **Confirm with the user**, then write it:
   `python -m engine.setup_cli write-master --json '<master json>'`
   If it returns issues, fix and retry.

7. **Verify and report.** Run `python -m engine.setup_cli show` and confirm
   `has_profile` and `has_master` are both true. Tell the user setup is complete and
   what to run next (`/job-search`, `/job-tailor`).

## Rules

- Never fabricate CV content. Only transcribe what is in the user's CV text.
- Never store or ask for passwords.
- Always use the CLI for writes so validation runs; never hand-edit workspace files.
