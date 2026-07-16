# Using Job Hunt in other AI agents

Job Hunt is built as a Claude Code plugin, but there's nothing Claude-Code-
specific about the engine underneath it: it's Python CLIs in
`plugins/job-hunt/scripts/` plus plain-markdown instructions in
`plugins/job-hunt/skills/*/SKILL.md`. Any AI coding agent that can run shell
commands can clone this repo, install the one required dependency, and use
the same engine. This page is the practical "use it anywhere" guide; see
[AGENTS.md](../AGENTS.md) for the full command catalog an agent should follow.

## What works where

| Platform | How you point the agent at it | MCP-based search/apply (`/job-search`, `/job-apply`) |
|---|---|---|
| **Claude Code** | `/plugin marketplace add Baxter-Labs/job-hunt` then `/plugin install job-hunt` — commands and skills auto-load. | Available if you've connected an Indeed MCP / LinkedIn scraper MCP / Playwright MCP as Claude Code MCP servers. |
| **Codex CLI** | Clone the repo and `cd` into it; Codex CLI reads `AGENTS.md` from the working directory by convention. | Available only if you configure the equivalent MCP servers in Codex CLI's own MCP config; otherwise those two features are skipped. |
| **Cursor** | Clone/open the repo as a workspace; `.cursor/rules/job-hunt.mdc` loads automatically and points the agent at `AGENTS.md` + the relevant `SKILL.md`. | Available only if you configure the equivalent MCP servers in Cursor's MCP settings; otherwise skipped. |
| **opencode** | Clone the repo and open it; opencode reads `AGENTS.md` by convention, same as Codex CLI. | Available only if you configure the equivalent MCP servers in opencode's MCP config; otherwise skipped. |
| **Any AI agent with shell access** | Clone the repo, `pip install -r plugins/job-hunt/scripts/requirements.txt`, then paste the contents of the relevant `plugins/job-hunt/skills/<name>/SKILL.md` into the agent's instructions (system prompt / task description) and let it run the `python -m <pkg>.<cli>` commands from `plugins/job-hunt/scripts/`. | Available only if that agent has its own equivalent of a job-board API/scraper and a browser automation tool wired up; otherwise skipped. |

## Per-platform setup

### Claude Code

```
/plugin marketplace add Baxter-Labs/job-hunt
/plugin install job-hunt
```

Then install the one required Python dependency (`pypdf`) into the Python
you'll use — see the [README's Setup section](../README.md#setup-one-time).
Run `/job-setup` to get started. This is the most integrated experience:
commands, skills, and prompt assets all auto-load, and Claude Code's own MCP
connectors provide `/job-search` and `/job-apply` if you've set them up.

### Codex CLI

```bash
git clone <this-repo>
cd job-hunt
python3 -m venv .venv
.venv/bin/pip install -r plugins/job-hunt/scripts/requirements.txt
```

Codex CLI reads `AGENTS.md` from the repo root automatically once you're
working inside it — follow that file's command catalog and let it open the
relevant `SKILL.md` per capability. For `/job-search` and `/job-apply`,
configure the equivalent MCP servers (job-board search, browser automation)
in your `~/.codex` configuration; without them, ask for offline features
instead (`job-setup`, `cv-tailor`, `job-upskill`, `job-redflag`,
`job-followup`, `interview-prep`, `job-track`).

### Cursor

Clone (or open) this repo as a Cursor workspace:

```bash
git clone <this-repo>
cd job-hunt
python3 -m venv .venv
.venv/bin/pip install -r plugins/job-hunt/scripts/requirements.txt
```

`.cursor/rules/job-hunt.mdc` loads automatically and tells Cursor's agent to
read `AGENTS.md` and the matching `SKILL.md` before acting, and to run the
Python CLIs from `plugins/job-hunt/scripts/`. For `/job-search` and
`/job-apply`, configure the equivalent MCP servers in Cursor's MCP settings
(Settings → MCP); without them, those two features are unavailable and
should be skipped rather than faked.

### Generic / any AI agent with shell access

```bash
git clone <this-repo>
cd job-hunt
python3 -m venv .venv
.venv/bin/pip install -r plugins/job-hunt/scripts/requirements.txt
```

Open the `SKILL.md` for the capability you want (e.g.
`plugins/job-hunt/skills/cv-tailor/SKILL.md`) and paste its contents as the
agent's instructions for that task, along with `AGENTS.md` for the workspace
model and safety rules. The agent then runs the same `python -m <pkg>.<cli>`
commands documented there, from `plugins/job-hunt/scripts/`, using the venv
Python. This works with essentially any agent that can execute shell
commands and read files — the engine doesn't know or care what's driving it.

## The honest take

Claude Code is the most integrated experience: the plugin installs in two
commands, commands/skills auto-load, prompt assets resolve via
`${CLAUDE_PLUGIN_ROOT}`, and Claude Code's MCP connectors are typically
already wired up for search/apply. Everywhere else, setup is more manual —
you clone the repo, install one Python dependency, and either rely on
`AGENTS.md`/`.cursor/rules` auto-loading or paste a `SKILL.md` in yourself —
but it's the *same deterministic engine* underneath, and the offline
features (tailoring, ATS scoring, red-flag scanning, upskilling, interview
prep, follow-up drafting, application tracking) work identically everywhere
Python runs.

## Which features need external tools

- **Offline, Python-only — works in any agent:** `job-setup` (workspace +
  profile + CV import), `cv-tailor`/`/job-tailor` (fabrication-checked
  tailored CV + cover letter + ATS score), `job-upskill` (missing-keyword gap
  analysis), `job-redflag` (JD red-flag scan), `job-followup` (follow-up
  email draft — never sent), `interview-prep` (grounded talking points),
  `job-track` (text summary; the optional Flask dashboard is also local-only
  and needs no MCP, just `pip install flask`).
- **MCP-dependent — needs the host agent's own tool config:** `job-search`
  (needs a job-board search tool, e.g. an Indeed MCP or LinkedIn scraper MCP,
  or Playwright for career pages / Naukri / Greenhouse-Lever) and
  `job-apply` (needs a Playwright MCP or equivalent browser automation to
  open the apply page, prefill fields, and attach files). If the required
  tool isn't available in a given session, the skill instructions say to
  skip that platform/feature and report it explicitly — never fabricate a
  listing or an apply action.
- **`job-pipeline` — MCP-dependent for discovery and apply, offline in
  between:** it chains `/job-search`'s discovery step (same job-board
  search / browser-automation tools as above) into fit-scoring, top-N
  selection, auto-tailoring, and readiness-scoring, which are all offline
  and deterministic; it hands off to assisted `/job-apply` (same browser
  automation) for every send. If a profile platform's search tool is
  unavailable in the session, `job-pipeline` skips that platform with an
  explicit note rather than faking results — it never fabricates a listing,
  a JD, or an apply action, and the user still approves every send.
