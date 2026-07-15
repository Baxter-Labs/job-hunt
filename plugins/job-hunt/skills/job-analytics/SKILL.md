---
name: job-analytics
description: Report the application-outcome funnel from the tracker — counts and rates for applied → response → interview → offer, broken down by source (platform), work-auth flag, and ATS band (<50 / 50–69 / 70+), with deterministic plain-language takeaways. Also records outcomes (log-outcome) using the documented status vocabulary. Read-mostly and offline; the Python computes the funnel, the skill coaches. Honest about small samples — never over-claims on tiny N. Use to see what is converting and what to do more or less of.
---

# Job Analytics

Show the user how their applications are converting — and coach them on what to do
more or less of — using the **deterministic** funnel computed by
`insights/analytics.py`. This skill runs the CLI, explains the numbers, and stays
honest: with few applications the signal is weak, and the skill says so rather than
inventing a trend.

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- Run the CLIs from that scripts dir with the venv Python from the repo README
  (stdlib only). Do not hardcode paths. The tracker is `$JOB_HUNT_HOME/tracker.csv`
  and packs live under `$JOB_HUNT_HOME/output/`.

## Status vocabulary (documented)

Ordered set: `not_applied`, `pack_generated`, `applied`, `response`, `interview`,
`offer`, `rejected`, `ghosted`. `applied` and everything beyond it (including the
terminal negatives `rejected`/`ghosted`) count as "applied" in the funnel;
`response`/`interview`/`offer` are the positive progressions.

## Modes (parse the argument after `/job-analytics`)

| Argument | Action |
|----------|--------|
| *(none)* | Show the funnel report |
| `log <company> / <role> / <status>` | Record an outcome, then show the funnel |

## Steps

1. **Record an outcome (only when asked to `log`).** Run
   `python -m search.search_cli log-outcome --company "<C>" --role "<R>" --status "<S>"`
   where `<S>` is one of the vocabulary above. If the CLI returns
   `{"ok": false, ...}` (unknown status), show the error and the valid statuses;
   never invent a status.

2. **Compute the funnel.** Run `python -m insights.insights_cli analytics`. It
   prints one JSON object:
   `{"ok": true, "min_takeaway_n": N, "overall": {...}, "by_source": {...}, "by_work_auth": {...}, "by_ats_band": {...}, "takeaways": [...]}`.
   If `ok` is false, show the error and stop — never fabricate numbers.

3. **Present the funnel.** Show `overall` as applied → response → interview → offer
   with each rate as a percentage. Then show the breakdowns (`by_source`,
   `by_work_auth`, `by_ats_band`) as short tables. The ATS bands are `<50`,
   `50-69`, `70+`, and `unknown` (roles with no pack/ATS report).

4. **Coach from the takeaways.** Read the `takeaways` verbatim — they are the only
   claims the deterministic layer will stand behind (each is gated on a minimum
   sample of `min_takeaway_n` applications per compared group). Translate them into
   next actions: which platform to lean into, whether higher-ATS tailors convert
   better, where the funnel leaks.

5. **Be honest about small samples.** If `overall.applied` is small (roughly below
   `min_takeaway_n`, or `takeaways` is empty), say plainly that there is not enough
   data yet to draw conclusions — report the raw counts and suggest logging more
   outcomes, rather than reading a trend into a handful of applications.

## Rules

- Read-mostly and offline: the only write is a tracker row via `log-outcome`; never
  calls the network. Report the numbers the CLI returned; never inflate a rate.
- Never fabricate outcomes, rates, or takeaways — show only what the tracker and the
  deterministic funnel produce.
- Honesty on small N: no over-claiming. When the sample is thin, say so.
