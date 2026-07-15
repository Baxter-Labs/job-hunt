---
name: job-followup
description: Draft a follow-up email for one application, grounded in the workspace tracker row and the tailored pack's ATS context (assembled by the deterministic insights CLI). The skill writes the DRAFT only; it NEVER sends anything — the user reviews and sends it themselves. No credentials, no mail, no network in the Python. Use when the user wants to follow up on a role they applied to.
---

# Job Follow-Up (draft only)

Draft a short, specific follow-up email for one role the user applied to. The
factual context — application status, date applied, source, whether a pack
exists, the ATS score — is assembled deterministically by
`insights/followup.py`. This skill writes the DRAFT and hands it back.

## Non-negotiable safety rule

- **This skill NEVER sends email and never opens a mail client, MCP, or
  network connection to send.** It produces a draft in the chat for the user to
  copy, review, edit, and send themselves. Never ask for or handle email
  credentials.

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- Run the CLI as `python -m insights.insights_cli <subcommand>` from that scripts
  dir, using the venv Python from the repo README. The workspace is
  `$JOB_HUNT_HOME` (default `~/.job-hunt`). Do not hardcode paths.

## Steps

1. **Assemble context.** Run
   `python -m insights.insights_cli followup-context --company "<C>" --role "<R>"`.
   It prints one JSON object:
   `{"ok": true, "company", "role", "status", "date_applied", "url", "source",
   "has_pack", "ats_score"}`.

2. **Sanity-check status.** If `status` is empty or not `applied`, tell the user
   the tracker doesn't show this role as applied yet, and suggest confirming
   before following up. Use `date_applied` to judge whether enough time has
   passed for a follow-up.

3. **Draft the email.** Write a concise, specific follow-up: reference the role
   and company, note the application date if present, reaffirm one or two
   genuine strengths (grounded in the pack, not invented), and a polite ask.
   Present it as a ready-to-copy draft.

4. **Hand it back — do NOT send.** Explicitly tell the user this is a draft for
   them to review and send themselves.

## Rules

- Never send anything; drafts only. The user reviews and sends.
- Never handle email credentials or any secret.
- Ground the draft in the assembled context; do not fabricate an application
  date, a status, or a strength the pack doesn't support.
