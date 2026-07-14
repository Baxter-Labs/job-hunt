# Job Hunt

A Claude Code plugin to find jobs, generate fabrication-checked tailored CVs and
cover letters from your own past CVs, and apply (assisted). Region-agnostic — you
pick the platforms and your work-authorisation requirement as settings.

## Install

```
/plugin marketplace add baxter-labs/job-hunt
/plugin install job-hunt
```

## Commands

- `/job-setup` — one-time setup: creates your workspace, profile, and master CV.
- `/job-search` — discover roles on your selected platforms (later phase).
- `/job-tailor` — tailor your CV + cover letter to a job (later phase).
- `/job-apply` — assisted apply (later phase).
- `/job-track` — track applications (later phase).

## Your data stays yours

All personal data lives in `~/.job-hunt/` (override with `JOB_HUNT_HOME`), never
in this repo. Passwords are never stored or typed by the plugin.
