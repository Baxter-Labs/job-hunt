---
name: job-apply
description: Assisted apply for a tailored pack. Shows the pack's ATS match score + top missing keywords BEFORE anything opens, then uses the Playwright MCP to open the apply URL, prefill safe contact fields (name/email/phone/links), and attach the tailored CV + cover letter. STOPS at any CAPTCHA, login, or consent step and hands control to the user. NEVER stores or types passwords. Submit stays manual unless the profile's apply_prefs.auto_submit_simple_forms opt-in is on (simple no-CAPTCHA/login/consent forms only). Use when the user wants to apply to a role they have already tailored.
---

# Job Apply (assisted)

Apply to ONE role the user has already tailored a pack for. This skill is
**assisted, not autonomous**: Claude drives the browser with the **Playwright
MCP**, but the human stays in control of every irreversible step. The deterministic
Python (`apply_cli`) assembles the ATS summary, the safe prefill map, and the
auto-submit gate; **the browser work is done here in the skill, never in Python.**

## Paths

- Scripts dir: `${CLAUDE_PLUGIN_ROOT}/scripts`
- Run the CLI as `python -m apply.apply_cli <subcommand>` from that scripts dir,
  using the venv Python from the repo README (stdlib only for apply).
- The workspace is `$JOB_HUNT_HOME` (default `~/.job-hunt`). Do not hardcode paths.

## Non-negotiable safety rules

- **Never store, type, or ask for a password, credential, token, or 2FA code.**
  The user authenticates their own accounts. If a field asks for a secret, STOP.
- **Stop conditions (hand control back to the user immediately):** any **CAPTCHA**
  or bot-check, any **login / SSO / authentication** step, any **consent / terms /
  cookie** acceptance, or any field asking for sensitive personal data (government
  ID, bank details, salary you did not authorise). Never solve a CAPTCHA. Never
  accept terms on the user's behalf.
- **Submit is irreversible.** Confirm with the user before clicking submit — unless
  the profile durably authorised it via `apply_prefs.auto_submit_simple_forms`, and
  then only on a simple form with NO CAPTCHA/login/consent. Even then, halt at any
  CAPTCHA/login/consent and never enter credentials.

## Steps

1. **Show the ATS score FIRST (required).** Run
   `python -m apply.apply_cli preapply --pack "<company-slug>-<role-slug>"`.
   Read `ats_score`, `missing_keywords`, `prefill_fields`, `attachments`,
   `warnings`, and `auto_submit`. Present the ATS match score and the top missing
   keywords to the user **before opening anything**, and ask whether to proceed or
   re-tailor (`/job-tailor`). If the pack is missing or has no `ats_report.json`,
   say so and stop — never invent a score.

2. **Open the apply page (Playwright MCP).** Navigate to the role's apply URL.
   If the Playwright MCP is unavailable, say so and stop — never fake an apply.

3. **Prefill safe fields only.** Fill the form fields that map to `prefill_fields`
   (name, email, phone, location, LinkedIn/GitHub/website). Skip anything not in
   that safe map. Never fill a password or secret.

4. **Attach the pack files.** Attach `attachments.cv` (tailored CV) and, where the
   form allows, `attachments.cover_letter`.

5. **Halt at the first stop condition.** The moment the flow reaches a CAPTCHA,
   login, consent/terms step, or a sensitive-data field, STOP and hand control to
   the user with a clear note of what is needed.

6. **Submit — manual by default.** If no stop condition was hit and the user
   confirms (or `auto_submit.allowed` is true from the CLI, meaning the opt-in
   toggle is on and any ATS threshold is met), click submit. Otherwise leave the
   filled form for the user to review and submit themselves.

7. **Record it.** After a submit (or after preparing the form for the user), run
   `python -m apply.apply_cli record --company "<C>" --role "<R>" --status applied
   --url "<apply_url>" --source "<platform>"` (use `--status prepared` if you only
   prefilled and the user will submit). This updates the workspace tracker.

## Rules

- ATS score is shown before opening/prefilling, every time.
- Never store or type passwords; the user authenticates their own accounts.
- Stop at every CAPTCHA/login/consent; submit is confirmed unless durably
  authorised by `apply_prefs.auto_submit_simple_forms`.
- Never fabricate an application, a confirmation, or an ATS score.
