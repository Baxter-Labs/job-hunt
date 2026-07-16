# AGENTS.md — Job Hunt for any AI coding agent

Job Hunt finds jobs, writes fabrication-checked tailored CVs and cover
letters from your own past CVs, and applies for you (assisted, human in the
loop) — via one workspace and one deterministic Python engine. It ships as a
**Claude Code plugin** (`/plugin marketplace add Baxter-Labs/job-hunt` +
`/plugin install job-hunt`), but everything it does is just Python CLIs plus
plain-markdown instructions, so any agent with shell access — Codex CLI,
Cursor, opencode, or a custom setup — can run it directly from this repo.
This file is that agent's guide. It is read by convention by Codex CLI,
opencode, and other AGENTS.md-aware tools.

See also: [docs/PLATFORMS.md](docs/PLATFORMS.md) for a human-readable,
per-platform walkthrough, and [README.md](README.md) for the Claude Code
install path.

## Setup

```bash
git clone <this-repo>
cd job-hunt
python3 -m venv .venv
.venv/bin/pip install -r plugins/job-hunt/scripts/requirements.txt
```

`requirements.txt` declares one required dependency (`pypdf`, for reading CV
PDFs during setup) and two optional extras: `weasyprint` (higher-fidelity
PDF rendering — without it the renderer falls back through wkhtmltopdf, then
reportlab, then a dependency-free stdlib writer, so output is always
produced, just plainer) and `flask` (only for the optional dashboard view;
the default text tracker summary never imports it). Every CLI reports a
missing-module error explicitly rather than failing silently — see
`docs/REQUIREMENTS.md`.

All commands below assume you `cd plugins/job-hunt/scripts` first and invoke
the venv's Python (e.g. `../../../.venv/bin/python -m tailor.tailor_cli
check`, path adjusted for where you cloned).

## The workspace model

The plugin's code never holds personal data. Everything a user provides
lives in a workspace at `$JOB_HUNT_HOME` (default `~/.job-hunt/`):

- `profile.json` — contact info, target locations, selected platforms,
  work-authorisation scheme, apply preferences.
- `cv_master.json` — the single source of truth CV, imported once from the
  user's real PDF(s). Every tailored CV is fabrication-checked against this.
- `output/<company>-<role>/` — one tailored pack per role: `tailored_cv.json`,
  `cv.pdf`/`cv.html`, `cover_letter.pdf`/`.html`, `ats_report.json`,
  `change_log.md`.
- `tracker.csv` — every discovered/tracked/applied role, one row each.

Every path is resolved via `plugins/job-hunt/scripts/engine/workspace.py`
reading `$JOB_HUNT_HOME`. Never hardcode `~/.job-hunt` or any absolute path.

## Command catalog

For each capability: the exact entry point (run from
`plugins/job-hunt/scripts/` with the venv Python) and the SKILL.md file that
holds the full step-by-step instructions an agent should follow — **those
files are the source of truth**, not this table.

| Capability | Entry point | Full instructions |
|---|---|---|
| One-time setup (profile + import CV) | `python -m engine.setup_cli <subcommand>` (`init-workspace`, `write-profile`, `extract-cv`, `write-master`, `show`) | `plugins/job-hunt/skills/job-setup/SKILL.md` |
| Search / discover roles | `python -m search.search_cli <subcommand>` (`refresh-register`, `filter-dedupe-rank`, `track`, `status`) | `plugins/job-hunt/skills/job-search/SKILL.md` |
| Tailor CV + cover letter | `python -m tailor.tailor_cli <subcommand>` (`check`, `save-jd`, `build-prompt`, `finalize`) | `plugins/job-hunt/skills/cv-tailor/SKILL.md` |
| Assisted apply | `python -m apply.apply_cli <subcommand>` (`preapply`, `record`) | `plugins/job-hunt/skills/job-apply/SKILL.md` |
| Track applications (text summary) | `python -m search.search_cli status` | `plugins/job-hunt/skills/job-track/SKILL.md` |
| Track applications (dashboard) | `python -m dashboard.app` (serves `http://127.0.0.1:5050`, needs `flask`) | `plugins/job-hunt/skills/job-track/SKILL.md` |
| Red-flag scan of a JD | `python -m insights.insights_cli red-flags --jd-text "<JD>"` (or `--jd-file`) | `plugins/job-hunt/skills/job-redflag/SKILL.md` |
| Upskill gap analysis | `python -m insights.insights_cli upskill --all` (or `--pack <slug>`) | `plugins/job-hunt/skills/job-upskill/SKILL.md` |
| Interview prep | reads `cv_master.json` + JD via `tailor.tailor_engine` helpers; minimal Python, mostly generative | `plugins/job-hunt/skills/interview-prep/SKILL.md` |
| Follow-up email draft | `python -m insights.insights_cli followup-context --company "<C>" --role "<R>"` | `plugins/job-hunt/skills/job-followup/SKILL.md` |
| Fit score (CV vs JD) | `python -m scoring.scoring_cli fit --jd-text "<JD>"` (or `--jd-file`) | `plugins/job-hunt/skills/job-fit/SKILL.md` |
| Readiness score (pack pre-apply) | `python -m scoring.scoring_cli readiness --pack "<slug>"` (JD from the pack, or `--jd-text`/`--jd-file`) | `plugins/job-hunt/skills/job-readiness/SKILL.md` |
| Outcome funnel analytics | `python -m insights.insights_cli analytics` | `plugins/job-hunt/skills/job-analytics/SKILL.md` |
| Log an application outcome | `python -m search.search_cli log-outcome --company "<C>" --role "<R>" --status "<S>"` | `plugins/job-hunt/skills/job-analytics/SKILL.md` |
| Auto-pipeline (search → fit → select → tailor → readiness → shortlist) | `python -m search.search_cli filter-dedupe-rank`, `python -m scoring.scoring_cli fit`/`select`/`readiness`, `python -m tailor.tailor_cli finalize` (skill-orchestrated, no single entry point) | `plugins/job-hunt/skills/job-pipeline/SKILL.md` |

**How to use this table:** for any capability, open the matching
`plugins/job-hunt/skills/<name>/SKILL.md` and follow it step by step. It
tells the agent what to ask the user, which CLI subcommands to run and in
what order, how to author the generative parts (tailored CV JSON, cover
letter, interview talking points, follow-up draft) grounded only in the
user's real `cv_master.json`, and how to react to `{"ok": false, ...}`
responses. Do not skip straight to running CLI commands without reading the
skill first — the CLIs are deliberately thin; the skill carries the process.

## Capability split: offline vs. MCP-dependent

Be honest with the user about what actually works in the current
environment — never fake a result to paper over a missing tool.

**Works everywhere, needs only Python** (no MCP, no browser):
`job-setup`, `cv-tailor`/`/job-tailor` (fabrication-checked CV + ATS score),
`job-upskill`, `job-redflag`, `job-followup`, `job-fit`, `job-readiness`,
`job-analytics`, `interview-prep`, `job-track` (text summary; the Flask
dashboard also needs only local Python/Flask).

**Needs external tools configured in the host agent:**
`job-search` and `job-apply` require live access to job platforms
(Indeed/LinkedIn) and a real browser (Playwright). In Claude Code these come
from its MCP connectors. In Codex CLI, Cursor, opencode, or any other agent,
you must configure the equivalent MCP servers (or an in-agent browser tool)
yourself — see [docs/PLATFORMS.md](docs/PLATFORMS.md). If the required tool
isn't available in the current session, **skip that feature and say so
explicitly** — never fabricate a listing, an apply action, or a submission
confirmation. `job-pipeline` chains `job-search`'s discovery step into the
otherwise-offline fit/select/tailor/readiness steps, so it inherits the same
MCP dependency for discovery; it skips any platform whose tool is unavailable
and says so, and every apply it hands off still goes through assisted
`job-apply`.

## Safety rules (binding, not optional)

- **Never store, type, or ask for a password, credential, token, or 2FA
  code.** The user authenticates their own accounts, always.
- **Assisted apply stops at the first CAPTCHA, login/SSO step, or
  consent/terms/cookie acceptance**, and hands control back to the user.
  Never solve a CAPTCHA. Never accept terms on the user's behalf. Submit is
  confirmed by the user unless they've durably opted in to
  `apply_prefs.auto_submit_simple_forms` — and even then, halt at any
  CAPTCHA/login/consent.
- **The fabrication check fails loud.** A tailored CV or cover letter may
  only reorder, rephrase, and re-emphasise facts already present in the
  user's `cv_master.json`. `tailor.tailor_cli finalize` fabrication-checks
  against the master and returns `fabrication_passed:false` with the
  specific `fabrication_issues` if anything doesn't match — fix or remove
  those items and re-run; never present a pack that failed the check.
- **The ATS score is honest keyword coverage**, computed against the job
  description — never a reason to add a claim the user doesn't genuinely
  have. Missing keywords are reported as gaps for the user to decide on.
- **Follow-up drafts are drafts only — never send.** `job-followup` produces
  text for the user to review, edit, and send themselves; it never opens a
  mail client, MCP, or network connection to send anything.
- **No personal data in this repo.** Example/template content uses the
  placeholder identity `Ada Lovelace` / `ada@example.com`, never a real name.
