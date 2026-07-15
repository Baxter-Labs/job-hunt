# Changelog

All notable changes to Job Hunt are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Added `/job-fit` (Phase C of the "Land It" suite): a deterministic, offline
  0–100 fit score between your master CV and a job description, in a new
  `scripts/scoring/` package (`fit.py` + `scoring_cli.py`). Blends skills
  coverage (0.5, reusing the ATS keyword engine), experience/title relevance
  (0.3), and seniority alignment (0.2) with documented weights; reports honest
  reasons and routes low fits to `/job-upskill` rather than padding the CV.
  Golden-eval'd under `evals/golden/fit/` and gated in `tests/test_evals.py`.
- Added cross-platform usage docs so the plugin can be used from any AI
  coding agent, not just Claude Code: `AGENTS.md` (setup, workspace model,
  command catalog for Codex CLI / opencode / any shell-capable agent),
  `.cursor/rules/job-hunt.mdc` (a Cursor project rule pointing at `AGENTS.md`
  and the relevant `SKILL.md`), and `docs/PLATFORMS.md` (a per-platform
  "what works where" guide covering Claude Code, Codex CLI, Cursor, opencode,
  and generic shell-capable agents). README and CHANGELOG updated to reflect
  that the engine isn't Claude-Code-only. Docs only — no code changes.
- Added a deterministic quality-evals harness (`evals/`): domain-diverse golden
  cases for ATS scoring and listing ranking, a scorecard CLI
  (`evals/run_evals.py`), and a `pytest` gate (`tests/test_evals.py`) with
  regression guards for the trailing-punctuation and score-honesty bugs. Dev
  tooling only — no user-facing command changes.
- Added four funnel-stage features, each a `/command` + skill backed by a new
  deterministic `scripts/insights/` package: `/job-redflag` (curated,
  word-boundary-correct JD red-flag scanner), `/job-upskill` (ranked
  missing-keyword gaps aggregated across tailored packs), `/job-interview-prep`
  (interview questions + talking points grounded only in the master CV), and
  `/job-followup` (a follow-up email *draft* assembled from the tracker + pack
  that is never sent). All new Python is offline, workspace-read-only, and fully
  unit-tested; the generative parts live in the skills.

## [0.1.0] - 2026-07-15

Initial release. Five slash commands sharing one workspace and one
deterministic Python engine.

### Added

- `/job-setup` — one-time workspace setup: writes `profile.json` (contact,
  target locations, platforms, work-authorisation scheme, apply
  preferences) and imports existing CV PDF(s) into a validated
  `cv_master.json`.
- `/job-search` — multi-platform search (`linkedin`, `indeed`, `naukri`,
  `career_pages`, `greenhouse_lever`, any combination), region-agnostic
  work-authorisation annotation via pluggable schemes
  (`nl-ind-hsm` against a cached IND recognised-sponsor register,
  `eu-blue-card` flagging for manual review, `none`), plus dedupe and
  ranking against your tracker.
- `/job-tailor` — a tailored CV and cover letter generated from a job
  description and your own master CV only, backed by a deterministic
  fabrication check (contact info, every `(company, title, dates)` triple,
  every skill compared against the master), and an honest ATS keyword
  match score with a reported list of missing keywords.
- `/job-apply` — assisted apply: shows the pack's ATS score first, opens
  the apply page via Playwright, prefills only non-secret contact fields,
  attaches the generated pack, and halts at any CAPTCHA, login/SSO, or
  consent step.
- `/job-track` — a text summary of the application tracker by default, or
  an optional local Flask dashboard (`dashboard`) showing work-auth status,
  ATS score, and pack download links, bound to `127.0.0.1` only.
- Graceful degradation throughout: every missing optional dependency
  (`weasyprint`, `flask`) or unavailable platform MCP tool produces an
  explicit, visible message rather than a silent skip or a fabricated
  result — see `docs/REQUIREMENTS.md`.
- 164 tests covering the engine, search pipeline, tailoring engine, ATS
  scorer, tracker, apply/track CLIs, dashboard, and every command/skill's
  static assets.

[Unreleased]: https://github.com/Baxter-Labs/job-hunt/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Baxter-Labs/job-hunt/releases/tag/v0.1.0
