"""CV import helpers: extract raw text from PDFs, and validate a structured
cv_master.json. The semantic step (raw text -> structured facts) is performed by
Claude in the /job-setup skill; this module is the deterministic, testable half.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from engine import workspace

SCHEMA_VERSION = "1.0"


def extract_pdf_text(paths: list[Path]) -> str:
    """Return concatenated visible text of the given PDF files."""
    from pypdf import PdfReader

    chunks: list[str] = []
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            raise FileNotFoundError(f"CV PDF not found: {p}")
        reader = PdfReader(str(p))
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
    return "\n".join(chunks).strip()


def _is_list_of_str(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def validate_master_cv(d: dict[str, Any]) -> list[str]:
    """Validate cv_master.json against the authoritative schema ([] == valid)."""
    issues: list[str] = []
    if not isinstance(d, dict):
        return ["root: expected a JSON object"]

    if d.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            f"schema_version: expected {SCHEMA_VERSION!r}, got {d.get('schema_version')!r}"
        )

    contact = d.get("contact")
    if not isinstance(contact, dict):
        issues.append("contact: missing or not an object")
    else:
        for key in ("name", "title", "email"):
            if not (isinstance(contact.get(key), str) and contact[key].strip()):
                issues.append(f"contact.{key}: required non-empty string")

    if not isinstance(d.get("summary"), str):
        issues.append("summary: missing or not a string")

    skills = d.get("skills")
    if not isinstance(skills, list):
        issues.append("skills: missing or not a list")
    else:
        for idx, s in enumerate(skills):
            if not isinstance(s, dict) or not isinstance(s.get("name"), str):
                issues.append(f"skills[{idx}].name: required string")

    experience = d.get("experience")
    if not isinstance(experience, list):
        issues.append("experience: missing or not a list")
    else:
        for idx, e in enumerate(experience):
            if not isinstance(e, dict):
                issues.append(f"experience[{idx}]: not an object")
                continue
            for key in ("company", "title", "dates"):
                if not isinstance(e.get(key), str):
                    issues.append(f"experience[{idx}].{key}: required string")
            if not _is_list_of_str(e.get("bullets")):
                issues.append(f"experience[{idx}].bullets: must be a list of strings")

    for key in ("education", "projects", "certifications", "languages"):
        if key in d and not isinstance(d[key], list):
            issues.append(f"{key}: must be a list")

    return issues


def save_master_cv(d: dict[str, Any], path: Optional[Path] = None) -> Path:
    path = Path(path) if path is not None else workspace.master_cv_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
