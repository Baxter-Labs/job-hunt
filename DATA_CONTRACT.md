# Data Contract

Job Hunt's engine is deterministic Python; the content inside several of its
JSON artifacts is authored by Claude (inside a skill) and then validated by
that Python. This document is the contract between the two: every workspace
artifact's schema, exactly as the code enforces it.

If this document and the code ever disagree, the code wins — the modules
named below are the source of truth. `schema_version` is `"1.0"` for every
artifact below.

## Workspace layout

All personal data lives outside the plugin's code, in a workspace rooted at
`$JOB_HUNT_HOME` (default `~/.job-hunt/`), resolved by
`plugins/job-hunt/scripts/engine/workspace.py`:

```
$JOB_HUNT_HOME/
  profile.json          # engine/profile.py
  cv_master.json         # engine/cv_import.py
  tracker.csv             # search/tracker.py
  output/<company>-<role>/
    tailored_cv.json      # tailor/tailor_engine.py
    ats_report.json       # tailor/ats.py
    cv.pdf / cv.html
    cover_letter.*
  jd_queue/
```

`output/<company>-<role>/` uses the slug from `search/listing.py`'s
`pack_slug()` (`slugify(company)-slugify(role)`), so a search-time dedupe key
and a tailor-time output directory always line up.

---

## `profile.json`

Validated by `validate_profile()` in
`plugins/job-hunt/scripts/engine/profile.py`. Default shape from
`default_profile()`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | must equal `"1.0"` |
| `contact.name` | string | yes | non-empty |
| `contact.email` | string | yes | non-empty |
| `contact.phone` | string \| null | no | |
| `contact.location` | string \| null | no | |
| `contact.links` | array | no | not type-checked beyond being a list |
| `target_locations` | array of string | no | if present, must be a list of strings |
| `platforms` | array | yes | non-empty; every entry must be in `PLATFORMS` |
| `work_auth.needs_sponsorship` | boolean | yes | |
| `work_auth.scheme` | string | yes | must be in `SCHEMES` |
| `language_constraints.english_only` | boolean | no | not independently validated |
| `apply_prefs.auto_submit_simple_forms` | boolean | no | not independently validated |

`PLATFORMS` (`engine/profile.py`): `linkedin`, `indeed`, `naukri`,
`career_pages`, `greenhouse_lever`.

`SCHEMES` (`engine/profile.py`): `nl-ind-hsm`, `eu-blue-card`, `none`.

Example: `templates/profile.example.json` (placeholder contact only — never
real personal data).

---

## `cv_master.json`

Validated by `validate_master_cv()` in
`plugins/job-hunt/scripts/engine/cv_import.py`. Built by Claude from your CV
PDF(s) during `/job-setup` (PDF text extraction is
`extract_pdf_text()`, deterministic; the text-to-structure step is Claude's).

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | must equal `"1.0"` |
| `contact.name` | string | yes | non-empty |
| `contact.title` | string | yes | non-empty |
| `contact.email` | string | yes | non-empty |
| `summary` | string | yes | |
| `skills` | array of object | yes | each item needs `name` (string) |
| `experience` | array of object | yes | each item needs `company`, `title`, `dates` (strings) and `bullets` (list of strings) |
| `education` | array | no | must be a list if present |
| `projects` | array | no | must be a list if present |
| `certifications` | array | no | must be a list if present |
| `languages` | array | no | must be a list if present |

`skills[]` and `experience[]` are also the ground truth the fabrication check
compares tailored output against — see `tailored_cv.json` below.

Example: `templates/cv_master.example.json`.

---

## `tailored_cv.json`

Authored by Claude inside the `/job-tailor` skill against the strict JSON
schema `TAILORED_CV_JSON_SCHEMA`, then validated by `validate_tailored_cv()`
— both in `plugins/job-hunt/scripts/tailor/tailor_engine.py`. `meta` and
`fabrication_check` are always overwritten by the engine after generation
(`_stamp_meta()` / `fabrication_check()`), never trusted from the model.

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | must equal `"1.0"` |
| `meta.company` | string | yes | engine-authored |
| `meta.role` | string | yes | engine-authored |
| `meta.model_used` | string | yes | engine-authored (e.g. `claude-opus-4-8`, or `"mock"`) |
| `meta.generated_at` | string | yes | engine-authored, ISO 8601 UTC with trailing `Z` |
| `contact.name` | string | yes | |
| `contact.title` | string | yes | |
| `contact.email` | string | yes | |
| `contact.phone` | string \| null | yes (key must be present) | |
| `contact.location` | string \| null | yes (key must be present) | |
| `contact.links` | array of `{label, url}` | yes | both `label` and `url` are strings |
| `contact.work_authorization` | string \| null | yes (key must be present) | |
| `summary` | string | yes | |
| `skills_grouped` | array of `{group, skills}` | yes | `group` is a string, `skills` a list of strings |
| `experience` | array of `{company, title, dates, bullets}` | yes | `bullets` is a list of strings |
| `highlights` | array of string | yes | **max 5 items** |
| `ats_keywords_used` | array of string | yes | |
| `fabrication_check.passed` | boolean | yes | engine-authored |
| `fabrication_check.issues` | array of string | yes | engine-authored |

### Fabrication check

`fabrication_check(tailored, master_cv)` in `tailor_engine.py` recomputes
`fabrication_check` from scratch every time, in code, and flags:

- `contact.name` / `contact.email` not matching the master CV exactly,
- any `experience` entry whose `(company, title, dates)` triple is not
  present verbatim in the master CV's `experience[]`,
- any skill listed in `skills_grouped[].skills` that is not in the master
  CV's `skills[].name`.

`passed` is `true` only when `issues` is empty. This is what "nothing is
invented" means mechanically — see `LEGAL_DISCLAIMER.md` for what it does
and doesn't guarantee.

---

## `ats_report.json`

Built by `build_ats_report()` in `plugins/job-hunt/scripts/tailor/ats.py`
and written by `write_ats_report()` alongside the tailored pack.

| Field | Type | Notes |
|---|---|---|
| `company` | string | |
| `role` | string | |
| `total_keywords` | integer | count of JD keywords extracted (lexicon hits + salient mined terms, capped at `max_keywords`, default 40) |
| `matched_count` | integer | keywords found in the tailored CV's flattened text |
| `missing_count` | integer | `total_keywords - matched_count` |
| `match_score` | integer | `round(matched_count / total_keywords * 100)`; `0` when `total_keywords` is `0` |
| `matched_keywords` | array of string | preserves keyword order |
| `missing_keywords` | array of string | preserves keyword order |

`match_score` is computed by `ats_score(matched_count, total)` — see
`ats.py`. It is an honest keyword-coverage measurement against the job
description text, never a target the tailoring step is allowed to game by
inserting an unearned keyword.

---

## `tracker.csv`

Read/written by `plugins/job-hunt/scripts/search/tracker.py`. Fixed column
order, `FIELDNAMES`:

| Column | Notes |
|---|---|
| `discovered_date` | `YYYY-MM-DD`, set on first insert |
| `date_applied` | `YYYY-MM-DD`, set when `status` first becomes `"applied"` |
| `company` | |
| `role` | |
| `url` | |
| `status` | free-form string; e.g. `discovered`, `applied` are the two statuses the code treats specially |
| `work_auth_status` | one of the `WorkAuthProvider` `STATUSES` values, or `""` |
| `job_id` | platform job id, used for dedupe when present |
| `source` | platform key |
| `notes` | free-form |

`upsert()` matches an existing row by case-insensitive `(company, role)` OR
by matching `job_id`; on a match, only non-empty incoming fields overwrite
existing ones. `summarize()` returns `{total, by_status, by_work_auth}`
counts across all rows.

---

## `JobListing` (in-memory / search pipeline, not persisted standalone)

Canonicalised by `normalize_listing()` /
`normalize_listings()` in `plugins/job-hunt/scripts/search/listing.py`.
`CANONICAL_FIELDS`:

| Field | Notes |
|---|---|
| `source` | platform key, one of `profile.platforms` |
| `company` | |
| `role` | |
| `location` | |
| `url` | apply / listing URL |
| `job_id` | platform job id, stable where available |
| `posted_date` | `""` or ISO `YYYY-MM-DD` |
| `level` | optional seniority hint, e.g. `"senior"` |

All canonical fields are coerced to strings, stripped, and defaulted to
`""` when missing or `None`. Any extra keys the caller included are
preserved (not stripped). This is the shape every platform's raw scrape
must be normalised into before it enters the deterministic
annotate/filter/dedupe/rank pipeline in `search/search_cli.py` — a new
platform only needs to produce this shape.

---

## Insights CLI outputs (stdout, not persisted)

`plugins/job-hunt/scripts/insights/insights_cli.py` prints one JSON object per
subcommand and writes nothing to the workspace. These shapes are a stable
contract for the funnel skills (`/job-redflag`, `/job-upskill`,
`/job-followup`), documented here even though no file is created.

`red-flags` (`insights/redflags.py`, `scan_red_flags`):

| Field | Type | Notes |
|---|---|---|
| `ok` | boolean | `false` + `error` on failure |
| `count` | integer | `len(red_flags)` |
| `red_flags` | array of object | each `{flag, category, evidence, severity}` |

Each red flag: `flag` (stable slug, e.g. `vague-compensation`), `category` (one
of `compensation`, `culture`, `workload`, `benefits`, `hiring-process`,
`seniority`), `evidence` (the exact matched JD substring), `severity` (`low` /
`medium` / `high`). Advisory only — never a verdict.

`upskill` (`insights/upskill.py`, `aggregate_gaps`):

| Field | Type | Notes |
|---|---|---|
| `ok` | boolean | |
| `packs_scanned` | integer | number of packs with a readable `ats_report.json` |
| `gaps` | array of object | each `{keyword, count, roles}`, ranked by `count` desc then `keyword` asc |

Gaps are drawn from each pack's `ats_report.json` `missing_keywords` — the same
honest gaps `/job-tailor` reports, aggregated, never re-scored or inflated.

`followup-context` (`insights/followup.py`, `application_context`):

| Field | Type | Notes |
|---|---|---|
| `ok` | boolean | |
| `company` / `role` | string | echoed from the request |
| `status` / `date_applied` / `url` / `source` | string | from the matching `tracker.csv` row, `""` if none |
| `has_pack` | boolean | whether the pack has an `ats_report.json` |
| `ats_score` | integer \| null | the pack's `match_score`, or `null` |

This assembles context for a follow-up email DRAFT only. The Python never sends
anything.
