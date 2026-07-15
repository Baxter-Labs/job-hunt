---
name: job-search
description: Discover new job listings across the platforms in the user's profile (Indeed MCP, LinkedIn scraper MCP, or Playwright on Naukri / company career pages / Greenhouse-Lever), annotate each company with the profile's work-authorisation provider (nl-ind-hsm, eu-blue-card, or none), dedupe against the workspace tracker and existing packs, rank, and present NEW roles with apply links. Region-agnostic and profile-driven. Use when the user wants to find and shortlist jobs.
---

# Job Search

Find new roles for the user. Nothing here is region- or person-specific: the
platforms to query and the work-authorisation behaviour come entirely from the
user's `profile.json`. Claude performs the platform queries with the MCP/Playwright
tools; the Python `search_cli` does the deterministic annotate/filter/dedupe/rank/
track work. Never invent a listing — only report what a tool actually returned.

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- Run the CLI as `python -m search.search_cli <subcommand>` from that scripts dir,
  using the venv Python from the repo README (stdlib only for search).
- The workspace is `$JOB_HUNT_HOME` (default `~/.job-hunt`). Do not hardcode paths.

## Modes (parse the argument after `/job-search`)

| Argument | Action |
|----------|--------|
| *(none)* | Full run: discover → filter/dedupe/rank → present → hand off |
| `scan` | Discover + filter/dedupe/rank + present only (no hand-off prompt) |
| `<platform>` | Restrict discovery to one platform key from the profile |
| `status` | Print the tracker summary and stop |
| `refresh-register` | Refresh the work-auth register (nl-ind-hsm only) |

## Steps

1. **Read the profile.** Load `$JOB_HUNT_HOME/profile.json`. If it is missing, stop
   and tell the user to run `/job-setup`. Note `platforms`, `target_locations`,
   `work_auth.scheme`, and `language_constraints`.

2. **Refresh the register if asked / stale (nl-ind-hsm only).** For
   `/job-search refresh-register`, or when the scheme is `nl-ind-hsm` and no
   register cache exists yet: either hand a freshly obtained CSV to
   `python -m search.search_cli refresh-register --from-file <csv>`, or run
   `refresh-register` with no file to let the provider fetch the live IND register.
   Report the sponsor count. Never block search on a failed refresh — proceed with
   whatever cache exists.

3. **Discover — run ONLY the selected platforms.** For each key in
   `profile.platforms`, use the matching tool. If the required tool is not
   available in this session, **skip that platform and say so explicitly** — never
   fabricate or approximate its results.
   - `indeed` — Indeed MCP: `search_jobs(search=<query>, location=<loc>,
     country_code=<cc>, job_type="fulltime")` per query/location, then parse each
     result for title, company, location, job id, and apply link.
   - `linkedin` — LinkedIn scraper MCP `search_jobs` if available; otherwise
     Playwright MCP on the user's logged-in LinkedIn Jobs search results. Extract
     title, company, location, stable job id, and URL.
   - `naukri` — Playwright MCP on the Naukri search results page; extract the same
     fields.
   - `career_pages` — Playwright MCP on company career sites (dismiss cookie
     banners by declining; use the site search box when present, else scan the
     listing page). Tag results with the company and `source: "career_pages"`.
   - `greenhouse_lever` — Playwright MCP on Greenhouse/Lever boards (keyword search
     + department filters).
   Build ONE combined list of raw listing dicts, each with at least
   `{source, company, role, location, url, job_id, posted_date}`. Use the user's
   `target_locations` for location filters and derive role queries from their
   target titles.

4. **Filter, dedupe, and rank (deterministic).** Write the combined raw list to a
   temp JSON file, e.g. `$JOB_HUNT_HOME/output/.search_raw.json`, then run:
   `python -m search.search_cli filter-dedupe-rank --listings-file <that file>`
   (add `--drop-unknown` only if the user wants a strict sponsors-only list). This
   annotates each company with the profile's work-auth provider, gates/drops per
   the scheme, removes anything already in the tracker or already packaged, and
   ranks the rest. Read `new` (ranked) and `counts` from the JSON.

5. **Present the ranked table of NEW roles.** Show, in `new` order:

   | # | Company | Role | Location | Work-auth | Source | Apply |
   |---|---------|------|----------|-----------|--------|-------|
   | 1 | …       | …    | …        | confirmed | indeed | [link] |

   Use the `work_auth.status` for each row (e.g. confirmed / possible / not_found /
   flag / n/a). Note which platforms were skipped for lack of a tool. State the
   counts (found, after work-auth gate, duplicates removed, new).

6. **Hand off to `/job-tailor`.** Ask which roles to prepare packs for
   (e.g. "1,3", "all", or "sponsors-only"). For each chosen role, record it and
   invoke the tailoring flow — run the `cv-tailor` skill (the `/job-tailor`
   command) with that role's company, title, and job description (fetch the JD via
   the platform's detail tool: Indeed MCP `get_job_details`, or Playwright on the
   listing URL). In `scan` mode, skip this hand-off.

7. **Track.** For each presented (or chosen) role, record it so future runs dedupe
   it:
   `python -m search.search_cli track --company "<C>" --role "<R>" --url "<url>"
   --job-id "<id>" --work-auth "<status>" --source "<platform>" --status "discovered"`.

8. **Status on demand.** For `/job-search status`, run
   `python -m search.search_cli status` and present the counts by status and by
   work-auth flag.

## Rules

- Query ONLY the platforms in the profile. If a platform's tool is unavailable,
  skip it with an explicit note — never fake or approximate listings.
- Never fabricate a job, a company, or a work-auth status. Statuses come from the
  provider; a `not_found` sponsor is reported as such, never upgraded.
- Always filter/dedupe/rank through `search_cli` so the logic is consistent and the
  tracker/output packs are respected.
- Hand tailoring off to `/job-tailor`; this skill discovers and shortlists only.
- Never store or ask for passwords; the user authenticates their own platform
  sessions.
