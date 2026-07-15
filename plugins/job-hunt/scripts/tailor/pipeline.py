#!/usr/bin/env python3
"""tailor/pipeline.py — pack assembly.

Ported from ``cv_system/scripts/tailor_pipeline.py``. Assembles the tailored
CV, rendered PDF/HTML, ATS report, and change log into the pack directory:

    $JOB_HUNT_HOME/output/<company-slug>-<role-slug>/
        ├── tailored_cv.json
        ├── cv.html
        ├── cv.pdf
        ├── ats_report.json
        └── change_log.md

The change log is the human's audit trail: it spells out what was emphasised
and reordered for this JD, the ATS match score + genuinely matched keywords,
the fabrication-check result, advisory humaniser flags, and the PDF backend
used.

``finalize_pack`` (Claude-authored ``tailored_cv``) and ``run_mock_pack``
(deterministic offline path) are the two entry points; the CLI that drives
them lives in ``tailor_cli.py``. ``finalize_pack`` FAILS LOUDLY (``ok: False``)
when the fabrication check fails or the schema is invalid — the human decides
what happens next, but the pipeline does not pretend the pack is safe to send.

See ``CONTRACT.md`` §5 for the binding interface.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

# Import the sibling modules cleanly whether invoked from the repo root, from the
# scripts/ directory, or as ``python plugins/job-hunt/scripts/tailor/pipeline.py``.
# The shared constants (DEFAULT_MODEL, HUMANIZER_PATH, ...) live in
# tailor_engine.py per CONTRACT.md §0 and are imported here, never redefined.
try:
    from tailor.tailor_engine import (
        DEFAULT_MODEL,
        HUMANIZER_PATH,
        SCHEMA_VERSION,
        tailor_cv,
        load_master_cv,
        fabrication_check,
        validate_tailored_cv,
        _stamp_meta,
    )
    from tailor.render_cv import render_cv
    from tailor.render_letter import render_letter
    from tailor import ats as ats_mod
except ImportError:  # running from an odd CWD — put scripts/ on the path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tailor.tailor_engine import (  # noqa: E402
        DEFAULT_MODEL, HUMANIZER_PATH, SCHEMA_VERSION, tailor_cv,
        load_master_cv, fabrication_check, validate_tailored_cv, _stamp_meta,
    )
    from tailor.render_cv import render_cv  # noqa: E402
    from tailor.render_letter import render_letter  # noqa: E402
    from tailor import ats as ats_mod  # noqa: E402

from engine import workspace  # noqa: E402


# ---------------------------------------------------------------------------
# Slug / pack-dir helpers
# ---------------------------------------------------------------------------


def slugify(value: str) -> str:
    """Lowercase; runs of non-alphanumerics become single hyphens; trim hyphens.

    ``'Booking.com' -> 'booking-com'``. Used for the pack folder name. Returns
    ``'untitled'`` when the input slugs to nothing (e.g. only punctuation).
    """
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "untitled"


def pack_dir_for(company: str, role: str, root: Optional[Path] = None) -> Path:
    """Return ``root / f'{slugify(company)}-{slugify(role)}'`` (not yet created).
    Defaults ``root`` to the user's workspace output dir."""
    if root is None:
        root = workspace.output_dir()
    return Path(root) / f"{slugify(company)}-{slugify(role)}"


# ---------------------------------------------------------------------------
# Humaniser ban-list scanning (advisory — never fails the run)
# ---------------------------------------------------------------------------

# The contract's minimum machine-scannable ban-list (CONTRACT.md §6). Used as a
# fallback if the ban-list cannot be parsed from humanizer_rules.md.
_MINIMUM_BAN_LIST: tuple[str, ...] = (
    "leverage",
    "delve",
    "tapestry",
    "moreover",
    "furthermore",
    "robust",
    "seamless",
    "in today's fast-paced",
    "testament",
    "underscore",
    "navigate the landscape",
)


def load_ban_list(humanizer_path: Path = HUMANIZER_PATH) -> list[str]:
    """Parse the machine-scannable ban-list from humanizer_rules.md.

    Extracts the backtick-quoted tokens that appear under the "BANNED PHRASES"
    section. Always merges in the contract minimum so the scan never silently
    weakens if the markdown is edited. Falls back to the minimum if the file is
    missing or unreadable.
    """
    tokens: set[str] = set(_MINIMUM_BAN_LIST)
    try:
        text = Path(humanizer_path).read_text(encoding="utf-8")
    except OSError:
        return sorted(tokens, key=len, reverse=True)

    # Scope to the "BANNED" section so the advisory wider-family prose (which is
    # comma-separated, not the hard ban) is not pulled in as exact-match tokens.
    lower = text.lower()
    start = lower.find("banned")
    section = text[start:] if start != -1 else text
    # Stop at the next top-level "## " heading after the banned section.
    next_heading = re.search(r"\n##\s", section[3:])
    if next_heading:
        section = section[: next_heading.start() + 3]

    for match in re.findall(r"`([^`]+)`", section):
        token = match.strip().lower()
        # Keep short, phrase-like tokens; skip code-ish noise.
        if token and len(token) <= 40 and not any(c in token for c in "{}()[]<>"):
            tokens.add(token)

    return sorted(tokens, key=len, reverse=True)


def _gather_tailored_text(tailored: dict[str, Any]) -> str:
    """Concatenate the human-written prose fields (summary + bullets +
    highlights) for ban-list scanning."""
    parts: list[str] = []
    summary = tailored.get("summary")
    if isinstance(summary, str):
        parts.append(summary)
    for entry in tailored.get("experience", []) or []:
        if isinstance(entry, dict):
            for bullet in entry.get("bullets", []) or []:
                if isinstance(bullet, str):
                    parts.append(bullet)
    for highlight in tailored.get("highlights", []) or []:
        if isinstance(highlight, str):
            parts.append(highlight)
    return "\n".join(parts)


def _token_present(token: str, lowered_text: str) -> bool:
    """True if a ban-list token occurs in ``lowered_text``.

    A single alphanumeric word (``leverage``, ``robust``) must match on word
    boundaries so legitimate words that merely contain it as a substring
    ("robustness testing", "underscored_name") are NOT falsely flagged. A
    multi-word or punctuated phrase ("in today's fast-paced", "navigate the
    landscape") is matched as a plain substring, which is what we want for the
    register tells. ``token`` is already lower-cased by ``load_ban_list``.
    """
    if re.fullmatch(r"[a-z0-9]+", token):
        return re.search(rf"\b{re.escape(token)}\b", lowered_text) is not None
    return token in lowered_text


def scan_humanizer_flags(
    tailored: dict[str, Any],
    *,
    humanizer_path: Path = HUMANIZER_PATH,
) -> list[str]:
    """Scan summary + bullets + highlights for banned tokens and em-dash overuse.

    Advisory only — surfaced in the change log, never fails the run. Returns a
    list of human-readable flag messages ([] == clean).
    """
    text = _gather_tailored_text(tailored)
    flags: list[str] = []

    lowered = text.lower()
    for token in load_ban_list(humanizer_path):
        if _token_present(token, lowered):
            flags.append(f'banned phrase: "{token}"')

    # Em-dash overuse: the rules cap at ~one em-dash per section; more than a few
    # across the whole document is worth flagging for review.
    em_dashes = text.count("—")
    if em_dashes > 3:
        flags.append(f"em-dash overuse: {em_dashes} em-dashes across the document")

    return flags


# ---------------------------------------------------------------------------
# Change log
# ---------------------------------------------------------------------------


def write_change_log(
    tailored: dict[str, Any],
    pack_dir: Path,
    *,
    pdf_backend: str,
    humanizer_flags: list[str],
    ats_report: Optional[dict[str, Any]] = None,
) -> Path:
    """Write change_log.md summarising the tailoring decisions for this JD.

    Covers: company/role, model used, what was emphasised/reordered, highlights,
    ATS match score (if ``ats_report`` is given), ATS keywords matched, the
    fabrication-check result (with an explicit "nothing fabricated" confirmation
    when it passes), advisory humaniser flags, and the PDF backend. Returns the
    written path.
    """
    pack_dir = Path(pack_dir)
    pack_dir.mkdir(parents=True, exist_ok=True)

    meta = tailored.get("meta", {}) or {}
    company = meta.get("company", "")
    role = meta.get("role", "")
    model_used = meta.get("model_used", "")
    generated_at = meta.get("generated_at", "")

    fab = tailored.get("fabrication_check", {}) or {}
    fab_passed = bool(fab.get("passed"))
    fab_issues = fab.get("issues", []) or []

    skills_grouped = tailored.get("skills_grouped", []) or []
    experience = tailored.get("experience", []) or []
    highlights = tailored.get("highlights", []) or []
    ats_keywords = tailored.get("ats_keywords_used", []) or []

    lines: list[str] = []
    lines.append(f"# Change log — {company} · {role}")
    lines.append("")
    lines.append(f"- **Generated:** {generated_at}")
    lines.append(f"- **Model:** {model_used}")
    lines.append(f"- **Schema version:** {tailored.get('schema_version', SCHEMA_VERSION)}")
    lines.append(f"- **PDF backend:** {pdf_backend}")
    lines.append("")

    # What was emphasised / reordered for this JD.
    lines.append("## What was emphasised and reordered for this JD")
    lines.append("")
    if skills_grouped:
        group_order = ", ".join(
            g.get("group", "") for g in skills_grouped if isinstance(g, dict)
        )
        lead_group = next(
            (g for g in skills_grouped if isinstance(g, dict)), None
        )
        lines.append(
            f"- Skills regrouped and ordered as: {group_order}."
        )
        if lead_group:
            lead_skills = ", ".join(lead_group.get("skills", []) or [])
            lines.append(
                f"  Lead group **{lead_group.get('group', '')}** surfaces: {lead_skills}."
            )
    if experience:
        exp_order = " → ".join(
            f"{e.get('title', '')} @ {e.get('company', '')}"
            for e in experience
            if isinstance(e, dict)
        )
        lines.append(f"- Experience ordered: {exp_order}.")
        for entry in experience:
            if not isinstance(entry, dict):
                continue
            bullets = entry.get("bullets", []) or []
            lead = bullets[0] if bullets else ""
            lines.append(
                f"  - **{entry.get('title', '')} @ {entry.get('company', '')}** "
                f"({entry.get('dates', '')}): {len(bullets)} bullet(s); "
                f"leads with — {lead}"
            )
    lines.append("")

    # Highlights.
    lines.append("## Highlights surfaced")
    lines.append("")
    if highlights:
        for highlight in highlights:
            lines.append(f"- {highlight}")
    else:
        lines.append("- (none)")
    lines.append("")

    # ATS keywords.
    lines.append("## ATS keywords genuinely matched")
    lines.append("")
    if ats_keywords:
        lines.append(", ".join(ats_keywords))
    else:
        lines.append("(none recorded)")
    lines.append("")

    # Fabrication check + explicit confirmation.
    lines.append("## Fabrication check")
    lines.append("")
    if fab_passed:
        lines.append(
            "**PASSED — nothing fabricated.** Every employer, job title, set of "
            "dates, and skill in this CV was selected, reordered, or rephrased "
            "from the master CV. No facts, metrics, or claims were invented."
        )
    else:
        lines.append(
            "**FAILED — review before sending.** The following items in the "
            "tailored CV do not match the master CV and may be fabricated:"
        )
        lines.append("")
        for issue in fab_issues:
            lines.append(f"- {issue}")
    lines.append("")

    # Humaniser flags (advisory).
    lines.append("## Humaniser flags (advisory — does not block sending)")
    lines.append("")
    if humanizer_flags:
        lines.append(
            "The following AI-tell patterns were detected and should be reviewed:"
        )
        lines.append("")
        for flag in humanizer_flags:
            lines.append(f"- {flag}")
    else:
        lines.append("None — no banned phrases or em-dash overuse detected.")
    lines.append("")

    # ATS match score (the headline readiness signal).
    lines.append("## ATS match score")
    lines.append("")
    if ats_report:
        lines.append(
            f"**{ats_report.get('match_score', 0)}%** — "
            f"{ats_report.get('matched_count', 0)} of "
            f"{ats_report.get('total_keywords', 0)} JD keywords matched."
        )
        missing = ats_report.get("missing_keywords", []) or []
        if missing:
            lines.append("")
            lines.append("Missing keywords (genuine gaps — do NOT fabricate to close them): "
                         + ", ".join(missing[:20]))
    else:
        lines.append("(not computed)")
    lines.append("")

    out_path = pack_dir / "change_log.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def finalize_pack(
    *,
    company: str,
    role: str,
    tailored: dict[str, Any],
    jd_text: str,
    model: str = DEFAULT_MODEL,
    output_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Finalize a Claude-authored tailored_cv into a full pack.

    Fabrication-checks against the USER's workspace master (fails loudly if it
    does not pass), validates the schema, writes tailored_cv.json, renders
    cv.html/cv.pdf, renders the cover letter if cover_letter.md is present,
    computes the ATS report, scans humaniser flags, and writes change_log.md.
    Returns a summary dict; ``ok`` is False (caller should exit non-zero) when
    the schema is invalid or the fabrication check fails.
    """
    master = load_master_cv()  # workspace master
    pack_dir = pack_dir_for(company, role, root=output_root)
    pack_dir.mkdir(parents=True, exist_ok=True)

    # Engine authors meta + fabrication_check regardless of what the model said.
    _stamp_meta(tailored, company, role, model)
    tailored["fabrication_check"] = fabrication_check(tailored, master)

    # Always persist the tailored JSON so a failed run is still inspectable.
    (pack_dir / "tailored_cv.json").write_text(
        json.dumps(tailored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    issues = validate_tailored_cv(tailored)
    if issues:
        return {"ok": False, "stage": "schema", "issues": issues,
                "pack_dir": str(pack_dir)}

    render_result = render_cv(tailored, pack_dir)
    pdf_backend = str(render_result["pdf_backend"])

    letter_pdf = None
    if (pack_dir / "cover_letter.md").exists():
        letter = render_letter(pack_dir)
        letter_pdf = str(letter["pdf"]) if letter.get("backend") == "weasyprint" else None

    cv_text = ats_mod.cv_text_from_tailored(tailored)
    report = ats_mod.build_ats_report(jd_text, cv_text, company, role)
    ats_mod.write_ats_report(report, pack_dir)

    flags = scan_humanizer_flags(tailored)
    write_change_log(tailored, pack_dir, pdf_backend=pdf_backend,
                     humanizer_flags=flags, ats_report=report)

    fab_passed = bool(tailored["fabrication_check"]["passed"])
    return {
        "ok": fab_passed,  # fail loudly on fabrication (decision #3)
        "stage": "complete",
        "pack_dir": str(pack_dir),
        "pdf_backend": pdf_backend,
        "cover_letter_pdf": letter_pdf,
        "fabrication_passed": fab_passed,
        "fabrication_issues": tailored["fabrication_check"]["issues"],
        "ats_score": report["match_score"],
        "matched_keywords": report["matched_keywords"],
        "missing_keywords": report["missing_keywords"],
        "humanizer_flags": flags,
    }


def run_mock_pack(
    *,
    company: str,
    role: str,
    jd_text: str,
    output_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Deterministic offline pack via the engine's --mock path (no API, no
    Claude). Renders, scores ATS, and writes the change log. Used by tests and
    the `mock-pack` CLI smoke path."""
    pack_dir = pack_dir_for(company, role, root=output_root)
    pack_dir.mkdir(parents=True, exist_ok=True)

    tailored = tailor_cv(jd_text=jd_text, company=company, role=role, mock=True,
                         out_path=pack_dir / "tailored_cv.json")
    render_result = render_cv(tailored, pack_dir)
    pdf_backend = str(render_result["pdf_backend"])

    cv_text = ats_mod.cv_text_from_tailored(tailored)
    report = ats_mod.build_ats_report(jd_text, cv_text, company, role)
    ats_mod.write_ats_report(report, pack_dir)

    flags = scan_humanizer_flags(tailored)
    write_change_log(tailored, pack_dir, pdf_backend=pdf_backend,
                     humanizer_flags=flags, ats_report=report)

    return {
        "ok": True,
        "pack_dir": str(pack_dir),
        "pdf_backend": pdf_backend,
        "fabrication_passed": bool(tailored["fabrication_check"]["passed"]),
        "ats_score": report["match_score"],
        "matched_keywords": report["matched_keywords"],
        "missing_keywords": report["missing_keywords"],
        "humanizer_flags": flags,
    }
