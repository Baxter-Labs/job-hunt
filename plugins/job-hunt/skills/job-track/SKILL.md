---
name: job-track
description: Show the workspace application tracker. Default is a dependency-free TEXT summary (counts by status and by work-auth flag) via the search CLI. The `dashboard` sub-action launches an OPTIONAL Flask web dashboard, re-pathed to the workspace, that lists each tracked role with its ATS match score and safe pack download links. Use when the user wants to review application progress.
---

# Job Track

Report on the user's application tracker. Two modes: a **text summary** (default,
no extra dependency) and an **optional web dashboard** (needs Flask).

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- The workspace is `$JOB_HUNT_HOME` (default `~/.job-hunt`); the tracker is
  `$JOB_HUNT_HOME/tracker.csv` and packs live under `$JOB_HUNT_HOME/output/`.
  Do not hardcode paths.

## Modes (parse the argument after `/job-track`)

| Argument | Action |
|----------|--------|
| *(none)* | Print the text summary (no Flask needed) |
| `dashboard` | Launch the optional Flask web dashboard |

## Steps

1. **Text summary (default).** Run `python -m search.search_cli status` from the
   scripts dir (this reuses the tracker `summarize` logic). Present `total`,
   `by_status`, and `by_work_auth` as a short table. This path has NO Flask
   dependency.

2. **Dashboard (`/job-track dashboard`).** The dashboard is **optional** and needs
   Flask (`pip install flask`, already listed in `scripts/requirements.txt`). If
   Flask is not installed, say so and offer the text summary instead — never fail
   silently. To launch, run `python -m dashboard.app` from the scripts dir; it
   serves `http://127.0.0.1:5050`, reading `$JOB_HUNT_HOME/tracker.csv` and the
   `output/` packs and showing each role's ATS match score plus pack download
   links. Tell the user the URL and that it is a local, read-mostly view.

## Rules

- The default summary must work with no optional dependency installed.
- Never store or ask for passwords; the dashboard is a local view of local files.
- Never fabricate tracker rows or ATS scores — show only what is in the workspace.
