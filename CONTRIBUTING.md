# Contributing to Job Hunt

Job Hunt is a Claude Code plugin: five slash commands, their skills, and a
deterministic Python engine underneath. This document covers how to develop
against it.

## Setup

```bash
git clone <this-repo>
cd job-hunt
python3 -m venv .venv
.venv/bin/pip install -r plugins/job-hunt/scripts/requirements.txt
.venv/bin/pip install pytest
```

`requirements.txt` declares one required dependency (`pypdf`) and two
optional extras (`weasyprint`, `flask`) — see `docs/REQUIREMENTS.md` for what
each unlocks and how the code degrades without it. Install all three so the
full test suite runs, including the fallback-PDF-renderer and dashboard
tests.

## Running tests

```bash
.venv/bin/python -m pytest -q
```

235 tests as of this writing, covering the engine modules
(`profile`, `cv_import`, `workspace`), the search pipeline (`listing`,
`dedupe`, `rank`, `tracker`, work-auth providers), the tailoring engine
(`tailor_engine`, `ats`, PDF rendering), the apply/track CLIs, the dashboard,
the quality-evals gate (`evals/`), the funnel insights package (`redflags`,
`upskill`, `followup`, `insights_cli`), and every command/skill's static
assets (frontmatter, `${CLAUDE_PLUGIN_ROOT}` usage, absence of personal
data).

The suite includes `tests/test_evals.py`, which drives the golden-case quality
evals in `evals/` (deterministic, offline). Add or update a golden case whenever
you change ATS scoring (`tailor.ats`) or ranking (`search.rank`) behavior — run
`.venv/bin/python evals/run_evals.py` to see the real numbers and set the band.

## Repository conventions

These are enforced in code or by tests, not just convention:

- **No personal data anywhere in the repo.** Example files
  (`templates/profile.example.json`, `templates/cv_master.example.json`) use
  the placeholder identity `Ada Lovelace` / `ada@example.com`, never a real
  name or a real filesystem path. `tests/test_setup_assets.py` asserts this
  directly (checks for the literal maintainer's username and name in the
  templates and skill text). If you add new example/fixture content, keep it
  placeholder-only.
- **All paths go through `engine.workspace`, never hardcoded.** Every
  personal-data path (`profile.json`, `cv_master.json`, `tracker.csv`,
  `output/`, `jd_queue/`) is resolved via
  `plugins/job-hunt/scripts/engine/workspace.py`, which reads
  `$JOB_HUNT_HOME` (default `~/.job-hunt`). Don't hardcode `~/.job-hunt` or
  any absolute path elsewhere — call the `workspace` helpers, or accept a
  `path: Optional[Path]` parameter the way the existing modules do (see
  `engine/profile.py`, `search/tracker.py`).
- **Plugin files reference other plugin files via `${CLAUDE_PLUGIN_ROOT}`,
  never an absolute path.** Commands and skills under `plugins/job-hunt/`
  must resolve sibling files (scripts, prompt templates, etc.) through
  `${CLAUDE_PLUGIN_ROOT}`, so the plugin works regardless of where it's
  installed. `tests/test_setup_assets.py` checks this for at least one
  skill; keep any new skill consistent.
- **Deterministic Python only — no MCP/browser calls in `plugins/job-hunt/scripts/`.**
  The Python engine (`engine/`, `search/`, `tailor/`, `apply/`, `dashboard/`)
  is pure, testable, and offline (aside from the one explicit network step
  in `nl-ind-hsm`'s `refresh()`, which is itself injectable — see
  `docs/EXTENDING.md`). Anything that talks to an MCP tool, a browser via
  Playwright, or the Anthropic API interactively belongs in a **skill**
  (`plugins/job-hunt/skills/*/SKILL.md`), which calls back into the Python
  engine for the deterministic parts (validation, scoring, dedupe, file
  I/O). Don't add a live network or MCP call inside `scripts/`.
- **Every CLI subcommand prints exactly one JSON object to stdout.** Each of
  `setup_cli.py`, `search_cli.py`, `tailor_cli.py`, `apply_cli.py` follows
  the same `print(json.dumps(obj, ensure_ascii=False))` pattern for its
  final output, so a skill can parse a single, predictable result. Errors
  are reported the same way (`{"ok": false, "error": "..."}`), not raised as
  uncaught exceptions or printed as free text.

## Adding a work-authorisation scheme or a platform

Both extension points — a new `WorkAuthProvider` scheme, or a new search
platform key — are documented in full in
[docs/EXTENDING.md](docs/EXTENDING.md): the interfaces, the two registries
that must agree (`engine/profile.py`'s `SCHEMES`/`PLATFORMS` and
`work_auth/__init__.py`'s `get_provider()`), and which skill prose needs a
one-line update. Follow it exactly — the registries are validated against
each other, and an unregistered scheme/platform is rejected by
`validate_profile()` rather than silently accepted.

## Test-driven development

Follow RED → GREEN: write (or extend) a test that fails for the behaviour
you're adding, then write the minimum code to make it pass. This codebase
leans on its test suite instead of runtime type-checking — every module
above has a corresponding `tests/test_*.py`; look at the one for the module
you're touching before adding new tests, to match its fixture and naming
style.

## Documentation you may need to update alongside code

- `DATA_CONTRACT.md` — if you change a workspace artifact's schema.
- `docs/EXTENDING.md` — if you change either extension point's interface.
- `docs/REQUIREMENTS.md` — if you add/remove a dependency or an MCP
  requirement, or change a graceful-degradation path.
- `README.md` — if you change what a command does from the user's
  perspective.
