# Requirements

What each Job Hunt command and feature needs, and what happens when a
dependency is missing. Nothing below is bundled with the plugin — you bring
your own Python environment and MCP tools; the plugin's code is read-only and
never installs anything on your behalf.

## Python

Only `pypdf` is required, for reading your CV PDFs during `/job-setup`. It's
declared in `plugins/job-hunt/scripts/requirements.txt`.

```bash
pip install -r plugins/job-hunt/scripts/requirements.txt
```

Two extras in that same file are optional:

| Package | Needed for | If absent |
|---|---|---|
| `weasyprint` | Higher-fidelity PDF rendering in `/job-tailor` | The renderer falls back through `wkhtmltopdf` (a system binary, if present on `PATH`), then `reportlab`, then a dependency-free stdlib PDF writer. The stdlib writer always succeeds, so a missing `weasyprint` degrades PDF *polish*, never breaks the pipeline. Note: `reportlab` itself is used as one of these fallback backends but is not declared in `requirements.txt` — if it's also absent, rendering falls through to the guaranteed stdlib writer. |
| `flask` | The optional `/job-track dashboard` web view | `/job-track`'s default text summary never imports Flask. Asking for `dashboard` without Flask installed is reported to you plainly, with the text summary offered instead — it never fails silently. |

Every CLI subcommand reports a missing-module error explicitly (e.g.
`{"ok": false, "error": "..."}` mentioning the missing package) rather than
crashing opaquely, so a skill can tell you what to install and stop.

## MCP tools (per platform)

`/job-setup` lets you choose any combination of five platform keys in
`profile.platforms`. `/job-search` queries **only** the platforms you picked,
and skips (with an explicit note, never a fabricated result) any platform
whose required tool isn't available in the current session.

| Platform key | Tool needed | Notes |
|---|---|---|
| `indeed` | An Indeed MCP server exposing `search_jobs` / `get_job_details` | Used for search and for fetching a job description at hand-off to `/job-tailor`. |
| `linkedin` | A LinkedIn scraper MCP with `search_jobs`, or a Playwright MCP against a logged-in LinkedIn Jobs session | You authenticate LinkedIn yourself; the plugin never stores that session or any credential. |
| `naukri` | A Playwright MCP | Drives the Naukri search-results page directly. |
| `career_pages` | A Playwright MCP | Navigates company career sites; declines cookie banners rather than accepting them. |
| `greenhouse_lever` | A Playwright MCP | Searches Greenhouse/Lever boards by keyword and department filter. |

## `/job-apply`

Requires a **Playwright MCP** unconditionally — it is how the skill opens the
apply page, prefills fields, and attaches files. If the Playwright MCP isn't
available, `/job-apply` says so and stops; it never fakes submitting an
application.

`/job-apply` also requires that the pack you're applying to already has an
`ats_report.json` (written by `/job-tailor`). If it's missing, the skill says
so and stops rather than inventing a score.

## `nl-ind-hsm` work-auth scheme

The `nl-ind-hsm` provider annotates companies against a **cached, offline**
CSV of the Dutch IND recognised-sponsor register
(`$JOB_HUNT_HOME/config/nl_ind_hsm_sponsors.csv`). Annotation during
`/job-search` never touches the network. Refreshing that cache
(`/job-search refresh-register`) is the only network-touching step for this
scheme, and a failed refresh never blocks search — it proceeds with whatever
cache already exists (or an empty one, in which case every company comes back
`not_found`/flagged rather than guessed).

## Graceful-degradation summary

- Missing `pypdf` → `/job-setup` cannot extract CV text; it reports the
  missing module and stops rather than skipping the step silently.
- Missing `weasyprint` (and `wkhtmltopdf`, and `reportlab`) → `/job-tailor`
  still produces a `cv.pdf`/`cv.html` via the stdlib writer; only visual
  polish is reduced.
- Missing `flask` → `/job-track dashboard` is unavailable; the default text
  summary is unaffected and is offered as the fallback.
- Missing a platform's MCP tool → `/job-search` skips only that platform and
  says so; other selected platforms still run.
- Missing the Playwright MCP → `/job-apply` stops before opening anything.
- A stale or empty `nl-ind-hsm` register cache → `/job-search` still runs;
  affected companies are flagged or reported `not_found` rather than assumed
  eligible.

In every case above, the failure mode is an explicit, visible message — never
a silently skipped step or a fabricated result.
