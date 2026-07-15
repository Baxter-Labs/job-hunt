# Job Hunt

Job Hunt finds jobs, writes fabrication-checked tailored CVs and cover
letters from your own past CVs, and applies for you — with a human in the
loop for every irreversible step. It is region-agnostic: you choose which
job platforms to search and which work-authorisation scheme (if any) applies
to you as plain settings, not hardcoded logic.

It ships as a **Claude Code plugin** — nine slash commands that share one
workspace and one deterministic Python engine: `/job-setup` → `/job-search`
→ `/job-tailor` → `/job-apply` → `/job-track` (plus `/job-redflag`,
`/job-upskill`, `/job-interview-prep`, `/job-followup`). Under the hood it's
just Python CLIs and markdown skill instructions, so it also runs in Codex
CLI, Cursor, opencode, and other AI coding agents — see
[Use it in other AI agents](#use-it-in-other-ai-agents-codex-cursor-) below.

## Dashboard preview

The optional `/job-track dashboard` gives you a local web view of every
application — work-authorisation status, **ATS match score**, the generated CV /
cover-letter files, and quick apply links:

![Job Hunt dashboard — application tracker showing ATS match scores, work-auth status, and generated packs](docs/img/dashboard.png)

_(Sample data shown; the dashboard runs locally on `127.0.0.1` and reads only
your own workspace.)_

## Install

```
/plugin marketplace add Baxter-Labs/job-hunt
/plugin install job-hunt
```

## Setup (one-time)

The engine needs one Python dependency, `pypdf`, to read your CV PDFs. Install
it into the Python you'll use (from the installed plugin directory, i.e.
`${CLAUDE_PLUGIN_ROOT}`):

```bash
pip install -r plugins/job-hunt/scripts/requirements.txt
```

Prefer an isolated environment? Create a venv and install there:

```bash
python3 -m venv .venv
.venv/bin/pip install -r plugins/job-hunt/scripts/requirements.txt
```

That same requirements file also lists two **optional** extras — install them
if you want the features they unlock:

- `weasyprint` — higher-fidelity PDF rendering for `/job-tailor`. Without it,
  the renderer still produces a PDF (falling back through wkhtmltopdf, then
  reportlab, then a dependency-free stdlib writer), just plainer.
- `flask` — only needed for the optional `/job-track dashboard` web view. The
  default text summary never imports Flask.

Every command will tell you if a dependency it needs is missing, rather than
failing silently. Once `pypdf` is installed, run:

```
/job-setup
```

## Commands

| Command | What it does |
|---|---|
| `/job-setup` | One-time: creates your workspace, writes `profile.json` (contact, target locations, platforms, work-auth scheme, apply preferences), and imports your existing CV PDF(s) into a validated `cv_master.json`. |
| `/job-search` | Runs only the platforms you selected in your profile, annotates each company with your work-authorisation status, drops anything you've already tracked or packaged, ranks what's left, and shows you a table of new roles. |
| `/job-tailor` | Takes a job description and produces a tailored CV + cover letter (PDF), an ATS match score with missing keywords, and a change log — grounded entirely in facts already in your master CV. |
| `/job-apply` | Assisted apply: shows you the pack's ATS score first, opens the apply page, prefills only safe non-secret contact fields, attaches your pack, and stops at any CAPTCHA, login, or consent step. |
| `/job-track` | Prints a text summary of your application tracker by default, or launches a local dashboard with `dashboard`. |
| `/job-redflag` | Scans a job description for advisory red flags (vague pay, culture cliches, unpaid assessments, unrealistic seniority ranges) with the exact evidence line and a severity for each — advisory, never a verdict. |
| `/job-upskill` | Aggregates the missing keywords across the roles you've tailored into ranked skill gaps (with frequency and which roles wanted each), then turns them into a focused learning plan. |
| `/job-interview-prep` | Generates likely interview questions and talking points for a role, grounded only in real experience from your master CV, flagging thin areas honestly. |
| `/job-followup` | Drafts a follow-up email for a role you've applied to, grounded in your tracker and pack — for you to review and send yourself. It never sends anything. |

### Example flow

```
/job-setup
  → creates ~/.job-hunt, walks you through profile.json, imports your CV(s)

/job-search
  → queries the platforms in your profile, shows a ranked table of new roles
  → you pick which ones to prepare: "1,3"

/job-tailor
  → tailors your CV + writes a cover letter for the JD, reports ATS score
    and missing keywords, fails loud if anything looks fabricated

/job-apply
  → shows the ATS score again, opens the apply page, prefills your contact
    fields, attaches the pack, and stops the moment a CAPTCHA/login/consent
    step appears — you take it from there

/job-track
  → "3 tracked, 1 applied, 2 discovered" — or /job-track dashboard for a
    local browser view with download links
```

## How it works

**Workspace vs. code.** The plugin's code never holds your personal data.
Everything you put in — contact details, target locations, your master CV,
every tailored pack, your application tracker — lives in a workspace at
`$JOB_HUNT_HOME` (default `~/.job-hunt/`): `profile.json`, `cv_master.json`,
`output/<company>-<role>/` packs, and `tracker.csv`. Passwords are never
stored or typed by the plugin, anywhere.

**Region as settings, not code.** There's nothing Netherlands-specific,
India-specific, or otherwise regional baked into the plugin. `/job-setup`
asks which platforms to search (`linkedin`, `indeed`, `naukri`,
`career_pages`, `greenhouse_lever` — pick any combination) and which
work-authorisation scheme applies to you:

- `nl-ind-hsm` — checks companies against the Dutch IND recognised-sponsor
  register (cached locally; confirmed / possible / not-found).
- `eu-blue-card` — no single authoritative employer register exists, so this
  scheme flags every role for manual salary/threshold review rather than
  guessing.
- `none` — no sponsorship filter (e.g. searching domestically).

`/job-search` only queries the platforms you picked, and only applies the
work-auth scheme you picked.

**ATS score and fabrication check.** `/job-tailor` never invents anything.
Claude may only reorder, rephrase, and re-emphasise facts already present in
your `cv_master.json`; a deterministic, code-level fabrication check (never
the model) then compares the tailored output's contact info, every
`(company, title, dates)` triple, and every listed skill against the master,
and fails loudly if anything doesn't match. The ATS match score is an honest
keyword-coverage number computed against the job description — never a
reason to add a claim you don't genuinely have. Keywords you're missing are
reported as gaps for you to decide on, not silently inserted.

**Assisted apply, not auto-apply.** `/job-apply` drives a real browser via
the Playwright MCP, but a human stays in control of every irreversible step.
It shows you the ATS score before it opens anything, fills in only
non-secret contact fields, attaches your pack, and halts immediately at any
CAPTCHA, login/SSO step, consent/terms acceptance, or request for sensitive
data. Clicking submit requires your confirmation unless you've explicitly
opted in to `apply_prefs.auto_submit_simple_forms` — and even then, it still
halts at any CAPTCHA, login, or consent step and never handles credentials.

## Requirements

- **Python** with `pypdf` installed (required). `weasyprint` and `flask` are
  optional extras — see [Setup](#setup-one-time) above.
- **MCP tools**, brought by you, not bundled with the plugin:
  - An **Indeed MCP** for the `indeed` platform.
  - A **LinkedIn scraper MCP** (or a logged-in browser session via
    Playwright) for the `linkedin` platform.
  - A **Playwright MCP** for `naukri`, `career_pages`, `greenhouse_lever`,
    and for all of `/job-apply`.

If a platform's tool isn't available in a session, `/job-search` skips that
platform and says so explicitly — it never fakes or approximates results.
See [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) for the full breakdown per
command and feature.

## Privacy & safety

- All personal data lives in your workspace (`$JOB_HUNT_HOME`, default
  `~/.job-hunt/`), never in the plugin's code.
- Passwords, credentials, tokens, and 2FA codes are never stored, typed, or
  asked for. You authenticate your own platform sessions.
- `/job-apply` never solves a CAPTCHA and never accepts terms/consent on your
  behalf — it stops and hands control back to you.
- The optional `/job-track dashboard` is a local Flask app bound to
  `127.0.0.1` only, serving files from an explicit allow-list.
- Nothing is uploaded or shared outside the tools you explicitly authorize
  (your chosen MCP tools) and the workspace on your own disk.

## Extending

Adding a new work-authorisation scheme or wiring up a new platform doesn't
require touching the skills' prompts — see
[docs/EXTENDING.md](docs/EXTENDING.md) for the provider interface and the
registry you plug into.

## Use it in other AI agents (Codex, Cursor, …)

Job Hunt is a Claude Code plugin, but underneath it's just Python CLIs in
`plugins/job-hunt/scripts/` and plain-markdown instructions in
`plugins/job-hunt/skills/*/SKILL.md`. Any agent with shell access can clone
this repo, install the one required dependency, and run the same engine —
Codex CLI and opencode read [AGENTS.md](AGENTS.md) by convention, and Cursor
picks up [`.cursor/rules/job-hunt.mdc`](.cursor/rules/job-hunt.mdc). The
offline features (`/job-setup`, `/job-tailor`, `/job-upskill`,
`/job-redflag`, `/job-followup`, `/job-interview-prep`, `/job-track`) need
only Python; `/job-search` and `/job-apply` need MCP tools (job-board
search, browser automation) configured in that agent's own MCP settings.
See [docs/PLATFORMS.md](docs/PLATFORMS.md) for the full per-platform guide.

## Documentation

- [AGENTS.md](AGENTS.md) — cross-agent guide: setup, workspace model, and
  the command catalog, for Codex CLI, opencode, and any shell-capable agent.
- [docs/PLATFORMS.md](docs/PLATFORMS.md) — using Job Hunt in Claude Code,
  Codex CLI, Cursor, opencode, or any other AI agent.
- [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) — what each command/feature
  needs, and how it degrades when a dependency is missing.
- [docs/EXTENDING.md](docs/EXTENDING.md) — how to add a work-authorisation
  scheme or a search platform.
- [DATA_CONTRACT.md](DATA_CONTRACT.md) — the schema of every workspace
  artifact (`profile.json`, `cv_master.json`, `tailored_cv.json`,
  `ats_report.json`, `tracker.csv`), and which module validates each.
- [LEGAL_DISCLAIMER.md](LEGAL_DISCLAIMER.md) — what Job Hunt does and does
  not guarantee; read this before relying on it for a real application.
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to set up a dev environment, run
  the test suite, and the repository's conventions.
- [CHANGELOG.md](CHANGELOG.md) — release history.

### Quality evals

Beyond unit tests, `evals/` holds a deterministic, offline **quality-evals
harness**: domain-diverse golden cases (JSON) that lock the exact/banded
behavior of the ATS scorer and the listing ranker, including regression guards
for two bugs the unit tests once missed (trailing-punctuation keyword fragments
and counting non-rendered keywords). Run the scorecard:

    .venv/bin/python evals/run_evals.py

It also runs as part of `pytest` via `tests/test_evals.py`. See
`evals/README.md` for the case schema and how to add a case.
