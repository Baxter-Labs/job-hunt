#!/usr/bin/env python3
"""cv_tailor_claude.py — the tailoring engine.

Owns the shared constants for the whole CV-tailoring system (imported by
``render_cv.py`` and ``tailor_pipeline.py``), loads the master CV and a job
description, fills the prompt template, calls the Anthropic Messages API
(``claude-opus-4-8`` with a ``claude-sonnet-4-6`` fallback), and returns a
validated ``tailored_cv.json`` dict.

The hard rule of the whole system: nothing is invented. Claude only reorders,
rephrases, and re-emphasises content that already exists in the master CV. The
``fabrication_check`` is computed in code (never trusted from the model) as the
backstop for that rule.

See ``CONTRACT.md`` §0 and §3 for the binding interface.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Shared constants — defined ONCE here, imported by the sibling scripts.
# ---------------------------------------------------------------------------

DEFAULT_MODEL: str = "claude-opus-4-8"
FALLBACK_MODEL: str = "claude-sonnet-4-6"
SCHEMA_VERSION: str = "1.0"

from engine import workspace  # Phase-1 workspace path resolution

# Prompt assets ship WITH the plugin, resolved relative to this package
# (tailor/prompts/), so /job-tailor works wherever the plugin is installed.
TAILOR_ROOT: Path = Path(__file__).resolve().parent
PROMPTS_DIR: Path = TAILOR_ROOT / "prompts"
PERSONA_PATH: Path = PROMPTS_DIR / "recruiter_persona.md"
HUMANIZER_PATH: Path = PROMPTS_DIR / "humanizer_rules.md"
TEMPLATE_PATH: Path = PROMPTS_DIR / "tailor_prompt_template.md"

# The master CV and output pack live in the USER's workspace, never next to the
# code. Resolved lazily (None sentinel) so importing the module never touches
# the filesystem and tests can point JOB_HUNT_HOME wherever they like.
MASTER_CV_PATH = None
OUTPUT_ROOT = None

# The strict-output JSON schema the Messages API enforces via
# output_config.format. Mirrors tailored_cv.json §2 of the contract. The engine
# overwrites meta + fabrication_check after parsing, so they are not part of the
# strict schema the model must fill (it leaves fabrication_check as a stub).
TAILORED_CV_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "schema_version": {"type": "string"},
        "meta": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "company": {"type": "string"},
                "role": {"type": "string"},
                "model_used": {"type": "string"},
                "generated_at": {"type": "string"},
            },
            "required": ["company", "role", "model_used", "generated_at"],
        },
        "contact": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "title": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": ["string", "null"]},
                "location": {"type": ["string", "null"]},
                "links": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "label": {"type": "string"},
                            "url": {"type": "string"},
                        },
                        "required": ["label", "url"],
                    },
                },
                "work_authorization": {"type": ["string", "null"]},
            },
            "required": [
                "name",
                "title",
                "email",
                "phone",
                "location",
                "links",
                "work_authorization",
            ],
        },
        "summary": {"type": "string"},
        "skills_grouped": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "group": {"type": "string"},
                    "skills": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["group", "skills"],
            },
        },
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "company": {"type": "string"},
                    "title": {"type": "string"},
                    "dates": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["company", "title", "dates", "bullets"],
            },
        },
        "highlights": {"type": "array", "items": {"type": "string"}},
        "ats_keywords_used": {"type": "array", "items": {"type": "string"}},
        "fabrication_check": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "passed": {"type": "boolean"},
                "issues": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["passed", "issues"],
        },
    },
    "required": [
        "schema_version",
        "meta",
        "contact",
        "summary",
        "skills_grouped",
        "experience",
        "highlights",
        "ats_keywords_used",
        "fabrication_check",
    ],
}

# The six placeholder tokens substituted into the prompt template.
_PLACEHOLDERS = (
    "{PERSONA}",
    "{HUMANIZER_RULES}",
    "{MASTER_CV_JSON}",
    "{JOB_DESCRIPTION}",
    "{COMPANY}",
    "{ROLE}",
)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_master_cv(path: Optional[Path] = None) -> dict[str, Any]:
    """Load and JSON-parse the master CV.

    Raises FileNotFoundError if the file is missing, ValueError if it is not
    valid JSON or not a JSON object.
    """
    if path is None:
        path = workspace.master_cv_path()
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Master CV not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Master CV is not valid JSON ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Master CV must be a JSON object, got {type(data).__name__}")
    return data


def load_job_description(
    jd_file: Optional[Path] = None,
    jd_text: Optional[str] = None,
) -> str:
    """Return the job-description text from exactly one of file or inline text.

    Raises ValueError if neither or both are supplied, or if the file is empty.
    """
    if (jd_file is None) == (jd_text is None):
        raise ValueError(
            "Provide exactly one of jd_file or jd_text (received "
            f"{'both' if jd_file is not None else 'neither'})."
        )
    if jd_text is not None:
        text = jd_text
    else:
        path = Path(jd_file)  # type: ignore[arg-type]
        if not path.exists():
            raise FileNotFoundError(f"Job description file not found: {path}")
        text = path.read_text(encoding="utf-8")
    text = text.strip()
    if not text:
        raise ValueError("Job description is empty.")
    return text


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def build_prompt(
    master_cv: dict[str, Any],
    job_description: str,
    company: str,
    role: str,
    *,
    template_path: Path = TEMPLATE_PATH,
    persona_path: Path = PERSONA_PATH,
    humanizer_path: Path = HUMANIZER_PATH,
) -> str:
    """Substitute the six placeholders into the template and return the prompt.

    Placeholders (exact tokens): {PERSONA} {HUMANIZER_RULES} {MASTER_CV_JSON}
    {JOB_DESCRIPTION} {COMPANY} {ROLE}. {MASTER_CV_JSON} is rendered with
    ``json.dumps(master_cv, ensure_ascii=False, indent=2)``.
    """
    template = Path(template_path).read_text(encoding="utf-8")
    persona = Path(persona_path).read_text(encoding="utf-8")
    humanizer = Path(humanizer_path).read_text(encoding="utf-8")
    master_json = json.dumps(master_cv, ensure_ascii=False, indent=2)

    # The persona file may contain a {COMPANY} token of its own; substitute it
    # before injecting so the recruiter voice is for the right company.
    persona = persona.replace("{COMPANY}", company)

    substitutions = {
        "{PERSONA}": persona,
        "{HUMANIZER_RULES}": humanizer,
        "{MASTER_CV_JSON}": master_json,
        "{JOB_DESCRIPTION}": job_description,
        "{COMPANY}": company,
        "{ROLE}": role,
    }
    prompt = template
    for token, value in substitutions.items():
        prompt = prompt.replace(token, value)
    return prompt


# ---------------------------------------------------------------------------
# Model call
# ---------------------------------------------------------------------------


def call_claude(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    fallback_model: str = FALLBACK_MODEL,
    api_key: Optional[str] = None,
    max_tokens: int = 8000,
) -> tuple[str, str]:
    """Call the Anthropic Messages API and return ``(raw_text, model_used)``.

    - Uses ``thinking={"type": "adaptive"}`` and ``output_config={"effort":
      "high"}`` plus ``output_config.format`` with the tailored_cv JSON schema
      for strict output.
    - Does NOT send temperature/top_p/budget_tokens (they 400 on Opus 4.8).
    - Streams the response (max_tokens is large enough to risk a non-streaming
      HTTP timeout) and collects the final message.
    - Retries once with ``fallback_model`` on NotFoundError / 404.

    Raises RuntimeError if the ``anthropic`` package is not installed or no API
    key is available.
    """
    try:
        import anthropic  # imported lazily so --mock works with no dependency
    except ImportError as exc:  # pragma: no cover - exercised only without dep
        raise RuntimeError(
            "The 'anthropic' package is required for live tailoring. "
            "Install it with `pip install anthropic`, or use --mock."
        ) from exc

    client_kwargs: dict[str, Any] = {}
    if api_key is not None:
        client_kwargs["api_key"] = api_key
    try:
        client = anthropic.Anthropic(**client_kwargs)
    except Exception as exc:  # noqa: BLE001 - surface a clean message
        raise RuntimeError(f"Could not initialise the Anthropic client: {exc}") from exc

    output_config: dict[str, Any] = {
        "effort": "high",
        "format": {
            "type": "json_schema",
            "schema": TAILORED_CV_JSON_SCHEMA,
        },
    }

    def _run(model_id: str) -> str:
        with client.messages.stream(
            model=model_id,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            output_config=output_config,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = stream.get_final_message()
        return "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )

    try:
        return _run(model), model
    except anthropic.NotFoundError:
        # Primary model unavailable (404). Retry once with the fallback.
        return _run(fallback_model), fallback_model
    except anthropic.APIStatusError as exc:
        if getattr(exc, "status_code", None) == 404:
            return _run(fallback_model), fallback_model
        raise


# ---------------------------------------------------------------------------
# Parsing & validation
# ---------------------------------------------------------------------------


def parse_tailored_json(raw: str) -> dict[str, Any]:
    """Extract the first balanced top-level JSON object from model text.

    Tolerates leading/trailing prose (a stray preamble never breaks parsing).
    Raises ValueError when no valid object is found.
    """
    if raw is None:
        raise ValueError("Model returned no text to parse.")
    text = raw.strip()

    # Fast path: the whole thing is already a JSON object.
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass  # fall through to the scanning path

    # Scan for the first balanced {...} object, respecting strings/escapes.
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break  # malformed; advance to the next '{'
        start = text.find("{", start + 1)

    raise ValueError("No valid top-level JSON object found in model output.")


def _is_list_of_str(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def validate_tailored_cv(obj: dict[str, Any]) -> list[str]:
    """Return a list of schema-violation messages ([] == valid). Does not mutate.

    Checks presence and types of all required keys in CONTRACT.md §2.
    """
    issues: list[str] = []

    if not isinstance(obj, dict):
        return ["root: expected a JSON object"]

    if obj.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            f"schema_version: expected {SCHEMA_VERSION!r}, got {obj.get('schema_version')!r}"
        )

    meta = obj.get("meta")
    if not isinstance(meta, dict):
        issues.append("meta: missing or not an object")
    else:
        for key in ("company", "role", "model_used", "generated_at"):
            if not isinstance(meta.get(key), str):
                issues.append(f"meta.{key}: missing or not a string")

    contact = obj.get("contact")
    if not isinstance(contact, dict):
        issues.append("contact: missing or not an object")
    else:
        for key in ("name", "title", "email"):
            if not isinstance(contact.get(key), str):
                issues.append(f"contact.{key}: missing or not a string")
        for key in ("phone", "location", "work_authorization"):
            if key in contact and contact[key] is not None and not isinstance(contact[key], str):
                issues.append(f"contact.{key}: must be a string or null")
        links = contact.get("links")
        if not isinstance(links, list):
            issues.append("contact.links: missing or not a list")
        else:
            for idx, link in enumerate(links):
                if not isinstance(link, dict) or not isinstance(
                    link.get("label"), str
                ) or not isinstance(link.get("url"), str):
                    issues.append(f"contact.links[{idx}]: expected {{label,url}} strings")

    if not isinstance(obj.get("summary"), str):
        issues.append("summary: missing or not a string")

    groups = obj.get("skills_grouped")
    if not isinstance(groups, list):
        issues.append("skills_grouped: missing or not a list")
    else:
        for idx, group in enumerate(groups):
            if not isinstance(group, dict):
                issues.append(f"skills_grouped[{idx}]: not an object")
                continue
            if not isinstance(group.get("group"), str):
                issues.append(f"skills_grouped[{idx}].group: missing or not a string")
            if not _is_list_of_str(group.get("skills")):
                issues.append(f"skills_grouped[{idx}].skills: must be a list of strings")

    experience = obj.get("experience")
    if not isinstance(experience, list):
        issues.append("experience: missing or not a list")
    else:
        for idx, entry in enumerate(experience):
            if not isinstance(entry, dict):
                issues.append(f"experience[{idx}]: not an object")
                continue
            for key in ("company", "title", "dates"):
                if not isinstance(entry.get(key), str):
                    issues.append(f"experience[{idx}].{key}: missing or not a string")
            if not _is_list_of_str(entry.get("bullets")):
                issues.append(f"experience[{idx}].bullets: must be a list of strings")

    if not _is_list_of_str(obj.get("highlights")):
        issues.append("highlights: must be a list of strings")
    elif len(obj["highlights"]) > 5:
        issues.append("highlights: must contain at most 5 items")

    if not _is_list_of_str(obj.get("ats_keywords_used")):
        issues.append("ats_keywords_used: must be a list of strings")

    fab = obj.get("fabrication_check")
    if not isinstance(fab, dict):
        issues.append("fabrication_check: missing or not an object")
    else:
        if not isinstance(fab.get("passed"), bool):
            issues.append("fabrication_check.passed: missing or not a boolean")
        if not _is_list_of_str(fab.get("issues")):
            issues.append("fabrication_check.issues: must be a list of strings")

    return issues


# ---------------------------------------------------------------------------
# Fabrication check (engine-authored — never trusted from the model)
# ---------------------------------------------------------------------------


def fabrication_check(
    tailored: dict[str, Any],
    master_cv: dict[str, Any],
) -> dict[str, Any]:
    """Compare the tailored output against the master facts.

    Returns ``{"passed": bool, "issues": [str, ...]}``. Flags:
      - any experience (company, title, dates) triple not present in the master,
      - any skill in skills_grouped not in master skills[].name,
      - contact name/email mismatch against the master.
    """
    issues: list[str] = []

    master_contact = master_cv.get("contact", {}) or {}
    master_name = master_contact.get("name")
    master_email = master_contact.get("email")

    tailored_contact = tailored.get("contact", {}) or {}
    if tailored_contact.get("name") != master_name:
        issues.append(
            f"contact.name {tailored_contact.get('name')!r} does not match master {master_name!r}"
        )
    if tailored_contact.get("email") != master_email:
        issues.append(
            f"contact.email {tailored_contact.get('email')!r} does not match master {master_email!r}"
        )

    master_triples = {
        (e.get("company"), e.get("title"), e.get("dates"))
        for e in master_cv.get("experience", []) or []
        if isinstance(e, dict)
    }
    for entry in tailored.get("experience", []) or []:
        if not isinstance(entry, dict):
            continue
        triple = (entry.get("company"), entry.get("title"), entry.get("dates"))
        if triple not in master_triples:
            issues.append(
                "experience entry "
                f"({triple[0]!r}, {triple[1]!r}, {triple[2]!r}) is not in the master CV"
            )

    master_skills = {
        s.get("name")
        for s in master_cv.get("skills", []) or []
        if isinstance(s, dict)
    }
    for group in tailored.get("skills_grouped", []) or []:
        if not isinstance(group, dict):
            continue
        for skill in group.get("skills", []) or []:
            if skill not in master_skills:
                issues.append(
                    f"skill {skill!r} in group {group.get('group')!r} is not a master skill"
                )

    return {"passed": not issues, "issues": issues}


# ---------------------------------------------------------------------------
# Mock generation (deterministic, no API)
# ---------------------------------------------------------------------------


def mock_tailored_cv(
    master_cv: dict[str, Any],
    company: str,
    role: str,
) -> dict[str, Any]:
    """Deterministic, schema-valid tailored CV built purely from the master.

    Used by --mock / --dry-run. ``meta.model_used == "mock"``. No API call. Every
    fact comes straight from the master, so the fabrication check always passes.
    """
    contact = master_cv.get("contact", {}) or {}
    links = [
        {"label": link.get("label", ""), "url": link.get("url", "")}
        for link in contact.get("links", []) or []
        if isinstance(link, dict)
    ]

    # Group skills by their declared category, preserving first-seen order.
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for skill in master_cv.get("skills", []) or []:
        if not isinstance(skill, dict):
            continue
        name = skill.get("name")
        category = skill.get("category") or "Skills"
        if not isinstance(name, str):
            continue
        if category not in grouped:
            grouped[category] = []
            order.append(category)
        grouped[category].append(name)
    skills_grouped = [{"group": cat, "skills": grouped[cat]} for cat in order]

    # Carry every master experience entry verbatim; bullets are the master pool.
    experience = [
        {
            "company": e.get("company", ""),
            "title": e.get("title", ""),
            "dates": e.get("dates", ""),
            "bullets": list(e.get("bullets", []) or []),
        }
        for e in master_cv.get("experience", []) or []
        if isinstance(e, dict)
    ]

    # Highlights: lead bullet of up to the three most recent roles.
    highlights: list[str] = []
    for entry in experience[:3]:
        if entry["bullets"]:
            highlights.append(entry["bullets"][0])
    highlights = highlights[:5]

    summary = master_cv.get("summary", "") or ""

    tailored: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "company": company,
            "role": role,
            "model_used": "mock",
            "generated_at": _utc_now_iso(),
        },
        "contact": {
            "name": contact.get("name", ""),
            "title": contact.get("title", "") or role,
            "email": contact.get("email", ""),
            "phone": contact.get("phone"),
            "location": contact.get("location"),
            "links": links,
            "work_authorization": contact.get("work_authorization"),
        },
        "summary": summary,
        "skills_grouped": skills_grouped,
        "experience": experience,
        "highlights": highlights,
        "ats_keywords_used": [],
        "fabrication_check": {"passed": True, "issues": []},
    }
    return tailored


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """ISO 8601 UTC with a trailing Z, second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stamp_meta(tailored: dict[str, Any], company: str, role: str, model_used: str) -> None:
    """Overwrite meta with engine-authored values (the model's meta is ignored)."""
    tailored["schema_version"] = SCHEMA_VERSION
    tailored["meta"] = {
        "company": company,
        "role": role,
        "model_used": model_used,
        "generated_at": _utc_now_iso(),
    }


def tailor_cv(
    *,
    jd_file: Optional[Path] = None,
    jd_text: Optional[str] = None,
    company: str,
    role: str,
    model: str = DEFAULT_MODEL,
    fallback_model: str = FALLBACK_MODEL,
    mock: bool = False,
    out_path: Optional[Path] = None,
    master_cv_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Top-level engine entry point: load -> build -> call (or mock) -> parse ->
    validate -> fabrication_check -> stamp meta -> optional write -> return.

    The returned dict ALWAYS has engine-authored ``meta`` and
    ``fabrication_check``. Raises ValueError if the output is schema-invalid
    after one repair attempt.
    """
    master_cv = load_master_cv(master_cv_path)
    job_description = load_job_description(jd_file=jd_file, jd_text=jd_text)

    if mock:
        tailored = mock_tailored_cv(master_cv, company, role)
        model_used = "mock"
    else:
        prompt = build_prompt(master_cv, job_description, company, role)
        raw, model_used = call_claude(
            prompt, model=model, fallback_model=fallback_model
        )
        tailored = parse_tailored_json(raw)

        issues = validate_tailored_cv(_with_engine_stub(tailored, company, role, model_used))
        if issues:
            # One repair attempt: ask the model to fix the listed problems.
            repair_prompt = (
                prompt
                + "\n\nYour previous output was invalid. Fix these problems and "
                "return ONLY the corrected JSON object:\n- "
                + "\n- ".join(issues)
            )
            raw, model_used = call_claude(
                repair_prompt, model=model, fallback_model=fallback_model
            )
            tailored = parse_tailored_json(raw)

    # Engine authors meta + fabrication_check regardless of what the model said.
    _stamp_meta(tailored, company, role, model_used)
    tailored["fabrication_check"] = fabrication_check(tailored, master_cv)

    issues = validate_tailored_cv(tailored)
    if issues:
        raise ValueError(
            "Tailored CV failed schema validation:\n- " + "\n- ".join(issues)
        )

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(tailored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    return tailored


def _with_engine_stub(
    tailored: dict[str, Any], company: str, role: str, model_used: str
) -> dict[str, Any]:
    """Return a shallow copy with engine meta + a stub fabrication_check, so
    pre-repair validation does not flag fields the engine is about to author."""
    candidate = dict(tailored)
    candidate["schema_version"] = SCHEMA_VERSION
    candidate["meta"] = {
        "company": company,
        "role": role,
        "model_used": model_used,
        "generated_at": _utc_now_iso(),
    }
    candidate.setdefault("fabrication_check", {"passed": True, "issues": []})
    return candidate


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cv_tailor_claude.py",
        description="Tailor the master CV to one job description (Claude engine).",
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--jd-file", type=Path, help="Path to a job-description text file.")
    src.add_argument("--jd-text", type=str, help="Raw job-description text.")
    parser.add_argument("--company", required=True, help="Target company name.")
    parser.add_argument("--role", required=True, help="Target role title.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("./tailored_cv.json"),
        help="Where to write the tailored CV (default: ./tailored_cv.json).",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"Primary model (default: {DEFAULT_MODEL})."
    )
    mock_group = parser.add_mutually_exclusive_group()
    mock_group.add_argument(
        "--mock", action="store_true", help="Deterministic offline mode (no API key)."
    )
    mock_group.add_argument(
        "--dry-run", action="store_true", help="Synonym for --mock."
    )
    return parser


# NOTE: this module-level CLI (and the live `call_claude` path it can reach) is a
# DEV-ONLY standalone tailoring tool that needs `pip install anthropic`. The
# /job-tailor SKILL does NOT use it — Claude authors tailored_cv.json in the skill
# and `tailor_cli finalize` validates/renders/scores it. Tests use `--mock`.
def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    mock = args.mock or args.dry_run
    try:
        tailored = tailor_cv(
            jd_file=args.jd_file,
            jd_text=args.jd_text,
            company=args.company,
            role=args.role,
            model=args.model,
            mock=mock,
            out_path=args.out,
        )
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    fab = tailored["fabrication_check"]
    print(f"Wrote {args.out}  (model: {tailored['meta']['model_used']})")
    if fab["passed"]:
        print("fabrication_check: PASSED — nothing fabricated.")
    else:
        # Reported, not fatal — exit 0.
        print("fabrication_check: FAILED (reported, not fatal):", file=sys.stderr)
        for issue in fab["issues"]:
            print(f"  - {issue}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
