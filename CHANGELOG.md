# Changelog

All notable changes to Job Hunt are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Added a deterministic quality-evals harness (`evals/`): domain-diverse golden
  cases for ATS scoring and listing ranking, a scorecard CLI
  (`evals/run_evals.py`), and a `pytest` gate (`tests/test_evals.py`) with
  regression guards for the trailing-punctuation and score-honesty bugs. Dev
  tooling only — no user-facing command changes.

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
