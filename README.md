# Job Hunt

A Claude Code plugin to find jobs, generate fabrication-checked tailored CVs and
cover letters from your own past CVs, and apply (assisted). Region-agnostic — you
pick the platforms and your work-authorisation requirement as settings.

## Install

```
/plugin marketplace add baxter-labs/job-hunt
/plugin install job-hunt
```

## Setup (one-time)

The plugin's engine needs one Python dependency, `pypdf`. Install it into the Python
you'll use (from the installed plugin directory, i.e. `${CLAUDE_PLUGIN_ROOT}`):

```bash
pip install -r plugins/job-hunt/scripts/requirements.txt
```

Prefer an isolated environment? Create a venv and install there, then make sure
`/job-setup` uses that interpreter:

```bash
python3 -m venv .venv
.venv/bin/pip install -r plugins/job-hunt/scripts/requirements.txt
```

`/job-setup` will tell you if a dependency is missing.

## Commands

- `/job-setup` — one-time setup: creates your workspace, profile, and master CV.
- `/job-search` — discover roles on your selected platforms (later phase).
- `/job-tailor` — tailor your CV + cover letter to a job (later phase).
- `/job-apply` — assisted apply (later phase).
- `/job-track` — track applications (later phase).

## Your data stays yours

All personal data lives in `~/.job-hunt/` (override with `JOB_HUNT_HOME`), never
in this repo. Passwords are never stored or typed by the plugin.
